import copy

import pytest

from arx.core.models import serialize
from arx.exporters import project_codex_report, validate_project_codex_contract
from arx.project import (
    ExecutionContext,
    InterpretationState,
    Recoverability,
    RequirementEvidenceType,
    Satisfaction,
    SemanticInvariantError,
    Severity,
    inspect_project,
    make_provider,
    preflight,
    resolve_python,
    validate_readiness_result,
)


def _project(tmp_path, requirement=">=3.12,<3.13", selection=None):
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="domain-lock"\nrequires-python="{requirement}"',
        encoding="utf-8",
    )
    if selection is not None:
        (tmp_path / ".python-version").write_text(selection, encoding="utf-8")
    return inspect_project(tmp_path)


def _provider(path, version, healthy=True):
    return make_provider(
        path=path,
        version=version,
        discovery_method="deterministic domain fixture",
        healthy=healthy,
    )


def _report(project, providers, resolved):
    context = ExecutionContext.capture(
        project.root,
        environment={"PATH": r"C:\fixture"},
        command="python",
    )
    resolution = resolve_python(
        providers,
        context,
        command_paths=[resolved.path] if resolved else [],
    )
    return preflight(project, providers, resolution)


def test_requirement_graph_preserves_typed_requirement_and_selection_evidence(tmp_path):
    project = _project(tmp_path, selection="3.12.13")
    primary = project.primary_python_requirement

    assert primary.is_effective is True
    assert primary.effective_specifier == ">=3.12,<3.13"
    assert primary.interpretation_state is InterpretationState.INTERPRETED
    assert {item.evidence_type for item in primary.evidence} == {
        RequirementEvidenceType.REQUIREMENT,
        RequirementEvidenceType.SELECTION,
    }
    assert project.requirement_graph.effective_requirement_ids == {
        "python.runtime": primary.id
    }
    assert len(project.requirement_graph.requirements_by_capability["python.runtime"]) == 2
    assert all(item.source_path for item in primary.evidence)
    assert all(item.source_key for item in primary.evidence)


def test_requirement_graph_surfaces_selection_conflict_without_overwrite(tmp_path):
    project = _project(tmp_path, selection="3.14")
    primary = project.primary_python_requirement
    selection = next(item for item in project.requirements if item.relation == "selects")

    assert primary.constraint == ">=3.12,<3.13"
    assert selection.constraint == "==3.14"
    assert primary.interpretation_state is InterpretationState.CONFLICT
    assert primary.conflict_ids == ["ARX-PROJECT-REQUIREMENT-CONFLICT"]
    assert project.requirement_graph.conflict_ids == [
        "ARX-PROJECT-REQUIREMENT-CONFLICT"
    ]


@pytest.mark.parametrize(
    ("resolved_version", "extra_version", "expected_severity", "expected_satisfaction", "expected_recoverability"),
    [
        ("3.12.13", None, Severity.GREEN, Satisfaction.SATISFIED, Recoverability.READY),
        ("3.14.6", "3.12.13", Severity.YELLOW, Satisfaction.UNSATISFIED, Recoverability.RECOVERABLE),
        ("3.14.6", "3.11.9", Severity.RED, Satisfaction.UNSATISFIED, Recoverability.BLOCKED),
    ],
)
def test_decision_separates_current_context_from_recoverability(
    tmp_path,
    resolved_version,
    extra_version,
    expected_severity,
    expected_satisfaction,
    expected_recoverability,
):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", resolved_version)
    providers = [current]
    if extra_version:
        providers.append(_provider(r"C:\Other\python.exe", extra_version))
    report = _report(project, providers, current)

    assert report.severity.severity is expected_severity
    assert report.severity.current_context_satisfaction is expected_satisfaction
    assert report.severity.recoverability is expected_recoverability


def test_execution_context_exports_only_account_fingerprint(tmp_path):
    first = ExecutionContext.capture(
        tmp_path,
        environment={"PATH": "fixture", "USERDOMAIN": "ACME", "USERNAME": "Alice"},
    )
    second = ExecutionContext.capture(
        tmp_path,
        environment={"PATH": "fixture", "USERDOMAIN": "ACME", "USERNAME": "Bob"},
    )

    assert first.account_fingerprint
    assert first.account_fingerprint != second.account_fingerprint
    assert "Alice" not in str(serialize(first))
    assert "ACME" not in str(serialize(first))


def test_readiness_result_rejects_preferred_without_compatible(tmp_path):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", "3.14.6")
    compatible = _provider(r"C:\Compatible\python.exe", "3.12.13")
    report = _report(project, [current, compatible], current)
    contradictory = copy.deepcopy(report)
    contradictory.provider_roles.compatible_provider_ids = []

    with pytest.raises(SemanticInvariantError, match="preferred provider"):
        validate_readiness_result(contradictory)


def test_readiness_result_rejects_no_compatible_blocker_with_compatible(tmp_path):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", "3.14.6")
    compatible = _provider(r"C:\Compatible\python.exe", "3.12.13")
    report = _report(project, [current, compatible], current)
    contradictory = copy.deepcopy(report)
    contradictory.severity.blocker_ids.append(
        "ARX-PYTHON-NO-COMPATIBLE-PROVIDER"
    )

    with pytest.raises(SemanticInvariantError, match="NO-COMPATIBLE-PROVIDER"):
        validate_readiness_result(contradictory)


def test_ai_contract_semantic_guard_rejects_cross_field_contradiction(tmp_path):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", "3.14.6")
    compatible = _provider(r"C:\Compatible\python.exe", "3.12.13")
    contract = project_codex_report(
        _report(project, [current, compatible], current), "2.0.0"
    )
    contract["blockers"].append(
        {
            "id": "ARX-PYTHON-NO-COMPATIBLE-PROVIDER",
            "finding_id": "ARX-PYTHON-NO-COMPATIBLE-PROVIDER",
            "severity": "BLOCKER",
            "category": "python.provider",
            "message": "contradictory fixture",
            "evidence_refs": [],
        }
    )

    with pytest.raises(SemanticInvariantError, match="no compatible provider"):
        validate_project_codex_contract(contract)


def test_green_readiness_guard_rejects_unsatisfied_required_context(tmp_path):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", "3.12.13")
    contradictory = copy.deepcopy(_report(project, [current], current))
    contradictory.evaluation.satisfaction = Satisfaction.UNSATISFIED

    with pytest.raises(SemanticInvariantError, match="current-context satisfaction"):
        validate_readiness_result(contradictory)


def test_green_ai_contract_guard_rejects_unsatisfied_required_context(tmp_path):
    project = _project(tmp_path)
    current = _provider(r"C:\Current\python.exe", "3.12.13")
    contract = project_codex_report(_report(project, [current], current), "2.0.0")
    contract["decisions"]["current_context"]["satisfaction"] = "UNSATISFIED"
    contract["decisions"]["current_context"]["satisfied"] = False

    with pytest.raises(SemanticInvariantError, match="satisfaction"):
        validate_project_codex_contract(contract)
