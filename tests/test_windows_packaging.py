import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "packaging" / "arx-desktop.iss").read_text(encoding="utf-8")
BUILD_SCRIPT = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")
PACKAGE_SCRIPT = (ROOT / "scripts" / "package-desktop-release.ps1").read_text(encoding="utf-8")
DESKTOP_SCRIPT = (ROOT / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")
RELEASE_SCRIPT = (ROOT / "scripts" / "build-release.ps1").read_text(encoding="utf-8")
CHECKSUM_SCRIPT = (ROOT / "scripts" / "write-release-checksums.ps1").read_text(encoding="utf-8")
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
    assert 'Name: "{group}\\ARX 4"' in INSTALLER
    assert 'Name: "{group}\\Uninstall ARX"' in INSTALLER
    assert 'Name: "desktopicon"' in INSTALLER and "Flags: unchecked" in INSTALLER
    assert "UninstallDisplayIcon={app}\\{#MyAppExeName}" in INSTALLER
    assert 'Description: "Launch ARX 4"; Flags: nowait postinstall skipifsilent' in INSTALLER


def test_beta_version_and_artifact_identity_are_consistent():
    assert '#define MyAppVersion "4.0.0b2"' in INSTALLER
    assert '#define MyAppFileVersion "4.0.0.2"' in INSTALLER
    assert '#define MyArtifactVersion "4.0.0-b2"' in INSTALLER
    assert '#define MyAppDisplayName "ARX 4.0.0 Beta 2"' in INSTALLER
    assert "VersionInfoVersion={#MyAppFileVersion}" in INSTALLER
    assert "VersionInfoProductVersion={#MyAppFileVersion}" in INSTALLER
    assert "OutputBaseFilename=ARX-Desktop-Setup-win-x64-v{#MyArtifactVersion}" in INSTALLER
    assert "[string]$Version = '4.0.0b2'" in BUILD_SCRIPT
    assert "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe" in BUILD_SCRIPT
    assert "[string]$Version = '4.0.0b2'" in PACKAGE_SCRIPT
    assert "ARX-Desktop-win-x64-v$ArtifactVersion.zip" in PACKAGE_SCRIPT
    assert "StringStruct('ProductName', 'ARX 4')" in VERSION_INFO
    assert "StringStruct('ProductVersion', '4.0.0b2')" in VERSION_INFO
    assert "StringStruct('FileVersion', '4.0.0.2')" in VERSION_INFO
    assert "filevers=(4, 0, 0, 2)" in VERSION_INFO


def test_installer_build_is_bounded_to_release_and_requires_validated_portable_payload():
    assert "ARX-Desktop-win-x64" in BUILD_SCRIPT
    assert "Refusing to create an installer outside the versioned release directory" in BUILD_SCRIPT
    assert "Missing portable desktop build" in BUILD_SCRIPT
    assert "_internal" in BUILD_SCRIPT
    assert "write-release-checksums.ps1" in BUILD_SCRIPT
    assert "Inno Setup 7" in BUILD_SCRIPT and "Inno Setup 6" in BUILD_SCRIPT
    assert "LOCALAPPDATA" in BUILD_SCRIPT
    assert "Invoke-Expression" not in BUILD_SCRIPT
    assert not re.search(r"powershell(?:\.exe)?\s+.*-Command", BUILD_SCRIPT, re.IGNORECASE)


def test_release_build_is_version_scoped_and_hashes_every_public_artifact():
    for script in (DESKTOP_SCRIPT, PACKAGE_SCRIPT, BUILD_SCRIPT, RELEASE_SCRIPT, CHECKSUM_SCRIPT):
        assert "version-specific directory" in script
        assert "Invoke-Expression" not in script
    assert "release\\v$ArtifactVersion" not in RELEASE_SCRIPT
    assert '"v$ArtifactVersion"' in RELEASE_SCRIPT
    assert "python -m build" not in RELEASE_SCRIPT  # invoked through the selected Python path
    assert "-m build --outdir" in RELEASE_SCRIPT
    assert "verify-release-assets.py" in RELEASE_SCRIPT
    assert "SHA256SUMS.txt" in CHECKSUM_SCRIPT
    for filename in (
        "arx_prescanner-$Version-py3-none-any.whl",
        "arx_prescanner-$Version.tar.gz",
        "ARX-Desktop-win-x64-v$ArtifactVersion.zip",
        "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe",
    ):
        assert filename in CHECKSUM_SCRIPT


def test_installer_documentation_discloses_signing_limit_and_portable_option():
    documentation = (ROOT / "packaging" / "INSTALLER.md").read_text(encoding="utf-8")

    assert "portable" in documentation.casefold()
    assert "not code-signed" in documentation
    assert "Do not place signing credentials" in documentation
    assert "Code-signing release gate" in documentation
    assert "the signing item is `BLOCKED`" in documentation
    assert "cannot be reported as a valid signature" in documentation
    assert "do not constitute install, upgrade, or uninstall acceptance" in documentation
