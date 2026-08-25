# ARX 4

[![ARX CI](https://github.com/chatgptopenaiagi/ARX/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/chatgptopenaiagi/ARX/actions/workflows/ci.yml)
[![CodeQL](https://github.com/chatgptopenaiagi/ARX/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/chatgptopenaiagi/ARX/actions/workflows/codeql.yml)
[![Security Gate](https://github.com/chatgptopenaiagi/ARX/actions/workflows/security-gate.yml/badge.svg?branch=main)](https://github.com/chatgptopenaiagi/ARX/actions/workflows/security-gate.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://github.com/chatgptopenaiagi/ARX/blob/main/pyproject.toml)
[![Windows 10/11 x64](https://img.shields.io/badge/Windows-10%2F11_x64-0078D4?logo=windows&logoColor=white)](https://github.com/chatgptopenaiagi/ARX/blob/main/packaging/INSTALLER.md)
[![MIT License](https://img.shields.io/github/license/chatgptopenaiagi/ARX)](https://github.com/chatgptopenaiagi/ARX/blob/main/LICENSE)

**Project-Aware Compatibility Intelligence for Windows**

ARX 4 correlates what a machine provides with what a selected software target or project requires. It resolves the active execution context, preserves the evidence behind every decision, reports readiness as GREEN, YELLOW, or RED, and proposes the shortest trusted path to GREEN without changing the workstation.

This branch prepares **ARX 4.0.0 Beta 3** (`4.0.0b3`; planned tag `v4.0.0-b3`). It preserves the Phase B trust foundation and Beta 2 release-trust controls while adding the Phase C Intelligence Console, independent bounded OpenAI/Codex conversations, explicit ARX context attachment, and flat Ask Both comparison. It is not ARX 4 stable. The deterministic engine and local inspection workflows remain fully usable without an AI provider or network connection.

> ARX is a read-only compatibility intelligence tool. It is not a malware scanner, does not guarantee that arbitrary software will run, and is not an autonomous repair bot.

## Why ARX 4 is different

Many diagnostic tools primarily tell users what exists on a machine.

ARX correlates what the machine actually provides with what a specific software target or project actually requires, resolves the active execution context, explains the evidence behind the decision, and can optionally consult external intelligence without allowing external advice to become ARX evidence.

That distinction matters. An installed runtime is not necessarily the runtime a command resolves. A compatible provider elsewhere on the machine does not make the current project context GREEN. A recommendation is not proof that it was applied.

## Architecture at a glance

```text
Project DNA  --> Requirement Graph -------------------\
                                                        \
Machine DNA  --> Provider Graph --> Execution Context --> Resolution
                                                        /       |
Software DNA --> Evidence -----------------------------/        |
                                                                 v
                                                     Satisfaction / Readiness
                                                       GREEN / YELLOW / RED
                                                                 |
                                                                 v
                                                     Trusted Recovery Plan
```

The recovery plan is advisory and policy-constrained. It prefers an existing healthy provider when possible and never installs, removes, or reconfigures software automatically.

External intelligence is a separate, one-way layer:

```text
ARX deterministic evidence
        |
        | explicit user action + bounded redacted context
        v
optional OpenAI API | Codex CLI | safe web research
        |
        v
non-authoritative advisory output --> Human decision

There is no return path from external advice into ARX evidence.
```

## The ARX evidence model

- **Machine DNA** records bounded observations about Windows, CPU, memory, GPU, storage, SDK hints, developer tools, runtimes, and safe environment state.
- **Software DNA** statically inspects a selected file or directory: hashes, magic/type, PE metadata, Authenticode status, archive listings, recognized manifests, and runtime indicators where available.
- **Project DNA** reads recognized Python project manifests without executing project code and preserves requirements, runtime-selection intent, provenance, conflicts, confidence, and unknowns.
- The **Requirement Graph** groups sourced project claims by capability without discarding competing evidence.
- The **Provider Graph** keeps discovered runtimes distinct by identity, path, version, architecture, health, scope, and discovery method.
- The **Execution Context** fingerprints the command, working directory, effective PATH, and relevant environment state so resolution is scoped to the context that was actually examined.
- **Resolution** records what `python`, `python3`, or `py` invokes in that context. Resolved, compatible, project-pinned, and ARX-preferred provider roles remain separate.

ARX keeps the analytical questions independent:

```text
availability != resolution != compatibility != relevance
relevance != satisfaction != severity != remediation
```

### Fact provenance and decision validation

Every serialized fact uses exactly one `EvidenceKind`: **DECLARED**, **OBSERVED**, **INFERRED**, **ESTIMATED**, **SIMULATED**, **STRUCTURAL**, or **UNKNOWN**. `Evidence` also retains `source`, `value`, `method`, `confidence`, and an optional `note`, so a consumer can identify the value, provenance, and basis of the claim. The three ARX 4 additions distinguish an assumption-backed estimate, an explicitly simulated result, and a fact about static structure from direct observation.

**VERIFIED is not an `EvidenceKind` and is not a peer per-fact provenance state.** Relations and decisions are validated separately by semantic invariants and, for serialized contracts, schema/composed-state checks. Validation does not rewrite a fact's provenance and does not imply guaranteed compatibility or a safety verdict.

Existing numeric `confidence` values are bounded, hand-authored detector weights. They are not probabilities, measured accuracy, statistical confidence, or substitutes for provenance or validation. See the [confidence semantics and assignment audit](docs/confidence-semantics.md).

### GREEN, YELLOW, and RED

- **GREEN**: the evaluated required capability is satisfied in the recorded execution context.
- **YELLOW**: the result is recoverable, partial, ambiguous, conflicting, or uncertain—for example, a healthy compatible provider exists but the current command resolves elsewhere.
- **RED**: a required capability is unsatisfied with no confirmed healthy compatible provider, or an authoritative blocking conflict exists.

GREEN is deliberately scoped. The current Python readiness vertical verifies interpreter/toolchain requirements; it does not prove dependency installation, lock/site-packages synchronization, project imports, or complete application startup.

## Install ARX 4

ARX `4.0.0b3` is a pre-release candidate. The Python package keeps the existing `arx-prescanner` identity and history. The Python package and the Windows installer contain the same ARX engine but serve different installation workflows.

### PyPI / Python developers

After the separately approved PyPI publication gate, install this exact beta from the existing `arx-prescanner` project:

```console
python -m pip install arx-prescanner==4.0.0b3
```

Alternatively, allow pip to discover the newest available ARX pre-release:

```console
python -m pip install --pre arx-prescanner
```

Then use either console entry point:

```console
arx --help
arx quick
arx-desktop
```

`arx-desktop` launches the Windows Tk desktop application. The CLI remains usable independently. An unpinned install selects the newest stable version and does not opt into this beta:

```console
python -m pip install arx-prescanner
```

### GitHub source / tag

Install the immutable beta source directly from its Git tag:

```console
python -m pip install "git+https://github.com/chatgptopenaiagi/ARX.git@v4.0.0-b3"
```

### Windows installer

After the candidate passes its release gates and is published, download `ARX-Desktop-Setup-win-x64-v4.0.0-b3.exe` from the `v4.0.0-b3` GitHub prerelease. It installs ARX under 64-bit Program Files and adds Start Menu and uninstall entries. The candidate remains unsigned because no approved production code-signing identity is configured; checksums and GitHub provenance do not substitute for Authenticode.

### Portable Windows

After publication, download `ARX-Desktop-win-x64-v4.0.0-b3.zip`, verify it with `SHA256SUMS.txt`, extract the complete folder, and run `ARX.exe` without installation.

### Editable source checkout

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

arx quick
arx deep
arx inspect C:\Path\To\Application.exe
arx compare C:\Path\To\Application.exe
arx project C:\Path\To\Project
arx resolve C:\Path\To\Project
arx preflight C:\Path\To\Project
arx codex --project C:\Path\To\Project
```

Use the global `--output` option to save structured output, for example `arx --output machine.json deep`.

## Windows desktop application

ARX Desktop presents the same canonical evidence and decisions as the CLI in a responsive Windows interface. It includes Project Preflight, Machine DNA, Software DNA, compatibility findings, evidence inspection, selectable and searchable reports, safe path navigation, redacted export, contextual advisory actions, background work, cancellation, and human-readable technical errors.

Unknown targets are never launched, imported, or extracted. Static inspection recognizes EXE/DLL/PE, MSI identity, ZIP/JAR/APK containers, scripts, application directories, and bounded project manifests. Trusted developer-tool diagnostics use fixed argument arrays, `shell=False`, captured output, and timeouts.

### Windows distribution

ARX 4 Beta 3 can be built in two Windows forms:

- a portable x64 folder and versioned ZIP containing `ARX.exe` and its private `_internal` runtime;
- an optional Inno Setup installer with a stable application identity, x64 Program Files installation, Start Menu and uninstall entries, an optional desktop shortcut, and SHA-256 checksums.

Generated release artifacts stay under the ignored, version-specific `release/v4.0.0-b3/` directory and are not committed. Historical release artifacts are not overwritten. Current beta builds are unsigned and use the executable's version resources rather than a custom signed project icon. See the [installer documentation](packaging/INSTALLER.md), [reproducible-build policy](docs/REPRODUCIBLE_BUILDS.md), and [trusted installation architecture](docs/TRUSTED_INSTALLATION.md).

## Optional advisory and safe research

External assistance is always optional, explicitly user-triggered, cancellable where the provider permits, visibly labeled, and separate from deterministic ARX evidence.

- **OpenAI API advisory** uses the supported OpenAI Responses API. Developer sessions may use `OPENAI_API_KEY`; the packaged Windows application can import a dedicated key into an ARX-owned, per-user Windows DPAPI store. A ChatGPT subscription is not treated as an API credential.
- **Codex CLI advisory** detects the official CLI and sends the bounded prompt through standard input to a read-only, ephemeral process in an empty temporary directory.
- **Safe web research** creates a short redacted, URL-encoded query and opens an allowlisted HTTPS search URL in the user's browser. ARX does not scrape or import results.

Open the provider configuration with `Settings → Intelligence Providers → OpenAI API`. The window provides Configure, Import, Replace, Remove, Test Connection, and Open OpenAI Chat actions. Configure opens the official OpenAI Platform API-key page; ARX never generates a key. Import immediately protects the selected key with DPAPI and never displays it again. Opening Settings performs no network request and finding a credential reports only `CONFIGURED`; an explicit successful authentication/API/model check is required for `READY`.

Provider health distinguishes missing, unreadable, authentication, network/TLS, rate-limit, quota, unavailable-model, timeout, cancellation, server, parse, and ready states. A protected blob that cannot be decrypted in the active Windows context is `CREDENTIAL_UNREADABLE`, not missing or rejected authentication.

A minimum-data authentication/model check can be `READY` while a later advisory generation fails with `QUOTA_EXHAUSTED` because the API project has no generation quota. ARX keeps that billing/usage condition separate from authentication failure.

The Phase C Intelligence Console supports GENERAL CHAT with no attached ARX state and ARX EVIDENCE CHAT with an explicit selected scope. Users can inspect Machine DNA, Software DNA, Project DNA, conclusions, contradictions, unknowns, and evidence in separate panels; preview the redacted packet; and consent separately for each provider/context identity. OpenAI Chat and Codex CLI retain independent, bounded, memory-only conversations.

Ask Both sends the same explicitly approved context and question to exactly two distinct providers and shows two flat, unranked panels. Only a second explicit **Compare Responses** action reveals textual overlap, differences, and unresolved statements. Similar wording is not consensus, verification, confidence, or evidence.

Only the selected bounded context may cross an external boundary after consent. ARX removes recognizable credentials, tokens, usernames, private roots, user-profile paths, project paths, arbitrary absolute local paths, control characters, and unrelated evidence. Copy/save paths reapply redaction.

AI and web outputs remain non-authoritative external advice. They cannot change an observed fact, assign GREEN/YELLOW/RED, mutate the evidence graph, or execute a recovery step. **The human remains the final decision-maker.**

Phase C deliberately does not include AI consensus, a winning or ranked provider, a synthesized authoritative answer, automatic remediation, or any path from advisory output into ARX evidence. Its architecture and limitations are documented in [ARX 4 Phase C](docs/PHASE_C.md). The immutable Beta 2 tag and assets remain unchanged and still exclude Phase C.

At the real provider boundary ARX writes only bounded local transmission metadata—never keys or prompt/response bodies—and distinguishes prepared, outbound, received, failed, and cancelled states. History rotates, expires after 30 days, has an explicit Clear History action, is not implicitly exported, and is never synchronized by ARX.

Read the complete [AI assistance and external-boundary security model](docs/ai-assistance-security.md).

## Build the ARX 4 Beta 3 artifacts

```powershell
python -m pip install -e ".[dev,build,release]"
.\scripts\build-release.ps1 -Version 4.0.0b3
```

Expected release filenames are:

- `arx_prescanner-4.0.0b3-py3-none-any.whl`
- `arx_prescanner-4.0.0b3.tar.gz`
- `ARX-Desktop-win-x64-v4.0.0-b3.zip`
- `ARX-Desktop-Setup-win-x64-v4.0.0-b3.exe`
- `SHA256SUMS.txt`

Building an installer is not install, upgrade, or uninstall acceptance. Those operating-system transitions remain explicit manual checks.

## Security and privacy

ARX treats inspected targets and project contents as untrusted. Recognized files are size-bounded, encoding-checked, and symlink-safe; archives are listed without extraction; unknown executables and project scripts are never run. Reports redact profile/project paths and expose only allowlisted or fingerprinted environment state. Deterministic scanning does not read unrelated credential stores, browser data, Wi-Fi secrets, private keys, or password/token variables. The optional OpenAI provider can access only its explicitly configured process credential or ARX-owned DPAPI blob inside the credential boundary.

The Resolution Planner only recommends actions. Normal analysis does not install or uninstall software, edit PATH or the registry, change execution aliases, weaken security controls, or apply remediation. See the [security model](docs/security-model.md) and [security policy](SECURITY.md).

## Documentation

| Document | Purpose |
|---|---|
| [ARX 4.0.0 Beta 3 release notes](docs/release-notes-4.0.0-b3.md) | Phase C Intelligence Console, bounded conversations/context, Ask Both, security gates, and prerelease limitations |
| [ARX 4.0.0 Beta 2 release notes](docs/release-notes-4.0.0-b2.md) | Security remediation, reproducibility, provenance, Windows trust preparation, Phase C exclusions, and beta limitations |
| [ARX 4.0.0 Beta 1 release notes](docs/release-notes-4.0.0-b1.md) | Historical Phase B trust-foundation prerelease |
| [ARX 3.0 RC1 release notes](docs/release-notes-3.0.0-rc1.md) | Changes since ARX 2, compatibility, verification, and RC limitations |
| [Architecture](docs/architecture.md) | Canonical domain, evidence boundaries, path identity, UI lifecycle, and packaging decisions |
| [Confidence semantics](docs/confidence-semantics.md) | Numeric assignment inventory and explicit non-probabilistic meaning |
| [ARX 4 baseline](docs/arx-4-baseline-report.md) | Verified checkout, toolchain, epistemic model, import graph, and baseline tests |
| [ARX 4 Phase B trust foundation](docs/arx-4-phase-b-trust-foundation.md) | Provenance, dependency enforcement, DPAPI credentials, provider health, OpenAI transport, and audit boundaries |
| [ARX 4 Phase C Intelligence Console](docs/PHASE_C.md) | Advisory-only console, bounded context, independent conversations, Ask Both, comparison, privacy, and limitations |
| [ARX 3 final acceptance](docs/arx-3-final-acceptance.md) | Phase A evidence, blocked gates, artifacts, and release decision |
| [Project-aware semantic engine](docs/project-semantic-engine.md) | Requirement/provider graphs, execution resolution, readiness, and planning rules |
| [Security model](docs/security-model.md) | Local inspection, subprocess, privacy, remediation, and external trust boundaries |
| [AI assistance security](docs/ai-assistance-security.md) | OpenAI, Codex CLI, web research, consent, redaction, and failure behavior |
| [Testing and acceptance](docs/testing.md) | Deterministic suite, runtime-shaped GUI isolation, CI, and evidence levels |
| [Python package publishing](docs/python-package-publishing.md) | PyPI/TestPyPI Trusted Publishing, release gates, and installation verification |
| [ARX 3 implementation report](docs/arx-3-implementation-report.md) | Point-by-point engineering record and remaining limitations |
| [Windows manual acceptance](docs/windows-desktop-acceptance.md) | Visible UX, DPI, accessibility, installer, upgrade, and uninstall checklist |
| [Report schemas](docs/report-schema.md) | Application/contract version independence and schema routing |
| [Changelog](CHANGELOG.md) | Release history |

Historical release notes and frozen contracts remain available under `docs/` and `schemas/`.

## Development, CI, and CodeQL

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python scripts/run-isolated-gui-tests.py
```

GitHub Actions runs compilation and deterministic pytest coverage on Windows and Linux for Python 3.10, 3.12, and 3.14. Windows runs each Tk-backed GUI node in a fresh interpreter; Linux runs the full suite under Xvfb. A separate job builds and imports the source distribution and wheel without publishing. CodeQL analyzes Python and GitHub Actions with least-privilege workflow permissions and pinned action revisions.

## Beta limitations

- Real DPI and multi-monitor acceptance is incomplete.
- Screen-reader and full accessibility acceptance is incomplete.
- Interactive/silent install, launch-after-install, upgrade, uninstall, and clean-removal acceptance is incomplete.
- The aggregate Definition of Done remains partial because those visible/manual checks are not complete.
- The installer is unsigned and has no separately approved custom application icon.
- Python is the implemented project-readiness ecosystem; other ecosystem adapters remain future work.
- Phase C is not included: Ask Both, AI consensus, synthesized or ranked answers, expanded contextual conversation architecture, and the final Intelligence Console remain future work.
- OpenAI provider health may be READY while advisory generation is unavailable because the API project has no generation quota; this is reported as quota exhaustion, not authentication failure.

Unchecked manual items are not reported as tested. Review the [Windows acceptance checklist](docs/windows-desktop-acceptance.md) before promoting a future release beyond its demonstrated evidence.

## License

ARX is available under the [MIT License](LICENSE). Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md).
