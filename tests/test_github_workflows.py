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
    assert "python scripts/run-isolated-gui-tests.py" in workflow
    assert workflow.count("--ignore=tests/test_desktop") == 4
    assert "xvfb-run -a python -m pytest" in workflow
    assert "python -m compileall -q src tests" in workflow


def test_package_validation_builds_but_normal_ci_never_publishes():
    workflow = _read("ci.yml")

    assert "python -m build" in workflow
    assert "python -m twine check --strict dist/*" in workflow
    assert "python -m check_wheel_contents dist/*.whl" in workflow
    assert 'python -m pip install "build>=1.2,<2" "twine>=6,<8" "check-wheel-contents>=0.6,<1"' in workflow
    assert "dist/*.whl" in workflow
    assert "GITHUB_WORKSPACE" in workflow
    assert "is_relative_to" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "id-token: write" not in workflow
    assert "twine upload" not in workflow.casefold()
    assert "secrets." not in workflow


def test_python_publish_workflow_is_release_controlled_pinned_and_oidc_only():
    workflow = _read("publish-pypi.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "types: [published]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request" not in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "ref: ${{ env.RELEASE_TAG }}" in workflow
    assert "git rev-list -n 1" in workflow
    assert "releases/tags/$RELEASE_TAG" in workflow
    assert "project[\"name\"] != \"arx-prescanner\"" in workflow
    assert "id-token: write" in workflow
    assert workflow.count("id-token: write") == 2
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "secrets." not in workflow
    assert "password:" not in workflow
    assert "TWINE_PASSWORD" not in workflow
    assert "skip-existing" not in workflow
    assert "contents: write" not in workflow
    assert "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33" in workflow
    assert workflow.count("pypa/gh-action-pypi-publish@") == 2
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 9


def test_python_publish_workflow_builds_once_and_verifies_both_indexes():
    workflow = _read("publish-pypi.yml")

    assert workflow.count("python -m build") == 1
    assert "python -m twine check --strict dist/*" in workflow
    assert "python -m check_wheel_contents dist/*.whl" in workflow
    assert "name: python-package-distributions" in workflow
    assert workflow.count("name: python-package-distributions") == 3
    assert "needs: [build, publish-testpypi]" in workflow
    assert "needs: [build, verify-testpypi]" in workflow
    assert "--index-url https://test.pypi.org/simple/" in workflow
    assert '"arx-prescanner==$PACKAGE_VERSION"' in workflow
    assert workflow.count('import arx; print(arx.__version__)') == 2
    assert workflow.count('"$VENV/bin/arx" --help') == 2
    assert workflow.count('"$VENV/bin/arx" quick') == 2
    assert workflow.count('test -x "$VENV/bin/arx-desktop"') == 2


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
