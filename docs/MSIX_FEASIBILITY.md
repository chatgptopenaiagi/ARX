# MSIX and Microsoft Store feasibility

## Conclusion

Keep the classic signed Inno Setup installer and portable ZIP as the Beta 2 architecture. An optional MSIX/Store channel is technically plausible, but remains a bounded future project because package identity, update ownership, filesystem behavior, full-trust desktop declarations, signing, Store policy, and lifecycle behavior have not been validated for ARX.

| Area | Classic Inno Setup | Portable ZIP | Future MSIX / Store |
| --- | --- | --- | --- |
| Current fit | Existing build and stable upgrade AppId | Existing no-install distribution | Feasibility only |
| Privilege model | Installer elevates for Program Files; app runs asInvoker | Standard user from user-owned directory | Package deployment and full-trust desktop behavior need explicit validation |
| Updates | Release/installer process owned by ARX | Manual replacement | Store or App Installer channel could own updates |
| Signing | Sign embedded executable, then installer | Contains the signed executable | Package signing and identity are mandatory outside Store-managed signing |
| Filesystem | Conventional Program Files install plus per-user data | User-selected directory plus per-user data | Packaged install location and redirected/virtualized behavior may affect assumptions |
| Distribution | Direct GitHub download | Direct GitHub download | Store submission or separately distributed signed MSIX |

## Benefits

- standardized package identity and deployment lifecycle;
- potential Store distribution and update channel;
- package-level integrity and signing requirements;
- cleaner uninstall behavior when all state follows package rules.

## Limitations and required work

- author and validate an AppxManifest with correct desktop/full-trust declarations;
- confirm Tk/PyInstaller application behavior inside packaged deployment;
- map DPAPI-backed per-user credentials and audit-history retention/uninstall behavior;
- test file dialogs, project scanning, portable behavior, shortcuts, updates, and uninstall;
- choose Store identity or a Windows-trusted certificate for direct MSIX distribution;
- execute Windows 10/11 and Smart App Control lifecycle testing;
- maintain channel-specific version/update semantics without replacing classic users unexpectedly.

Microsoft's MSIX signing guidance distinguishes production signing from test certificates and requires the certificate identity to match the package manifest: [MSIX package signing](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview). A self-signed test package would not establish public publisher trust and is outside this phase.

No Store submission, package identity reservation, certificate request, or MSIX build is performed here.
