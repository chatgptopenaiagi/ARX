ARX
Experimental Desktop Release 0.2.0

PURPOSE
ARX is a read-only pre-installation compatibility intelligence tool. It scans
this PC, statically inspects software, compares requirements, and explains its
evidence. ARX is not a malware scanner and does not certify software as safe.

SUPPORTED OPERATING SYSTEM
Windows 10/11 x64. This experimental build has been validated on Windows 10
x64. Windows Server and ARM64 have not been validated.

START
Extract the complete folder, then double-click ARX.exe. Keep the _internal
folder beside ARX.exe; it contains the standalone Python/Tk runtime.

READ-ONLY MODEL
Normal scanning does not install software, change PATH, edit the registry, or
execute the selected target. Only fixed, timeout-bound trusted diagnostic
commands are used to identify developer tools.

SUPPORTED INSPECTION TARGETS
EXE, DLL, MSI identification, ZIP, JAR, APK, scripts, and application
directories. Static analysis includes hashes, PE metadata, Authenticode,
archive entries, recognized manifests, runtime indicators, and requirements
where available.

KNOWN LIMITATIONS
MSI action/table parsing, APK binary-manifest decoding, complete PE import-table
resolution, and complex semantic-version ranges are incomplete. Compatibility
results express available evidence and uncertainty; they are not malware
verdicts or guarantees that an installer will succeed.

PRIVACY
Reports redact the current user-profile path and allowlist environment data.
ARX does not collect passwords, tokens, cookies, private keys, Wi-Fi secrets,
or credential-manager contents. Review reports before sharing them.

SOURCE AND ISSUES
https://github.com/chatgptopenaiagi/ARX
