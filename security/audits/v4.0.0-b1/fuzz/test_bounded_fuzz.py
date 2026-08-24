"""Bounded, local-only property tests for ARX 4.0.0 Beta 1 input boundaries."""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from arx.advisory.context import MAX_FIELD_CHARS, redact_external
from arx.advisory.providers import OpenAIProvider, ProviderError, parse_openai_response
from arx.core.models import Evidence, EvidenceKind, serialize
from arx.project.scanner import _parse_setup_cfg, _parse_setup_py, _toml
from arx.project.versions import (
    parse_python_version,
    python_constraints_overlap,
    python_version_satisfies,
)
from arx.software.scanner import scan_software


FUZZ_SETTINGS = settings(
    max_examples=200,
    deadline=250,
    derandomize=True,
    database=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
TEXT = st.text(max_size=2_048)
SHORT_TEXT = st.text(max_size=256)
JSON_SCALAR = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | SHORT_TEXT
JSON_VALUE = st.recursive(
    JSON_SCALAR,
    lambda children: st.lists(children, max_size=8)
    | st.dictionaries(st.text(max_size=32), children, max_size=8),
    max_leaves=24,
)


@FUZZ_SETTINGS
@given(JSON_VALUE)
def test_openai_response_parser_has_only_documented_outcomes(payload: object) -> None:
    try:
        text = parse_openai_response(payload)
    except ProviderError as exc:
        assert exc.status.value in {"parse_failure", "server_failure"}
    else:
        assert isinstance(text, str)
        assert text.strip()


@FUZZ_SETTINGS
@given(SHORT_TEXT)
def test_openai_endpoint_acceptance_implies_exact_https_origin(url: str) -> None:
    try:
        OpenAIProvider._validate_endpoint(url)
    except ProviderError:
        return
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.hostname == "api.openai.com"
    assert parsed.port in (None, 443)
    assert parsed.username is None
    assert parsed.password is None


@st.composite
def secret_assignment(draw: st.DrawFn) -> tuple[str, str]:
    token = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=16, max_size=48))
    wrapper = draw(st.sampled_from((
        lambda value: f"api_key={value}",
        lambda value: f"TOKEN: {value}",
        lambda value: f"Bearer {value}",
        lambda value: f"sk-proj-{value}",
        lambda value: f"ghp_{value}",
    )))
    return token, wrapper(token)


@FUZZ_SETTINGS
@given(secret_assignment(), JSON_VALUE)
def test_external_redaction_removes_secret_value_and_stays_json_serializable(
    secret: tuple[str, str], background: object
) -> None:
    token, rendered = secret
    value = {"note": rendered, "background": background, "credential": rendered}
    redacted = redact_external(value)
    encoded = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
    assert token not in encoded
    assert rendered not in encoded
    assert "\x00" not in encoded


@FUZZ_SETTINGS
@given(TEXT)
def test_project_text_parsers_return_without_unhandled_exceptions(text: str) -> None:
    evidence: list[Evidence] = []
    unknowns: list[str] = []
    parsed_toml = _toml(text, "fuzz.toml", evidence, unknowns)
    assert parsed_toml is None or isinstance(parsed_toml, dict)
    setup_cfg = _parse_setup_cfg(text, evidence, unknowns)
    setup_py = _parse_setup_py(text, evidence, unknowns)
    assert len(setup_cfg) == 2
    assert len(setup_py) == 2


@FUZZ_SETTINGS
@given(SHORT_TEXT, SHORT_TEXT)
def test_python_version_parsers_are_total_for_bounded_text(version: str, constraint: str) -> None:
    parsed = parse_python_version(version)
    assert parsed is None or len(parsed) == 5
    assert python_version_satisfies(version, constraint) in (True, False, None)
    assert python_constraints_overlap(version, constraint) in (True, False, None)


@FUZZ_SETTINGS
@given(JSON_VALUE)
def test_evidence_serialization_is_json_serializable(value: object) -> None:
    evidence = Evidence(
        kind=EvidenceKind.STRUCTURAL,
        source="bounded-fuzz",
        value=value,
        method="Hypothesis-generated JSON-compatible value",
        confidence=0.5,
    )
    encoded = json.dumps(serialize({"evidence": evidence, "path": Path("relative/path")}))
    assert "structural" in encoded
    assert "bounded-fuzz" in encoded


ENTRY_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-", min_size=1, max_size=40).filter(
    lambda value: value != "package.json"
)


@FUZZ_SETTINGS
@given(
    package_data=JSON_VALUE,
    other_entries=st.dictionaries(ENTRY_NAME, st.binary(max_size=2_048), max_size=8),
)
def test_archive_inspection_is_bounded_and_never_extracts(
    tmp_path: Path, package_data: object, other_entries: dict[str, bytes]
) -> None:
    archive_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("package.json", json.dumps(package_data, ensure_ascii=False))
        for name, payload in other_entries.items():
            archive.writestr(name, payload)
    before = {item.name for item in tmp_path.iterdir()}
    result = scan_software(archive_path)
    after = {item.name for item in tmp_path.iterdir()}
    assert before == after == {"sample.zip"}
    assert result["detected_file_type"] == "zip_archive"
    assert result["archive"]["entries"] == len(other_entries) + 1
    assert len(result["archive"]["sample_entries"]) <= 100


@FUZZ_SETTINGS
@given(package_data=JSON_VALUE)
def test_directory_package_metadata_is_handled_without_execution(tmp_path: Path, package_data: object) -> None:
    package = tmp_path / "package.json"
    package.write_text(json.dumps(package_data, ensure_ascii=False), encoding="utf-8")
    result = scan_software(tmp_path)
    assert result["detected_file_type"] == "directory"
    assert package.exists()


@FUZZ_SETTINGS
@given(optional_size=st.integers(min_value=2, max_value=69), tail=st.binary(max_size=256))
def test_truncated_pe_optional_header_is_reported_not_raised(
    tmp_path: Path, optional_size: int, tail: bytes
) -> None:
    pe_offset = 64
    optional_offset = pe_offset + 24
    payload = bytearray(max(optional_offset + optional_size, 90))
    payload[:2] = b"MZ"
    struct.pack_into("<I", payload, 60, pe_offset)
    payload[pe_offset : pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", payload, pe_offset + 4, 0x8664, 1, 0, 0, 0, optional_size, 0x22)
    struct.pack_into("<H", payload, optional_offset, 0x20B)
    payload.extend(tail)
    executable = tmp_path / "sample.exe"
    executable.write_bytes(payload)
    result = scan_software(executable)
    assert result["detected_file_type"] == "windows_pe"
    assert "inspection_error" in result
    assert executable.exists()


def test_fuzz_campaign_bounds_are_explicit() -> None:
    assert MAX_FIELD_CHARS == 2_000
    assert FUZZ_SETTINGS.max_examples == 200
    assert FUZZ_SETTINGS.deadline.total_seconds() == pytest.approx(0.25)
