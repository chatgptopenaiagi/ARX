# ARX 4.0.0 Beta 4

Package version: `4.0.0b4`

Artifact version: `4.0.0-b4`

Windows file/product version: `4.0.0.4`

Git tag: `v4.0.0-b4`
Release channel: GitHub prerelease; not ARX 4 stable

ARX 4.0.0 Beta 4 adds the optional Local AI Bridge to the completed Phase C Intelligence Console. It does not modify the immutable Beta 1, Beta 2, or Beta 3 releases.

## Deterministic authority remains unchanged

ARX still owns Machine DNA, Software DNA, Project DNA, compatibility/readiness decisions, semantic-invariant results, and their evidence. The fact-provenance enum remains exactly:

`DECLARED / OBSERVED / INFERRED / ESTIMATED / SIMULATED / STRUCTURAL / UNKNOWN`

`VERIFIED` remains outside `EvidenceKind`. It may describe only an actual relation, schema, invariant, or composed-state validation. Current numeric confidence values remain uncalibrated detector-author weights, not probabilities, measured accuracy, or statistical confidence.

Every AI surface is visibly labeled:

> AI ADVISORY — NON-AUTHORITATIVE

There is no response path into deterministic ARX objects. OpenAI, Codex CLI, and Local AI output cannot modify Evidence, EvidenceKind, Machine DNA, Software DNA, Project DNA, compatibility, readiness, severity, scanner conclusions, or provenance ancestry.

## Local AI Bridge

Beta 4 adds a provider-neutral localhost bridge through the existing advisory interface:

- explicit loopback-only endpoint profiles; wildcard, LAN, public, credential-bearing, query, and fragment URLs are rejected;
- bounded `/v1/models` discovery with redirects rejected, ambient proxies disabled, and malformed metadata rejected;
- endpoint-only OpenAI-compatible profiles and an approved typed llama.cpp launch profile;
- direct process creation with fixed typed arguments, `shell=False`, and no model-generated command execution;
- hidden Windows process launch, lifecycle supervision, cancellation, disconnect, and clean shutdown behavior;
- explicit first-run approval for managed backends and exact-profile approval fingerprints;
- GUIDED, BALANCED, EXPERT, and AUTOMATED assistance policies that describe interaction rather than human ability;
- memory-only, expiring session capabilities for explicitly compatible wrappers, never persisted in evidence, profiles, reports, audit, URLs, or command-line arguments;
- explicit operational and failure states, kept separate from evidence provenance;
- reuse of the same bounded, redacted `AdvisoryContext`, preview, consent, and metadata-only transmission audit as remote providers.

ARX never scans arbitrary networks or filesystems for a model server, never binds a managed backend to `0.0.0.0`, and does not bundle or silently download a model.

## Phase C retained

The Phase C Intelligence Console remains available with:

- GENERAL CHAT, which attaches no ARX state;
- ARX EVIDENCE CHAT, with selected scope, `REDACTED + BOUNDED` state, local context preview, and explicit consent;
- independent, bounded OpenAI Chat and Codex CLI conversations;
- visible provider identity and explicit health/failure status;
- Ask Both with exactly two distinct provider identities and two flat, unranked responses;
- an opt-in comparison limited to TEXTUAL OVERLAP, DIFFERENCES, and UNRESOLVED, labeled `COMPARISON AID — NO EVIDENCE UPGRADE`;
- local, bounded, rotated, metadata-only transmission history with explicit clearing.

Local AI is a separate single-provider console path in this release. It does not silently change the reviewed two-provider Ask Both contract into ranking, consensus, or synthesis.

OpenAI Chat continues to use the supported OpenAI Responses API and Windows current-user DPAPI credential boundary. Codex CLI remains independent. ARX remains useful without an AI provider, API credential, local model, or network connection.

## Observed real-backend validation

The bridge was validated on 2026-08-25 against an externally running Windows x64 `llama-server`.

Live validation classification: **PASS WITH LIMITATION**.

- server version: `0.1.2-dev`;
- build: `10545`;
- commit: `a30273376`;
- model: `Qwen/Qwen3-4B-GGUF:Q4_K_M`;
- endpoint class: literal IPv4 loopback (`http://127.0.0.1:8080`);
- `/v1/models`: successful, bounded model discovery;
- provider state: READY;
- advisory transport and response parser: successful;
- lifecycle: BUSY → READY and clean ARX disconnect;
- external process ownership: retained; ARX did not terminate a process it did not launch;
- transmission audit: metadata-only expected events;
- deterministic state: no mutation;
- product-code change required by validation: none.

This is OBSERVED integration-validation evidence, not AI advisory content and not a universal compatibility claim. The model response body is deliberately excluded. The external server configuration accepted unauthenticated loopback requests and exposed broad CORS behavior; this is an observed property of that manually launched backend, not an ARX trust upgrade. The ordinary llama.cpp endpoint did not provide an ARX-compatible capability wrapper, so live capability enforcement was not proven. Mid-flight cancellation was not reliably observable because the local response completed too quickly; pre-transmission cancellation and deterministic cancellation behavior remain separately tested.

## Release and supply-chain continuity

Beta 4 retains the architecture dependency gate, forbidden-import mutation proof, tracked-secret and release-privacy scans, Bandit/Semgrep classification, CodeQL, dependency advisory checks, bounded Hypothesis campaign, CycloneDX SBOM generation, deterministic archive controls, release provenance interfaces, GitHub Artifact Attestations, Authenticode verification policy, and human-gated publication design.

The GitHub release bundle is designed to contain the reviewed wheel, source distribution, portable ZIP, installer, CycloneDX SBOM, reproducibility record, security-gate record, signing record, lifecycle record, provenance bundle, release notes, and final SHA-256 manifest.

## Limitations and independent gates

- Real integration covered one llama.cpp/Qwen configuration; it does not establish universal local-backend or model compatibility.
- AI output can be incomplete, wrong, outdated, or unsafe; users must evaluate it against ARX evidence and official documentation.
- No finite redactor can identify every domain-specific secret; scope selection, preview, and consent remain material controls.
- Cancellation cannot retract bytes already accepted by a provider.
- A health check does not prove a generation will fit available RAM/VRAM or complete successfully.
- Windows 10/11 visible accessibility, DPI/multi-monitor, SmartScreen/Smart App Control, and complete standard-user install/upgrade/uninstall lifecycle observations remain independent manual gates unless direct evidence is recorded for this candidate.
- No approved production code-signing identity is configured. Candidate Windows binaries are `UNSIGNED_EXPECTED_PRE_SIGNING`; hashes, SBOMs, malware scans, and provenance do not substitute for Authenticode publisher identity or SmartScreen reputation.
- TestPyPI and production PyPI publication are separate, explicitly authorized workflows and are not implied by this GitHub prerelease.

ARX passed only the defined gates reported by the final candidate validation record. This document does not claim that ARX is secure, that unsigned binaries are publisher-trusted, or that blocked manual gates passed.
