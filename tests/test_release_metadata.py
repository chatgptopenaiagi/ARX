from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from arx import PRODUCT_NAME, RELEASE_NAME, __version__
from arx.cli import envelope


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "3.0.0rc1"
ARTIFACT_VERSION = "3.0.0-rc1"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_active_product_and_package_versions_are_consistent():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)

    assert metadata["project"]["version"] == PACKAGE_VERSION
    assert metadata["project"]["description"] == "ARX 3 — Project-Aware Compatibility Intelligence"
    assert __version__ == PACKAGE_VERSION
    assert PRODUCT_NAME == "ARX 3"
    assert RELEASE_NAME == "ARX 3.0 Release Candidate"
    assert envelope()["scanner"]["version"] == PACKAGE_VERSION


def test_windows_and_release_surfaces_use_the_rc_identity():
    installer = _read("packaging/arx-desktop.iss")
    version_info = _read("packaging/windows-version-info.txt")
    portable_readme = _read("packaging/README.txt")
    readme = _read("README.md")
    changelog = _read("CHANGELOG.md")
    notes = _read("docs/release-notes-3.0.0-rc1.md")

    for content in (installer, version_info, portable_readme, readme, changelog, notes):
        assert PACKAGE_VERSION in content
    for content in (installer, readme, notes):
        assert ARTIFACT_VERSION in content
    assert "filevers=(3, 0, 0, 1)" in version_info
    assert "ARX 3.0 Release Candidate" in portable_readme


def test_application_and_contract_versions_remain_independent():
    assert envelope()["schema_version"] == "0.1"
    assert '"const": "0.2"' in _read("schemas/ai-contract.schema.json")
    assert _read("docs/release-notes-2.0.0.md").startswith("# ARX 2.0.0")
