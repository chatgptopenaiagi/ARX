# GitHub Artifact Attestations

## Scope

Future ARX release workflows use GitHub OIDC to create build-provenance attestations for the exact staged release bytes. The attestation binds an artifact digest to the repository, workflow, workflow run, and source commit recorded by GitHub. It is independent of Authenticode, SHA-256 manifests, SBOMs, malware scans, and Windows reputation.

The historical `v4.0.0-b1` assets remain unchanged and have no retrofitted GitHub Artifact Attestations.

## Workflow boundaries

`trusted-installation-preflight.yml` may attest explicitly unsigned, short-retention preflight subjects. Those attestations prove the preflight workflow produced the named bytes; they do not establish Windows publisher identity and are not final release provenance.

`release-assets.yml` attests every exact file staged for a future GitHub release, including `SHA256SUMS.txt` and supported security/SBOM evidence. The action runs before the same staging bundle is uploaded for release attachment. Only this build job receives `id-token: write` and `attestations: write`; the attachment job receives `contents: write` but no OIDC or attestation permission.

The workflows pin `actions/attest-build-provenance` to reviewed commit `4d101475d8b20a2381f78447822ac1eab6504dd8` (release `v4.2.2`). No long-lived attestation secret is used.

## Verification

For a published future artifact, record the release asset SHA-256 first, then use GitHub CLI attestation verification against the expected repository:

```powershell
gh attestation verify path\to\artifact --repo chatgptopenaiagi/ARX
```

The evidence record must preserve the verifier version, artifact hash, repository, verified workflow, source commit, verification timestamp, and result. A missing or invalid attestation is reported independently; it must not be converted into an Authenticode, malware, or deterministic ARX result.

## Final-byte rule

Production releases must sign and timestamp Windows binaries before calculating final hashes and creating final attestations. Beta 2 remains an explicitly unsigned prerelease unless a real approved signing identity becomes available; its attestation, when created, binds the final disclosed unsigned bytes and must not imply publisher trust.
