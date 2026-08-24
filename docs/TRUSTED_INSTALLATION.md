# ARX trusted Windows installation

## Scope and current state

This program defines a future path to verifiable Windows publisher identity. It does not make an unsigned candidate signed, and it does not alter the immutable `v4.0.0-b1` release. ARX currently has no approved production signing identity. Production signing is therefore `BLOCKED_NO_PRODUCTION_CERTIFICATE`.

ARX must arrive with cryptographic evidence. Windows decides whether to trust it. ARX must never install a custom root certificate on customer machines, disable Defender, SmartScreen, Smart App Control, UAC, or reputation checks, add blanket exclusions, weaken Windows security policy, or require permanent administrator execution.

## Independent trust signals

These signals answer different questions and must never be collapsed into a single `TRUSTED` flag:

| Signal | What it establishes | What it does not establish |
| --- | --- | --- |
| SHA-256 | Identity of exact artifact bytes | Publisher identity, build origin, or safety |
| Authenticode | Windows publisher identity and signed-byte integrity under the evaluated chain policy | Build provenance, component inventory, or established reputation |
| RFC 3161 timestamp | Evidence that a signature was timestamped through the configured timestamp authority | Current safety or build provenance |
| GitHub Artifact Attestation | Repository/workflow/commit provenance bound to an artifact digest | Windows publisher identity or absence of vulnerabilities |
| SBOM | Declared component and dependency inventory | Absence of vulnerabilities or malicious behavior |
| Malware scan | A named engine's result for exact bytes at a stated time | Proof that an artifact is harmless |
| SmartScreen / Smart App Control | A separate Windows reputation and policy decision | A substitute for signature verification or artifact identity |

Status is not provenance. `PASS`, `BLOCKED`, and `UNSIGNED_EXPECTED_PRE_SIGNING` describe gate outcomes; they are not `EvidenceKind` values.

## Required production order

Future production signing must use this byte-ordering and approval sequence:

1. Build the candidate `ARX.exe`.
2. Complete every required pre-signing test.
3. Sign `ARX.exe`.
4. RFC 3161 timestamp `ARX.exe`.
5. Independently verify `ARX.exe`.
6. Package the signed `ARX.exe` into the portable distribution.
7. Build the installer containing the signed `ARX.exe`.
8. Sign the final installer.
9. RFC 3161 timestamp the final installer.
10. Independently verify the installer.
11. Rerun malware scanning, secret scanning, package-content validation, product-version validation, installer smoke testing, and artifact-identity checks after signing.
12. Generate final SHA-256 hashes only after every byte-changing signing operation is complete.
13. Generate provenance and attestations against the final bytes.
14. Obtain the protected human release approval.
15. Publish.

Pre-signing hashes remain build evidence; they are never represented as final distribution hashes. ARX does not patch PE metadata or timestamps after a build merely to force two hashes to agree.

## Identity and verification policy

The public, provider-neutral policy lives in `security/signing/signing-policy.schema.json`. A production configuration must identify:

- the selected signing provider;
- a non-secret certificate identity selector;
- the RFC 3161 timestamp URL;
- the exact expected publisher subject;
- approved issuer or chain subjects;
- SHA-256 signing and timestamp algorithms;
- fail-closed verification requirements.

Provider credentials, private keys, PFX files, passwords, PINs, tokens, and certificate secrets never belong in source, release archives, logs, prompts, command-line arguments, or workflow artifacts. A provider may later use a hardware-backed key, a protected CI identity, or an approved managed service; the repository policy stores only public identity expectations.

Verification uses both `Get-AuthenticodeSignature` and Windows SDK `signtool verify /pa /all /tw /v`. It requires a valid Windows chain, exact publisher subject, approved issuer/chain, timestamp certificate, SHA-256 digest evidence, and successful policy verification. The protected signing-operation record must separately prove that signing invoked an RFC 3161 timestamp service (`signtool /tr` with `/td SHA256`, or the selected provider's equivalent). A missing timestamp, changed publisher, invalid chain, warning, changed artifact, or tool error fails closed.

The Windows SDK documents `/tr` as the RFC 3161 timestamp option, `/td` as its digest selection, and `/tw` as the timestamp-warning verification option: [SignTool documentation](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).

For an unsigned development candidate, the only acceptable verification result is `UNSIGNED_EXPECTED_PRE_SIGNING`. That result is not `PASS_SIGNED` and does not establish publisher trust.

## Installation and elevation

The desktop application normally runs `asInvoker` as a standard user. The Inno Setup installer may request elevation only to install machine-wide files under `Program Files`. ARX must not permanently mark `ARX.exe` as requiring administrator rights. Standard-user launch, upgrade, uninstall, ACL, credential access, and residue behavior require observation in disposable Windows 10 and Windows 11 guests; static manifests do not substitute for those tests.

## Reputation and Windows policy

A valid Authenticode signature and established SmartScreen reputation are different results. Microsoft notes that a newly signed application may still be reported as unknown until reputation is established; ARX must record the observed Windows behavior rather than infer it from signature validity. See [Windows code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

The clean-machine matrix must cover Windows 10 22H2, Windows 11 stable, and Windows 11 Smart App Control where available. No result may be recorded until directly observed on the named image and exact artifact hash.

## Provider options

No provider is selected in this phase. A later human decision may approve Microsoft Artifact Signing, a public CA organizational code-signing certificate, or another Windows-trusted provider. Microsoft describes Artifact Signing as a managed signing service and distinguishes public from private trust models: [service overview](https://learn.microsoft.com/en-us/azure/artifact-signing/overview) and [trust models](https://learn.microsoft.com/en-us/azure/artifact-signing/concept-trust-models).

No purchase, identity-verification request, certificate issuance, or production signing is performed by this repository preparation.

## Human gates

Production signing belongs in a protected environment that contains the approved provider integration and requires explicit authorized approval. Publication is a separate gate. The normal CI and preflight workflows may build, test, scan, verify unsigned state, and prepare provenance, but they cannot gain production-signing or publication authority.

Temporary self-signed certificates may be used only on disposable, unpublished copies to exercise a test pipeline. They may never be installed into a machine-wide trusted-root store or presented as public trust. No such test signing is required by, or performed in, this preparation.
