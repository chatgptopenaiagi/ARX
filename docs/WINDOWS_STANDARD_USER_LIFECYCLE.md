# ARX Windows standard-user lifecycle gate

This gate is destructive to installed application state and must run only in disposable Windows guests. It does not weaken UAC, Defender, SmartScreen, Smart App Control, ACLs, or certificate trust.

The collector at `scripts/collect-windows-lifecycle-evidence.ps1` is read-only. Installation, upgrade, launch, and uninstall transitions remain visible human actions so the record cannot imply that a command completed merely because a process was started.

## Required guests

Use fresh snapshots of both:

- Windows 10 22H2 x64 with a standard-user account and separate administrator credentials;
- current stable Windows 11 x64, plus a distinct Smart App Control observation when available.

Each guest must have networking disabled unless a specifically reviewed test requires it. Use only local ARX artifacts whose SHA-256 values already appear in the candidate manifest. Never import a production OpenAI or signing credential.

## Evidence protocol

Create a separate evidence directory for every guest and retain all collector JSON, installer logs, hashes, screenshots, and the exact VM snapshot identifier. Do not publish usernames, machine names, local paths, credential blobs, or unrelated system inventory.

Run the collector from a normal, non-elevated PowerShell session for every `*_STANDARD_USER` stage. Run `INSTALLER_ELEVATED_SHELL_OBSERVATION` only when explicitly testing an already elevated shell.

```powershell
.\scripts\collect-windows-lifecycle-evidence.ps1 `
  -Stage PRE_INSTALL_STANDARD_USER `
  -ArtifactPath .\ARX-Desktop-Setup-win-x64-v4.0.0-b3.exe `
  -ExpectedVersion 4.0.0b3 `
  -OutputPath .\evidence\pre-install.json
```

## Windows 10 and Windows 11 matrix

Perform every row independently on both required guests.

| Stage | Required action | Required observation |
|---|---|---|
| Pre-install | Verify installer SHA-256 and signature state; run `PRE_INSTALL_STANDARD_USER` collector | Standard token; exact reviewed installer identity |
| Interactive install | Start installer as standard user and approve normal UAC using separate administrator credentials | Elevation is limited to installer; destination is 64-bit Program Files; desktop shortcut remains optional |
| Installed launch | Launch ARX from Start Menu and install directory as the original standard user | ARX token is non-elevated; Program Files directory has no broad writable ACL; normal scan succeeds |
| Denied write | Attempt to create a harmless file in the ARX installation directory from standard-user PowerShell | Access denied; no permissions are changed |
| Credential boundary | Configure a disposable test credential through ARX, close/reopen ARX, then remove it | Credential is accessible only in the same user context; plaintext is never redisplayed; another user cannot decrypt it |
| Upgrade | Install the Beta 3 candidate over the approved prior test build using the stable AppId | One product registration remains; expected files and versions update; ARX still launches non-elevated |
| Already-elevated shell | Start installer from an explicitly elevated shell | Installer behavior is recorded; post-install launch is not misreported as a standard-user launch |
| Portable | Extract the reviewed portable ZIP into a standard-user-owned directory and launch ARX | Application starts without installation or elevation; no files are written outside documented user-data locations |
| Uninstall | Use Installed Apps and repeat with the Start Menu uninstaller on a restored snapshot | Program Files payload and shortcuts are removed; unrelated files and portable copies remain |
| Post-uninstall | Run `POST_UNINSTALL_STANDARD_USER` collector | Install directory absent; per-user `%LOCALAPPDATA%\ARX` behavior matches documentation and is not silently upgraded to “removed” |

## Required application-token observation

The static `asInvoker` manifest is necessary but not sufficient. During the installed and portable launches, inspect the running `ARX.exe` with a trusted Windows process-token viewer and record that its elevation type is limited/default rather than full. A screenshot or exported process record must identify the artifact hash and guest snapshot without including unrelated processes.

## Gate decision

Allowed final results are:

- `PASS`: every required Windows 10 and Windows 11 transition was directly observed;
- `PARTIAL`: some direct observations succeeded but at least one required row was not executed;
- `BLOCKED_NOT_EXECUTED`: suitable disposable guests or required separate accounts were unavailable;
- `FAIL`: a required lifecycle or permission property failed.

Static inspection, installer compilation, an elevated development workstation, or a successful silent command is not a substitute for this gate.
