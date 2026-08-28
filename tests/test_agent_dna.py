from __future__ import annotations

import json
from pathlib import Path

import pytest

from arx.agent.assessment import calibration_outcome
from arx.agent.importer import (
    AgentDNAImportError,
    import_experimental_baseline,
    normalized_dict,
    validate_capability_graph,
    validate_capability_dimensions,
    validate_experimental_baseline,
)
from arx.agent.models import AgentOperationalState, CalibrationOutcome
from arx.cli import main


def record(identifier, state="PASS", **overrides):
    value = {
        "id": identifier,
        "name": identifier,
        "status": state,
        "scope": "experiment_workspace_only",
        "declared_state": "UNKNOWN",
        "availability": "AVAILABLE",
        "permission": "PERMITTED",
        "execution": "EXECUTED",
        "result": state,
        "reason_code": "FIXTURE",
        "evidence_kind": "OBSERVED",
        "evidence": [{"command": "bounded fixture", "exit_code": 0, "normalized_output": state}],
    }
    value.update(overrides)
    return value


@pytest.fixture
def baseline():
    return {
        "schema_version": "agent-dna-experiment/0.1",
        "experiment": {"generated_at": "2026-08-28T00:00:00Z", "safety_profile": "bounded-nondestructive"},
        "agent": {
            "identity": {"agent_name": "Generic CLI agent", "cli_name": "agent", "cli_version": "1"},
            "execution_context": {"working_directory": r"C:\Lab", "host_os": "Windows NT 10.0.29639"},
        },
        "self_declaration": {"predictions": {"cuda.runtime_initialize": "UNKNOWN"}},
        "capability_families": {
            "cpp": [
                record("cpp.compiler_resolution"),
                record("cpp.compile", "FAIL", result="iostream unresolved", reason_code="STANDARD_LIBRARY_UNRESOLVED"),
            ],
            "dotnet": [record("dotnet.cli"), record("dotnet.offline_build", "BLOCKED", reason_code="RESTORE_REQUIRED_NETWORK_NOT_AUTHORIZED")],
            "cuda": [
                record("cuda.driver_capability", result="driver API 13.4"),
                record("cuda.toolkit", result="toolkit 13.3"),
                record("cuda.nvcc_resolution"),
                record("cuda.compile", "FAIL", result="cl.exe unresolved"),
                record("cuda.runtime_initialize"),
            ],
            "github": [
                record("github.repository.write_permission", availability="OBSERVED_PERMISSION", execution="NOT_EXECUTED", reason_code="PERMISSION_METADATA_ONLY"),
                record("github.push", "NOT_TESTED", availability="OBSERVED_PERMISSION", permission="PROHIBITED_BY_EXPERIMENT", execution="NOT_EXECUTED"),
            ],
            "misc": [record("misc.unknown", "UNKNOWN")],
        },
        "contradictions": [{"id": "contradiction.cuda.compiler_visible_unusable", "summary": "visible but unusable", "evidence_refs": ["cuda.toolkit", "cuda.compile"], "reason": "host compiler unresolved"}],
        "operator_interventions": [{
            "id": "operator_intervention.provider_resolution", "timestamp": None, "reason": "PATH transition",
            "before_state": {"resolution": "FAIL"}, "action_performed_by_human": "refreshed environment",
            "after_state": {"resolution": "PASS"}, "effect_on_agent_capability": "provider now resolves", "scope": "current process",
        }],
    }


def test_import_normalizes_phase0_semantics(baseline):
    snapshot = import_experimental_baseline(baseline)
    by_id = {item.id: item for item in snapshot.capabilities}
    assert by_id["dotnet.offline_build"].state is AgentOperationalState.BLOCKED
    assert by_id["dotnet.offline_build"].state is not AgentOperationalState.FAIL
    assert by_id["github.push"].dimensions.authorization == "NOT_AUTHORIZED"
    assert by_id["github.push"].state is AgentOperationalState.NOT_TESTED
    assert by_id["cuda.runtime_initialize"].state is AgentOperationalState.PASS
    assert by_id["cuda.compile"].state is AgentOperationalState.FAIL
    assert by_id["cuda.toolkit"].result != by_id["cuda.driver_capability"].result
    assert snapshot.machine_reference.status == "UNRESOLVED"
    assert snapshot.execution_context.agent_reported_host == "Windows NT 10.0.29639"
    assert len(snapshot.interventions) == 1


def test_graph_preserves_failed_prerequisite_chain(baseline):
    snapshot = import_experimental_baseline(baseline)
    edges = {(edge.source_id, edge.target_id) for edge in snapshot.capability_graph.edges}
    assert ("cpp.compiler_resolution", "cpp.compile") in edges
    assert "cpp.standard_library.available" in snapshot.capability_graph.unresolved_dependency_ids
    assert "cuda.host_compiler.resolution" in snapshot.capability_graph.unresolved_dependency_ids
    assert ("cuda.runtime_initialize", "cuda.device_visible") not in edges


def test_unknown_prediction_resolved_by_pass():
    assert calibration_outcome("UNKNOWN", AgentOperationalState.PASS) is CalibrationOutcome.UNKNOWN_RESOLVED_AVAILABLE
    assert calibration_outcome("UNKNOWN", AgentOperationalState.BLOCKED) is CalibrationOutcome.UNKNOWN_RESOLVED_BLOCKED


def test_calibration_does_not_use_unrelated_family_pass(baseline):
    baseline["self_declaration"]["predictions"] = {"cuda.toolkit_compile": "UNKNOWN"}
    snapshot = import_experimental_baseline(baseline)
    assert snapshot.calibration.entries[0].observed_state is AgentOperationalState.FAIL
    assert snapshot.calibration.entries[0].outcome is CalibrationOutcome.UNKNOWN_RESOLVED_UNAVAILABLE


def test_permission_does_not_imply_authorization(baseline):
    snapshot = import_experimental_baseline(baseline)
    item = next(item for item in snapshot.capabilities if item.id == "cuda.toolkit")
    assert item.dimensions.permission == "PERMITTED"
    assert item.dimensions.authorization == "UNKNOWN"


def test_graph_cycle_rejected():
    from arx.agent.models import AgentCapabilityEdge
    with pytest.raises(AgentDNAImportError, match="cycle"):
        validate_capability_graph({"a", "b"}, [AgentCapabilityEdge("a", "b"), AgentCapabilityEdge("b", "a")])


def test_graph_dangling_edge_rejected():
    from arx.agent.models import AgentCapabilityEdge
    with pytest.raises(AgentDNAImportError, match="undeclared"):
        validate_capability_graph({"a"}, [AgentCapabilityEdge("missing", "a")])


def test_impossible_dimension_combinations_rejected(baseline):
    snapshot = import_experimental_baseline(baseline)
    item = next(item for item in snapshot.capabilities if item.id == "cuda.toolkit")
    item.dimensions.execution = "NOT_EXECUTED"
    with pytest.raises(AgentDNAImportError, match="cannot be unexecuted"):
        validate_capability_dimensions([item])
    item.state = AgentOperationalState.FAIL
    item.dimensions.attempt = "NOT_TESTED"
    with pytest.raises(AgentDNAImportError, match="must have been attempted"):
        validate_capability_dimensions([item])
    item.state = AgentOperationalState.NOT_TESTED
    item.dimensions.attempt = "ATTEMPTED"
    item.dimensions.execution = "EXECUTED"
    item.dimensions.authorization = "NOT_AUTHORIZED"
    with pytest.raises(AgentDNAImportError, match="unauthorized"):
        validate_capability_dimensions([item])


def test_contradiction_subject_and_evidence_domains_are_separate(baseline):
    snapshot = import_experimental_baseline(baseline)
    contradiction = snapshot.contradictions[0]
    assert contradiction.code == "CUDA_COMPILE_CHAIN_INCOMPLETE"
    assert contradiction.subject_capability_id is None
    assert contradiction.evidence_refs == ["cuda.toolkit", "cuda.compile"]
    assert contradiction.source_record["summary"] == "visible but unusable"


def test_pass_requires_scope(baseline):
    baseline["capability_families"]["cpp"][0]["scope"] = ""
    with pytest.raises(AgentDNAImportError, match="requires scope"):
        validate_experimental_baseline(baseline)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version="wrong"),
    lambda value: value["capability_families"].update(bad={}),
    lambda value: value["capability_families"]["cpp"][0].update(status="GREEN"),
])
def test_malformed_baseline_rejected(baseline, mutation):
    mutation(baseline)
    with pytest.raises(AgentDNAImportError):
        validate_experimental_baseline(baseline)


def test_evidence_provenance_and_stable_serialization(baseline):
    first = import_experimental_baseline(baseline)
    second = import_experimental_baseline(baseline)
    assert first.snapshot_id == second.snapshot_id
    assert first.capabilities[0].evidence[0].kind.value == "observed"
    assert normalized_dict(first) == normalized_dict(second)


def test_redaction(baseline, monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Person")
    baseline["agent"]["execution_context"]["working_directory"] = r"C:\Users\Person\Lab"
    output = json.dumps(normalized_dict(import_experimental_baseline(baseline)))
    assert "Person" not in output
    assert "%PROJECT_ROOT%" in output


def test_schema_validation(baseline):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((Path(__file__).parents[1] / "schemas" / "agent-dna.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(normalized_dict(import_experimental_baseline(baseline)))


def test_cli_validate_import_summary(tmp_path, baseline, capsys):
    source = tmp_path / "baseline.json"
    source.write_text(json.dumps(baseline), encoding="utf-8")
    assert main(["agent", "validate", str(source)]) == 0
    assert '"valid": true' in capsys.readouterr().out
    assert main(["agent", "summary", str(source)]) == 0
    assert "AGENT DNA" in capsys.readouterr().out
    target = tmp_path / "normalized.json"
    assert main(["-o", str(target), "agent", "import", str(source)]) == 0
    assert json.loads(target.read_text())["schema_version"] == "agent-dna/0.1"


def test_real_phase0_baseline_imports_when_available():
    path = Path(r"C:\Codex-Projects\ARX-Agent-DNA-Lab\codex-capability-baseline.json")
    if not path.exists():
        pytest.skip("external Phase 0 acceptance evidence is not present")
    from arx.agent.importer import load_experimental_baseline
    snapshot = import_experimental_baseline(load_experimental_baseline(path))
    assert len(snapshot.capabilities) == 129
    assert snapshot.summary["status_counts"] == {
        "BLOCKED": 1, "FAIL": 10, "NOT_APPLICABLE": 3, "NOT_TESTED": 8, "PASS": 102, "UNKNOWN": 5
    }
