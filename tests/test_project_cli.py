import json

from arx.cli import main, parser
from arx.project import (
    ExecutionContext,
    ProjectDNA,
    ProviderKind,
    Severity,
    inspect_project,
    make_provider,
    preflight,
    resolve_python,
)


def fixture_report(path):
    project = inspect_project(path)
    current = make_provider(
        path=r"C:\Python312\python.exe",
        version="3.12.13",
        kind=ProviderKind.CPYTHON,
        discovery_method="fixture",
        healthy=True,
    )
    context = ExecutionContext.capture(project.root, environment={"PATH": current.path})
    return preflight(project, [current], resolve_python([current], context, command_paths=[current.path]))


def mismatch_report(path):
    project = inspect_project(path)
    current = make_provider(
        path=r"C:\Python314\python.exe",
        version="3.14.6",
        kind=ProviderKind.CPYTHON,
        discovery_method="fixture",
        healthy=True,
    )
    compatible = make_provider(
        path=project.root / ".venv" / "Scripts" / "python.exe",
        version="3.12.13",
        kind=ProviderKind.VIRTUAL_ENVIRONMENT,
        discovery_method="fixture",
        healthy=True,
    )
    context = ExecutionContext.capture(project.root, environment={"PATH": current.path})
    providers = [current, compatible]
    return preflight(
        project,
        providers,
        resolve_python(providers, context, command_paths=[current.path]),
    )


def blocked_report(path):
    project = inspect_project(path)
    old = make_provider(
        path=r"C:\Python311\python.exe",
        version="3.11.9",
        kind=ProviderKind.CPYTHON,
        discovery_method="fixture",
        healthy=True,
    )
    current = make_provider(
        path=r"C:\Python314\python.exe",
        version="3.14.6",
        kind=ProviderKind.CPYTHON,
        discovery_method="fixture",
        healthy=True,
    )
    context = ExecutionContext.capture(project.root, environment={"PATH": current.path})
    providers = [old, current]
    return preflight(
        project,
        providers,
        resolve_python(providers, context, command_paths=[current.path]),
    )


def test_legacy_commands_remain_parseable():
    for command in ("quick", "deep", "inspect", "compare", "codex"):
        argv = [command]
        if command in {"inspect", "compare"}:
            argv.append("target")
        assert parser().parse_args(argv).command == command


def test_project_commands_are_additive():
    assert parser().parse_args(["project", "."]).command == "project"
    assert parser().parse_args(["resolve", "."]).command == "resolve"
    assert parser().parse_args(["preflight", "."]).command == "preflight"
    assert parser().parse_args(["codex", "--project", "."]).project == "."


def test_project_command_prints_project_dna(monkeypatch, capsys, tmp_path):
    project = ProjectDNA.create(root=tmp_path, identity="sample")
    monkeypatch.setattr("arx.cli.inspect_project", lambda path: project)

    assert main(["project", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "PROJECT DNA" in output
    assert "sample" in output


def test_preflight_command_prints_textual_semaphore(monkeypatch, capsys, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="sample"\nrequires-python=">=3.12,<3.13"', encoding="utf-8"
    )
    report = fixture_report(tmp_path)
    monkeypatch.setattr("arx.cli.project_preflight", lambda path, **kwargs: report)

    assert main(["preflight", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "PROJECT READINESS: GREEN" in output
    assert "What is wrong?" in output
    assert "Shortest trusted path to GREEN" in output
    assert "dependencies and application execution are not verified" in output
    assert report.severity.severity is Severity.GREEN


def test_preflight_command_reports_compatible_default_mismatch_as_yellow(
    monkeypatch, capsys, tmp_path
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="sample"\nrequires-python=">=3.12,<3.13"', encoding="utf-8"
    )
    (tmp_path / ".python-version").write_text("3.12", encoding="utf-8")
    report = mismatch_report(tmp_path)
    monkeypatch.setattr("arx.cli.project_preflight", lambda path, **kwargs: report)

    assert main(["preflight", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "PROJECT READINESS: YELLOW" in output
    assert "Resolved: 3.14.6" in output
    assert "Compatible: 3.12.13" in output
    assert "Preferred: 3.12.13" in output
    assert "WARNING ARX-PYTHON-DEFAULT-MISMATCH" in output
    assert "BLOCKER ARX-PYTHON-NO-COMPATIBLE-PROVIDER" not in output
    assert "Use the existing Python 3.12.13" in output


def test_preflight_command_reports_true_provider_absence_as_red(
    monkeypatch, capsys, tmp_path
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="sample"\nrequires-python=">=3.12,<3.13"', encoding="utf-8"
    )
    report = blocked_report(tmp_path)
    monkeypatch.setattr("arx.cli.project_preflight", lambda path, **kwargs: report)

    assert main(["preflight", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "PROJECT READINESS: RED" in output
    assert "Compatible: none" in output
    assert "Preferred: none" in output
    assert "BLOCKER ARX-PYTHON-NO-COMPATIBLE-PROVIDER" in output


def test_codex_project_writes_schema_02(monkeypatch, capsys, tmp_path):
    report = fixture_report(tmp_path)
    monkeypatch.setattr("arx.cli.project_preflight", lambda path, **kwargs: report)

    assert main(["codex", "--project", str(tmp_path)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == "0.2"
    assert data["producer"]["version"] == "4.0.0b4"
