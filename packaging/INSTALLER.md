# ARX 4 Desktop installer

ARX 4.0.0 Beta 2 retains the complete portable PyInstaller distribution and its optional Inno Setup 6 or 7 installer for Windows 10/11 x64.

This installer is distinct from the existing `arx-prescanner` Python package. Python developers can use `python -m pip install arx-prescanner==4.0.0b2` after a separately authorized index publication to install the `arx` and `arx-desktop` entry points into a managed Python environment. The installer instead deploys the self-contained portable Windows payload and does not require a separately managed Python installation.

Build the validated portable application first, then compile the installer:

```powershell
python -m pip install -e ".[dev,build,release]"
.\scripts\build-release.ps1 -Version 4.0.0b2
```

The release outputs are `arx_prescanner-4.0.0b2-py3-none-any.whl`, `arx_prescanner-4.0.0b2.tar.gz`, `ARX-Desktop-win-x64-v4.0.0-b2.zip`, `ARX-Desktop-Setup-win-x64-v4.0.0-b2.exe`, and `SHA256SUMS.txt`. They are isolated under `release/v4.0.0-b2/`; historical release directories are not overwritten. `build-installer.ps1` locates `ISCC.exe` from `PATH` or standard per-user and Program Files locations for Inno Setup 7 and 6. Use `-IsccPath` for another installation. Generated binaries and checksums are not committed.

The installer has a stable application identifier for in-place upgrades, installs in 64-bit Program Files, displays the repository's actual MIT license, creates Start Menu launch/uninstall entries, offers an unchecked desktop-shortcut task, registers uninstall metadata, and offers to launch ARX when an interactive installation finishes. Silent installs do not launch ARX.

The ARX 4.0.0 Beta 2 installer and portable executable are not code-signed because no approved production signing identity is configured. They use ARX 4 version metadata rather than a custom signed project icon. Compilation, checksums, and build attestations do not constitute install, upgrade, or uninstall acceptance. They also do not constitute Authenticode acceptance; those actions remain independent Windows gates.

## Code-signing release gate

Code signing is an explicit release item, not an implied property of a successful build. A production release requires all of the following:

- an approved publisher identity and currently valid code-signing certificate;
- a protected private-key and timestamping policy outside the repository and ordinary build logs;
- signing of both the portable application executable and the installer at the controlled release boundary;
- independent Authenticode verification of the exact files named in the checksum manifest.

Do not place signing credentials in this repository or pass them through ordinary build logs.

If an approved certificate or signing service is unavailable, the signing item is `BLOCKED`. `Get-FileHash`, Inno Setup verification, and an unsigned executable cannot be reported as a valid signature. The inherited Phase A workstation result is recorded in [ARX 3 final acceptance](../docs/arx-3-final-acceptance.md); this beta does not silently close those historical manual acceptance blockers.

Python distribution publishing uses the separately documented, manual-only [Trusted Publishing process](../docs/python-package-publishing.md). Installer compilation and GitHub Release publication do not upload to either TestPyPI or production PyPI, and Python package publication does not establish Windows installer lifecycle acceptance.

## Per-user OpenAI provider data on uninstall

The optional OpenAI API provider stores its current-user DPAPI blob and bounded metadata-only transmission audit under `%LOCALAPPDATA%\ARX`, outside the machine-wide Program Files installation. The uninstaller deliberately does not enumerate Windows profiles or silently delete this per-user data.

Before uninstalling, a user who wants complete provider-data cleanup should open `Settings → Intelligence Providers → OpenAI API`, choose `Remove Credential`, and choose `Clear History`. After uninstall, the same user may deliberately remove any remaining `%LOCALAPPDATA%\ARX` provider-data directory. The installer never removes a temporary plaintext key file selected for import; that source remains under the user's control and should be deleted intentionally after protected import and a successful connection test.
