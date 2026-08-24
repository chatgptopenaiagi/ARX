"""Validate an ARX public security or provenance record without exposing private data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import jsonschema

PLACEHOLDER = re.compile(r"(?:\$\{[^}]+\}|\bTBD\b)")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
PACKAGE_VERSION = re.compile(r"\d+\.\d+\.\d+(?:a|b|rc)\d+\Z")
ARTIFACT_VERSION = re.compile(r"\d+\.\d+\.\d+-(?:a|b|rc)\d+\Z")
LOCAL_PATH = re.compile(r"(?i)(?:\b[A-Z]:[\\/]|/(?:home|Users)/[^/\s]+/)")
SECRET_SHAPE = re.compile(
    r"(?i)(?:sk-[A-Za-z0-9_.-]{16,}|-----BEGIN [^-]*PRIVATE KEY-----|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|pypi-[A-Za-z0-9_-]{20,})"
)
FORBIDDEN_FIELDS = {
    "api_key",
    "credential",
    "dpapi_blob",
    "password",
    "pfx",
    "pin",
    "private_key",
    "signing_secret",
    "token",
}
REQUIRED_GATES = {
    "dependency/CVE",
    "SBOM",
    "malware",
    "SAST",
    "CodeQL",
    "fuzz",
    "privilege",
    "tamper",
    "Authenticode",
    "reproducibility",
    "provenance",
    "regression",
    "secrets",
    "installer lifecycle",
}


def _walk(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            yield "key", str(key)
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, str):
        yield "value", value


def _require_unique(items: list[dict], field: str, label: str) -> None:
    values = [item[field] for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicate {field} values.")


def _validate_privacy(record: object, *, allow_template: bool) -> None:
    for kind, text in _walk(record):
        folded = text.casefold()
        if kind == "key" and folded in FORBIDDEN_FIELDS:
            raise ValueError("Record contains a forbidden secret-bearing field.")
        if kind == "value":
            if SECRET_SHAPE.search(text):
                raise ValueError("Record contains credential- or private-key-shaped material.")
            if LOCAL_PATH.search(text):
                raise ValueError("Record contains an absolute private local path.")
            if not allow_template and PLACEHOLDER.search(text):
                raise ValueError("A final record contains an unresolved placeholder.")


def _validate_final_identity(record: dict) -> None:
    release = record.get("release_identity", record.get("release"))
    if not isinstance(release, dict):
        raise TypeError("Final record has no release identity.")
    if not PACKAGE_VERSION.fullmatch(release["version"]):
        raise ValueError("Final package version is invalid.")
    if not ARTIFACT_VERSION.fullmatch(release["artifact_version"]):
        raise ValueError("Final artifact version is invalid.")
    if release["tag"] != f"v{release['artifact_version']}":
        raise ValueError("Final tag and artifact version disagree.")
    if not COMMIT_SHA.fullmatch(release["commit_sha"]):
        raise ValueError("Final release commit must be a lowercase 40-character SHA.")


def validate_record(record: object, schema: object, *, allow_template: bool) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(record, schema, format_checker=jsonschema.FormatChecker())
    if not isinstance(record, dict):
        raise TypeError("Record must be a JSON object.")
    if record["record_state"] == "TEMPLATE" and not allow_template:
        raise ValueError("Template records require explicit --allow-template validation.")
    _validate_privacy(record, allow_template=allow_template)

    if record["record_type"] == "arx_release_security_record":
        _require_unique(record["gates"], "name", "Security gate table")
        actual_gates = {gate["name"] for gate in record["gates"]}
        if actual_gates != REQUIRED_GATES:
            raise ValueError("Security record does not contain exactly the required gates.")
    elif record["record_type"] == "arx_release_provenance_bundle":
        for collection in ("artifacts", "sboms", "evidence"):
            _require_unique(record[collection], "name", collection)

    if record["record_state"] == "FINAL":
        _validate_final_identity(record)
        if record["record_type"] == "arx_release_security_record":
            audit_commit = record["release_identity"]["audit_commit"]
            if not COMMIT_SHA.fullmatch(audit_commit):
                raise ValueError("Final audit commit must be a lowercase 40-character SHA.")
        else:
            for collection in ("artifacts", "sboms", "evidence"):
                for subject in record[collection]:
                    if not HEX_SHA256.fullmatch(subject["sha256"]):
                        raise ValueError(f"Final {collection} subject has an invalid SHA-256.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--allow-template", action="store_true")
    arguments = parser.parse_args()
    record = json.loads(arguments.record.read_text(encoding="utf-8"))
    schema = json.loads(arguments.schema.read_text(encoding="utf-8"))
    validate_record(record, schema, allow_template=arguments.allow_template)
    print(f"Security record: VALID ({record['record_type']}; {record['record_state']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
