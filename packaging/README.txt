ARX 4
ARX 4.0.0 Beta 2
Package version 4.0.0b2

PURPOSE
ARX is a read-only project-aware compatibility and resolution engine. It scans
this PC, statically inspects software and Python projects, resolves providers,
compares requirements, and explains a GREEN/YELLOW/RED decision and advisory
path to GREEN. ARX is not a malware scanner and does not certify software as safe.

SUPPORTED OPERATING SYSTEM
Windows 10/11 x64. Windows Server and ARM64 have not been validated for this
beta.

START
Extract the complete folder, then double-click ARX.exe. Keep the _internal
folder beside ARX.exe; it contains the standalone Python/Tk runtime.

INSTALLER DISTRIBUTION
When ARX is distributed as ARX-Desktop-Setup-win-x64-v4.0.0-b2.exe, the installer provides
Start Menu and uninstall entries, offers an optional desktop shortcut, and can
launch ARX after an interactive install. The portable extracted-folder workflow
remains supported. Installer builds are currently unsigned; verify the published
SHA-256 checksum before installation.

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
Reports redact the current user-profile path and allowlist environment data.
ARX does not collect passwords, tokens, cookies, private keys, Wi-Fi secrets,
or credential-manager contents. Review reports before sharing them.

OPTIONAL OPENAI API
Open Settings, Intelligence Providers, OpenAI API to configure the supported
OpenAI API provider. ARX never creates an API key. A key selected for import is
protected with Windows DPAPI for the current user and is never displayed again.
Use Remove Credential and Clear History before uninstall if you want to remove
the ARX-owned per-user provider data; the uninstaller does not silently delete
data under %LOCALAPPDATA%\ARX or the user's temporary plaintext import file.

OpenAI authentication/model health can be READY while an advisory generation
still fails with QUOTA_EXHAUSTED when the API project lacks generation quota.
That condition is not reported as an authentication failure. AI output remains
non-authoritative and cannot modify deterministic ARX evidence, compatibility,
readiness, or EvidenceKind.

BETA SCOPE
ARX 4.0.0 Beta 2 preserves the Phase B trust foundation and adds security-audit
remediation, reproducible-build controls, provenance preparation, and a future
Windows signing architecture. Phase C and the final
Intelligence Console are not included. Ask Both, AI consensus, synthesized or
ranked provider answers, and the expanded contextual conversation architecture
are not claimed by this build.

SOURCE AND ISSUES
https://github.com/chatgptopenaiagi/ARX
