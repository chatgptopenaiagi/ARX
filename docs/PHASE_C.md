# ARX 4 Phase C — Intelligence Console

Phase C adds an optional, bounded advisory console to the ARX desktop application. It does not replace the deterministic compatibility engine. ARX remains useful without an AI provider, an OpenAI API credential, Codex CLI, or network access.

The persistent UI notice is:

> AI ADVISORY — NON-AUTHORITATIVE

AI responses may interpret an explicitly approved projection of ARX data. They cannot modify deterministic ARX evidence, compatibility, readiness, or the workstation.

## What Phase C is

The Intelligence Console provides:

- independent in-session OpenAI Chat and Codex CLI conversations;
- multi-turn transcripts, a multiline message editor, Send, Stop / Cancel, Retry, New Conversation, Clear Conversation, copying, selection, and safe saving;
- GENERAL CHAT, which attaches no ARX evidence;
- ARX EVIDENCE CHAT, which attaches only the enabled context sections;
- visible provider identity, availability, operational status, and failure status;
- an inspectable redacted context preview before transmission;
- explicit per-provider and per-context consent before ARX evidence crosses the provider boundary;
- explicit context attach, detach, and scope controls;
- metadata-only transmission-audit inspection and explicit clearing;
- Ask Both when exactly two distinct providers are configured;
- an explicit Compare Responses action limited to textual overlap, differences, and unresolved statements.

The desktop projects already computed Machine DNA, Software DNA, Project DNA, compatibility/readiness conclusions, contradictions, unknowns, and supporting evidence. Projection is presentation work: it does not recompute or replace canonical decisions.

## What Phase C is not

Phase C is not a second evidence engine, an autonomous remediation engine, a ChatGPT desktop/web automation layer, or an AI verification system. It does not:

- add AI text to `Evidence`;
- change `EvidenceKind`;
- modify Machine DNA, Software DNA, or Project DNA;
- modify compatibility, readiness, deterministic findings, severity, or semantic-invariant results;
- execute an AI recommendation;
- rank providers or choose a winner;
- synthesize two responses into an authoritative answer;
- interpret similar provider wording as consensus or independent verification;
- persist chat transcripts or model context automatically;
- require an AI provider for normal ARX operation.

There is deliberately no return path from a provider response into `DesktopController` or the canonical ARX model.

## Evidence and validation semantics

The fact-provenance enum remains exactly:

`DECLARED / OBSERVED / INFERRED / UNKNOWN / ESTIMATED / SIMULATED / STRUCTURAL`

`VERIFIED` is not an `EvidenceKind`. Verification belongs only to a relation, schema, semantic invariant, or composed decision where the implementation actually performs that validation.

Evidence records retain VALUE, PROVENANCE, and BASIS through their existing `value`, `kind`, `source`, `method`, `confidence`, and `note` fields. Decision projections carry their validation basis separately. Current numeric confidence values remain uncalibrated detector-author weights, not probabilities, measured accuracy, or statistical confidence.

An advisory may quote an attached record such as `Python 3.13 [OBSERVED]`. Any explanation it adds remains AI interpretation. The explanation does not inherit `OBSERVED`, create `VERIFIED`, or change GREEN/YELLOW/RED state.

## Bounded context builder

The deterministic context builder uses an explicit allowlist:

- selected finding;
- relevant evidence;
- Machine DNA;
- Software DNA;
- Project DNA;
- deterministic conclusions;
- contradictions;
- unknowns.

Every section can be enabled or disabled before sending. The builder detaches the packet from mutable controller objects, recursively makes the packet immutable, reapplies external-boundary redaction, and applies fixed limits:

- 16,000 characters for the serialized ARX context;
- 2,000 characters for an ordinary text field;
- at most eight relevant evidence records;
- section-specific budgets;
- bounded contradiction and unknown lists.

Redaction preserves useful placeholders including `%USERPROFILE%`, `%PROJECT_ROOT%`, and `%LOCAL_PATH%`. It removes or replaces credential-shaped fields, API keys, bearer tokens, GitHub tokens, JWTs, password/token assignments, usernames, control characters, and local absolute paths. No credential, environment dump, DPAPI blob, private key, token, arbitrary project file, or unrestricted filesystem content is selected.

The user can choose **View Redacted Context** or **Preview What Will Be Sent** without causing a request. Redaction and request-size enforcement run again at each provider transport boundary.

## General Chat and ARX Evidence Chat

GENERAL CHAT constructs a context packet that explicitly says `NO ARX EVIDENCE ATTACHED`. Its provider prompt contains no machine, software, project, finding, compatibility, or readiness payload. The user's Send action is the only trigger.

ARX EVIDENCE CHAT displays the context identifier, finding, status, evidence count, and `REDACTED + BOUNDED` state. A distinct mouse action attaches the current selection. Consent is remembered only for the same provider and context identifier during the current ARX process. Changing context creates a different identifier and therefore requires new consent.

## Conversations

OpenAI Chat and Codex CLI keep independent conversations. Switching providers never supplies one provider's turns to the other provider. Each in-memory provider session retains at most 16 turns and 24,000 characters. A provider prompt uses only the most recent bounded subset. Conversation state is not written to ARX reports, evidence files, configuration, or credential storage.

Copy and save paths reapply redaction. A user-initiated save is an advisory text export, not an ARX evidence export.

## Providers

### OpenAI API

The UI surface is named **OpenAI Chat**; the provider and configuration identity is **OpenAI API**. ARX uses the supported OpenAI Responses API and never automates the ChatGPT application or website. The existing Phase B credential resolver continues to support the current-process `OPENAI_API_KEY` for developer sessions and Windows per-user DPAPI storage for the packaged application.

Requests use the exact allowlisted HTTPS endpoint, reject redirects, use timeouts and cancellation, bound input/output, set `store: false`, and place the credential only in the Authorization header for the minimum practical lifetime. Bounded recent conversation turns are supplied in the redacted request; ARX does not silently transmit unlimited history.

A successful model health lookup means authentication, API access, and configured model access were observed for that lookup. It does not prove generation quota. A later advisory may still fail with `QUOTA_EXHAUSTED`; ARX does not relabel that as authentication failure.

### Codex CLI

Codex CLI remains a separate local provider. Its local authentication is not OpenAI API authentication. ARX invokes the supported non-interactive CLI through a fixed argument array, standard input, a read-only ephemeral sandbox, a temporary working directory, bounded output, timeout, cancellation, and `shell=False`.

OpenAI can remain unavailable while Codex works, and Codex can remain unavailable while OpenAI works. Neither provider's failure is an ARX Core failure.

## Ask Both

Ask Both requires exactly two distinct configured provider identities. It gives both providers the same explicitly approved context and question, while each provider receives only its own bounded prior conversation.

The default result is two flat panels. Each panel identifies its provider and its own completion or failure state. There is no winner, ranking, confidence boost, green consensus indicator, or synthesized authoritative answer.

Comparison is hidden by default. Only the explicit **Compare Responses** action reveals:

- TEXTUAL OVERLAP;
- DIFFERENCES;
- UNRESOLVED.

The comparison is labeled `COMPARISON AID — NO EVIDENCE UPGRADE`. It is deterministic presentation analysis of response text, not Evidence, provenance, validation, readiness, or compatibility.

## Transmission audit

The real OpenAI HTTPS and Codex standard-input boundaries retain the Phase B transport states:

- `REQUEST_PREPARED`;
- `OUTBOUND_REQUEST_INITIATED`;
- `RESPONSE_RECEIVED`;
- `REQUEST_FAILED`;
- `CANCELLED`.

The audit contains metadata only: time, attempt/provider/operation identity, model where relevant, byte counts, latency, and sanitized error category. It stores no prompt, response, credential, Authorization header, secret, raw URL, full path, or `SENT=true` claim.

History remains local under `%LOCALAPPDATA%\ARX\audit`, retained for at most 30 days, rotated across bounded files, and absent from deterministic exports. It has explicit inspection and Clear History actions, no implicit export, no automatic ARX cloud synchronization, and no implicit deletion during ordinary application cleanup.

## Failure and offline behavior

The console presents provider-specific missing configuration, unreadable credential, unavailable executable, network/TLS, authentication, quota, rate-limit, unavailable-model, timeout, cancellation, service, and parse failures. A cancelled operation remains `CANCELLED`; an outbound request is not relabeled `RESPONSE_RECEIVED` unless a response arrived.

ARX Core scanning, Software DNA, Project DNA, compatibility, readiness, evidence inspection, report export, and local search-context preparation continue to work when every AI provider is unavailable.

## Security and privacy limitations

No finite redactor can identify every domain-specific secret. The context preview and explicit consent are therefore material controls, not decorative steps. Users should select the smallest relevant scope and review placeholders before transmission.

Cancellation stops ARX waiting and ignores late results. The standard-library HTTPS transport cannot retract bytes that a remote service has already received. The audit preserves that distinction.

AI output can be incorrect, outdated, or unsafe. The user remains responsible for evaluating advice against deterministic ARX evidence and official documentation. Phase C does not claim AI independence, statistical confidence, or security certification.
