# ARX 4 Phase B trust foundation

Phase B starts from immutable approved commit `a9c30981fc775b325494a22eacba8e31019f4cc9` on branch `arx4-development`. ARX remains package version `3.0.0rc1`; this work does not authorize or create a stable `v3.0.0` tag.

## Scope and invariants

This phase establishes provenance, dependency, credential, provider-health, transport-redaction, and external-transmission-audit foundations. It does not implement the full Phase C Intelligence Console or a new chat architecture. The existing advisory window is reused by the minimal `Open OpenAI Chat` configuration action.

The governing invariant is:

> ARX MAY TRANSFORM EVIDENCE, BUT IT MAY NEVER SILENTLY UPGRADE PROVENANCE.

`EvidenceKind` contains `DECLARED`, `OBSERVED`, `INFERRED`, `ESTIMATED`, `SIMULATED`, `STRUCTURAL`, and `UNKNOWN`. It does not contain `VERIFIED`. Fact provenance remains in the existing `Evidence` fields—`kind`, `source`, `value`, `method`, `confidence`, and `note`. Decision and relation validation remain separate semantic-invariant, schema, or composed-state operations.

All existing numeric confidence assignments, including operational-health claims, are detector-author weights. No calibration data supports interpreting them as probabilities, measured accuracy, or statistical confidence.

## Dependency enforcement

CI executes `scripts/check-architecture.py` to parse all ARX imports, enforce the reviewed directed layer graph, and reject cycles. `core` imports no other ARX layer. `machine`, `software`, and `project` cannot import `advisory`. The baseline's existing late `project → machine` orchestration edge is represented explicitly and remains non-cyclic.

The architectural test mutation inserts a temporary forbidden `core → advisory` import into an isolated copied source tree, proves the checker fails, reverts the mutation by discarding that copy, and proves the original source tree passes. The mutation never touches the working source tree.

## OpenAI API configuration surface

The normal desktop path is:

```text
Settings
└── Intelligence Providers
    └── OpenAI API…
```

The settings window provides:

- Configure OpenAI API Key
- Import OpenAI API Key
- Replace Credential
- Remove Credential
- Test Connection
- Open OpenAI Chat
- Clear History for the local metadata-only transmission audit

Configure opens the fixed official OpenAI Platform key page. ARX never generates or invents an API key and never automates the ChatGPT desktop application or website. Import and Replace accept a user-selected temporary plaintext key file, protect it immediately with Windows DPAPI for the current user, and never redisplay it. Developer mode may use `OPENAI_API_KEY` from the current process environment.

Opening Settings does not contact OpenAI and does not transmit ARX data. Safe display states keep credential presence, authentication, API access, model access, and overall readiness separate. `CONFIGURED` is never silently upgraded to `READY`.

## Credential and health states

The provider-neutral credential resolver reports source and state without returning plaintext to UI or diagnostics. The packaged store uses native per-user Windows DPAPI at `%LOCALAPPDATA%\ARX\credentials\openai-api.dpapi`. A protected blob that cannot be decrypted in the active Windows context produces `CREDENTIAL_UNREADABLE`, not `NOT_CONFIGURED` or `AUTHENTICATION_FAILURE`.

The explicit connection test sends no prompt or ARX evidence. It performs an authenticated HTTPS model-metadata request and reports one of:

```text
NO_CREDENTIAL
CREDENTIAL_UNREADABLE
NETWORK_FAILURE
TLS_HTTPS_FAILURE
AUTHENTICATION_FAILURE
RATE_LIMIT
QUOTA_EXHAUSTED
MODEL_NOT_AVAILABLE
TIMEOUT
CANCELLED
SERVER_FAILURE
PARSE_FAILURE
READY
```

Health claims use existing `Evidence` records. VALUE is the observed safe state/model/latency, PROVENANCE is `OBSERVED`, and BASIS identifies credential inspection, authenticated model metadata, local timing, or sanitized failure classification. The health decision separately records `VALIDATION = provider-health-state-v1`.

## OpenAI Responses transport

The OpenAI provider uses the supported Responses API at the exact allowlisted `https://api.openai.com/v1/responses` endpoint. Every advisory request repeats external-boundary redaction, enforces request and response bounds, sets a timeout, supports cancellation, places the credential only in the HTTPS authorization header, and sets `store` to `false`.

The provider never sends credentials in prompt bodies, URLs, command arguments, logs, reports, conversations, or deterministic exports. It sanitizes all displayed failures. OpenAI response text is `AI ADVISORY — NON-AUTHORITATIVE`; it has no write path to deterministic reports, Evidence, EvidenceKind, Machine DNA, Software DNA, Project DNA, compatibility, readiness, or semantic-invariant results.

## Transmission audit and uninstall

The real OpenAI HTTPS and Codex standard-input boundaries record only `REQUEST_PREPARED`, `OUTBOUND_REQUEST_INITIATED`, `RESPONSE_RECEIVED`, `REQUEST_FAILED`, or `CANCELLED`. Audit records contain safe metadata only and never prompt/response bodies, keys, authorization headers, URLs, full project paths, or secret values.

The audit is local-only, multi-process serialized, limited to 30 days, at most 600 events across three rotating 128,000-byte files, and never automatically exported or synchronized. Settings provides explicit history clearing; explicit metadata export reapplies redaction.

Uninstall does not silently delete `%LOCALAPPDATA%\ARX` because a machine-wide uninstaller must not guess which Windows users' data may be removed. Users can remove the protected OpenAI credential and clear audit history in Settings before uninstall, then deliberately remove the remaining ARX provider-data directory if complete local cleanup is desired.

## Review gate

The Phase B report must distinguish controlled/mock tests from live connectivity. A provider may be reported `READY` only if a real successful API request occurred with a securely resolved credential. The temporary plaintext import source must not be deleted without explicit user confirmation after protected import and live verification.

Phase C remains blocked until human approval. This phase does not add Ask Both, comparison, consensus, response ranking, synthesized answers, or any mechanism that feeds AI output into deterministic ARX conclusions.
