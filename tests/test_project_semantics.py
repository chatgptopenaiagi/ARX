import json
import os
from pathlib import Path

import pytest

from arx.core.models import Evidence, EvidenceKind, serialize
from arx.exporters import project_codex_report
from arx.project import (
    ExecutionContext,
    ExecutionResolution,
    Policy,
    ProjectDNA,
    ProviderKind,
    Relevance,
    Requirement,
    Satisfaction,
    Severity,
    inspect_project,
    make_provider,
    preflight,
    providers_from_machine,
    resolve_python,
)


FIXTURES = Path(__file__).parent / "fixtures" / "python"


def provider(path, version, *, healthy=True, kind=ProviderKind.CPYTHON):
    return make_provider(
        path=str(path),
        version=version,
        kind=kind,
        discovery_method="fixture",
        healthy=healthy,
    )


def resolution(project, providers, resolved):
    context = ExecutionContext.capture(
        project.root,
        environment={"PATH": os.pathsep.join(str(item.path) for item in providers)},
    )
    return resolve_python(providers, context, command_paths=[str(resolved.path)])


def test_case_a_matching_resolution_is_green():
    project = inspect_project(FIXTURES / "case_a")
    current = provider(project.root / ".venv" / "Scripts" / "python.exe", "3.12.13")
    report = preflight(project, [current], resolution(project, [current], current))

    assert project.identity == "case-a"
    assert project.primary_python_requirement.constraint == ">=3.12,<3.13"
    assert report.evaluation.satisfaction is Satisfaction.SATISFIED
    assert report.severity.severity is Severity.GREEN
    assert report.resolution.resolved_provider_id == current.id
    assert report.evaluation.preferred_provider_id == current.id


def test_case_b_mismatch_with_existing_compatible_provider_is_yellow():
    project = inspect_project(FIXTURES / "case_b")
    current = provider(r"C:\Python314\python.exe", "3.14.6")
    compatible = provider(project.root / ".venv" / "Scripts" / "python.exe", "3.12.13")
    providers = [current, compatible]
    report = preflight(project, providers, resolution(project, providers, current))

    assert report.evaluation.satisfaction is Satisfaction.UNSATISFIED
    assert report.evaluation.compatible_provider_ids == [compatible.id]
    assert report.evaluation.preferred_provider_id == compatible.id
    assert report.severity.severity is Severity.YELLOW
    assert "ARX-PYTHON-DEFAULT-MISMATCH" in {item.id for item in report.conflicts}
    assert any(step.id == "ARX-PLAN-USE-EXISTING-PYTHON" for step in report.plan.steps)
    assert all(step.automatic is False for step in report.plan.steps)


def test_case_c_mismatch_without_compatible_provider_is_red():
    project = inspect_project(FIXTURES / "case_c")
    current = provider(r"C:\Python314\python.exe", "3.14.6")
    report = preflight(project, [current], resolution(project, [current], current))

    assert report.evaluation.satisfaction is Satisfaction.UNSATISFIED
    assert report.evaluation.compatible_provider_ids == []
    assert report.severity.severity is Severity.RED
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" in report.severity.blocker_ids
    assert all(step.automatic is False for step in report.plan.steps)


def test_case_d_unknown_requirement_is_yellow_without_invention():
    project = inspect_project(FIXTURES / "case_d")
    current = provider(r"C:\Python314\python.exe", "3.14.6")
    report = preflight(project, [current], resolution(project, [current], current))

    assert project.primary_python_requirement.constraint is None
    assert report.evaluation.satisfaction is Satisfaction.UNKNOWN
    assert report.severity.severity is Severity.YELLOW
    assert "ARX-RESOLUTION-UNKNOWN" in report.severity.warning_ids


def test_case_e_equal_versions_have_distinct_provider_identity():
    first = provider(r"C:\PythonA\python.exe", "3.12.13")
    second = provider(r"C:\PythonB\python.exe", "3.12.13")

    assert first.id != second.id
    assert first.executable_identity != second.executable_identity


def test_case_f_windowsapps_alias_is_not_a_healthy_interpreter():
    machine = {
        "python_installations": [
            {
                "path": r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps\python.exe",
                "version": None,
                "healthy": False,
                "health_probe": "import ssl, ctypes",
                "error": "alias did not start an interpreter",
                "evidence": [],
            }
        ]
    }
    providers = providers_from_machine(machine)

    assert providers[0].kind is ProviderKind.WINDOWSAPPS_ALIAS
    assert providers[0].healthy is False
    assert providers[0].version is None


def test_unused_windowsapps_alias_does_not_downgrade_a_satisfied_project():
    project = inspect_project(FIXTURES / "case_a")
    current = provider(project.root / ".venv" / "Scripts" / "python.exe", "3.12.13")
    alias = provider(
        r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps\python.exe",
        None,
        healthy=False,
        kind=ProviderKind.WINDOWSAPPS_ALIAS,
    )
    providers = [current, alias]
    report = preflight(project, providers, resolution(project, providers, current))

    assert "ARX-PYTHON-WINDOWSAPPS-ALIAS" in {item.id for item in report.findings}
    assert report.severity.severity is Severity.GREEN


def test_case_g_python_version_conflict_is_explicit():
    project = inspect_project(FIXTURES / "case_g")
    selected = provider(r"C:\Python314\python.exe", "3.14.6")
    compatible = provider(r"C:\Python312\python.exe", "3.12.13")
    providers = [selected, compatible]
    report = preflight(project, providers, resolution(project, providers, selected))

    conflict = next(item for item in report.conflicts if item.id == "ARX-PROJECT-REQUIREMENT-CONFLICT")
    assert len(conflict.participant_ids) >= 2
    assert conflict.evidence_refs
    assert report.severity.severity is Severity.RED
    assert [item.id for item in report.plan.steps] == [
        "ARX-PLAN-ALIGN-PYTHON-CONSTRAINTS",
        "ARX-PLAN-REEVALUATE-CONTEXT",
    ]


def test_case_h_optional_python_capability_unavailable_is_not_red(tmp_path):
    requirement = Requirement.create(
        capability="python.optional-runtime",
        constraint=">=3.12",
        source="feature.toml",
        field="features.python",
        relevance=Relevance.OPTIONAL,
        evidence=[Evidence(EvidenceKind.DECLARED, "feature.toml", ">=3.12", "fixture")],
    )
    project = ProjectDNA.create(root=tmp_path, identity="optional", optional_requirements=[requirement])
    context = ExecutionContext.capture(tmp_path, environment={"PATH": ""}, command="python.optional-runtime")
    unresolved = ExecutionResolution.create(command="python.optional-runtime", context=context)
    report = preflight(project, [], unresolved)

    assert report.evaluations[0].satisfaction is Satisfaction.OPTIONAL_UNAVAILABLE
    assert report.severity.severity is Severity.GREEN


def test_requirement_files_are_bounded_static_project_evidence():
    project = inspect_project(FIXTURES / "requirements")

    assert {item.path for item in project.manifests} == {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements/docs.txt",
    }
    assert {item.capability for item in project.requirements} == {"python.package:requests"}
    assert {item.capability for item in project.optional_requirements} == {
        "python.package:pytest",
        "python.package:sphinx",
    }


@pytest.mark.parametrize(
    ("payload", "expected_reason"),
    [
        (b"[project\nname='broken'", "malformed"),
        (b"\xff\xfe\x00\x00", "encoding"),
    ],
)
def test_manifest_failures_become_unknown_evidence(tmp_path, payload, expected_reason):
    (tmp_path / "pyproject.toml").write_bytes(payload)
    project = inspect_project(tmp_path)

    assert project.primary_python_requirement.constraint is None
    assert any(item.kind is EvidenceKind.UNKNOWN for item in project.evidence)
    assert any(expected_reason in item.lower() for item in project.unknowns)


def test_huge_manifest_is_not_read(tmp_path):
    (tmp_path / "pyproject.toml").write_bytes(b"x" * (1024 * 1024 + 1))
    project = inspect_project(tmp_path)

    assert project.primary_python_requirement.constraint is None
    assert any("size limit" in item.lower() for item in project.unknowns)


def test_symlink_manifest_is_not_followed(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.toml"
    outside.write_text('[project]\nrequires-python=">=9"', encoding="utf-8")
    try:
        (tmp_path / "pyproject.toml").symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    project = inspect_project(tmp_path)
    assert project.primary_python_requirement.constraint is None
    assert any("symbolic link" in item.lower() for item in project.unknowns)


def test_unsupported_constraint_stays_unknown(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="unsupported"\nrequires-python="===vendor-python"',
        encoding="utf-8",
    )
    current = provider(r"C:\Python312\python.exe", "3.12.13")
    project = inspect_project(tmp_path)
    report = preflight(project, [current], resolution(project, [current], current))

    assert report.evaluation.satisfaction is Satisfaction.UNKNOWN
    assert report.severity.severity is Severity.YELLOW


def test_malicious_requirement_filename_is_only_parsed_as_data(tmp_path, monkeypatch):
    manifest = tmp_path / "requirements-&whoami.txt"
    manifest.write_text("safe-package==1", encoding="utf-8")
    invoked = []
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: invoked.append((args, kwargs)))

    project = inspect_project(tmp_path)

    assert invoked == []
    assert project.optional_requirements[0].capability == "python.package:safe-package"


def test_resolution_is_context_scoped_and_path_is_not_exported():
    first = ExecutionContext.capture(
        r"C:\Project",
        environment={"PATH": r"C:\One", "VIRTUAL_ENV": r"C:\Secret\venv", "CONDA_DEFAULT_ENV": "private-name"},
    )
    second = ExecutionContext.capture(r"C:\Project", environment={"PATH": r"C:\Two"})

    assert first.id != second.id
    assert first.path_fingerprint != second.path_fingerprint
    assert not hasattr(first, "effective_path")
    assert first.virtual_environment is True
    assert first.conda_environment is True
    assert "Secret" not in json.dumps(serialize(first))
    assert "private-name" not in json.dumps(serialize(first))


def test_empty_project_is_unknown_yellow_not_green(tmp_path):
    project = inspect_project(tmp_path)
    context = ExecutionContext.capture(tmp_path, environment={"PATH": ""})
    report = preflight(project, [], ExecutionResolution.create(command="python", context=context))

    assert report.severity.severity is Severity.YELLOW
    assert "ARX-RESOLUTION-UNKNOWN" in report.severity.warning_ids
    assert project.unknowns
    assert [item.id for item in report.plan.steps] == [
        "ARX-PLAN-VERIFY-PYTHON-REQUIREMENT",
        "ARX-PLAN-REEVALUATE-CONTEXT",
    ]


def test_policy_forbids_host_mutation_by_default():
    policy = Policy()

    assert policy.host_mutation == "forbidden"
    assert policy.global_path_changes == "forbidden"
    assert policy.global_runtime_upgrade == "forbidden"
    assert policy.prefer_existing_providers is True
    assert policy.prefer_project_local is True


def test_ai_contract_uses_schema_02_and_separates_semantics(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Alice")
    project = inspect_project(FIXTURES / "case_b")
    current = provider(r"C:\Users\Alice\Python314\python.exe", "3.14.6")
    compatible = provider(project.root / ".venv" / "Scripts" / "python.exe", "3.12.13")
    providers = [current, compatible]
    report = preflight(project, providers, resolution(project, providers, current))
    contract = project_codex_report(report, "0.3.0")

    assert contract["schema_version"] == "0.2"
    assert contract["producer"] == {"name": "ARX", "version": "0.3.0"}
    assert contract["decision"] == "YELLOW"
    assert set(contract) >= {
        "facts",
        "decisions",
        "selected_providers",
        "blockers",
        "warnings",
        "recommendations",
        "constraints",
        "unknowns",
        "evidence_references",
    }
    encoded = json.dumps(contract)
    assert r"C:\\Users\\Alice" not in encoded
    assert str(project.root) not in encoded
    assert "%USERPROFILE%" in encoded
    assert "%PROJECT_ROOT%" in encoded
    assert all(item["automatic"] is False for item in contract["recommendations"])


def test_explanation_graph_traces_severity_back_to_requirement_evidence():
    project = inspect_project(FIXTURES / "case_c")
    current = provider(r"C:\Python314\python.exe", "3.14.6")
    report = preflight(project, [current], resolution(project, [current], current))

    node_types = {node.type for node in report.explanation.nodes}
    assert {"evidence", "requirement", "provider", "resolution", "satisfaction", "severity", "recommendation"} <= node_types
    assert any(edge.relation == "supports" for edge in report.explanation.edges)
    assert any(edge.relation == "causes" for edge in report.explanation.edges)


def test_serialized_project_models_remain_presentation_independent():
    project = inspect_project(FIXTURES / "case_a")
    data = serialize(project)

    assert data["requirements"][0]["evidence"][0]["kind"] == "declared"
    assert "widget" not in json.dumps(data).lower()
