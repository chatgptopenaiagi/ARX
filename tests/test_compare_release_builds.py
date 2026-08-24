import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare-release-builds.py"
VERSION = "4.0.0b2"
ARTIFACT_VERSION = "4.0.0-b2"
COMMIT = "a" * 40


def _load_module():
    spec = importlib.util.spec_from_file_location("compare_release_builds", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip(path: Path, timestamp: tuple[int, int, int, int, int, int], entries: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name, date_time=timestamp)
            archive.writestr(info, payload)


def _sdist(path: Path, mtime: int):
    payload = b"ARX\n"
    tar_payload = io.BytesIO()
    with tarfile.open(fileobj=tar_payload, mode="w") as archive:
        info = tarfile.TarInfo(f"arx_prescanner-{VERSION}/README.md")
        info.mode = 0o644
        info.mtime = mtime
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with path.open("wb") as stream, gzip.GzipFile(
        fileobj=stream, mode="wb", mtime=mtime
    ) as compressed:
        compressed.write(tar_payload.getvalue())


def _environment(path: Path, label: str, *, tool_version="1"):
    record = {
        "schema_version": 1,
        "record_type": "arx_release_build_environment",
        "builder_label": label,
        "source_commit": COMMIT,
        "source_date_epoch": 1700000000,
        "platform": {"system": "Windows", "release": "fixture", "machine": "AMD64"},
        "python": {"implementation": "CPython", "version": "3.12.0", "architecture_bits": 64},
        "tools": {"build": tool_version, "inno_setup": "7.1.0"},
        "controls": {
            "python_hash_seed": "0",
            "timezone": "UTC",
            "source_date_epoch_origin": "source commit timestamp",
        },
    }
    path.write_text(json.dumps(record), encoding="utf-8")


def _write_tree(root: Path, timestamp, mtime, exe, installer):
    root.mkdir()
    wheel = root / f"arx_prescanner-{VERSION}-py3-none-any.whl"
    sdist = root / f"arx_prescanner-{VERSION}.tar.gz"
    portable = root / f"ARX-Desktop-win-x64-v{ARTIFACT_VERSION}.zip"
    setup = root / f"ARX-Desktop-Setup-win-x64-v{ARTIFACT_VERSION}.exe"
    _zip(wheel, timestamp, {"arx/__init__.py": b"version"})
    _sdist(sdist, mtime)
    _zip(portable, timestamp, {"ARX-Desktop-win-x64/ARX.exe": exe})
    setup.write_bytes(installer)
    desktop = root / "ARX-Desktop-win-x64"
    desktop.mkdir()
    (desktop / "ARX.exe").write_bytes(exe)
    artifacts = (wheel, sdist, portable, setup)
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )


def _arguments(tmp_path, first, second, environment_a, environment_b):
    return argparse.Namespace(
        build_a=first,
        build_b=second,
        environment_a=environment_a,
        environment_b=environment_b,
        version=VERSION,
        artifact_version=ARTIFACT_VERSION,
        source_commit=COMMIT,
        output=tmp_path / "comparison.json",
    )


def test_comparator_distinguishes_byte_structure_and_binary_difference(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_tree(first, (2024, 1, 1, 0, 0, 0), 100, b"MZ-first", b"same-installer")
    _write_tree(second, (2025, 1, 1, 0, 0, 0), 200, b"MZ-second", b"same-installer")
    environment_a = tmp_path / "environment-a.json"
    environment_b = tmp_path / "environment-b.json"
    _environment(environment_a, "build-a")
    _environment(environment_b, "build-b")

    record = _load_module().compare(_arguments(tmp_path, first, second, environment_a, environment_b))

    assert record["equal_toolchain"] is True
    assert record["artifacts"]["wheel"]["classification"] == "STRUCTURALLY_EQUIVALENT"
    assert record["artifacts"]["sdist"]["classification"] == "STRUCTURALLY_EQUIVALENT"
    assert record["artifacts"]["portable_zip"]["classification"] == "NOT_REPRODUCIBLE"
    assert record["artifacts"]["arx_exe"]["classification"] == "NOT_REPRODUCIBLE"
    assert record["artifacts"]["installer"]["classification"] == "BIT_FOR_BIT_REPRODUCIBLE"
    assert record["artifacts"]["sha256sums"]["classification"] == "STRUCTURALLY_EQUIVALENT"


def test_comparator_rejects_unequal_toolchains(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_tree(first, (2024, 1, 1, 0, 0, 0), 100, b"MZ", b"installer")
    _write_tree(second, (2024, 1, 1, 0, 0, 0), 100, b"MZ", b"installer")
    environment_a = tmp_path / "environment-a.json"
    environment_b = tmp_path / "environment-b.json"
    _environment(environment_a, "build-a")
    _environment(environment_b, "build-b", tool_version="2")

    with pytest.raises(ValueError, match="Build environments differ in: tools"):
        _load_module().compare(_arguments(tmp_path, first, second, environment_a, environment_b))


def test_comparator_rejects_absolute_path_in_environment_record(tmp_path):
    environment = tmp_path / "environment.json"
    _environment(environment, "C:\\private\\builder")

    with pytest.raises(ValueError, match="absolute local path"):
        _load_module()._safe_environment(environment)
