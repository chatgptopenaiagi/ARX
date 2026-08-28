from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arx.agent.challenges import (
    CATALOG,
    MAX_SUMMARY_CHARS,
    catalog_summary,
    load_challenge,
    load_receipt,
    prepare_challenge,
    validate_challenge_receipt,
)
from arx.agent.models import AgentOperationalState
from arx.agent.protocol import (
    CHALLENGE_PROTOCOL_VERSION,
    AgentCapabilityReceipt,
    ExecutionProvenanceState,
    ReceiptArtifact,
    TrustedExecutionObservation,
)
from arx.core.models import EvidenceKind, serialize
from arx.cli import main


def _receipt(challenge, *, state=AgentOperationalState.PASS, artifacts=(), **overrides):
    values = dict(
        protocol_version=CHALLENGE_PROTOCOL_VERSION,
        challenge_id=challenge.challenge_id,
        agent_reference="agent:fixture",
        execution_context_reference="context:fixture",
        execution_context={"working_directory_class": "disposable-workspace", "executor": "fixture-agent"},
        claimed_state=state,
        started_at="2026-08-28T00:00:00Z",
        finished_at="2026-08-28T00:00:00Z",
        duration_ms=10,
        exit_code=0,
        stdout_summary="bounded",
        stderr_summary="",
        evidence_refs=["receipt-evidence:fixture"],
        artifacts=list(artifacts),
        performed_operations=list(challenge.allowed_operations),
        tool_observations=[],
        limitations=[],
        reason=None,
    )
    values.update(overrides)
    return AgentCapabilityReceipt(**values)


def _write_expected(challenge, workspace: Path, *, content: str | None = None):
    expected = challenge.artifact_expectations[0]
    path = workspace / expected.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (content if content is not None else expected.expected_text or "BINARY").encode()
    path.write_bytes(data)
    return ReceiptArtifact(expected.relative_path, len(data), hashlib.sha256(data).hexdigest())


def _trusted_observation(challenge, receipt, artifacts):
    hashes = {item.relative_path: item.sha256 for item in artifacts}
    return TrustedExecutionObservation(
        observation_id="agent-execution-observation:fixture",
        challenge_id=challenge.challenge_id,
        provider_id=f"provider:{challenge.family}:fixture",
        resolved_executable_class=f"trusted-{challenge.family}-provider",
        command_fingerprint="1" * 64,
        working_directory_fingerprint="2" * 64,
        started_at=receipt.started_at,
        finished_at=receipt.finished_at,
        exit_code=0,
        stdout_sha256="3" * 64,
        stderr_sha256="4" * 64,
        artifact_hashes=hashes,
        execution_context_reference=receipt.execution_context_reference,
        evidence_kind=EvidenceKind.OBSERVED,
        observer={"name": "ARX trusted execution observer", "version": "fixture"},
    )


def test_catalog_is_small_safe_and_dependency_aware():
    assert set(CATALOG) == {
        "artifact.create", "filesystem.workspace.write", "powershell.execute", "python.execute",
        "git.local.repository", "cpp.compile", "cpp.execute", "cuda.compile", "cuda.runtime_initialize",
    }
    summary = catalog_summary()
    assert summary["protocol_version"] == "agent-challenge/0.1"
    assert CATALOG["cpp.execute"]["dependencies"] == ["cpp.compile", "cpp.binary.created"]
    assert CATALOG["cuda.runtime_initialize"]["dependencies"] == ["cuda.runtime.fixture.available"]


def test_challenge_serialization_and_stable_identity(tmp_path):
    first, first_workspace = prepare_challenge("python.execute", workspace_root=tmp_path)
    second, _ = prepare_challenge("python.execute", workspace_root=tmp_path)
    assert first.challenge_id == second.challenge_id
    assert first.workspace_id != second.workspace_id
    assert serialize(first)["protocol_version"] == CHALLENGE_PROTOCOL_VERSION
    loaded = load_challenge(first_workspace / "challenge.json")
    assert loaded.challenge_id == first.challenge_id
    assert loaded.fixtures[0].sha256 == hashlib.sha256((first_workspace / loaded.fixtures[0].relative_path).read_bytes()).hexdigest()
    assert loaded.scope.kind == "workspace"
    assert loaded.scope.target == "ARX-owned disposable challenge workspace"


def test_arx_validates_exact_artifact_instead_of_trusting_pass(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    receipt = _receipt(challenge)
    missing = validate_challenge_receipt(challenge, receipt)
    assert receipt.claimed_state is AgentOperationalState.PASS
    assert missing.validated_state is AgentOperationalState.FAIL
    assert "EXPECTED_ARTIFACT_MISSING" in missing.reason_codes
    artifact = _write_expected(challenge, workspace)
    valid = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[artifact]))
    assert valid.validated_state is AgentOperationalState.PASS
    assert valid.outcome_validated is True
    assert valid.execution_provenance is ExecutionProvenanceState.NOT_APPLICABLE
    assert valid.artifact_hashes_valid and valid.expected_output_valid
    assert valid.evidence[0]["kind"] == "observed"
    assert valid.scope.kind == "workspace"
    assert valid.execution_context_reference == "context:fixture"


@pytest.mark.parametrize(
    "capability,content,tool_observations",
    [
        ("powershell.execute", None, []),
        ("python.execute", None, [{"provider_id": "python:fixture", "resolution": "RESOLVED"}]),
        ("git.local.repository", "fixture-commit-id\n", []),
        ("cpp.compile", None, []),
        ("cpp.execute", None, []),
        ("cuda.compile", None, []),
        ("cuda.runtime_initialize", "ARX_AGENT_CHALLENGE_CUDA_STATUS=0 DEVICE_COUNT=1\n", []),
    ],
)
def test_execution_outcome_does_not_prove_provider_attribution(tmp_path, capability, content, tool_observations):
    challenge, workspace = prepare_challenge(capability, workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace, content=content)
    receipt = _receipt(challenge, artifacts=[artifact], tool_observations=tool_observations)
    result = validate_challenge_receipt(challenge, receipt)
    assert result.outcome_validated is True
    assert result.execution_provenance is ExecutionProvenanceState.RECEIPT_REPORTED
    assert result.validated_state is AgentOperationalState.UNKNOWN
    assert "PROVIDER_EXECUTION_NOT_INDEPENDENTLY_OBSERVED" in result.reason_codes


@pytest.mark.parametrize(
    "overrides",
    [
        {"tool_observations": [{"provider_id": "python:fixture", "resolution": "RESOLVED"}]},
        {"exit_code": 0},
        {"stdout_summary": "ARX_AGENT_CHALLENGE_PYTHON_OK"},
        {"execution_context": {"executor": "python.exe", "working_directory_class": "disposable-workspace"}},
    ],
)
def test_receipt_authored_process_fields_cannot_upgrade_provenance(tmp_path, overrides):
    challenge, workspace = prepare_challenge("python.execute", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    defaults = {"tool_observations": [], "exit_code": None, "stdout_summary": "", "execution_context": {}}
    defaults.update(overrides)
    receipt = _receipt(challenge, artifacts=[artifact], **defaults)
    result = validate_challenge_receipt(challenge, receipt)
    assert result.execution_provenance is ExecutionProvenanceState.RECEIPT_REPORTED


def test_absent_execution_provenance_remains_unknown(tmp_path):
    challenge, workspace = prepare_challenge("powershell.execute", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    receipt = _receipt(
        challenge,
        artifacts=[artifact],
        execution_context={},
        tool_observations=[],
        exit_code=None,
        stdout_summary="",
    )
    result = validate_challenge_receipt(challenge, receipt)
    assert result.execution_provenance is ExecutionProvenanceState.UNKNOWN
    assert "not independently observed or established" in result.remaining_uncertainty[0]


def test_arx_owned_execution_observation_can_establish_scoped_pass(tmp_path):
    challenge, workspace = prepare_challenge("python.execute", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    receipt = _receipt(
        challenge,
        artifacts=[artifact],
        tool_observations=[{"provider_id": "python:fixture", "resolution": "RESOLVED"}],
    )
    observation = _trusted_observation(challenge, receipt, [artifact])
    result = validate_challenge_receipt(
        challenge,
        receipt,
        trusted_execution_observation=observation,
    )
    assert result.outcome_validated is True
    assert result.execution_provenance is ExecutionProvenanceState.OBSERVED
    assert result.validated_state is AgentOperationalState.PASS
    assert "PROVIDER_EXECUTION_NOT_INDEPENDENTLY_OBSERVED" not in result.reason_codes
    assert any(
        item.get("observation_ref") == observation.observation_id
        and item["method"] == "arx-trusted-execution-observation"
        for item in result.evidence
    )


@pytest.mark.parametrize("change,reason", [
    (lambda receipt: setattr(receipt, "challenge_id", "agent-challenge:" + "0" * 24), "CHALLENGE_ID_MISMATCH"),
    (lambda receipt: setattr(receipt, "protocol_version", "agent-challenge/9.9"), "PROTOCOL_VERSION_MISMATCH"),
    (lambda receipt: setattr(receipt, "duration_ms", 31_000), "TIMEOUT_EXCEEDED"),
    (lambda receipt: setattr(receipt, "performed_operations", ["install-packages"]), "UNAUTHORIZED_OR_FORBIDDEN_OPERATION_REPORTED"),
])
def test_identity_policy_and_timeout_fail_closed(tmp_path, change, reason):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    receipt = _receipt(challenge, artifacts=[artifact])
    change(receipt)
    result = validate_challenge_receipt(challenge, receipt)
    assert result.validated_state is AgentOperationalState.FAIL
    assert reason in result.reason_codes


def test_hash_and_content_mismatch_are_independent_failures(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace, content="WRONG\n")
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[artifact]))
    assert "EXPECTED_ARTIFACT_HASH_MISMATCH" in result.reason_codes
    assert "EXPECTED_OUTPUT_MISMATCH" in result.reason_codes
    forged = ReceiptArtifact(artifact.relative_path, artifact.size, "0" * 64)
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[forged]))
    assert "ARTIFACT_RECEIPT_MISMATCH" in result.reason_codes


@pytest.mark.parametrize("relative", ["../outside.txt", "C:/outside.txt", "C:outside.txt", "/outside.txt"])
def test_artifact_escape_is_rejected(tmp_path, relative):
    challenge, _ = prepare_challenge("artifact.create", workspace_root=tmp_path)
    artifact = ReceiptArtifact(relative, 0, hashlib.sha256(b"").hexdigest())
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[artifact]))
    assert result.workspace_boundary_valid is False
    assert "ARTIFACT_PATH_ESCAPE" in result.reason_codes


def test_duplicate_artifact_identity_rejected(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[artifact, artifact]))
    assert result.artifacts_valid is False
    assert "DUPLICATE_ARTIFACT_RECORD" in result.reason_codes


def test_fixture_tampering_is_independently_detected(tmp_path):
    challenge, workspace = prepare_challenge("python.execute", workspace_root=tmp_path)
    (workspace / challenge.fixtures[0].relative_path).write_text("tampered", encoding="utf-8")
    artifact = _write_expected(challenge, workspace)
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[artifact]))
    assert result.fixture_integrity_valid is False
    assert "CHALLENGE_FIXTURE_INTEGRITY_FAILURE" in result.reason_codes


def test_receipt_bounds_and_missing_evidence(tmp_path):
    challenge, _ = prepare_challenge("artifact.create", workspace_root=tmp_path)
    result = validate_challenge_receipt(challenge, _receipt(challenge, stdout_summary="x" * (MAX_SUMMARY_CHARS + 1), evidence_refs=[]))
    assert result.receipt_structurally_valid is False
    assert "RECEIPT_BOUNDS_EXCEEDED" in result.reason_codes
    assert "REQUIRED_EVIDENCE_MISSING" in result.reason_codes


def test_actual_oversized_artifact_is_not_read_for_hashing(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    path = workspace / "artifacts" / "hello.txt"
    path.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
    record = ReceiptArtifact("artifacts/hello.txt", path.stat().st_size, "0" * 64)
    result = validate_challenge_receipt(challenge, _receipt(challenge, artifacts=[record]))
    assert "ARTIFACT_SIZE_LIMIT_EXCEEDED" in result.reason_codes
    assert result.validated_state is AgentOperationalState.FAIL


def test_context_is_scoped_and_allowlisted(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    raw = serialize(_receipt(challenge, state=AgentOperationalState.NOT_TESTED, performed_operations=[]))
    raw["execution_context"] = {"developer_environment": "visual_studio_x64", "secret_environment_dump": "forbidden"}
    path = workspace / "receipt.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="allowlisted"):
        load_receipt(path)
    raw = serialize(_receipt(challenge, state=AgentOperationalState.NOT_TESTED, performed_operations=[]))
    raw["tool_observations"] = [{"authorization_token": "must-not-be-accepted"}]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="tool observations"):
        load_receipt(path)


def test_blocked_not_tested_unknown_and_not_applicable_remain_distinct(tmp_path):
    challenge, _ = prepare_challenge("cpp.execute", workspace_root=tmp_path)
    for state in (AgentOperationalState.BLOCKED, AgentOperationalState.NOT_TESTED, AgentOperationalState.UNKNOWN, AgentOperationalState.NOT_APPLICABLE):
        result = validate_challenge_receipt(challenge, _receipt(challenge, state=state, performed_operations=[]))
        assert result.validated_state is state
    assert CATALOG["cpp.execute"]["dependencies"] == ["cpp.compile", "cpp.binary.created"]


def test_receipt_cannot_redefine_policy_or_validator(tmp_path):
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    raw = serialize(_receipt(challenge, state=AgentOperationalState.NOT_TESTED, performed_operations=[]))
    raw["allowed_operations"] = ["install-packages"]
    path = workspace / "receipt.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="redefine policy"):
        load_receipt(path)
    challenge_raw = json.loads((workspace / "challenge.json").read_text())
    challenge_raw["allowed_operations"] = ["install-packages"]
    (workspace / "challenge.json").write_text(json.dumps(challenge_raw), encoding="utf-8")
    with pytest.raises(ValueError, match="ARX-owned catalog"):
        load_challenge(workspace / "challenge.json")


def test_receipt_document_size_is_bounded(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="1 MiB"):
        load_receipt(path)


def test_challenge_schemas_are_draft_202012_and_validate(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    root = Path(__file__).parents[1]
    challenge, workspace = prepare_challenge("artifact.create", workspace_root=tmp_path)
    artifact = _write_expected(challenge, workspace)
    receipt = _receipt(challenge, artifacts=[artifact])
    validation = validate_challenge_receipt(challenge, receipt)
    cases = [
        ("agent-capability-challenge.schema.json", serialize(challenge)),
        ("agent-capability-receipt.schema.json", serialize(receipt)),
        ("agent-capability-validation.schema.json", serialize(validation)),
    ]
    for name, value in cases:
        schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(value)


def test_cli_catalog_prepare_validate_and_summary(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("arx.agent.challenges.tempfile.tempdir", str(tmp_path))
    assert main(["agent", "challenge", "catalog"]) == 0
    assert "artifact.create" in capsys.readouterr().out
    assert main(["agent", "challenge", "prepare", "artifact.create"]) == 0
    prepared = json.loads(capsys.readouterr().out)
    challenge_path = Path(prepared["prepared"][0]["challenge"])
    challenge = load_challenge(challenge_path)
    artifact = _write_expected(challenge, challenge_path.parent)
    receipt_path = challenge_path.parent / "receipt.json"
    receipt_path.write_text(json.dumps(serialize(_receipt(challenge, artifacts=[artifact]))), encoding="utf-8")
    validation_path = tmp_path / "validation.json"
    assert main(["-o", str(validation_path), "agent", "challenge", "validate", str(challenge_path), str(receipt_path)]) == 0
    assert json.loads(validation_path.read_text())["validated_state"] == "PASS"
    capsys.readouterr()
    assert main(["agent", "challenge", "summarize", str(validation_path)]) == 0
    summary = capsys.readouterr().out
    assert "Outcome validation: PASS" in summary
    assert "Execution provenance: NOT_APPLICABLE" in summary
    assert "ARX capability state: PASS" in summary
