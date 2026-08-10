import os
from pathlib import Path

from arx.project import (
    ExecutionContext,
    MutationRisk,
    Policy,
    ProviderKind,
    ResolutionCandidate,
    ResolutionCost,
    inspect_project,
    make_provider,
    preflight,
    rank_resolution_candidates,
    resolve_python,
)


FIXTURES = Path(__file__).parent / "fixtures" / "python"


def test_resolution_cost_components_are_explicit_and_normalized():
    existing = ResolutionCost(human_steps=1, machine_operations=0, mutation_risk=MutationRisk.NONE, reversible=True, downloads_required=0, new_runtime_installations=0, ai_interactions=0)
    install = ResolutionCost(human_steps=4, machine_operations=2, mutation_risk=MutationRisk.MEDIUM, reversible=True, downloads_required=1, new_runtime_installations=1, ai_interactions=1)

    assert existing.normalized_score < install.normalized_score
    assert existing.score_method == "normalized_component_weights_v1"
    assert existing.unit == "normalized_score_not_physical_units"


def test_candidate_ranking_filters_policy_and_requirement_before_cost():
    allowed = ResolutionCandidate(
        id="use-existing",
        action="Use existing provider",
        provider_id="provider:existing",
        satisfies_requirement=True,
        evidence_supported=True,
        policy_compliant=True,
        reusable=True,
        cost=ResolutionCost(1, 0, MutationRisk.NONE, True, 0, 0, 0),
    )
    global_mutation = ResolutionCandidate(
        id="rewrite-global-path",
        action="Rewrite global PATH",
        provider_id=None,
        satisfies_requirement=True,
        evidence_supported=True,
        policy_compliant=False,
        reusable=False,
        cost=ResolutionCost(1, 1, MutationRisk.HIGH, False, 0, 0, 0),
        rejection_reasons=["global_path_changes_forbidden"],
    )
    selection = rank_resolution_candidates([global_mutation, allowed], Policy())

    assert selection.selected.id == "use-existing"
    assert selection.rejected[0].id == "rewrite-global-path"
    assert "global_path_changes_forbidden" in selection.rejected[0].rejection_reasons


def test_planner_never_recommends_equivalent_install_when_provider_exists():
    project = inspect_project(FIXTURES / "case_b")
    current = make_provider(path=r"C:\Python314\python.exe", version="3.14.6", kind=ProviderKind.CPYTHON, discovery_method="fixture", healthy=True)
    compatible = make_provider(path=project.root / ".venv" / "Scripts" / "python.exe", version="3.12.13", kind=ProviderKind.VIRTUAL_ENVIRONMENT, discovery_method="fixture", healthy=True)
    providers = [current, compatible]
    context = ExecutionContext.capture(project.root, environment={"PATH": os.pathsep.join(item.path for item in providers)})
    report = preflight(project, providers, resolve_python(providers, context, command_paths=[current.path]))

    assert report.plan.selected_candidate_id == "ARX-CANDIDATE-USE-EXISTING-PYTHON"
    assert report.plan.cost.machine_mutations == 0
    assert report.plan.cost.new_runtime_installations == 0
    install = next(item for item in report.plan.candidates if item.id == "ARX-CANDIDATE-INSTALL-EQUIVALENT-PYTHON")
    assert install.policy_compliant is False
    assert "existing_compatible_provider_available" in install.rejection_reasons
    assert not any("install" in step.action.lower() for step in report.plan.steps)


def test_missing_provider_plan_is_advisory_and_avoids_global_mutation():
    project = inspect_project(FIXTURES / "case_c")
    current = make_provider(path=r"C:\Python314\python.exe", version="3.14.6", kind=ProviderKind.CPYTHON, discovery_method="fixture", healthy=True)
    context = ExecutionContext.capture(project.root, environment={"PATH": current.path})
    report = preflight(project, [current], resolve_python([current], context, command_paths=[current.path]))

    assert report.plan.selected_candidate_id == "ARX-CANDIDATE-PROVISION-PROJECT-PYTHON"
    assert report.plan.cost.new_runtime_installations == 1
    assert report.plan.cost.global_mutations == 0
    assert report.plan.automatic_execution is False
    assert all(step.automatic is False for step in report.plan.steps)
