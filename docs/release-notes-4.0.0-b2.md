# ARX 4.0.0 Beta 2

Package version: `4.0.0b2`

Git tag: `v4.0.0-b2`

Release channel: GitHub prerelease

ARX 4.0.0 Beta 2 is a security-remediation and release-trust prerelease. It preserves the deterministic, offline-capable compatibility core and the ARX 4 Phase B provider boundary while addressing gaps identified by the read-only Beta 1 security audit. It is not ARX 4 stable.

## Deterministic evidence boundary

- `EvidenceKind` remains exactly `DECLARED`, `OBSERVED`, `INFERRED`, `UNKNOWN`, `ESTIMATED`, `SIMULATED`, and `STRUCTURAL`.
- `VERIFIED` remains outside `EvidenceKind`. Fact provenance stays on the existing `Evidence` fields; relation and decision validation stays with semantic invariants and schema/composed-state checks.
- Numeric confidence values remain uncalibrated detector-author weights, not probabilities, measured accuracy, or statistical confidence.
- OpenAI API and Codex CLI output remains `AI ADVISORY - NON-AUTHORITATIVE`. It cannot modify Evidence, Machine DNA, Software DNA, Project DNA, compatibility, readiness, or semantic-invariant results.

## Security remediation

- Repaired the bounded Hypothesis harness so malformed PE, directory `package.json`, and ZIP/archive properties reach ARX product code with isolated per-example storage and fixed example bounds.
- Corrected bounded parsers to reject truncated PE optional headers and non-object `package.json` documents without execution, extraction, or unbounded reads.
- Corrected the provider-error and redaction generator property assumptions without weakening their intended security properties.
- Hardened index-supplied distribution downloads to require exact allowlisted HTTPS hosts, the default HTTPS port, credential-free URLs, no redirects, response-destination revalidation, connect/read timeout, bounded metadata and distribution sizes, streamed enforcement, expected size, and exact SHA-256 identity.
- Errors at that boundary remain sanitized, and neither URLs nor command-line arguments receive credentials.

## Reproducibility and supply-chain evidence

- Release scripts derive `SOURCE_DATE_EPOCH` from the exact source commit, set controlled child-build environment values, use stable file ordering, and normalize portable ZIP member timestamps without falsifying source time.
- PyInstaller uses the reviewed onedir build without UPX; Inno Setup uses deterministic file timestamps/order and single-threaded compression controls where supported.
- The release security record reports wheel, sdist, portable ZIP, `ARX.exe`, installer, and `SHA256SUMS.txt` independently as bit-for-bit reproducible, structurally equivalent, not reproducible, or unresolved. Structural equivalence is never presented as byte identity.
- CycloneDX JSON records the isolated release-package component inventory.
- GitHub Artifact Attestations use short-lived GitHub OIDC and bind exact release bytes to repository, workflow, run, commit, and digest. Beta 1 remains unchanged and receives no retrofitted attestations.

## Windows publisher-trust preparation

- Added a provider-neutral public signing-policy schema for a future approved Windows-trusted identity.
- Added reusable fail-closed verification using `Get-AuthenticodeSignature` and `signtool verify /pa /all /tw /v`, including exact publisher, approved issuer/chain, timestamp, digest, and artifact-hash evidence.
- Defined the required production byte order: sign and RFC 3161 timestamp `ARX.exe`, verify it, package it, build/sign/timestamp/verify the installer, rerun post-signing gates, and only then calculate final hashes and provenance.
- Kept SHA-256, Authenticode, RFC 3161 timestamping, GitHub provenance, SBOM inventory, malware scans, and SmartScreen/Smart App Control reputation as separate signals.
- Prepared a defensive Windows 10/11 standard-user lifecycle matrix and read-only evidence collector. Disposable guest execution remains a separate gate and is not inferred from manifests or host inspection.

No approved production code-signing certificate or managed signing identity is configured. The Beta 2 Windows executable and installer are therefore accurately distributed as **unsigned**. Checksums and GitHub attestations do not substitute for Authenticode or established SmartScreen reputation. No trust store was modified and no test or production signing occurred.

## Phase B provider foundation retained

- Windows per-user DPAPI protection remains the packaged OpenAI credential mechanism, with `CREDENTIAL_UNREADABLE` distinct from missing credentials and authentication rejection.
- OpenAI provider health remains structured across credential, network/TLS, authentication, rate limit, quota, model, timeout, cancellation, server, parse, and ready states.
- The supported OpenAI Responses API transport keeps exact HTTPS endpoint validation, rejects redirects, and enforces bounded/redacted context, cancellation, timeout, response bounds, and sanitized errors.
- The visible `Settings -> Intelligence Providers -> OpenAI API` surface retains Configure, Import, Replace, Remove, Test Connection, Open OpenAI Chat, and Clear History actions without redisplaying a stored key.
- The metadata-only transmission audit remains bounded, rotating, local-only, explicitly clearable, and free of prompt/response bodies, credentials, and full local paths.
- The Codex CLI advisory provider remains independent and functional when OpenAI is unavailable.

Provider authentication and model health may be `READY` while advisory generation fails with `QUOTA_EXHAUSTED` because the API project has no generation quota. ARX does not relabel that failure as invalid authentication.

## Phase C is **NOT included**

This prerelease does **not** claim completion of:

- Ask Both;
- AI agreement, consensus, confidence boosts, or provider ranking;
- synthesized provider answers;
- expanded contextual conversation architecture;
- the final ARX 4 Intelligence Console.

Two advisory providers producing similar text never verifies deterministic ARX evidence or upgrades provenance.

## Release and installation limitations

- This is a GitHub prerelease, not stable `v4.0.0`.
- The package identity remains the existing `arx-prescanner` project. GitHub publication does not authorize or trigger TestPyPI or production PyPI publication.
- The Windows artifacts are unsigned until a real approved publisher identity exists.
- Standard-user install/upgrade/uninstall and SmartScreen/Smart App Control behavior require disposable Windows 10/11 execution and are not claimed from static checks.
- Phase C remains out of scope.
- Scanner results establish only the named, bounded gates; the release does not claim that “ARX is secure.”

The public release-security record uses the wording: “ARX passed the following defined security gates.” Each row retains its evidence and limitation.
