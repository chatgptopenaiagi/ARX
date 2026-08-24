# ARX Trusted Installation Program

## Purpose

Future ARX Windows releases should arrive with verifiable publisher identity and provenance so Windows can make a normal trust decision without requiring users to install a custom root certificate or bypass security prompts.

The already-published `v4.0.0-b1` release is immutable. Do not sign, rebuild, replace, or republish its artifacts.

## Trust model

ARX must never make Windows trust ARX by modifying the machine trust store. Public distribution must use a publisher identity chained to a trust path Windows already recognizes.

The preferred trust stack is:

1. Microsoft Store MSIX, where practical.
2. Azure Artifact Signing (formerly Trusted Signing) for direct non-Store distribution when eligibility is satisfied.
3. A public CA-issued OV code-signing certificate when Artifact Signing is not available.

Self-signed certificates are for development, test, or managed-enterprise deployment only.

## Release trust chain

A future signed release should follow this order:

1. Check out the exact release commit/tag.
2. Build in a clean environment.
3. Run compile, architecture, unit, GUI, secret, dependency, SAST, SBOM, malware, and release-integrity gates.
4. Produce unsigned release candidates.
5. Stop for a human approval gate.
6. Sign embedded PE executables that require Authenticode.
7. Build/sign the final Windows installer as appropriate.
8. Apply an RFC 3161 timestamp to every production signature.
9. Verify signatures with `Get-AuthenticodeSignature`, `signtool verify`, and Sigcheck.
10. Compute final SHA-256 digests only after signing.
11. Generate `SHA256SUMS.txt` from the final signed artifacts.
12. Generate build provenance / artifact attestations.
13. Stop for a final human release approval.
14. Publish immutable artifacts.

Signing changes bytes, so pre-signing hashes are build evidence, not final distribution hashes.

## Human gates

No workflow may publish or production-sign artifacts without an explicit human gate.

Safe automatic CI may perform:

- build and test
- dependency/CVE audit
- SBOM generation and validation
- SAST and secret scans
- artifact-integrity checks
- unsigned artifact staging
- provenance generation for non-production candidates

Manual / protected-environment steps include:

- production Authenticode signing
- timestamping with production identity
- production publication
- Microsoft Store submission

Production credentials must never be stored in source, release archives, logs, prompts, test data, or repository files.

## Windows installation architecture

The installer may request elevation when installation into `Program Files` requires it. The ARX desktop application should run as a standard user by default. Any operation that genuinely needs elevated rights should request elevation explicitly and only for the bounded operation.

Do not mark the entire ARX application as permanently requiring administrator rights unless a future security review demonstrates that it is unavoidable.

## Windows metadata

Future artifacts should expose consistent Windows metadata:

- Product: `ARX`
- Product version: release version
- File version: numeric Windows version
- Publisher: verified legal publisher identity once signing is configured
- Description
- Copyright
- Original filename
- Architecture

The certificate subject displayed by Windows is controlled by the validated signing identity and must not be fabricated in metadata.

## Verification gate

For a future signed release, all of the following must be recorded before publication:

- exact release commit/tag
- security gate result
- dependency audit result
- SAST result
- malware scan result
- SBOM filenames and validation status
- Authenticode status for every signed PE/installer
- RFC 3161 timestamp status
- final SHA-256 values
- GitHub provenance / attestation status
- clean Windows 10 installation result
- clean Windows 11 installation result
- standard-user launch result
- administrator-required operation result
- uninstall and reinstall result
- human signing approval
- human publication approval

A new signed application can still receive an initial Microsoft Defender SmartScreen reputation warning. Signing establishes publisher identity and allows publisher reputation to accumulate; it is not a mechanism for bypassing SmartScreen.

## Store path

Investigate a parallel MSIX / Microsoft Store distribution path after the classic Win32 installer is stable. Keep the two channels distinct:

- ARX Classic: signed Win32 installer
- ARX Store: MSIX / Store distribution

The Store path must not replace the direct installer until packaging, update, filesystem, and privilege behavior have been verified.

## Future Trust Viewer

A future ARX UI may expose a read-only `Security & Trust` view showing:

- ARX version
- release channel
- signature status
- publisher certificate subject
- timestamp status
- SHA-256
- build commit
- attestation/provenance reference

This view is informational only and must not alter trust decisions or evidence provenance.
