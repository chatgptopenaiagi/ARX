# ARX 3.0 Release Candidate

Package version: `3.0.0rc1`

Planned Git tag: `v3.0.0-rc1`

Release date: 2026-08-24

ARX 3 advances the ARX 2 project-aware semantic engine into a Windows release-candidate experience. The deterministic local engine remains the evidence authority; the desktop, exporters, installer, and optional external-advisory layer consume that authority without replacing it.

## What changed since ARX 2

### Architecture and project-aware intelligence

- Preserved the locked Project DNA, Requirement Graph, Provider Graph, Execution Context, resolution, satisfaction, severity, explanation, and policy-aware planning model across CLI, desktop, and structured output.
- Strengthened canonical semantic guards so presentation and advisory surfaces cannot independently reinterpret compatibility or readiness.
- Made path identity and redaction host-independent for evidence that carries Windows paths through Linux CI or other non-Windows processing.
- Formalized thin interaction surfaces, owned desktop lifecycles, one-way external boundaries, and portable-payload-before-installer packaging as standing architectural decisions.

Application version `3.0.0rc1` remains independent from the frozen machine/software schema `0.1` and project/AI contract schema `0.2`. The ARX 2 release notes and the earlier pre-RC implementation build records retain their original version references as historical evidence.

### Windows desktop experience

- Added selectable, searchable, copyable, and saveable text and JSON report surfaces with standard keyboard behavior.
- Added contextual actions for result rows, evidence, existing paths, static ARX inspection, AI interpretation, and privacy-aware web research.
- Added safe Explorer/file navigation using explicit arguments or Windows file APIs without shell interpolation.
- Added background-operation state, cancellation/late-result handling, copyable technical errors, remembered session directories, bounded non-sensitive UI state, reusable dialogs/widgets, and lifecycle cleanup.
- Added textual status alongside color and improved focusability, scrolling, panes, tooltips, menus, and About/version presentation.

### Portable application and installer

- Retained the portable x64 PyInstaller application as the canonical Windows payload.
- Added an Inno Setup 6/7 wrapper with a stable AppId, x64 Program Files installation, Start Menu and uninstall entries, an optional desktop shortcut, MIT license display, silent-install launch suppression, and checksum generation.
- Standardized RC artifacts as `ARX-Desktop-win-x64-v3.0.0-rc1.zip`, `ARX-Desktop-Setup-win-x64-v3.0.0-rc1.exe`, and `SHA256SUMS-v3.0.0-rc1.txt`.
- Embedded `3.0.0rc1` product strings and numeric Windows version `3.0.0.1` in `ARX.exe`; the visible application identifies itself as ARX 3.0 Release Candidate.

Generated binaries, installers, and checksums remain outside source control.

### Optional AI, Codex, and web advisory bridge

- Added explicit user-triggered ChatGPT/OpenAI and official Codex CLI advisory providers behind a common optional interface.
- Added context modes for explanation, safe-fix suggestions, project-requirement comparison, and next checks.
- Added safe web, Google, exact-error, and official-documentation searches that open bounded redacted queries in the user's browser without scraping or importing results.
- Kept external responses visibly labeled `AI ADVISORY — UNVERIFIED AI ANALYSIS`; they cannot set ARX evidence classifications, GREEN/YELLOW/RED, or remediation state.

The human remains the decision-maker. ARX does not automate the ChatGPT website, turn into an autonomous repair bot, or treat AI confidence as evidence.

## Security and privacy model

- Unknown targets and project scripts remain unexecuted; archives are listed without extraction and recognized manifest reads are bounded, encoding-checked, and symlink-safe.
- Diagnostic processes use fixed argument arrays, `shell=False`, captured streams, timeouts, and bounded output.
- External context follows `select -> filter -> redact -> bound -> preview/consent -> transmit -> unverified label` and fails closed without changing the deterministic report.
- OpenAI credentials remain in process configuration and the HTTPS authorization header, never in prompts, request bodies, URLs, reports, subprocess arguments, or saved state.
- Codex prompts travel through standard input to a read-only ephemeral process in an empty temporary directory; the inspected project is not granted as its working directory.
- Web queries are redacted, URL-encoded, and restricted to allowlisted HTTPS search hosts.

## Tests, CI, and release verification

- Expanded deterministic coverage for project semantics, cross-surface consistency, advisory selection/redaction, providers, cancellation, subprocess safety, URLs, desktop interaction, path handling, shutdown, version metadata, packaging, documentation, and workflow policy.
- GitHub Actions tests Windows and Linux on Python 3.10, 3.12, and 3.14. Windows GUI nodes run in isolated interpreters; Linux runs the full GUI suite under Xvfb.
- CI builds and imports the sdist/wheel without publishing.
- CodeQL analyzes Python and GitHub Actions with pinned actions, non-persisted checkout credentials, and least-privilege permissions.
- The RC portable payload, packaged UI smoke workflow, versioned ZIP, Inno installer, and SHA-256 manifest are built and verified locally as a release checkpoint. Building these artifacts does not claim installed lifecycle acceptance.

## Release-candidate limitations

The following remain deliberately visible and prevent a final Definition-of-Done claim:

- Real DPI and multi-monitor acceptance is incomplete.
- Screen-reader and complete accessibility acceptance is incomplete.
- Interactive and silent installation, launch-after-install, same-AppId upgrade, uninstall, and clean-removal acceptance are incomplete.
- The aggregate Definition of Done remains partial because those manual checks have not been completed.

Additional boundaries:

- The installer is unsigned and uses no separately approved custom icon; signing requires a publisher-controlled certificate and release policy.
- OpenAI and Codex availability depends on separately configured services/tools. Controlled tests cover their boundaries, but availability is not required for core ARX operation.
- Browser opening, Explorer integration, native dialogs, and physical keyboard/visual behavior still require the documented visible Windows acceptance pass.
- Python is the implemented project-readiness ecosystem. GREEN remains scoped to evaluated interpreter/toolchain requirements and does not prove dependency synchronization, imports, or full application execution.
- ARX is not a malware scanner, compatibility guarantee, or autonomous remediation system.

See the [implementation report](arx-3-implementation-report.md), [testing boundaries](testing.md), and [Windows acceptance checklist](windows-desktop-acceptance.md) for the complete evidence and remaining work.
