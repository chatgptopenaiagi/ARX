# Changelog

## Unreleased — ARX 4 Phase B trust foundation
- Extend `EvidenceKind` with ESTIMATED, SIMULATED, and STRUCTURAL while keeping VERIFIED out of fact provenance and preserving separate decision validation.
- Enforce the reviewed ARX dependency graph and cycle rejection in CI, including a forbidden-import FAIL → discard mutation → PASS regression proof.
- Add a provider-neutral credential resolver, developer `OPENAI_API_KEY` support, and native current-user Windows DPAPI storage with distinct `CREDENTIAL_UNREADABLE` handling.
- Add the visible `Settings → Intelligence Providers → OpenAI API` configuration/status surface with official Platform configuration, import, replace, remove, minimum-data connection test, existing-assistant launch, and explicit audit clearing.
- Harden the OpenAI Responses API transport with exact HTTPS endpoint validation, transport-boundary redaction, request/response bounds, timeout/cancellation, sanitized health categories, and no-secret request/audit behavior.
- Add bounded, rotating, local-only metadata transmission events for the real OpenAI HTTPS and Codex standard-input boundaries without prompt/response bodies or credentials.
- Keep OpenAI and Codex advisory output non-authoritative and one-way; no provider response can mutate deterministic ARX evidence, compatibility, readiness, or semantic validation.

## Unreleased — ARX 3 final acceptance baseline
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
