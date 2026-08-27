# ARX 3 Desktop installer

ARX 3 retains its portable PyInstaller distribution and adds an optional Inno Setup 6 or 7 installer for Windows 10/11 x64.

This installer is distinct from the `arx-prescanner` Python package. Python developers can use `python -m pip install arx-prescanner==3.0.0rc1` to install the `arx` and `arx-desktop` entry points into a managed Python environment. The installer instead deploys the self-contained portable Windows payload and does not require a separately managed Python installation.

Build the validated portable application first, then compile the installer:

```powershell
python -m pip install -e .[build]
.\scripts\build-desktop.ps1
.\scripts\package-desktop-release.ps1 -Version 3.0.0rc1
.\scripts\build-installer.ps1 -Version 3.0.0rc1
```

The release scripts accept PEP 440 package versions `X.Y.Z`, `X.Y.ZrcN`, and `X.Y.ZbN`. Stable versions retain `X.Y.Z` artifact names and use the Windows numeric version `X.Y.Z.0`; RC and Beta package versions become `X.Y.Z-rcN` and `X.Y.Z-bN` in artifact names and use `X.Y.Z.N` for Windows file/product metadata. For example, `4.0.0b4` produces `ARX-Desktop-Setup-win-x64-v4.0.0-b4.exe` with Windows version `4.0.0.4`.

The release-candidate outputs are `ARX-Desktop-win-x64-v3.0.0-rc1.zip`, `ARX-Desktop-Setup-win-x64-v3.0.0-rc1.exe`, and `SHA256SUMS-v3.0.0-rc1.txt`. `build-installer.ps1` locates `ISCC.exe` from `PATH` or standard per-user and Program Files locations for Inno Setup 7 and 6. Use `-IsccPath` for another installation. Output remains under `release/`; generated binaries and checksums are not committed.

The installer has a stable application identifier for in-place upgrades, installs in 64-bit Program Files, displays the repository's actual MIT license, creates Start Menu launch/uninstall entries, offers an unchecked desktop-shortcut task, registers uninstall metadata, and offers to launch ARX when an interactive installation finishes. Silent installs do not launch ARX.

The current installer is not code-signed and uses the executable's ARX 3 version metadata rather than a custom project icon. Production releases should be signed with a publisher-controlled code-signing certificate after the release workflow has a secure signing policy. Do not place signing credentials in this repository or pass them through ordinary build logs. Compilation and checksum verification do not constitute install, upgrade, or uninstall acceptance; those actions remain on the manual Windows checklist.

Python distribution publishing uses the separately documented [Trusted Publishing process](../docs/python-package-publishing.md). Installer compilation does not upload to PyPI, and Python package publication does not establish Windows installer lifecycle acceptance.
