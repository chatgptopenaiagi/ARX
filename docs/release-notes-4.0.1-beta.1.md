# ARX 4.0.1-beta.1 | AI Compute Installer and Wheel

Package version `4.0.1b1`; Windows version `4.0.1.1`; tag `v4.0.1-beta.1`.
This patch prerelease retains the verified Mission 20 / Beta 7 AI Compute code
and changes packaging to preserve existing ARX installations.

## Why a patch prerelease

The Beta 7 tag's installer definition shares Beta 6's application ID and default
installation directory. It could automatically replace the existing application.
The preservation fix therefore requires a new source commit and version. The
original Beta 7 ZIP/checksum assets and tag remain unchanged. A separate Beta 7
wheel is built from that exact original tag.

## Windows installer

Download `ARX-4.0.1-beta.1-Setup-Windows-x64.exe` and verify its SHA-256.
The installer includes the GUI, AI Compute tab, embedded Python/Tk runtime and
license notices. It creates a version-specific Start Menu group and a standard
Windows uninstall entry. An optional desktop shortcut is unchecked by default.

Installation uses a new version-specific folder and application ID. Occupied
destinations and an already registered copy of this version are rejected before
file installation. This prerelease supports side-by-side installation only; it
does not offer in-place upgrades. Uninstall this version explicitly before
reinstalling it. Earlier ARX versions and unrelated user files are preserved.

## Python wheel

The build system generates `arx_prescanner-4.0.1b1-py3-none-any.whl`. Use a new
virtual environment with Python 3.10 or newer:

```powershell
python -m venv arx-env
.\arx-env\Scripts\python.exe -m pip install .\arx_prescanner-4.0.1b1-py3-none-any.whl
.\arx-env\Scripts\arx.exe --help
.\arx-env\Scripts\arx.exe ai-compute --python C:\path\to\python.exe --verify --reports-dir .\ai-reports
```

The wheel exposes the `arx` API, `arx` CLI and `arx-desktop` entry point. Python
3.10 needs the declared `tomli>=2` dependency. The GUI additionally uses tkinter
from the chosen Python installation. PyTorch, CUDA, cuDNN and TensorRT are not
wheel dependencies; AI tests probe separately selected existing environments.

## Verification and limits

Release acceptance covers real installer installation, GUI startup, fresh AI
discovery and cu134 GPU checks, uninstall registration/shortcuts and clean
uninstallation, plus occupied-directory protection. Wheel acceptance uses clean
virtual environments outside the checkout, verifies imports, CLI JSON reports,
pip dependency checks and actual AI Compute operations against the existing target.
Final release notes record the measured test results and checksums.

This is an unsigned Windows x64 prerelease tested on the current Windows 11 host.
No personal Python environment, AI framework, GPU driver, toolkit, credential or
workstation preservation snapshot is included. Discovery is bounded; GPU checks
use device 0. Optional unavailable components remain unavailable, and restoration
of preservation snapshots remains untested. PyPI publication is not performed.
