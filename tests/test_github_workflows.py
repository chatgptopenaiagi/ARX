import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA_ACTION = re.compile(r"^\s*uses:\s+[^\s@]+@[0-9a-f]{40}(?:\s+#.*)?$", re.MULTILINE)
ANY_ACTION = re.compile(r"^\s*uses:\s+(.+)$", re.MULTILINE)


def _read(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_ci_uses_least_privilege_pinned_actions_and_safe_triggers():
    workflow = _read("ci.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "secrets." not in workflow
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 4


def test_ci_covers_supported_windows_and_linux_python_matrix():
    workflow = _read("ci.yml")

    assert "windows-latest" in workflow
    assert "ubuntu-latest" in workflow
    assert 'python-version: ["3.10", "3.12", "3.14"]' in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "python -m pytest" in workflow
    assert "xvfb-run -a python -m pytest" in workflow
    assert "python -m compileall -q src tests" in workflow


def test_package_validation_builds_but_never_publishes():
    workflow = _read("ci.yml")
    all_workflows = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml"))

    assert "python -m build" in workflow
    assert "dist/*.whl" in workflow
    assert "pypi" not in all_workflows.casefold()
    assert "twine upload" not in all_workflows.casefold()
    assert "anaconda" not in all_workflows.casefold()
    assert "azure" not in all_workflows.casefold()
    assert "django" not in all_workflows.casefold()


def test_codeql_analyzes_python_and_workflows_with_current_pinned_action():
    workflow = _read("codeql.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "language: python" in workflow
    assert "language: actions" in workflow
    assert "security-events: write" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "github/codeql-action/init@99df26d4f13ea111d4ec1a7dddef6063f76b97e9" in workflow
    assert "github/codeql-action/analyze@99df26d4f13ea111d4ec1a7dddef6063f76b97e9" in workflow
    assert "pull_request_target" not in workflow
    assert "secrets." not in workflow
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 3
