# ARX Desktop installer

ARX retains its portable PyInstaller distribution and adds an optional Inno Setup 6 or 7 installer for Windows 10/11 x64.

Build the validated portable application first, then compile the installer:

```powershell
python -m pip install -e .[build]
.\scripts\build-desktop.ps1
.\scripts\build-installer.ps1 -Version 2.0.0
```

`build-installer.ps1` locates `ISCC.exe` from `PATH` or standard per-user and Program Files locations for Inno Setup 7 and 6. Use `-IsccPath` for another installation. Output remains under `release/`, alongside an updated SHA-256 checksum file.

The installer has a stable application identifier for in-place upgrades, installs in 64-bit Program Files, displays the repository's actual MIT license, creates Start Menu launch/uninstall entries, offers an unchecked desktop-shortcut task, registers uninstall metadata, and offers to launch ARX when an interactive installation finishes. Silent installs do not launch ARX.

The current installer is not code-signed and uses the executable's existing application metadata rather than a custom project icon. Production releases should be signed with a publisher-controlled code-signing certificate after the release workflow has a secure signing policy. Do not place signing credentials in this repository or pass them through ordinary build logs.
