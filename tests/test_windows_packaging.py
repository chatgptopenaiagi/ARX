import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "packaging" / "arx-desktop.iss").read_text(encoding="utf-8")
BUILD_SCRIPT = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")


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
