# ARX 3

[![ARX CI](https://github.com/chatgptopenaiagi/ARX/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/chatgptopenaiagi/ARX/actions/workflows/ci.yml)
[![CodeQL](https://github.com/chatgptopenaiagi/ARX/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/chatgptopenaiagi/ARX/actions/workflows/codeql.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://github.com/chatgptopenaiagi/ARX/blob/main/pyproject.toml)
[![Windows 10/11 x64](https://img.shields.io/badge/Windows-10%2F11_x64-0078D4?logo=windows&logoColor=white)](https://github.com/chatgptopenaiagi/ARX/blob/main/packaging/INSTALLER.md)
[![MIT License](https://img.shields.io/github/license/chatgptopenaiagi/ARX)](https://github.com/chatgptopenaiagi/ARX/blob/main/LICENSE)

**Project-Aware Compatibility Intelligence for Windows**

ARX 3 correlates what a machine provides with what a selected software target or project requires. It resolves the active execution context, preserves the evidence behind every decision, reports readiness as GREEN, YELLOW, or RED, and proposes the shortest trusted path to GREEN without changing the workstation.

This branch presents **ARX 3.0 Release Candidate** (`3.0.0rc1`; planned tag `v3.0.0-rc1`). The deterministic engine and local inspection workflows remain fully usable without an AI provider or network connection.

> ARX is a read-only compatibility intelligence tool. It is not a malware scanner, does not guarantee that arbitrary software will run, and is not an autonomous repair bot.

## Why ARX 3 is different

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
optional ChatGPT/OpenAI | Codex CLI | safe web research
        |
        v
unverified advisory output --> Human decision

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

### OBSERVED, INFERRED, and VERIFIED reasoning

- **OBSERVED** facts come from bounded static reads or fixed, timeout-bound diagnostic probes.
- **INFERRED** conclusions are produced by deterministic rules and retain the evidence references and confidence that support them.
- **VERIFIED** relationships or decisions have passed ARX's semantic invariant checks and, where serialized, schema validation. VERIFIED does not mean guaranteed compatibility or a safety verdict.

Serialized evidence provenance remains explicit as `declared`, `observed`, `inferred`, or `unknown`. ARX does not turn missing or unsupported information into certainty.

### GREEN, YELLOW, and RED

- **GREEN**: the evaluated required capability is satisfied in the recorded execution context.
- **YELLOW**: the result is recoverable, partial, ambiguous, conflicting, or uncertain—for example, a healthy compatible provider exists but the current command resolves elsewhere.
- **RED**: a required capability is unsatisfied with no confirmed healthy compatible provider, or an authoritative blocking conflict exists.

GREEN is deliberately scoped. The current Python readiness vertical verifies interpreter/toolchain requirements; it does not prove dependency installation, lock/site-packages synchronization, project imports, or complete application startup.

## Windows desktop application

ARX Desktop presents the same canonical evidence and decisions as the CLI in a responsive Windows interface. It includes Project Preflight, Machine DNA, Software DNA, compatibility findings, evidence inspection, selectable and searchable reports, safe path navigation, redacted export, contextual advisory actions, background work, cancellation, and human-readable technical errors.

Unknown targets are never launched, imported, or extracted. Static inspection recognizes EXE/DLL/PE, MSI identity, ZIP/JAR/APK containers, scripts, application directories, and bounded project manifests. Trusted developer-tool diagnostics use fixed argument arrays, `shell=False`, captured output, and timeouts.

Run the desktop from source:

```powershell
$env:PYTHONPATH = 'src'
python -m arx.desktop
```

### Windows distribution

ARX 3 RC can be built in two forms:

- a portable x64 folder and versioned ZIP containing `ARX.exe` and its private `_internal` runtime;
- an optional Inno Setup installer with a stable application identity, x64 Program Files installation, Start Menu and uninstall entries, an optional desktop shortcut, and SHA-256 checksums.

Generated release artifacts stay under the ignored `release/` directory and are not committed. Current RC builds are unsigned and use the executable's version resources rather than a custom signed project icon. See the [installer documentation](packaging/INSTALLER.md).

## Optional advisory and safe research

External assistance is always optional, explicitly user-triggered, cancellable where the provider permits, visibly labeled, and separate from deterministic ARX evidence.

- **ChatGPT/OpenAI advisory** uses the OpenAI Responses API when `OPENAI_API_KEY` is present in the ARX process environment. A ChatGPT subscription is not treated as an API credential.
- **Codex CLI advisory** detects the official CLI and sends the bounded prompt through standard input to a read-only, ephemeral process in an empty temporary directory.
- **Safe web research** creates a short redacted, URL-encoded query and opens an allowlisted HTTPS search URL in the user's browser. ARX does not scrape or import results.

Only the selected finding and relevant bounded context may cross an external boundary after consent. ARX removes recognizable credentials, tokens, usernames, private roots, user-profile paths, project paths, arbitrary absolute local paths, control characters, and unrelated evidence. Copy/save paths reapply redaction.

AI and web outputs remain unverified advice. They cannot change an observed fact, assign GREEN/YELLOW/RED, mutate the evidence graph, or execute a recovery step. **The human remains the final decision-maker.**

Read the complete [AI assistance and external-boundary security model](docs/ai-assistance-security.md).

## Install and use from source

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

## Build the Windows RC artifacts

```powershell
python -m pip install -e ".[build]"
.\scripts\build-desktop.ps1
.\scripts\package-desktop-release.ps1 -Version 3.0.0rc1
.\scripts\build-installer.ps1 -Version 3.0.0rc1
```

Expected release filenames are:

- `ARX-Desktop-win-x64-v3.0.0-rc1.zip`
- `ARX-Desktop-Setup-win-x64-v3.0.0-rc1.exe`
- `SHA256SUMS-v3.0.0-rc1.txt`

Building an installer is not install, upgrade, or uninstall acceptance. Those operating-system transitions remain explicit manual checks.

## Security and privacy

ARX treats inspected targets and project contents as untrusted. Recognized files are size-bounded, encoding-checked, and symlink-safe; archives are listed without extraction; unknown executables and project scripts are never run. Reports redact profile/project paths and expose only allowlisted or fingerprinted environment state. ARX does not read credential stores, browser data, Wi-Fi secrets, private keys, or password/token variables.

The Resolution Planner only recommends actions. Normal analysis does not install or uninstall software, edit PATH or the registry, change execution aliases, weaken security controls, or apply remediation. See the [security model](docs/security-model.md) and [security policy](SECURITY.md).

## Documentation

| Document | Purpose |
|---|---|
| [ARX 3.0 RC1 release notes](docs/release-notes-3.0.0-rc1.md) | Changes since ARX 2, compatibility, verification, and RC limitations |
| [Architecture](docs/architecture.md) | Canonical domain, evidence boundaries, path identity, UI lifecycle, and packaging decisions |
| [Project-aware semantic engine](docs/project-semantic-engine.md) | Requirement/provider graphs, execution resolution, readiness, and planning rules |
| [Security model](docs/security-model.md) | Local inspection, subprocess, privacy, remediation, and external trust boundaries |
| [AI assistance security](docs/ai-assistance-security.md) | OpenAI, Codex CLI, web research, consent, redaction, and failure behavior |
| [Testing and acceptance](docs/testing.md) | Deterministic suite, runtime-shaped GUI isolation, CI, and evidence levels |
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

## Release-candidate limitations

- Real DPI and multi-monitor acceptance is incomplete.
- Screen-reader and full accessibility acceptance is incomplete.
- Interactive/silent install, launch-after-install, upgrade, uninstall, and clean-removal acceptance is incomplete.
- The aggregate Definition of Done remains partial because those visible/manual checks are not complete.
- The installer is unsigned and has no separately approved custom application icon.
- Python is the implemented project-readiness ecosystem; other ecosystem adapters remain future work.

Unchecked manual items are not reported as tested. Review the [Windows acceptance checklist](docs/windows-desktop-acceptance.md) before promoting the release candidate to a final release.

## License

ARX is available under the [MIT License](LICENSE). Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md).
