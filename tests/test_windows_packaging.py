import json
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "packaging" / "arx-desktop.iss").read_text(encoding="utf-8")
BUILD_SCRIPT = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")
PACKAGE_SCRIPT = (ROOT / "scripts" / "package-desktop-release.ps1").read_text(encoding="utf-8")
VERSIONING_SCRIPT = ROOT / "scripts" / "versioning.ps1"
VERSION_INFO = (ROOT / "packaging" / "windows-version-info.txt").read_text(encoding="utf-8")


def test_installer_has_stable_upgrade_and_x64_identity():
    app_id = re.search(r"^AppId=(.+)$", INSTALLER, re.MULTILINE)

    assert app_id
    assert app_id.group(1) == "{{1BC9E705-070A-42B4-9378-45E2DD7C416A}"
    assert "ArchitecturesAllowed=x64compatible" in INSTALLER
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in INSTALLER
    assert "DefaultDirName={autopf}\\ARX" in INSTALLER


def test_installer_uses_real_license_and_complete_windows_entries():
    assert "LicenseFile=..\\LICENSE" in INSTALLER
    assert 'Name: "{group}\\ARX"' in INSTALLER
    assert 'Name: "{group}\\Uninstall ARX"' in INSTALLER
    assert 'Name: "desktopicon"' in INSTALLER and "Flags: unchecked" in INSTALLER
    assert "UninstallDisplayIcon={app}\\{#MyAppExeName}" in INSTALLER
    assert 'Description: "Launch ARX"; Flags: nowait postinstall skipifsilent' in INSTALLER


def test_rc_version_and_artifact_identity_are_consistent():
    assert '#define MyAppVersion "3.0.0rc1"' in INSTALLER
    assert '#define MyAppFileVersion "3.0.0.1"' in INSTALLER
    assert '#define MyArtifactVersion "3.0.0-rc1"' in INSTALLER
    assert '#define MyAppDisplayName "ARX 3.0 Release Candidate 1"' in INSTALLER
    assert "VersionInfoVersion={#MyAppFileVersion}" in INSTALLER
    assert "VersionInfoProductVersion={#MyAppFileVersion}" in INSTALLER
    assert "OutputBaseFilename=ARX-Desktop-Setup-win-x64-v{#MyArtifactVersion}" in INSTALLER
    assert "[string]$Version = '3.0.0rc1'" in BUILD_SCRIPT
    assert "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe" in BUILD_SCRIPT
    assert "[string]$Version = '3.0.0rc1'" in PACKAGE_SCRIPT
    assert "ARX-Desktop-win-x64-v$ArtifactVersion.zip" in PACKAGE_SCRIPT
    assert "StringStruct('ProductName', 'ARX 3')" in VERSION_INFO
    assert "StringStruct('ProductVersion', '3.0.0rc1')" in VERSION_INFO
    assert "filevers=(3, 0, 0, 1)" in VERSION_INFO


@pytest.mark.parametrize(
    ("package_version", "artifact_version", "file_version"),
    [
        ("4.0.0", "4.0.0", "4.0.0.0"),
        ("3.0.0rc1", "3.0.0-rc1", "3.0.0.1"),
        ("4.0.0b1", "4.0.0-b1", "4.0.0.1"),
        ("4.0.0b4", "4.0.0-b4", "4.0.0.4"),
    ],
)
def test_release_version_normalization(package_version, artifact_version, file_version):
    command = (
        f". '{VERSIONING_SCRIPT}'; "
        f"ConvertTo-ArxReleaseVersion -Version '{package_version}' | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )
    normalized = json.loads(completed.stdout)
    assert normalized["PackageVersion"] == package_version
    assert normalized["ArtifactVersion"] == artifact_version
    assert normalized["FileVersion"] == file_version


@pytest.mark.parametrize(
    "malformed",
    ["4", "4.0", "4.0.0beta4", "4.0.0b", "4.0.0rc0", "04.0.0", "4.0.0-b4", "4.0.0.dev1"],
)
def test_release_version_normalization_rejects_malformed_versions(malformed):
    command = f". '{VERSIONING_SCRIPT}'; ConvertTo-ArxReleaseVersion -Version '{malformed}'"
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "X.Y.Z, X.Y.ZrcN, or X.Y.ZbN" in completed.stderr


def test_installer_build_is_bounded_to_release_and_requires_validated_portable_payload():
    assert "ARX-Desktop-win-x64" in BUILD_SCRIPT
    assert "Refusing to create an installer outside the release directory" in BUILD_SCRIPT
    assert "Missing portable desktop build" in BUILD_SCRIPT
    assert "_internal" in BUILD_SCRIPT
    assert "Get-FileHash" in BUILD_SCRIPT and "SHA256SUMS" in BUILD_SCRIPT
    assert "Inno Setup 7" in BUILD_SCRIPT and "Inno Setup 6" in BUILD_SCRIPT
    assert "LOCALAPPDATA" in BUILD_SCRIPT
    assert "Invoke-Expression" not in BUILD_SCRIPT
    assert not re.search(r"powershell(?:\.exe)?\s+.*-Command", BUILD_SCRIPT, re.IGNORECASE)


def test_installer_documentation_discloses_signing_limit_and_portable_option():
    documentation = (ROOT / "packaging" / "INSTALLER.md").read_text(encoding="utf-8")

    assert "portable" in documentation.casefold()
    assert "not code-signed" in documentation
    assert "Do not place signing credentials" in documentation
    assert "do not constitute install, upgrade, or uninstall acceptance" in documentation
