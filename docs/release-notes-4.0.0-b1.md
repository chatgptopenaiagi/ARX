# ARX 4.0.0 Beta 1

Package version: `4.0.0b1`

Git tag: `v4.0.0-b1`

Release type: GitHub prerelease

ARX 4.0.0 Beta 1 is the first prerelease of the ARX 4 trust foundation. It preserves the deterministic, offline-capable compatibility core and adds explicit provenance categories, architectural enforcement, and a hardened provider boundary for optional OpenAI API and Codex CLI advice. It is not ARX 4 stable.

## Deterministic evidence and architecture

- The ARX deterministic compatibility core remains authoritative and operates without an OpenAI credential or network connection.
- `EvidenceKind` now contains `DECLARED`, `OBSERVED`, `INFERRED`, `UNKNOWN`, `ESTIMATED`, `SIMULATED`, and `STRUCTURAL`.
- `VERIFIED` remains outside `EvidenceKind`. Fact provenance is retained on `Evidence`; relation and decision validation remains the responsibility of semantic invariants and schema/composed-state checks.
- Existing numeric confidence values are documented as uncalibrated detector-author weights, not probabilities, measured accuracy, or statistical confidence.
- CI enforces the reviewed ARX dependency graph, rejects cycles, and includes a mutation proof in which a temporary forbidden `core -> advisory` import fails before the copied source tree is restored and passes.

## OpenAI API trust foundation

- Provider-neutral credential resolution supports developer `OPENAI_API_KEY` configuration and ARX-owned secure storage.
- The packaged Windows application protects imported OpenAI API credentials with native Windows per-user DPAPI. ARX never creates an API key and never redisplays a saved plaintext key.
- `CREDENTIAL_UNREADABLE` is distinct from `NOT_CONFIGURED` and from provider authentication rejection when a protected blob cannot be decrypted in the current Windows context.
- Structured provider health distinguishes missing or unreadable credentials, network, TLS/HTTPS, authentication, rate limit, quota, unavailable model, timeout, cancellation, server, parse, and ready states.
- OpenAI uses the supported Responses API. The transport validates the exact allowlisted HTTPS endpoint, rejects redirects, applies timeouts and cancellation, sanitizes errors, bounds requests and responses, and sends `store: false`.
- Context is selected, filtered, redacted, and bounded before it reaches the provider boundary. The transport repeats redaction immediately before every request.
- A local metadata-only transmission audit records `REQUEST_PREPARED`, `OUTBOUND_REQUEST_INITIATED`, `RESPONSE_RECEIVED`, `REQUEST_FAILED`, or `CANCELLED`. It stores no API key, prompt body, response body, authorization header, URL, full project path, or secret value. Retention, count, file size, and rotation are bounded; history has an explicit clear action and no implicit export or cloud synchronization.

## Windows provider settings and advisory entry points

- `Settings -> Intelligence Providers -> OpenAI API` exposes Configure OpenAI API Key, Import OpenAI API Key, Replace Credential, Remove Credential, Test Connection, Open OpenAI Chat, and Clear History actions.
- Configure opens the official OpenAI Platform API-key page. ARX does not automate the ChatGPT desktop application or website.
- Import and Replace read only a deliberately selected, bounded plaintext credential file inside the credential-import boundary, immediately DPAPI-protect the credential for the current user, and do not remove the source file without a separate user decision.
- Opening Settings performs no provider request and transmits no ARX evidence. Test Connection sends only the minimum request needed to validate credential, API, and selected-model access.
- The existing OpenAI advisory assistant entry point uses the hardened provider transport and the existing consent/redacted-context preview flow. The Codex CLI advisory provider remains available independently.
- Provider output is labeled `AI ADVISORY — NON-AUTHORITATIVE`. It cannot write to `Evidence`, `EvidenceKind`, Machine DNA, Software DNA, Project DNA, compatibility, readiness, deterministic findings, or semantic-invariant results.

## OpenAI quota behavior

A minimum-data authentication/model health check may report authentication, API access, model access, and overall provider health as `READY` while a later Responses API advisory generation still fails with `QUOTA_EXHAUSTED`. OpenAI documents billing, spend, and usage-limit failures as distinct 429 categories whose broader type can be `insufficient_quota`; ARX does not relabel those failures as invalid authentication. See the [OpenAI API error-code guide](https://developers.openai.com/api/docs/guides/error-codes).

## Phase C is not included

Phase C is **NOT included** in this prerelease. ARX 4.0.0 Beta 1 does not claim completion of:

- Ask Both;
- AI consensus or convergence indicators;
- synthesized provider answers;
- provider ranking or a winning answer;
- expanded contextual multi-turn conversation architecture;
- the final ARX 4 Intelligence Console.

Two advisory providers do not constitute independent verification. No similarity between provider responses can upgrade deterministic ARX provenance or validation.

## Distribution and release limits

- Python distribution name remains `arx-prescanner`; `4.0.0b1` is a new version of the existing PyPI/TestPyPI project, not a new package identity.
- The Python wheel and source distribution, complete Windows x64 portable ZIP, optional Inno Setup installer, and `SHA256SUMS.txt` are attached to the GitHub prerelease after release-gate verification.
- The Windows executable and installer are unsigned because no approved code-signing certificate or service is available. SHA-256 checksums do not substitute for Authenticode.
- Visible multi-DPI behavior, screen-reader verification, and destructive installer lifecycle transitions were not inferred from automated tests or artifact construction. The historical ARX 3 acceptance blockers remain documented.
- Windows Server and ARM64 are not validated for this beta.
- TestPyPI and production PyPI publication are separate manual OIDC workflows. Neither is implied by publishing the GitHub prerelease, and production PyPI remains blocked until explicitly approved.
