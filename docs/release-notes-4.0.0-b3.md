# ARX 4.0.0 Beta 3

Package version: `4.0.0b3`

Artifact version: `4.0.0-b3`

Git tag: `v4.0.0-b3`
Release channel: GitHub prerelease; not ARX 4 stable

ARX 4.0.0 Beta 3 adds the Phase C Intelligence Console without changing the deterministic compatibility engine or the immutable Beta 1 and Beta 2 releases.

## Deterministic authority is unchanged

ARX still owns Machine DNA, Software DNA, Project DNA, compatibility/readiness decisions, semantic-invariant results, and their evidence. The fact-provenance enum remains exactly:

`DECLARED / OBSERVED / INFERRED / UNKNOWN / ESTIMATED / SIMULATED / STRUCTURAL`

`VERIFIED` remains outside `EvidenceKind`. It may describe only an actual relation, schema, invariant, or composed-state validation. Current numeric confidence values remain uncalibrated detector-author weights, not probabilities, measured accuracy, or statistical confidence.

Every AI surface is visibly labeled:

> AI ADVISORY — NON-AUTHORITATIVE

There is no response path into deterministic ARX objects. Provider output cannot modify Evidence, EvidenceKind, Machine DNA, Software DNA, Project DNA, compatibility, readiness, severity, scanner conclusions, or provenance ancestry.

## Intelligence Console

The Windows desktop now provides an Intelligence menu and contextual finding actions that reuse one bounded console. The console includes:

- structured local views for evidence, contradictions, and unknowns;
- independent OpenAI Chat and Codex CLI sessions;
- a multiline input editor, Send, Retry, Stop / Cancel, New Conversation, Clear Conversation, selection, Copy Response, Copy Conversation, and explicit Save Conversation;
- provider identity, safe availability/operational state, and explicit failure presentation;
- GENERAL CHAT, which attaches no ARX machine, software, project, compatibility, readiness, finding, or evidence context;
- ARX EVIDENCE CHAT, with visible attachment identity, evidence count, `REDACTED + BOUNDED` state, scope controls, local preview, and explicit consent;
- View Redacted Context, View Evidence, Preview What Will Be Sent, web search, and official-documentation search;
- local metadata-only transmission history inspection and explicit Clear History.

OpenAI Chat uses the supported OpenAI Responses API. It does not automate the ChatGPT application or website. The existing provider-neutral credential resolver and Windows current-user DPAPI store remain the credential boundary. Codex CLI remains a separate local provider and its account state is not OpenAI API authentication.

ARX remains useful without an AI provider, API credential, Codex CLI, or network connection.

## Bounded advisory context

The context builder starts from an explicit allowlist: selected finding, relevant evidence, Machine DNA, Software DNA, Project DNA, deterministic conclusions, contradictions, and unknowns. It detaches those projections from mutable canonical state, recursively redacts them, applies deterministic section/item limits, preserves evidence provenance and validation basis, and rejects any packet that cannot satisfy the final 16,000-character context limit.

Opening the console, Settings, provider status, the context inspector, prompt preview, or transmission history does not contact a provider. ARX evidence requires a deliberate attach action and consent for each provider/context identity. Redaction and request bounds run again at the actual OpenAI HTTPS or Codex standard-input boundary.

Recognizable credentials, Authorization values, tokens, DPAPI blobs, private keys, password/cookie assignments, user names, private roots, full local paths, arbitrary environment variables, unrestricted files, prompts, and response bodies are excluded from transmission-audit records. Useful location placeholders include `%USERPROFILE%`, `%PROJECT_ROOT%`, and `%LOCAL_PATH%`.

## Ask Both and comparison

Ask Both requires exactly two distinct configured provider identities. Both receive the same explicitly approved context and question, while each receives only its own bounded prior conversation. The default UI presents exactly two flat, unranked provider panels.

There is no winner, provider ranking, consensus halo, confidence boost, green consensus state, or synthesized authoritative answer. Similar model output is not independent verification.

Only an explicit **Compare Responses** action reveals deterministic presentation aids:

- TEXTUAL OVERLAP;
- DIFFERENCES;
- UNRESOLVED.

The comparison is labeled `COMPARISON AID — NO EVIDENCE UPGRADE`. It is not Evidence, provenance, validation, compatibility, or readiness.

## Provider and audit behavior

The OpenAI provider preserves distinct operational states for no credential, `CREDENTIAL_UNREADABLE`, network/TLS failure, authentication failure, rate limit, `QUOTA_EXHAUSTED`, unavailable model, timeout, cancellation, server failure, parse failure, and READY. Authentication/model health may be READY while paid advisory generation later fails because the API project has no generation quota; ARX does not call that an authentication failure.

The real provider boundaries record only:

- `REQUEST_PREPARED`;
- `OUTBOUND_REQUEST_INITIATED`;
- `RESPONSE_RECEIVED`;
- `REQUEST_FAILED`;
- `CANCELLED`.

The audit remains local, metadata-only, bounded, rotated, retained for at most 30 days, explicitly clearable, absent from deterministic exports, and never synchronized by ARX.

## Security and release-trust continuity

Beta 3 retains the Beta 2 dependency graph gate, forbidden-import mutation proof, index-download hardening, tracked-secret and release-privacy scans, Bandit/Semgrep classification, CodeQL, dependency advisory checks, bounded Hypothesis campaign, CycloneDX SBOM generation, deterministic archive controls, release provenance interfaces, Authenticode verification policy, and human-gated publication design.

The Phase C fuzz campaign additionally covers immutable/bounded context construction, conversation retention, and comparison bounds. A NUL-containing `setup.py` is now classified as UNKNOWN by the static parser instead of escaping as an unhandled `ValueError`; project code remains unexecuted.

## Limitations and independent gates

- AI output can be incomplete, wrong, outdated, or unsafe; users must evaluate it against ARX evidence and official documentation.
- No finite redactor can identify every domain-specific secret; scope selection, preview, and consent remain material controls.
- Cancellation stops ARX waiting and ignores late results but cannot retract bytes already accepted by a provider.
- A health check does not perform or guarantee advisory generation and does not prove quota.
- Windows 10/11 visible accessibility, DPI/multi-monitor, SmartScreen/Smart App Control, and complete standard-user install/upgrade/uninstall lifecycle observations remain independent manual gates unless direct evidence is recorded for this candidate.
- No approved production code-signing identity is configured. Candidate Windows binaries are `UNSIGNED_EXPECTED_PRE_SIGNING`; SHA-256, SBOMs, malware scans, and provenance do not substitute for Authenticode publisher identity.
- A valid future signature would not itself establish SmartScreen reputation.
- TestPyPI and production PyPI publication are separate, explicitly authorized workflows and are not implied by a GitHub prerelease.

ARX passed only the defined gates reported by the final candidate validation record. This document does not claim that ARX is secure, that unsigned binaries are publisher-trusted, or that blocked manual gates passed.
