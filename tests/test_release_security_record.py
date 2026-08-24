import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-security-record.py"
SECURITY_SCHEMA = ROOT / "security" / "release-record" / "release-security-record.schema.json"
SECURITY_TEMPLATE = ROOT / "security" / "release-record" / "release-security-record.template.json"
PROVENANCE_SCHEMA = ROOT / "security" / "provenance" / "provenance-bundle.schema.json"
PROVENANCE_TEMPLATE = ROOT / "security" / "provenance" / "provenance-bundle.template.json"


def _load_validator():
    spec = importlib.util.spec_from_file_location("security_record_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("record", "schema"),
    [(SECURITY_TEMPLATE, SECURITY_SCHEMA), (PROVENANCE_TEMPLATE, PROVENANCE_SCHEMA)],
)
def test_templates_validate_only_with_explicit_template_mode(record, schema):
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(record), "--schema", str(schema), "--allow-template"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "VALID" in result.stdout

    rejected = subprocess.run(
        [sys.executable, str(VALIDATOR), str(record), "--schema", str(schema)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0


def test_security_template_has_exact_gate_vocabulary_and_required_categories():
    record = json.loads(SECURITY_TEMPLATE.read_text(encoding="utf-8"))
    schema = json.loads(SECURITY_SCHEMA.read_text(encoding="utf-8"))
    _load_validator().validate_record(record, schema, allow_template=True)
    allowed = schema["$defs"]["gate"]["properties"]["result"]["enum"]
    assert allowed == [
        "PASS",
        "PASS WITH LIMITATION",
        "REVIEWED",
        "NOT APPLICABLE",
        "BLOCKED",
        "FAIL",
    ]
    assert record["claim"] == "ARX passed the following defined security gates."
    assert len(record["gates"]) == 14


def test_final_record_rejects_private_path_and_secret_shaped_value():
    module = _load_validator()
    schema = json.loads(PROVENANCE_SCHEMA.read_text(encoding="utf-8"))
    record = json.loads(PROVENANCE_TEMPLATE.read_text(encoding="utf-8"))
    record["record_state"] = "FINAL"
    record["release"].update(
        version="4.0.0b2",
        artifact_version="4.0.0-b2",
        tag="v4.0.0-b2",
        commit_sha="a" * 40,
    )
    for collection in ("artifacts", "sboms", "evidence"):
        record[collection][0].update(name=f"{collection}.json", sha256="b" * 64, provenance="build")
    record["build"].update(workflow="release-assets.yml", run_id="1", builder="windows-latest", python_version="3.12")

    record["evidence"][0]["provenance"] = "C:\\Users\\private\\report.json"
    with pytest.raises(ValueError, match="private local path"):
        module.validate_record(record, schema, allow_template=False)

    record["evidence"][0]["provenance"] = "sk-" + "x" * 20
    with pytest.raises(ValueError, match="credential"):
        module.validate_record(record, schema, allow_template=False)


def test_reproducibility_vocabulary_does_not_conflate_structural_and_exact():
    schema = json.loads(SECURITY_SCHEMA.read_text(encoding="utf-8"))
    values = schema["$defs"]["reproducibilityResult"]["properties"]["classification"]["enum"]
    assert values == [
        "BIT_FOR_BIT_REPRODUCIBLE",
        "STRUCTURALLY_EQUIVALENT",
        "NOT_REPRODUCIBLE",
        "UNRESOLVED",
    ]
