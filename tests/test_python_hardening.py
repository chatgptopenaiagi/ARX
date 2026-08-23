import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from arx.core.models import Evidence, EvidenceKind
from arx.machine.windows import discover_python_installations
from arx.project import (
    ExecutionContext,
    ProviderHealth,
    ProviderKind,
    ProviderScope,
    Satisfaction,
    Severity,
    assign_provider_roles,
    inspect_project,
    make_provider,
    preflight,
    python_constraints_overlap,
    python_version_satisfies,
    resolve_python,
)


def runtime(path, version, *, healthy=True, health_status=None, architecture="64-bit"):
    return make_provider(
        path=path,
        version=version,
        kind=ProviderKind.CPYTHON,
        discovery_method="deterministic fixture",
        healthy=healthy,
        health_status=health_status,
        architecture=architecture,
        evidence=[Evidence(EvidenceKind.OBSERVED, str(path), "fixture", "fixture")],
    )


def project_at(tmp_path, constraint=">=3.12,<3.13", *, selection=None):
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="hardening"\nrequires-python="{constraint}"',
        encoding="utf-8",
    )
    if selection:
        (tmp_path / ".python-version").write_text(selection, encoding="utf-8")
    return inspect_project(tmp_path)


def report_for(project, providers, resolved, *, command="python"):
    context = ExecutionContext.capture(
        project.root, environment={"PATH": str(Path(resolved.path).parent)}, command=command
    )
    resolution = resolve_python(
        providers, context, command_paths=[resolved.path]
    )
    return preflight(project, providers, resolution)


def test_true_red_has_only_incompatible_healthy_providers(tmp_path):
    project = project_at(tmp_path)
    old = runtime(r"C:\Python311\python.exe", "3.11.9")
    new = runtime(r"C:\Python314\python.exe", "3.14.6")
    report = report_for(project, [old, new], new)

    assert report.provider_roles.compatible_provider_ids == []
    assert report.provider_roles.preferred_provider_id is None
    assert report.severity.severity is Severity.RED
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" in report.severity.blocker_ids


def test_windowsapps_shadowing_preserves_resolution_and_recovery(tmp_path):
    project = project_at(tmp_path)
    alias = make_provider(
        path=r"C:\Users\Alice\AppData\Local\Microsoft\WindowsApps\python.exe",
        version=None,
        kind=ProviderKind.WINDOWSAPPS_ALIAS,
        discovery_method="deterministic fixture",
        healthy=False,
        health_status=ProviderHealth.UNHEALTHY,
        health_reason="execution alias did not start an interpreter",
    )
    compatible = runtime(r"C:\Python312\python.exe", "3.12.13")
    report = report_for(project, [alias, compatible], alias)

    assert report.resolution.resolved_provider_id == alias.id
    assert report.provider_roles.resolved_provider_id == alias.id
    assert report.provider_roles.compatible_provider_ids == [compatible.id]
    assert report.provider_roles.preferred_provider_id == compatible.id
    assert report.evaluation.satisfaction is Satisfaction.CONFLICT
    assert report.severity.severity is Severity.YELLOW
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in report.severity.blocker_ids
    assert report.plan.steps[0].provider_id == compatible.id


def test_python_python3_and_py_are_independent_context_resolutions(tmp_path):
    providers = [
        runtime(r"C:\Commands\python.exe", "3.12.1"),
        runtime(r"C:\Commands\python3.exe", "3.13.2"),
        runtime(r"C:\Windows\py.exe", "3.11.9"),
    ]
    resolved = {}
    for command, provider in zip(("python", "python3", "py"), providers):
        context = ExecutionContext.capture(
            tmp_path, environment={"PATH": r"C:\Commands"}, command=command
        )
        result = resolve_python(providers, context, command_paths=[provider.path])
        resolved[command] = (context.id, result.resolved_provider_id)

    assert {item[1] for item in resolved.values()} == {item.id for item in providers}
    assert len({item[0] for item in resolved.values()}) == 3


def test_found_command_path_is_retained_when_provider_mapping_is_unavailable(tmp_path):
    path = str(tmp_path / "Unparseable Python" / "python3.exe")
    context = ExecutionContext.capture(
        tmp_path, environment={"PATH": str(Path(path).parent)}, command="python3"
    )
    resolution = resolve_python([], context, command_paths=[path])

    assert resolution.resolved_path == str(Path(path).resolve(strict=False))
    assert resolution.resolved_provider_id is None
    assert resolution.candidate_provider_ids == []


def test_provider_identity_retains_path_and_architecture():
    first = runtime(r"C:\PythonA\python.exe", "3.12.13", architecture="64-bit")
    second = runtime(r"C:\PythonB\python.exe", "3.12.13", architecture="64-bit")
    alternate_arch = runtime(
        r"C:\PythonA\python.exe", "3.12.13", architecture="32-bit"
    )

    assert first.id != second.id
    assert first.executable_identity != second.executable_identity
    assert first.id != alternate_arch.id
    assert first.executable_identity == alternate_arch.executable_identity


def test_healthy_same_version_provider_is_not_poisoned_by_unhealthy_peer(tmp_path):
    project = project_at(tmp_path)
    broken = runtime(
        r"C:\Broken\python.exe",
        "3.12.13",
        healthy=False,
        health_status=ProviderHealth.UNHEALTHY,
    )
    healthy = runtime(r"C:\Healthy\python.exe", "3.12.13")
    current = runtime(r"C:\Python314\python.exe", "3.14.6")
    report = report_for(project, [broken, healthy, current], current)

    assert report.provider_roles.compatible_provider_ids == [healthy.id]
    assert report.provider_roles.preferred_provider_id == healthy.id
    assert report.severity.severity is Severity.YELLOW
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in report.severity.blocker_ids


def test_preferred_unavailable_recomputes_to_healthy_pinned_alternative(tmp_path):
    project = project_at(tmp_path, selection="3.12")
    stale = runtime(
        project.root / ".venv" / "Scripts" / "python.exe",
        "3.12.13",
        healthy=False,
        health_status=ProviderHealth.UNHEALTHY,
    )
    alternative = runtime(r"C:\Python312\python.exe", "3.12.13")
    current = runtime(r"C:\Python314\python.exe", "3.14.6")
    report = report_for(project, [stale, alternative, current], current)

    assert set(report.provider_roles.pinned_provider_ids) == {stale.id, alternative.id}
    assert report.provider_roles.compatible_provider_ids == [alternative.id]
    assert report.provider_roles.preferred_provider_id == alternative.id
    assert "ARX-PYTHON-PINNED-PROVIDER-UNUSABLE" in report.severity.warning_ids
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in report.severity.blocker_ids
    assert report.severity.severity is Severity.YELLOW
    assert report.plan.steps[0].provider_id == alternative.id


def test_pinned_and_preferred_remain_distinct_from_current_resolution(tmp_path):
    project = project_at(tmp_path, selection="3.12.12")
    current = runtime(r"C:\Current\python.exe", "3.12.13")
    pinned = runtime(r"C:\Pinned\python.exe", "3.12.12")
    report = report_for(project, [current, pinned], current)

    assert report.evaluation.satisfaction is Satisfaction.SATISFIED
    assert report.provider_roles.resolved_provider_id == current.id
    assert report.provider_roles.pinned_provider_ids == [pinned.id]
    assert report.provider_roles.preferred_provider_id == pinned.id
    assert "ARX-PYTHON-PINNED-MISMATCH" in report.severity.warning_ids
    assert report.severity.severity is Severity.YELLOW
    assert report.plan.steps[0].id == "ARX-PLAN-USE-PINNED-PYTHON"
    assert report.plan.steps[0].provider_id == pinned.id
    assert not hasattr(report.provider_roles, "selected_provider_id")
    assert not hasattr(report.provider_roles, "active_for_project_provider_id")


def test_version_compatible_but_unhealthy_is_not_usable_or_green(tmp_path):
    project = project_at(tmp_path)
    broken = runtime(
        r"C:\Broken\python.exe",
        "3.12.13",
        healthy=False,
        health_status=ProviderHealth.UNHEALTHY,
    )
    report = report_for(project, [broken], broken)

    assert python_version_satisfies(broken.version, project.primary_python_requirement.constraint)
    assert report.provider_roles.compatible_provider_ids == []
    assert report.provider_roles.preferred_provider_id is None
    assert report.severity.severity is Severity.RED


def test_timeout_remains_unknown_and_does_not_prove_absence(tmp_path):
    project = project_at(tmp_path)
    uncertain = runtime(
        r"C:\Slow\python.exe",
        "3.12.13",
        healthy=None,
        health_status=ProviderHealth.UNKNOWN,
    )
    current = runtime(r"C:\Python314\python.exe", "3.14.6")
    report = report_for(project, [uncertain, current], current)

    assert report.evaluation.unverified_provider_ids == [uncertain.id]
    assert report.provider_roles.compatible_provider_ids == []
    assert "ARX-PYTHON-PROVIDER-USABILITY-UNKNOWN" in report.severity.warning_ids
    assert "ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in report.severity.blocker_ids
    assert report.severity.severity is Severity.YELLOW


@pytest.mark.parametrize(
    ("failure", "status", "healthy"),
    [
        (PermissionError("denied"), "unknown", None),
        (subprocess.TimeoutExpired("python", 2), "unknown", None),
    ],
)
def test_probe_failures_preserve_exists_health_and_reason(
    monkeypatch, tmp_path, failure, status, healthy
):
    executable = tmp_path / "Python Ü" / "python.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")
    monkeypatch.setattr("arx.machine.windows._python_candidates", lambda: [str(executable)])
    monkeypatch.setattr(
        "arx.machine.windows.subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(failure)
    )

    record = discover_python_installations(timeout=2)[0]
    assert record["exists"] is True
    assert record["health_status"] == status
    assert record["healthy"] is healthy
    assert record["health_reason"]


def test_found_but_unparseable_is_degraded_not_absent(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr("arx.machine.windows._python_candidates", lambda: [str(executable)])
    monkeypatch.setattr(
        "arx.machine.windows.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="Python 3.12.13", stderr=""
        ),
    )

    record = discover_python_installations()[0]
    assert record["exists"] is True
    assert record["health_status"] == "degraded"
    assert record["healthy"] is False
    assert "valid fixed-probe output" in record["health_reason"]


def test_non_ascii_spaced_and_long_paths_remain_stable():
    nested = "\\".join(["very-long-segment"] * 15)
    path = rf"C:\Users\Zoë\Project Space\{nested}\python.exe"
    provider = runtime(path, "3.12.13")

    assert "Zoë" in provider.path
    assert "Project Space" in provider.path
    assert provider.id.startswith("provider:")


def test_execution_context_changes_invalidate_resolution_assumptions(tmp_path):
    base = {"PATH": r"C:\One", "PATHEXT": ".EXE"}
    contexts = [
        ExecutionContext.capture(tmp_path, environment=base),
        ExecutionContext.capture(tmp_path, environment={**base, "PATH": r"C:\Two"}),
        ExecutionContext.capture(tmp_path / "other", environment=base),
        ExecutionContext.capture(tmp_path, environment={**base, "VIRTUAL_ENV": r"C:\venv"}),
        ExecutionContext.capture(tmp_path, environment={**base, "CONDA_PREFIX": r"C:\conda"}),
        ExecutionContext.capture(tmp_path, environment={**base, "UV_PROJECT_ENVIRONMENT": ".uv"}),
    ]

    assert len({item.id for item in contexts}) == len(contexts)
    assert contexts[3].virtual_environment is True
    assert contexts[4].conda_environment is True
    assert contexts[5].uv_indicators == ["UV_PROJECT_ENVIRONMENT"]


def test_process_contexts_can_resolve_same_command_differently(tmp_path):
    first = runtime(r"C:\GUI\python.exe", "3.12.13")
    second = runtime(r"C:\CI\python.exe", "3.14.6")
    gui = ExecutionContext.capture(tmp_path, environment={"PATH": r"C:\GUI"})
    ci = ExecutionContext.capture(tmp_path, environment={"PATH": r"C:\CI"})

    gui_resolution = resolve_python([first, second], gui, command_paths=[first.path])
    ci_resolution = resolve_python([first, second], ci, command_paths=[second.path])

    assert gui.id != ci.id
    assert gui_resolution.resolved_provider_id == first.id
    assert ci_resolution.resolved_provider_id == second.id


def test_user_and_machine_scope_are_preserved(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Alice")
    user = runtime(r"C:\Users\Alice\Python312\python.exe", "3.12.13")
    machine = runtime(r"C:\Program Files\Python312\python.exe", "3.12.13")

    assert user.scope is ProviderScope.USER
    assert machine.scope is ProviderScope.MACHINE
    assert user.path == r"C:\Users\Alice\Python312\python.exe"
    assert machine.path == r"C:\Program Files\Python312\python.exe"


def test_generic_provider_role_contract_keeps_facts_and_policy_separate():
    resolved = runtime(r"C:\Current\python.exe", "3.14.6")
    compatible = runtime(r"C:\Compatible\python.exe", "3.12.13")
    roles = assign_provider_roles(
        capability="python.runtime",
        providers=[resolved, compatible],
        resolved_provider_id=resolved.id,
        is_compatible=lambda item: item.id == compatible.id,
        preferred_key=lambda item: (item.path,),
        pinned_constraints=["==3.12"],
        is_pinned=lambda item: item.version.startswith("3.12"),
    )

    assert roles.resolved_provider_id == resolved.id
    assert roles.compatible_provider_ids == [compatible.id]
    assert roles.preferred_provider_id == compatible.id
    assert roles.pinned_provider_ids == [compatible.id]


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (">=3.12,<3.13", ">=3.12.1,<3.13", True),
        (">=3.12,<3.13", ">=3.13", False),
        (">=3.12,<3.13", "~=3.12", None),
    ],
)
def test_constraint_overlap_is_explicit_and_conservative(left, right, expected):
    assert python_constraints_overlap(left, right) is expected


def test_prerelease_does_not_enter_stable_compatible_set_by_tuple_order_alone():
    assert python_version_satisfies("3.15.0b4", ">=3.14,<3.15") is None
    assert python_version_satisfies("3.15.0b4", ">=3.15b1,<3.15") is True


def test_multiple_runtime_constraints_are_classified(tmp_path):
    project_at(tmp_path)
    (tmp_path / "uv.lock").write_text(
        'version=1\nrequires-python=">=3.12.1,<3.13"', encoding="utf-8"
    )
    project = inspect_project(tmp_path)
    current = runtime(r"C:\Python312\python.exe", "3.12.13")
    report = report_for(project, [current], current)

    assert project.primary_python_requirement.source == "pyproject.toml"
    assert {item.evidence_purpose for item in project.requirements} >= {
        "requirement",
        "dependency_resolution",
    }
    assert "ARX-PYTHON-MULTIPLE-CONSTRAINTS" in report.severity.warning_ids
    assert report.severity.severity is Severity.YELLOW


def test_conflicting_runtime_constraints_are_blocking(tmp_path):
    project_at(tmp_path)
    (tmp_path / "uv.lock").write_text(
        'version=1\nrequires-python=">=3.13"', encoding="utf-8"
    )
    project = inspect_project(tmp_path)
    current = runtime(r"C:\Python312\python.exe", "3.12.13")
    report = report_for(project, [current], current)

    assert "ARX-PROJECT-REQUIREMENT-CONFLICT" in report.severity.blocker_ids
    assert report.severity.severity is Severity.RED


def test_unsupported_secondary_constraint_remains_unknown(tmp_path):
    project_at(tmp_path)
    (tmp_path / "uv.lock").write_text(
        'version=1\nrequires-python="~=3.12"', encoding="utf-8"
    )
    project = inspect_project(tmp_path)
    current = runtime(r"C:\Python312\python.exe", "3.12.13")
    report = report_for(project, [current], current)

    secondary = next(item for item in report.evaluations if item.requirement_id != report.evaluation.requirement_id)
    assert secondary.satisfaction is Satisfaction.UNKNOWN
    assert "ARX-RESOLUTION-UNKNOWN" in report.severity.warning_ids
    assert report.severity.severity is Severity.YELLOW


def test_setup_cfg_and_setup_py_are_static_requirement_evidence(tmp_path, monkeypatch):
    (tmp_path / "setup.cfg").write_text(
        "[metadata]\nname=legacy\n[options]\npython_requires=>=3.11,<3.13",
        encoding="utf-8",
    )
    (tmp_path / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='never-run', python_requires=dynamic_value)\nraise RuntimeError('must not execute')",
        encoding="utf-8",
    )
    invoked = []
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: invoked.append((args, kwargs)))

    project = inspect_project(tmp_path)

    assert invoked == []
    assert project.identity == "legacy"
    assert project.primary_python_requirement.source == "setup.cfg"
    assert project.primary_python_requirement.constraint == ">=3.11,<3.13"
    assert any(item.source == "setup.py" and item.constraint is None for item in project.requirements)
    assert any("was not executed" in item for item in project.unknowns)


def test_selection_only_project_is_unknown_not_false_green(tmp_path):
    (tmp_path / ".python-version").write_text("3.12", encoding="utf-8")
    project = inspect_project(tmp_path)
    current = runtime(r"C:\Python312\python.exe", "3.12.13")
    report = report_for(project, [current], current)

    assert project.primary_python_requirement is None
    assert project.requirements[0].evidence_purpose == "selection"
    assert report.provider_roles.pinned_provider_ids == [current.id]
    assert report.severity.severity is Severity.YELLOW
    assert "ARX-RESOLUTION-UNKNOWN" in report.severity.warning_ids
