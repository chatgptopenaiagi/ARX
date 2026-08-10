import pytest

from arx import __version__
from arx.cli import preflight_envelope, preflight_text
from arx.desktop.controllers import DesktopController, project_readiness_view_model
from arx.exporters import project_codex_report
from arx.project import (
    ExecutionContext,
    ProviderKind,
    Severity,
    inspect_project,
    make_provider,
    preflight,
    provider_graph_from_machine,
    providers_from_machine,
    resolve_python,
)


pytestmark = pytest.mark.integration


def canonical_yellow(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="cross-surface"\nrequires-python=">=3.12,<3.13"',
        encoding="utf-8",
    )
    (tmp_path / ".python-version").write_text("3.12", encoding="utf-8")
    machine = {
        "generated_at": "2026-08-10T10:00:00+00:00",
        "python_installations": [
            {
                "path": r"C:\Python314\python.exe",
                "version": "3.14.6",
                "architecture_bits": "64-bit",
                "healthy": True,
                "health_status": "healthy",
                "health_probe": "fixture",
            },
            {
                "path": r"C:\Python312\python.exe",
                "version": "3.12.13",
                "architecture_bits": "64-bit",
                "healthy": True,
                "health_status": "healthy",
                "health_probe": "fixture",
            },
        ],
    }
    project = inspect_project(tmp_path)
    providers = providers_from_machine(machine)
    graph = provider_graph_from_machine(machine)
    current = next(item for item in providers if item.version == "3.14.6")
    context = ExecutionContext.capture(
        project.root, environment={"PATH": r"C:\Python314"}, command="python"
    )
    resolution = resolve_python(providers, context, command_paths=[current.path])
    return machine, project, providers, graph, context, preflight(
        project,
        providers,
        resolution,
        provider_inventory_generated_at=machine["generated_at"],
    )


def test_canonical_semantics_are_identical_across_all_surfaces(tmp_path):
    machine, project, providers, graph, context, report = canonical_yellow(tmp_path)
    cli = preflight_envelope(report)["project_preflight"]
    contract = project_codex_report(report, __version__)
    desktop = project_readiness_view_model(report)
    controller = DesktopController()
    controller.machine = machine
    controller.project_preflight = report

    assert report.severity.severity is Severity.YELLOW
    assert cli["severity"]["severity"] == "yellow"
    assert contract["decision"] == "YELLOW"
    assert desktop["decision"] == "YELLOW"
    assert controller.project_preflight is report

    expected_blockers = report.severity.blocker_ids
    expected_warnings = report.severity.warning_ids
    expected_preferred = report.provider_roles.preferred_provider_id
    expected_resolved = report.provider_roles.resolved_provider_id
    expected_compatible = report.provider_roles.compatible_provider_ids
    expected_pinned = report.provider_roles.pinned_provider_ids
    expected_plan = [item.id for item in report.plan.steps]
    assert cli["severity"]["blocker_ids"] == expected_blockers
    assert [item["id"] for item in contract["blockers"]] == expected_blockers
    assert desktop["blocker_ids"] == expected_blockers
    assert cli["severity"]["warning_ids"] == expected_warnings
    assert [item["id"] for item in contract["warnings"]] == expected_warnings
    assert desktop["warning_ids"] == expected_warnings
    assert cli["provider_roles"]["preferred_provider_id"] == expected_preferred
    assert contract["selected_providers"]["preferred"]["id"] == expected_preferred
    assert desktop["preferred"]["id"] == expected_preferred
    assert cli["provider_roles"]["resolved_provider_id"] == expected_resolved
    assert contract["selected_providers"]["resolved"]["id"] == expected_resolved
    assert desktop["resolved"]["id"] == expected_resolved
    assert cli["provider_roles"]["compatible_provider_ids"] == expected_compatible
    assert [item["id"] for item in contract["selected_providers"]["compatible"]] == expected_compatible
    assert [item["id"] for item in desktop["compatible"]] == expected_compatible
    assert cli["provider_roles"]["pinned_provider_ids"] == expected_pinned
    assert [item["id"] for item in contract["selected_providers"]["pinned"]] == expected_pinned
    assert [item["id"] for item in desktop["pinned"]] == expected_pinned
    assert cli["severity"]["current_context_satisfaction"] == "unsatisfied"
    assert contract["decisions"]["current_context"]["satisfaction"] == "UNSATISFIED"
    assert desktop["current_context_satisfaction"] == "UNSATISFIED"
    assert cli["severity"]["recoverability"] == "recoverable"
    assert contract["decisions"]["recoverability"]["status"] == "RECOVERABLE"
    assert desktop["recoverability"] == "RECOVERABLE"
    assert [item["id"] for item in cli["plan"]["steps"]] == expected_plan
    assert [item["id"] for item in contract["recommendations"]] == expected_plan
    assert desktop["plan_step_ids"] == expected_plan

    assert graph.providers == providers
    assert report.context.id == context.id
    assert desktop["resolved"]["health_status"] == "healthy"
    assert "PROJECT READINESS: YELLOW" in preflight_text(report)


def test_ai_contract_exposes_reasoning_and_freshness_without_role_collapse(tmp_path):
    _, project, _, _, context, report = canonical_yellow(tmp_path)
    contract = project_codex_report(report, __version__)

    assert contract["facts"]["evaluated_requirement"] == {
        "id": report.evaluation.requirement_id,
        "capability": "python.runtime",
        "constraint": ">=3.12,<3.13",
        "source": "pyproject.toml",
        "field": "project.requires-python",
        "evidence_purpose": "requirement",
        "evidence_refs": [
            item["evidence_ref"]
            for item in contract["facts"]["requirements"][0]["evidence"]
        ],
    }
    freshness = contract["facts"]["freshness"]
    assert freshness["report_generated_at"] == report.generated_at
    assert freshness["project_observed_at"] == project.generated_at
    assert freshness["execution_context_id"] == context.id
    assert freshness["path_fingerprint"] == context.path_fingerprint
    assert freshness["process_environment_fingerprint"] == context.process_environment_fingerprint
    assert freshness["account_fingerprint"] == context.account_fingerprint
    assert freshness["project_evidence_fingerprint"].startswith("project-evidence:")
    assert freshness["provider_inventory_fingerprint"].startswith("provider-inventory:")
    assert freshness["provider_inventory_observed_at"] == "2026-08-10T10:00:00+00:00"
    assert contract["decisions"]["scope"] == "python_interpreter_and_toolchain_requirements"
    assert contract["decisions"]["current_context"]["satisfaction"] == "UNSATISFIED"
    assert contract["decisions"]["recoverability"]["status"] == "RECOVERABLE"
    assert contract["selected_providers"]["resolved"]["id"] != contract["selected_providers"]["preferred"]["id"]
    assert contract["selected_providers"]["compatible"]
    assert contract["selected_providers"]["pinned_constraints"] == ["==3.12"]
    warning = contract["warnings"][0]
    assert warning["id"] == warning["finding_id"]
    assert warning["severity"] == "WARNING"
    assert warning["category"]
    assert warning["evidence_refs"]
