from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from arx import PRODUCT_NAME, RELEASE_NAME, __version__
from arx.cli import envelope

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "4.0.0b2"
ARTIFACT_VERSION = "4.0.0-b2"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_active_product_and_package_versions_are_consistent():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)

    assert metadata["project"]["version"] == PACKAGE_VERSION
    assert metadata["project"]["description"] == "ARX 4 — Project-Aware Compatibility Intelligence"
    assert metadata["project"]["name"] == "arx-prescanner"
    assert metadata["project"]["requires-python"] == ">=3.10"
    assert metadata["project"]["readme"] == "README.md"
    assert metadata["project"]["scripts"] == {
        "arx": "arx.cli:main",
        "arx-desktop": "arx.desktop.__main__:main",
    }
    assert metadata["project"]["optional-dependencies"]["release"] == [
        "build>=1.2,<2",
        "twine>=6,<8",
        "check-wheel-contents>=0.6,<1",
    ]
    assert set(metadata["project"]["urls"]) == {
        "Homepage",
        "Documentation",
        "Source",
        "Issues",
        "Changelog",
    }
    assert __version__ == PACKAGE_VERSION
    assert PRODUCT_NAME == "ARX 4"
    assert RELEASE_NAME == "ARX 4.0.0 Beta 2"
    assert envelope()["scanner"]["version"] == PACKAGE_VERSION


def test_windows_and_release_surfaces_use_the_beta_identity():
    installer = _read("packaging/arx-desktop.iss")
    version_info = _read("packaging/windows-version-info.txt")
    portable_readme = _read("packaging/README.txt")
    readme = _read("README.md")
    changelog = _read("CHANGELOG.md")
    notes = _read("docs/release-notes-4.0.0-b2.md")

    for content in (installer, version_info, portable_readme, readme, changelog, notes):
        assert PACKAGE_VERSION in content
    for content in (installer, readme, notes):
        assert ARTIFACT_VERSION in content
    assert "filevers=(4, 0, 0, 2)" in version_info
    assert "StringStruct('FileVersion', '4.0.0.2')" in version_info
    assert "ARX 4.0.0 Beta 2" in portable_readme


def test_application_and_contract_versions_remain_independent():
    assert envelope()["schema_version"] == "0.1"
    assert '"const": "0.2"' in _read("schemas/ai-contract.schema.json")
    assert _read("docs/release-notes-2.0.0.md").startswith("# ARX 2.0.0")


def test_readme_documents_every_supported_release_installation_path():
    readme = _read("README.md")

    for command_or_asset in (
        "python -m pip install arx-prescanner==4.0.0b2",
        "python -m pip install --pre arx-prescanner",
        "python -m pip install arx-prescanner",
        'python -m pip install "git+https://github.com/chatgptopenaiagi/ARX.git@v4.0.0-b2"',
        "arx --help",
        "arx quick",
        "arx-desktop",
        "ARX-Desktop-Setup-win-x64-v4.0.0-b2.exe",
        "ARX-Desktop-win-x64-v4.0.0-b2.zip",
        "SHA256SUMS.txt",
    ):
        assert command_or_asset in readme
    assert "ARX `4.0.0b2` is a pre-release" in readme
