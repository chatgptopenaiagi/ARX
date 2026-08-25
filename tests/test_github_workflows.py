import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA_ACTION = re.compile(r"^\s*uses:\s+[^\s@]+@[0-9a-f]{40}(?:\s+#.*)?$", re.MULTILINE)
ANY_ACTION = re.compile(r"^\s*uses:\s+(.+)$", re.MULTILINE)
SECRET_CONTEXT = re.compile(r"\$\{\{\s*secrets\.", re.IGNORECASE)


def _read(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_ci_uses_least_privilege_pinned_actions_and_safe_triggers():
    workflow = _read("ci.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert SECRET_CONTEXT.search(workflow) is None
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
    assert "python scripts/scan-tracked-secrets.py" in workflow
    assert 'python -m pip install "build>=1.2,<2" "twine>=6,<8" "check-wheel-contents>=0.6,<1"' in workflow
    assert "dist/*.whl" in workflow
    assert "GITHUB_WORKSPACE" in workflow
    assert "is_relative_to" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "id-token: write" not in workflow
    assert "twine upload" not in workflow.casefold()
    assert SECRET_CONTEXT.search(workflow) is None


def test_python_publish_workflow_is_manual_targeted_pinned_and_oidc_only():
    workflow = _read("publish-pypi.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "workflow_dispatch:" in workflow
    assert "release:\n" not in workflow
    assert "push:" not in workflow
    assert "pull_request" not in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "type: choice" in workflow
    assert "- testpypi" in workflow
    assert "- production" in workflow
    assert "ref: ${{ env.RELEASE_TAG }}" in workflow
    assert "git rev-list -n 1" in workflow
    assert "releases/tags/$RELEASE_TAG" in workflow
    assert "tomllib.load" in workflow and "arx-prescanner" in workflow
    assert "id-token: write" in workflow
    assert workflow.count("id-token: write") == 2
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "if: inputs.target == 'testpypi'" in workflow
    assert "if: inputs.target == 'production'" in workflow
    assert SECRET_CONTEXT.search(workflow) is None
    assert "password:" not in workflow
    assert "TWINE_PASSWORD" not in workflow
    assert "skip-existing" not in workflow
    assert "contents: write" not in workflow
    assert "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33" in workflow
    assert workflow.count("pypa/gh-action-pypi-publish@") == 2
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 16


def test_python_publish_workflow_consumes_reviewed_assets_and_verifies_both_indexes():
    workflow = _read("publish-pypi.yml")

    assert "python -m build" not in workflow
    assert "gh release download" in workflow
    assert "verify-release-assets.py" in workflow
    assert "python -m twine check --strict release-assets/*.whl release-assets/*.tar.gz" in workflow
    assert "python -m check_wheel_contents release-assets/*.whl" in workflow
    assert "name: reviewed-python-distributions-" in workflow
    assert workflow.count("name: reviewed-python-distributions-") == 6
    assert "needs: [prepare, publish-testpypi]" in workflow
    assert "needs: [prepare, verify-existing-testpypi]" in workflow
    assert workflow.count("verify-python-index.py --index testpypi") == 2
    assert "verify-python-index.py --index pypi" in workflow
    assert "--index-url https://test.pypi.org/simple/" in workflow
    assert '"arx-prescanner==$PACKAGE_VERSION"' in workflow
    assert 'import arx; print(arx.__version__)' in workflow
    assert '"$VENV/bin/arx" --help' in workflow
    assert '"$VENV/bin/arx" quick' in workflow
    assert 'test -x "$VENV/bin/arx-desktop"' in workflow


def test_github_release_asset_workflow_is_manual_draft_only_and_cannot_publish():
    workflow = _read("release-assets.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "workflow_dispatch:" in workflow
    assert "attach_assets:" in workflow
    assert "if: inputs.attach_assets" in workflow
    assert "release:\n" not in workflow
    assert "push:" not in workflow
    assert "pull_request" not in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "persist-credentials: false" in workflow
    assert "draft" in workflow and "prerelease" in workflow
    assert "releases?per_page=100" in workflow
    assert "releases/$release_id" in workflow
    assert "build-release.ps1" in workflow
    assert "-AllowMissingInstaller" not in workflow
    assert "python=3.12.13" in workflow
    assert "Release Python identity mismatch" in workflow
    assert "Library\\bin" in workflow
    assert all(runtime in workflow for runtime in ("ffi.dll", "tcl86t.dll", "tk86t.dll"))
    assert "packaging/release-build-requirements.txt" in workflow
    assert "write-build-environment.py" in workflow
    assert "release-build-environment-${{ github.run_id }}" in workflow
    assert '"FILE_VERSION=$($Matches[\'base\']).$($Matches[\'number\'])"' in workflow
    assert "$Executable.VersionInfo.FileVersion.Trim() -ne $env:FILE_VERSION" in workflow
    assert "$InstallerItem.VersionInfo.FileVersion.Trim() -ne $env:FILE_VERSION" in workflow
    assert "scan-tracked-secrets.py" in workflow
    assert "Get-AuthenticodeSignature" in workflow
    assert "--smoke-test" in workflow and "--ui-smoke-test" in workflow
    assert "Portable desktop runtime is incomplete" in workflow
    assert "gh release upload" in workflow
    assert workflow.count("contents: write") == 1
    assert workflow.count("id-token: write") == 2
    assert workflow.count("attestations: write") == 2
    assert "actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8" in workflow
    assert "subject-path: ${{ runner.temp }}/release-assets/*" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "twine upload" not in workflow.casefold()
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 5


def test_beta2_release_trigger_separates_attachment_from_reproduction():
    workflow = _read("beta2-release-assets-trigger.yml")

    assert "release-v4.0.0-b2-assets" in workflow
    assert "release-v4.0.0-b2-repro-*" in workflow
    assert "attach_assets: ${{ github.ref_name == 'release-v4.0.0-b2-assets' }}" in workflow


def test_beta3_provenance_trigger_can_read_drafts_but_cannot_mutate_releases():
    workflow = _read("beta3-provenance-trigger.yml")

    assert "release-v4.0.0-b3-provenance-*" in workflow
    assert "uses: ./.github/workflows/release-provenance.yml" in workflow
    assert workflow.count("contents: write") == 2
    assert workflow.count("id-token: write") == 2
    assert workflow.count("attestations: write") == 2
    assert "gh release upload" not in workflow
    assert "gh release edit" not in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "signtool sign" not in workflow.casefold()
    assert SECRET_CONTEXT.search(workflow) is None


def test_trusted_preflight_attests_but_never_signs_or_publishes():
    workflow = _read("trusted-installation-preflight.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "workflow_dispatch:" in workflow
    assert "pull_request_target" not in workflow
    assert "persist-credentials: false" in workflow
    assert "python=3.12.13" in workflow
    assert "Release Python identity mismatch" in workflow
    assert "Library\\bin" in workflow
    assert all(runtime in workflow for runtime in ("ffi.dll", "tcl86t.dll", "tk86t.dll"))
    assert "packaging/release-build-requirements.txt" in workflow
    assert "write-build-environment.py" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8" in workflow
    assert "unsigned preflight" in workflow.casefold()
    assert "--smoke-test" in workflow and "--ui-smoke-test" in workflow
    assert "Unsigned portable runtime is incomplete" in workflow
    assert "does not:" in workflow.casefold()
    assert "sign ARX.exe" in workflow
    assert "publish GitHub release assets" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "gh release upload" not in workflow
    assert "signtool sign" not in workflow.casefold()
    assert "contents: write" not in workflow
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 3


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
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 3


def test_security_gate_is_safe_automatic_nonpublishing_and_pinned():
    workflow = _read("security-gate.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request_target" not in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "pip-audit==2.10.1" in workflow
    assert "--vulnerability-service pypi" in workflow
    assert "--vulnerability-service osv" in workflow
    assert "bandit==1.9.4" in workflow
    assert "semgrep==1.174.0" in workflow
    assert "semgrep-classification.json" in workflow
    assert "security/phase-c/evidence/semgrep-classification.json" in workflow
    assert "unreviewed_errors" in workflow
    assert "stale_reviews" in workflow
    assert 'item.get("level") == "error"' in workflow
    assert "cyclonedx-bom==7.3.1" in workflow
    assert "detect-secrets==1.5.0" in workflow
    assert "hypothesis==6.165.10" in workflow
    assert "tests/test_advisory_intelligence.py" in workflow
    assert "detect-secrets-classification.json" in workflow
    assert "security/phase-c/evidence/detect-secrets-classification.json" in workflow
    assert "detect-secrets-summary.json" in workflow
    assert "stale_reviews" in workflow
    assert "scan-tracked-secrets.py" in workflow
    assert "output-reproducible" in workflow
    assert "security-results/*" in workflow
    assert "id-token: write" not in workflow
    assert "contents: write" not in workflow
    assert "signtool sign" not in workflow.casefold()
    assert "gh release upload" not in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "twine upload" not in workflow.casefold()
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 3


def test_trusted_signing_workflow_is_manual_protected_and_incapable_of_signing():
    workflow = _read("trusted-signing.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request" not in workflow
    assert "pull_request_target" not in workflow
    assert "environment: windows-production-signing" in workflow
    assert "persist-credentials: false" in workflow
    assert "contents: read" in workflow
    assert "contents: write" not in workflow
    assert "id-token: write" not in workflow
    assert "attestations: write" not in workflow
    assert "BLOCKED_NO_PRODUCTION_CERTIFICATE" in workflow
    assert "throw 'Production Authenticode signing is intentionally blocked.'" in workflow
    assert "signtool sign" not in workflow.casefold()
    assert "set-authenticodesignature" not in workflow.casefold()
    assert "import-pfxcertificate" not in workflow.casefold()
    assert "gh release upload" not in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 2


def test_release_provenance_workflow_reproduces_without_modifying_release():
    workflow = _read("release-provenance.yml")
    actions = ANY_ACTION.findall(workflow)

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request" not in workflow
    assert "persist-credentials: false" in workflow
    assert "python=3.12.13" in workflow
    assert "Release Python identity mismatch" in workflow
    assert "Library\\bin" in workflow
    assert all(runtime in workflow for runtime in ("ffi.dll", "tcl86t.dll", "tk86t.dll"))
    assert "packaging/release-build-requirements.txt" in workflow
    assert "releases?per_page=100" in workflow
    assert "releases/tags/$env:RELEASE_TAG" not in workflow
    assert "exactly one matching draft or public prerelease" in workflow
    assert "$ReleaseMatches = @(" in workflow
    assert "$Matches = @(" not in workflow
    assert "--require-security-bundle" in workflow
    assert "Core artifact is not bit-for-bit reproducible" in workflow
    assert "--smoke-test" in workflow and "--ui-smoke-test" in workflow
    assert "Reproduced portable runtime is incomplete" in workflow
    assert "-m cyclonedx_py" in workflow
    assert "--without-pip" in workflow
    assert "--output-reproducible" in workflow
    assert "Published CycloneDX SBOM is not bit-for-bit reproducible" in workflow
    assert "Published checksum manifest is not exactly reproducible" in workflow
    assert "Stage complete validated release subjects" in workflow
    assert 'Get-ChildItem -LiteralPath "$env:RUNNER_TEMP\\published" -File' in workflow
    assert "Attestation subjects do not exactly match" in workflow
    assert "actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8" in workflow
    assert workflow.count("id-token: write") == 2
    assert workflow.count("attestations: write") == 2
    assert workflow.count("contents: write") == 2
    assert "required solely to read and download the human-gated draft subjects" in workflow
    assert "gh release upload" not in workflow
    assert "gh release edit" not in workflow
    assert "signtool sign" not in workflow.casefold()
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert SECRET_CONTEXT.search(workflow) is None
    assert len(FULL_SHA_ACTION.findall(workflow)) == len(actions) == 3
