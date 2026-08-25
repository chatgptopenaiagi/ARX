# AI assistance and external-boundary security

ARX remains the deterministic evidence authority, safe local observer, and project-aware compatibility engine. AI and public web research are optional investigation instruments controlled by the user. External intelligence cannot modify the workstation or become ARX evidence.

## Three trust domains

1. **ARX deterministic local evidence** is produced by bounded static reads, fixed diagnostics, and the canonical compatibility/project engines.
2. **External AI advice** receives a deliberately selected, bounded, redacted packet only after a visible user action and provider consent. Responses are labeled `AI ADVISORY — NON-AUTHORITATIVE` and identify the actual provider.
3. **Public web search** receives only a short redacted, URL-encoded query after the user selects a search command. Search results stay in the browser and outside ARX evidence.

Information never crosses these boundaries automatically. AI output cannot assign or change an `EvidenceKind`, claim semantic/schema validation, set GREEN/YELLOW/RED state, change compatibility or readiness, or execute a recommendation. There is no return path from an OpenAI or Codex response into Machine DNA, Software DNA, Project DNA, or deterministic findings.

## Context selection, preview, and redaction

The Phase C Intelligence Console constructs context from an explicit allowlist: the selected finding, relevant evidence, Machine DNA, Software DNA, Project DNA, deterministic conclusions, contradictions, and unknowns. Each section is independently selectable. The resulting packet remains capped at 16,000 characters and at most eight relevant evidence records, with smaller per-section and per-field budgets. ARX does not send the complete raw Machine DNA report, arbitrary project files, browser state, Wi-Fi credentials, private keys, credential stores, or unrelated file contents.

The console provides visible `View Redacted Context` and `Preview What Will Be Sent` actions. Opening the console, Settings, provider status, either preview, or transmission history performs no OpenAI request. Before the actual provider transport boundary, ARX redacts the selected packet again and enforces its serialized size bound. It removes sensitive field values and recognizable API keys, bearer tokens, GitHub tokens, JWTs, password/token assignments, usernames, control characters, private roots, user-profile paths, and arbitrary absolute local paths. Project roots use `%PROJECT_ROOT%`, the active profile uses `%USERPROFILE%`, and other local paths use `%LOCAL_PATH%` where appropriate.

GENERAL CHAT explicitly carries no ARX machine, software, project, finding, compatibility, or readiness context. ARX EVIDENCE CHAT requires a visible attach action, preview capability, and per-provider/per-context consent. Changing the context identifier requires new consent. Packets are recursively detached from mutable controller objects before a provider receives them.

Copying or saving context, prompts, responses, and conversations reapplies external-boundary redaction. Users should still review exported material before sharing it because no finite redactor can recognize every domain-specific secret.

## OpenAI API credential boundary

The internal provider and settings name is **OpenAI API**. The conversational surface may be labeled **OpenAI Chat**. ARX uses the supported API and does not automate, scrape, or control the ChatGPT website or desktop application. A ChatGPT subscription is not treated as an API credential.

OpenAI documents that API keys must not be committed or exposed and recommends environment variables or a protected secret-management mechanism. ARX supports two sources:

- developer sessions may provide `OPENAI_API_KEY` in the current process environment;
- the packaged Windows application stores a credential in `%LOCALAPPDATA%\ARX\credentials\openai-api.dpapi` after protecting it with native Windows DPAPI for the current user. ARX does not invent cryptography.

The desktop path is `Settings → Intelligence Providers → OpenAI API`. `Configure OpenAI API Key` opens the fixed official OpenAI Platform API-key page. ARX never creates a key itself. `Import OpenAI API Key` and `Replace Credential` read one small regular local file only inside the import boundary, validate one key, immediately DPAPI-protect it, verify the protected store, and zero the mutable import buffers. After import, the UI reports only safe state and never offers a show-key action. `Remove Credential` deletes only the ARX-owned protected blob; it cannot remove a process environment variable.

The plaintext import source is deliberately not deleted automatically. After a successful connection test, the user should delete that temporary file through an intentional local action. This avoids a silent destructive operation against a user-selected file.

Credential states remain distinct:

- `NOT_CONFIGURED`: no usable process or stored credential exists;
- `CONFIGURED`: a credential exists and can be leased at the credential boundary; this alone does **not** mean the provider is ready;
- `CREDENTIAL_UNREADABLE`: an ARX protected blob exists but cannot be decrypted in the current Windows context.

For the last state, ARX displays: “A saved OpenAI credential exists but cannot be decrypted in the current Windows context. Reconfigure or remove the stored credential.” It is never collapsed into missing configuration or authentication rejection.

The plaintext credential is leased only around construction and execution of the authenticated HTTPS request. It is put only in the `Authorization` header and never in a prompt, request body, URL, command-line argument, JSON setting, ARX report/state, conversation file, diagnostic, crash message, audit event, clipboard action, or repository file. Python cannot guarantee erasure of every interpreter-managed temporary string; ARX therefore minimizes lifetime and removes the authorization header from its request object immediately after the transport returns.

## Provider health and OpenAI transport

`Test Connection` is the only automatic health action in Settings, and it occurs only after a direct mouse click. It sends no machine, project, finding, evidence, prompt, or conversation content. It performs the minimum authenticated HTTPS `GET /v1/models/{model}` operation documented by OpenAI, then validates the returned model identifier. A successful result supports separate safe UI states for Credential, Authentication, API, Model, and Overall. A configured credential is not provider readiness; merely opening Settings or finding a credential never produces `READY`.

Operational health distinguishes `NO_CREDENTIAL`, `CREDENTIAL_UNREADABLE`, `NETWORK_FAILURE`, `TLS_HTTPS_FAILURE`, `AUTHENTICATION_FAILURE`, `RATE_LIMIT`, `QUOTA_EXHAUSTED`, `MODEL_NOT_AVAILABLE`, `TIMEOUT`, `CANCELLED`, `SERVER_FAILURE`, `PARSE_FAILURE`, and `READY`. Health keeps only safe category, model, latency, check time, and sanitized message. Its supporting claims use the existing `Evidence` model with VALUE, provenance, and BASIS; the composed health decision identifies `provider-health-state-v1` validation separately. Numeric claim confidence is an uncalibrated detector-author weight, not a probability or measured accuracy.

Advisory requests use the supported OpenAI Responses API endpoint `POST https://api.openai.com/v1/responses`. ARX validates the exact HTTPS host, rejects redirects, puts the key only in the authorization header, sends the already selected/redacted/bounded input, limits output, and sets `store` to `false`. The request parser handles supported `output_text` content and fails closed on malformed or empty output. See the official [Responses create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), [model retrieval reference](https://developers.openai.com/api/reference/typescript/resources/models/methods/retrieve), and [API key safety guidance](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

Cancellation stops ARX waiting and ignores a late response. With the current standard-library HTTPS transport, it cannot retract data after the remote service has already received the request. The transmission audit therefore distinguishes an outbound request from a response. Timeout, authentication, quota, rate-limit, unavailable-model, server, TLS/network, cancellation, and parse failures become bounded sanitized categories.

## Metadata-only transmission audit

Logging occurs where the OpenAI HTTPS request or Codex standard-input handoff actually crosses the provider boundary. Events use transport states rather than a misleading sent boolean:

- `REQUEST_PREPARED`
- `OUTBOUND_REQUEST_INITIATED`
- `RESPONSE_RECEIVED`
- `REQUEST_FAILED`
- `CANCELLED`

The audit stores only timestamp, random attempt identifier, provider identifier, operation, state, configured model where applicable, byte counts, elapsed milliseconds, and a sanitized error category. It never stores the API key, authorization header, prompt/response body, URL, full project path, or secret value.

Audit data is sensitive behavioral metadata. It remains local at `%LOCALAPPDATA%\ARX\audit\external-transmissions.jsonl`, is serialized across local ARX processes, retains at most 30 days, and rotates across at most three 128,000-byte files with no more than 200 events per file. Settings provides an explicit `Clear History` action. There is no implicit export, automatic ARX cloud synchronization, or inclusion in deterministic evidence exports. The internal explicit-export function reapplies redaction before writing a user-chosen metadata file.

The Windows installer does not silently remove per-user provider data during uninstall. A user who wants complete provider-data removal should use `Remove Credential` and `Clear History` before uninstalling, or deliberately remove the `%LOCALAPPDATA%\ARX` provider-data directory afterward. This behavior avoids deleting another Windows user's data or unrelated files from a machine-wide uninstaller.

## Codex CLI provider

ARX detects the official Codex CLI with executable lookup and verifies availability with an explicit `codex --version` argument array. Advisory execution uses the documented non-interactive `codex exec` interface with:

- prompt input through standard input, never the command line;
- `--sandbox read-only` and `--ephemeral`;
- `--ignore-user-config`, `--color never`, and `--skip-git-repo-check`;
- an empty temporary working directory rather than the inspected project;
- `shell=False`, hidden process creation on Windows, bounded output, timeout, terminate, and kill fallback.

The selected project is not granted to Codex as a working directory, so the process sees only the already filtered prompt by default. ARX never simulates typing into a terminal. A missing or unauthenticated Codex installation produces a provider explanation, not an application failure. Codex remains usable when OpenAI is not configured and OpenAI remains optional when Codex is absent.

## Phase C conversations and Ask Both

OpenAI Chat and Codex CLI keep independent, memory-only sessions. Each session retains at most 16 turns and 24,000 characters; provider prompts use a smaller recent subset. Switching providers never transmits one provider's history to the other. New Conversation and Clear Conversation operate only on the selected provider session. Saving is an explicit user action and reapplies redaction.

Ask Both requires exactly two distinct provider identities. Each receives the same approved context and question, plus only its own bounded prior turns. The default result contains two flat, unranked panels. Comparison is hidden until the user explicitly chooses `Compare Responses`; it then shows only textual overlap, differences, and unresolved statements under `COMPARISON AID — NO EVIDENCE UPGRADE`. No comparison output is written to Evidence, provenance, compatibility, readiness, or validation state.

## Web research and release boundary

Web, Google, exact-error, and official-documentation commands build concise queries from the selected finding. Generated URLs are limited to allowlisted HTTPS search endpoints and opened in the user's default browser. ARX does not fetch, scrape, summarize, or import the result page.

GitHub CI runs deterministic pytest coverage on Windows and Linux across the declared Python support range, verifies source and wheel builds without publishing from CI, and runs CodeQL for Python and Actions. External-provider functionality does not grant publishing, release, signing, cloud-sync, or deployment authority; those remain separate workflows and human decisions.
