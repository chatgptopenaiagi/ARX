# ARX Windows installer and portable packages

ARX 4.0.1 Beta 1 uses an Inno Setup 6/7 installer with a version-specific
application ID, default directory and Start Menu group. Earlier ARX installations
are preserved. Occupied destination folders and an already registered copy of
this version are rejected before files are installed. No in-place upgrade option
is provided; explicitly uninstall this version before reinstalling it.

The installer includes the complete Python/Tk runtime and AI Compute GUI from
the portable package. It does not install Python globally, modify PATH or bundle
personal AI environments. Standard Windows uninstallation removes files installed
by this version, its shortcuts and its registration, preserving user-created files.

Build in a new output directory with these PowerShell commands:

```powershell
.\scripts\build-desktop.ps1 -Version 4.0.1b1 -ReleaseRoot C:\build\arx-patch
.\scripts\package-desktop-release.ps1 -Version 4.0.1b1 -ReleaseRoot C:\build\arx-patch
.\scripts\build-installer.ps1 -Version 4.0.1b1 -ReleaseRoot C:\build\arx-patch -IsccPath C:\tools\Inno\ISCC.exe
```

Outputs include ARX-4.0.1-beta.1-Setup-Windows-x64.exe,
ARX-4.0.1-beta.1-Windows-x64.zip and SHA256SUMS-v4.0.1-beta.1.txt.
The Python package version is 4.0.1b1; the Windows numeric version is 4.0.1.1.
The Python build system generates valid wheel filenames. Historical tags and
the published Beta 7 ZIP/checksum remain unchanged.

The installer is not code-signed. Do not place signing credentials in this
repository. Compilation and checksum verification do not constitute install, upgrade, or uninstall acceptance.
Release acceptance separately installs into a fresh directory, runs GUI and AI
tests, checks shortcuts/registration, and invokes that installation's uninstaller.
It also tests occupied-directory and duplicate-registration rejection while
preserving the existing installed application.

The [Python publishing workflow](../docs/python-package-publishing.md) is separate;
GitHub wheel publication does not publish to PyPI. See the
[patch release notes](../docs/release-notes-4.0.1-beta.1.md) for installation
commands, optional framework requirements and limitations.
