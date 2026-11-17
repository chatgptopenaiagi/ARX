ARX 4
ARX 4.0.1 Beta 1 | AI Compute Edition
Package version 4.0.1b1

PURPOSE
ARX is a read-only project-aware compatibility and resolution engine. It scans
this PC, statically inspects software and Python projects, resolves providers,
compares requirements, and explains a GREEN/YELLOW/RED decision and advisory
path to GREEN. ARX is not a malware scanner and does not certify software as safe.

SUPPORTED OPERATING SYSTEM
Windows x64. This prerelease is validated on Windows 11 x64. This release has
not been independently validated on Windows 10, Windows Server or ARM64.

START
Extract the complete folder, then double-click ARX.exe. Keep the _internal
folder beside ARX.exe; it contains the standalone Python/Tk runtime.

PORTABLE DISTRIBUTION
The portable package is ARX-4.0.1-beta.1-Windows-x64.zip. A separate
ARX-4.0.1-beta.1-Setup-Windows-x64.exe installs the same payload with its own
Start Menu group and Windows uninstall entry. It uses a new empty directory
and preserves earlier ARX installations. In-place upgrades are not offered;
uninstall this version explicitly before reinstalling it. The executable is
unsigned; verify the published SHA-256 checksum before running it.

AI COMPUTE
Open AI Compute, choose Discover environments, select an interpreter, then use
Verify selected or Benchmark selected. Results come from your local environment;
no successful result is preloaded. GPU verification needs an existing compatible
Python/PyTorch environment and GPU driver. These frameworks are not bundled.
Preserve selected copies package files and matching cached wheels to a unique
snapshot in the chosen destination and verifies their hashes. It does not move
or remove source files. Package copies are not independently portable; follow
the snapshot restoration instructions. Actual restoration was not tested.

READ-ONLY MODEL
Normal scanning does not install software, change PATH, edit the registry, or
execute the selected target. Only fixed, timeout-bound trusted diagnostic
commands are used to identify developer tools.

PROJECT PREFLIGHT
Select a Python project directory to inspect supported manifests without
executing project scripts. ARX distinguishes the currently resolved Python,
healthy compatible existing providers, project-pinned runtime intent, and the
policy-preferred provider. GREEN is limited to evaluated Python interpreter and
toolchain requirements. It does not verify installed dependencies, lockfile and
site-packages synchronization, project imports, or complete application startup.

SUPPORTED INSPECTION TARGETS
EXE, DLL, MSI identification, ZIP, JAR, APK, scripts, and application
directories. Static analysis includes hashes, PE metadata, Authenticode,
archive entries, recognized manifests, runtime indicators, and requirements
where available.

KNOWN LIMITATIONS
MSI action/table parsing, APK binary-manifest decoding, complete PE import-table
resolution, pip-to-interpreter mismatch detection, non-Python project ecosystems,
and some Python constraint forms are incomplete. Compatibility results express
available evidence and uncertainty; they are not malware verdicts or guarantees
that an installer will succeed.

PRIVACY
Core reports redact the current user-profile path and allowlist environment data.
AI Compute evidence retains local installation paths needed for restoration.
ARX does not collect passwords, tokens, cookies, private keys, Wi-Fi secrets,
or credential-manager contents. Review reports before sharing them.

SOURCE AND ISSUES
https://github.com/chatgptopenaiagi/ARX
