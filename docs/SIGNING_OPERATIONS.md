# Authenticode signing operations

This is an operator contract for a future protected signing job. It intentionally contains no production provider, certificate identity, credential, signing command, or secret-resolution implementation.

## Prerequisites

The gate remains blocked until all of these exist:

- an approved Windows-trusted production signing provider and publisher identity;
- a completed provider identity-validation process;
- a protected GitHub environment with named approvers;
- a reviewed configured policy derived from `security/signing/signing-policy.template.json`;
- an RFC 3161 timestamp service approved for that identity;
- a provider integration that does not expose private material to repository code or logs;
- clean Windows 10 and Windows 11 lifecycle evidence for the candidate.

The policy validator accepts only public identity expectations. It rejects secret-bearing fields and credential-bearing timestamp URLs:

```powershell
python scripts/validate-signing-policy.py path\to\reviewed-signing-policy.json
```

## Pre-signing verification

Unsigned candidates may be inventoried without claiming signature trust:

```powershell
pwsh -File scripts/verify-authenticode.ps1 `
  -ArtifactPath release\candidate\ARX.exe,release\candidate\ARX-Setup.exe `
  -PolicyPath security\signing\signing-policy.template.json `
  -OutputPath security-results\authenticode-pre-signing.json `
  -AllowUnsignedPreSigning
```

The expected result is `UNSIGNED_EXPECTED_PRE_SIGNING`. Mixed signed/unsigned inputs, an unexpectedly signed file, or any other state fails.

## Protected signing operation

The protected workflow must implement the exact order in `TRUSTED_INSTALLATION.md`. It must record, without secrets:

- repository, workflow run, environment, commit, and candidate hash;
- public certificate subject, issuer/chain, serial or provider identity reference;
- signing algorithm;
- RFC 3161 timestamp URL host and timestamp digest algorithm;
- provider operation/result identifier where safe;
- post-signing hash and verification result;
- authorized approval identity exposed by the protected environment.

Signing must use SHA-256. For SignTool-compatible integrations, RFC 3161 timestamping uses `/tr <approved-url> /td SHA256`; legacy `/t` timestamping is not the production path.

## Independent verification

Run the verifier on final signed `ARX.exe` and the final signed installer using the configured reviewed policy:

```powershell
pwsh -File scripts/verify-authenticode.ps1 `
  -ArtifactPath release\final\ARX.exe,release\final\ARX-Setup.exe `
  -PolicyPath path\to\reviewed-signing-policy.json `
  -OutputPath security-results\authenticode-final.json
```

`PASS_SIGNED` requires both PowerShell and SignTool checks. The verifier records public certificate and hash metadata, not raw tool output or credentials. The current digest-label check expects English Windows SDK output; a localized signing runner must be characterized before use.

After verification, repeat the required post-signing scanners and package checks. Only then generate public checksums and attestations for the final bytes.

## Failure handling

Do not publish if verification reports any warning or failure, the signer differs, the chain cannot be built, the timestamp is absent, the digest is not SHA-256, or a post-signing hash differs. Preserve the failed evidence, revoke or quarantine affected credentials through the selected provider's incident process when appropriate, and rebuild from the reviewed source rather than modifying signed bytes.
