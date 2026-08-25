# Changelog

## Unreleased — Local AI Bridge
- Add a provider-neutral, loopback-only Local AI provider that reuses the immutable, bounded, redacted Phase C `AdvisoryContext` and existing Intelligence Console.
- Add explicit localhost profile configuration, bounded `/v1/models` discovery, first-run backend approval, typed hidden llama.cpp process launch, health/state supervision, cancellation, clean shutdown, and safe reconnect behavior.
- Add memory-only, expiring local session capabilities for explicitly compatible backend wrappers without persisting capability values in profiles, approvals, evidence, audit, or reports.
- Extend the ARX architecture gate with a `local_ai -> advisory` layer while preventing deterministic layers from acquiring Local AI or advisory dependencies.
- Preserve the published ARX 4.0.0 Beta 3 tag and assets unchanged; this work has no new release tag or Python-index publication.

## 4.0.0b3 - 2026-08-25
- Add the advisory-only ARX Intelligence Console with visibly separate deterministic evidence, contradictions, unknowns, provider status, redacted context, transcripts, and transmission-audit views.
- Add independent, bounded, memory-only OpenAI Chat and Codex CLI conversations with multiline input, send, retry, cancellation, new/clear conversation, selection, copying, and explicit saving.
- Add GENERAL CHAT with no ARX context and ARX EVIDENCE CHAT with explicit scope, attachment, redaction, preview, and per-provider/per-context consent.
- Add Ask Both for exactly two distinct providers with flat, unranked responses and a separate opt-in textual-overlap/differences/unresolved comparison that cannot create evidence or validation.
- Preserve the one-way provider boundary: advisory output cannot mutate Evidence, EvidenceKind, Machine DNA, Software DNA, Project DNA, compatibility, readiness, or semantic-invariant results.
- Extend bounded local Hypothesis coverage for Phase C contexts, conversations, comparisons, and nested truncation; make invalid NUL-containing `setup.py` metadata fail closed as UNKNOWN.
- Add Phase C-specific Semgrep and detect-secrets review identities without modifying historical Beta 2 evidence.
- Preserve the Beta 2 release-security, reproducible-build, SBOM, provenance, and future Authenticode architecture while keeping production signing and Windows lifecycle acceptance independent.

## 4.0.0b2 - 2026-08-24
- Repair the bounded Hypothesis audit harness and correct malformed PE and non-object `package.json` handling exposed once all security properties reached product code.
- Harden index-supplied artifact downloads with exact HTTPS host/port policy, credential-free URLs, redirect rejection and destination revalidation, bounded streaming, timeout, size, and SHA-256 enforcement.
- Add commit-derived `SOURCE_DATE_EPOCH`, deterministic portable ZIP construction, stable archive ordering/timestamps, and controlled PyInstaller/Inno Setup inputs without rewriting binary metadata after a build.
- Define a provider-neutral Authenticode policy and fail-closed verification layer while accurately keeping production signing blocked because no approved certificate or managed signing identity exists.
- Prepare defensive Windows 10/11 standard-user install, upgrade, launch, ACL, credential, and uninstall evidence collection; lifecycle execution remains blocked until disposable guests are available.
- Add a non-publishing security-gate workflow covering two dependency-advisory sources, bounded security regression, SAST, secrets, package integrity, and reproducible CycloneDX SBOM generation.
- Add GitHub OIDC artifact-attestation preparation for exact release bytes without retrofitting or changing the immutable Beta 1 assets.
- Add machine-validated public release-security and provenance record schemas that keep PASS, limitations, blocked, not-applicable, signature, reputation, SBOM, scanner, and reproducibility states independent.
- Preserve the Phase B deterministic/advisory boundary and keep the Phase C Intelligence Console outside this prerelease.

## 4.0.0b1 - 2026-08-24
- Extend `EvidenceKind` with ESTIMATED, SIMULATED, and STRUCTURAL while keeping VERIFIED out of fact provenance and preserving separate decision validation.
- Enforce the reviewed ARX dependency graph and cycle rejection in CI, including a forbidden-import FAIL → discard mutation → PASS regression proof.
- Add a provider-neutral credential resolver, developer `OPENAI_API_KEY` support, and native current-user Windows DPAPI storage with distinct `CREDENTIAL_UNREADABLE` handling.
- Add the visible `Settings → Intelligence Providers → OpenAI API` configuration/status surface with official Platform configuration, import, replace, remove, minimum-data connection test, existing-assistant launch, and explicit audit clearing.
- Harden the OpenAI Responses API transport with exact HTTPS endpoint validation, transport-boundary redaction, request/response bounds, timeout/cancellation, sanitized health categories, and no-secret request/audit behavior.
- Add bounded, rotating, local-only metadata transmission events for the real OpenAI HTTPS and Codex standard-input boundaries without prompt/response bodies or credentials.
- Keep OpenAI and Codex advisory output non-authoritative and one-way; no provider response can mutate deterministic ARX evidence, compatibility, readiness, or semantic validation.
- Preserve the existing `arx-prescanner` package identity while introducing the ARX 4 Beta 1 package, Windows, installer, artifact, and release-note identity.
- Separate GitHub release-asset construction from manual TestPyPI and production PyPI publication; preserve the existing Trusted Publisher environments and require a distinct explicit production target.
- Build into a clean version-scoped output directory, hash every public artifact, and scan tracked files and release artifacts without printing any matched secret material.
- Keep Phase C explicitly out of this beta: Ask Both, consensus, synthesis, ranking, expanded contextual conversation architecture, and the final Intelligence Console are not claimed.

## ARX 3 final acceptance baseline - 2026-08-24
- Correct the Phase A epistemic documentation and advisory prompt so `VERIFIED` is never presented as an `EvidenceKind`; baseline fact provenance was `DECLARED`, `OBSERVED`, `INFERRED`, or `UNKNOWN`, separate from decision validation.
- Audit every numeric confidence assignment and document the current values as uncalibrated detector-author weights rather than probabilities, measured accuracy, or statistical confidence.
- Record the ARX 4 baseline and Phase A acceptance evidence, including blocked visible DPI, screen-reader, isolated installer lifecycle, and code-signing gates.
- Keep ARX at `3.0.0rc1`; stable `v3.0.0` is not approved while those acceptance gates remain incomplete.

## 3.0.0rc1 - 2026-08-24
- Present ARX 3 as Project-Aware Compatibility Intelligence across package metadata, CLI text, the Windows application, portable resources, installer metadata, and public documentation.
- Complete the Windows desktop interaction layer with reusable selectable reports, contextual evidence/path actions, keyboard behavior, responsive background work, cancellation, errors, state handling, and lifecycle cleanup.
- Add the optional, explicit, bounded, redacted, cancellable ChatGPT/OpenAI and Codex CLI advisory bridge without allowing external output to become ARX evidence.
- Add privacy-aware web, exact-error, Google, and official-documentation research that remains in the user's browser and outside deterministic results.
- Add a stable-AppId Inno Setup installer around the validated portable payload, versioned RC ZIP/installer/checksum naming, and Windows version resources.
- Add the `arx-prescanner` Python distribution path with strict package validation, isolated installation checks, and tokenless TestPyPI-to-PyPI Trusted Publishing.
- Expand deterministic, cross-surface, GUI-isolated, packaging, documentation, workflow, and external-boundary security coverage across Windows and Linux CI.
- Add CodeQL analysis for Python and GitHub Actions with pinned actions and least-privilege permissions.
- Retain honest release-candidate limitations for real DPI/multi-monitor, screen-reader/accessibility, and full installer lifecycle acceptance; aggregate Definition of Done remains partial.

## 2.0.0 - 2026-08-10
- Promote ARX to Project-Aware Semantic Compatibility Intelligence with a locked canonical project-readiness domain.
- Implement Python project semantic intelligence across CLI, desktop, Evidence Inspector, and AI Contract 0.2 output.
- Harden typed requirement provenance, provider roles and health, execution-context satisfaction, recoverability, invariant checks, schemas, and cross-surface consistency.
- Add Phase II matched-arm benchmark infrastructure with empty evidence containers and an explicit no-claims gate; no efficiency savings are claimed.
- Preserve AI Contract schema 0.2 and the legacy machine/software schema 0.1.
- Publish a Windows x64 portable desktop build and checksums.

## 0.3.0 - 2026-08-10
- Lock the project semantic domain with typed requirement evidence, a capability-grouped requirement graph, explicit current-context satisfaction/recoverability, account-scoped context fingerprinting, and construction/AI-contract contradiction guards.
- Add bounded static Python Project DNA for `pyproject.toml`, `.python-version`, `uv.lock`, `setup.cfg`, static `setup.py` metadata, and supported requirements files.
- Add typed requirement/provider graphs, execution contexts, and context-scoped Python resolution.
- Keep availability, resolution, compatibility, relevance, satisfaction, severity, and remediation separate.
- Add explicit conflicts, unknown handling, stable finding IDs, GREEN/YELLOW/RED severity, safe policy defaults, recommendation-only planning, and explanation graphs.
- Add redacted project-aware AI contract schema 0.2 while preserving legacy schema 0.1 reports.
- Add `project`, `resolve`, and `preflight` commands plus `codex --project` without removing ARX 0.2 commands.
- Add desktop Project Preflight and Project Readiness views with textual status and Evidence Inspector integration.
- Cover Python semantic cases A-H, manifest security boundaries, privacy, schemas, CLI, and desktop behavior.
- Harden resolved/compatible/pinned/preferred roles, provider health/architecture/scope, Windows command/context divergence, recoverable provider-state changes, semantic aggregation, freshness metadata, and cross-surface consistency.

## 0.2.0 - 2026-08-10
- Add a responsive, dark-themed Windows desktop interface for Machine DNA, capabilities, Software DNA, compatibility, evidence, and redacted exports.
- Represent multiple Python installations independently and preserve Java/JBR and MSBuild discovery in the desktop dashboard.
- Distinguish PE CLR headers from application-level .NET evidence in neighboring runtime artifacts.
- Add Windows x64 standalone packaging and portable release validation support.

## 0.1.1 - 2026-08-09
- Discover Visual Studio MSBuild with `vswhere` and Android/CUDA tools from SDK roots.
- Add explicit extension protocols and JSON, text, and Codex exporter modules.
- Infer runtime indicators and declared Node engine requirements from bounded manifest reads.
- Conservatively evaluate simple numeric version constraints and preserve unknown ranges.
- Expand Windows OS metadata and static-scanner regression coverage.

## 0.1.0 - 2026-08-09
- Initial Machine DNA, Software DNA, capability graph, compatibility engine, reports, and CLI.
