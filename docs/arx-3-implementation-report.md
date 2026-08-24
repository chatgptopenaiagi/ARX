# ARX 3 implementation report

This report records the engineering implementation and audit requested by ARX 3 Points 1 through 27. The implementation is complete to the safe limit of the original release-candidate work. Points 12, 13, 16, and 24 remain explicitly partial because visible Windows/DPI/accessibility acceptance and installer install/upgrade/uninstall actions were not exercised. No unchecked manual action is represented as tested.

The maintained working checklist and checkpoint history are in [ARX 3 implementation checklist](arx-3-implementation-checklist.md). The release acceptance procedure is in [ARX Desktop manual Windows acceptance checklist](windows-desktop-acceptance.md). The later authoritative Phase A disposition, including new RC artifact evidence and blocked signing/lifecycle gates, is in [ARX 3 final acceptance](arx-3-final-acceptance.md).

Phase A did not approve or create stable `v3.0.0`. It confirmed that the fact-provenance enum remains `DECLARED / OBSERVED / INFERRED / UNKNOWN`, corrected documentation that treated `VERIFIED` like peer fact provenance, and documented all numeric confidence assignments as uncalibrated detector-author weights.

## UX problems found

- Several report surfaces used disabled text widgets, which made meaningful text difficult to select, search, copy, or save.
- Result rows and paths were mostly passive; they lacked familiar copy, details, Explorer, keyboard, and context-sensitive actions.
- Colored states did not consistently expose equivalent textual interaction and detail paths.
- Menus, standard shortcuts, tooltips, session directory reuse, copyable technical errors, and safe UI-state persistence were incomplete.
- Worker feedback did not consistently disable conflicting controls or clean up periodic callbacks at application shutdown.
- The portable build had no repository-native installer layer, upgrade identity, uninstall entry, or installer checksum wrapper.
- ARX had no optional bounded AI/Codex/web investigation bridge and no continuous Windows/Linux matrix or CodeQL workflow.
- Windows-looking provider paths were normalized using the host OS, which made scope and identity nondeterministic in cross-platform CI fixtures.

## Changes implemented

- Added reusable selectable `Text`/JSON panels, search/save/copy commands, compact context menus, keyboard bindings, horizontal and vertical scrolling, tooltips, status badges, and technical-error details.
- Added path-sensitive row activation and safe Open, Open Containing Folder, Reveal in File Explorer, and Inspect with ARX commands using argument arrays or Windows APIs without shell interpolation.
- Added responsive busy/completion/failure/cancel feedback, control-state restoration, and deterministic shutdown cleanup for polling, active operations, and advisory children.
- Added bounded non-sensitive geometry/tab persistence, Windows DPI-awareness startup, smaller minimum sizes, resizable report windows, File/Edit/Help menus, and a factual About dialog.
- Added an Inno Setup x64 installer with stable AppId, MIT license, Program Files destination, Start Menu/uninstall entries, optional desktop shortcut, launch-at-finish, version metadata, and SHA-256 manifest generation while preserving the portable distribution.
- Added a provider-neutral advisory layer with deterministic context selection, external-boundary redaction, OpenAI Responses API and official Codex CLI adapters, consent, prompt preview, modes, cancellation, redacted export, and visible advisory/evidence separation.
- Added redacted user-triggered DuckDuckGo/Google, exact-error, and official-documentation searches with HTTPS host allowlisting and no result ingestion.
- Added pinned least-privilege GitHub CI for Windows/Linux and Python 3.10/3.12/3.14, isolated Windows GUI test interpreters, package builds without publishing, and CodeQL for Python and Actions.
- Preserved foreign absolute Windows provider paths and scope independently of the runner OS.

## Files changed

Workflows, build, and packaging:

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `pyproject.toml`
- `packaging/arx-desktop.iss`
- `packaging/INSTALLER.md`
- `packaging/README.txt`
- `scripts/build-installer.ps1`
- `scripts/run-isolated-gui-tests.py`

Application code:

- `src/arx/advisory/__init__.py`
- `src/arx/advisory/context.py`
- `src/arx/advisory/providers.py`
- `src/arx/advisory/web.py`
- `src/arx/desktop/advisory.py`
- `src/arx/desktop/app.py`
- `src/arx/desktop/theme.py`
- `src/arx/desktop/ux.py`
- `src/arx/desktop/widgets.py`
- `src/arx/project/resolver.py`

Documentation:

- `CONTRIBUTING.md`
- `README.md`
- `docs/ai-assistance-security.md`
- `docs/arx-3-implementation-checklist.md`
- `docs/arx-3-implementation-report.md`
- `docs/security-model.md`
- `docs/testing.md`
- `docs/windows-desktop-acceptance.md`

Tests:

- `tests/test_advisory_context.py`
- `tests/test_advisory_providers.py`
- `tests/test_advisory_web.py`
- `tests/test_desktop.py`
- `tests/test_desktop_advisory.py`
- `tests/test_desktop_ux.py`
- `tests/test_documentation.py`
- `tests/test_github_workflows.py`
- `tests/test_python_hardening.py`
- `tests/test_windows_packaging.py`

Phase A final-acceptance additions and corrections:

- `CHANGELOG.md`
- `docs/ARX_CODEX_MASTER_PROMPT.md`
- `docs/architecture.md`
- `docs/arx-3-final-acceptance.md`
- `docs/arx-4-baseline-report.md`
- `docs/confidence-semantics.md`
- `docs/project-semantic-engine.md`
- `docs/report-schema.md`
- `src/arx/advisory/context.py`
- `tests/test_arx.py`

## Tests and verification

- Baseline before implementation: 105 tests passed on Windows with Python 3.10.8.
- Original RC final local suite: 170 tests passed on Windows with Python 3.10.8.
- Phase A final local suite: 146 non-GUI tests passed together and all 38 GUI nodes passed in fresh Python interpreters, for 184 passing tests; no GUI test was skipped.
- Portable payload: `scripts/build-desktop.ps1` produced `release/ARX-Desktop-win-x64/ARX.exe`.
- Packaged application: both software and project UI smoke workflows exited successfully from the final Phase A payload.
- Installer: Inno Setup 7.1.0 compiled `release/ARX-Desktop-Setup-win-x64-v3.0.0-rc1.exe` through automatic discovery.
- Checksums: independently calculated executable, ZIP, and installer SHA-256 values matched every entry in `release/SHA256SUMS-v3.0.0-rc1.txt`.
- Packaging: all five packaging tests passed after the real build.
- Package metadata: `python -m build` produced an sdist and wheel; strict Twine and wheel-content checks passed, and a fresh Python 3.10 environment outside the checkout installed and exercised the wheel and both entry points.
- Hosted CI: Windows and Ubuntu jobs pass for Python 3.10, 3.12, and 3.14; Linux GUI coverage runs under Xvfb and Windows GUI nodes run in isolated interpreters because production ARX uses one Tk root per process.
- CodeQL: Python and GitHub Actions analyses pass.
- Compilation and diff checks pass.

New automated coverage includes external context selection and redaction, provider availability/transport/failure/cancel/timeout behavior, Codex argument/stdin/process safety, web query/URL allowlisting, advisory GUI consent and separation, reusable desktop interaction helpers, path and Explorer safety, packaging structure, workflow policy, documentation completeness, UI shutdown, and host-independent provider paths. Existing desktop and Python-hardening tests were extended for integration and regression coverage.

## Manual verification

Structurally or directly exercised on this workstation:

- Desktop widgets, bindings, menus, text/JSON save and copy behavior, row/path actions, busy/cancel state, errors, advisory panels, consent, and shutdown were exercised through Tk integration tests.
- The portable application payload was built.
- Inno Setup 7.1.0 compiled the installer and the resulting artifact and checksum were independently verified.
- The installed Codex CLI was found as `codex.cmd`; `codex --version` reported `codex-cli 0.149.0`, and the supported non-interactive flags were inspected.

Not manually exercised:

- A visible end-to-end Windows 10/11 acceptance pass, maximize/restore, multiple real DPI settings, physical keyboard traversal, native dialogs/associations, Explorer visual behavior, screen readers, and visual contrast review.
- Interactive install, launch-after-install, silent install, upgrade over an older version, uninstall, or clean-removal behavior.
- A live OpenAI request because no API key was configured; no credentials were created for testing.
- A live Codex advisory or public-browser search with project data; their boundaries were tested with controlled transports/openers.

## Point 24 Definition of Done audit

| Condition | Result | Evidence or limitation |
|---:|---|---|
| 1. Core ARX behavior still works | PASS — AUTOMATED | Canonical engines and cross-surface semantic tests pass; presentation does not own evidence decisions. |
| 2. Existing tests pass | PASS — AUTOMATED | Complete local and hosted suites pass. |
| 3. New relevant tests pass | PASS — AUTOMATED | Advisory, UX, packaging, workflow, documentation, and boundary tests pass. |
| 4. JSON is easy to copy/save | PASS — STRUCTURAL AUTOMATION | Read-only JSON panels expose copy, copy-all, find, Ctrl+S, and UTF-8 save tests. |
| 5. Important text is selectable | PASS — STRUCTURAL AUTOMATION | Meaningful report/error surfaces use selectable read-only text widgets. |
| 6. Standard clipboard shortcuts work | PASS — STRUCTURAL AUTOMATION | Ctrl+C/Ctrl+A and exact Unicode clipboard helpers are tested. |
| 7. Natural context menus exist | PASS — STRUCTURAL AUTOMATION | Text, JSON, result, path, evidence, and advisory actions are integration-tested. |
| 8. Paths expose safe actions | PASS — AUTOMATED | Existence checks, argument arrays, `shell=False`, and missing/injection-shaped paths are tested. |
| 9. Colored rows are interactive | PASS — STRUCTURAL AUTOMATION | Rows support focus, selection, copy/details, activation, actions, and textual status. |
| 10. Error details are copyable | PASS — STRUCTURAL AUTOMATION | Human summary and selectable technical-details behavior is tested. |
| 11. File dialogs behave naturally | PASS — STRUCTURAL AUTOMATION | Parents, filters, cancellation, and session directory reuse are tested. |
| 12. Resizing/scrolling work | PARTIAL | Layout, minimum sizes, panes, and scrollbars are structural; visible resize/maximize/DPI acceptance was not run. |
| 13. Installer/release improved | PASS — ARTIFACT CONSTRUCTION; LIFECYCLE/SIGNING BLOCKED | Portable/installer/checksum builds pass; isolated lifecycle actions and signing were not completed. |
| 14. Manual acceptance documentation exists | PASS — AUTOMATED DOCUMENT CHECK | The complete unchecked Windows release checklist is versioned and structurally tested. |
| 15. Security/redaction remain intact | PASS — AUTOMATED | Boundary, redaction, path, subprocess, URL, export, workflow, and credential scans pass. |

These labels report how the acceptance condition was checked; they are not `EvidenceKind` values. Point 24 remains `PARTIALLY IMPLEMENTED`: visible window/DPI and screen-reader checks, isolated installer lifecycle, and code signing cannot be truthfully closed from artifact or structural evidence.

## Point 27 final implementation report

### AI integration discovered and selected

- Reused the canonical engine reports, typed Project DNA/Provider Graph/ExecutionContext, existing evidence serializer/redaction, desktop worker pattern, result trees, report exporters, and project-aware view model.
- Codex discovery uses executable lookup (`shutil.which("codex")`) followed by a bounded argument-array `codex --version` check.
- OpenAI uses the HTTPS Responses API with `store: false`, bounded output, configurable `ARX_OPENAI_MODEL`, and `OPENAI_API_KEY` read only from process configuration.
- `AIProvider`, `ProviderAvailability`, `AdvisoryContext`, and `AdvisoryResponse` keep provider implementation, deterministic context, UI, and unverified output separate.

### Context-menu additions

Result/path actions are shown only when applicable:

- Copy Row; Copy Details; Copy Value; Copy Path.
- Open; Open Containing Folder; Reveal in File Explorer; Inspect with ARX.
- Ask ChatGPT About This…; Ask Codex About This…; Suggest Safe Fix with AI…; Compare With Project Requirements….
- Search Web About This…; Search Google About This…; Search Exact Error Message…; Search Official Documentation….
- View Evidence; View Raw Data; View Details.

Text and JSON surfaces add Copy, Copy All Text/JSON, Select All, Find, and Save Text/JSON As… where meaningful.

### Privacy and security

Only an explicitly selected finding, bounded project summary, at most eight relevant evidence entries, the selected mode/question, and at most six recent redacted conversation turns may leave the machine after consent. Complete Machine DNA, unrelated project files, browser state, credential stores, and arbitrary file contents are not transmitted.

Before the boundary, ARX removes sensitive keys, password/token assignments, API/GitHub keys, bearer tokens, JWTs, usernames, control characters, private roots, profile/project paths, and other absolute local paths. Context fields, prompts, queries, conversation, and response exports are size-bounded; saved/copy output is redacted again.

- Codex receives the prompt on stdin, never in argv, and runs with `shell=False`, `--sandbox read-only`, `--ephemeral`, `--ignore-user-config`, and an empty temporary working directory. Timeout uses terminate then kill fallback.
- The OpenAI key appears only in the HTTPS Authorization header, never in prompts, bodies, URLs, reports, process arguments, or saved state.
- Search queries are bounded, redacted, URL-encoded, and limited to allowlisted HTTPS Google/DuckDuckGo hosts. ARX does not scrape or import results.
- No network transmission occurs until the user selects an external action and consents to the provider. Prompt preview itself sends nothing.
- Responses carry `AI ADVISORY — UNVERIFIED AI ANALYSIS`, cannot modify evidence status, and cannot execute remediation. The human remains the decision-maker.

### GitHub Actions and artifacts

- `ARX CI` runs compile checks and pytest on `windows-latest` and `ubuntu-latest` for Python 3.10, 3.12, and 3.14; it separately builds and imports the sdist/wheel without publishing.
- Windows runs all GUI tests in isolated interpreters to match ARX's one-root production lifecycle; Ubuntu runs the complete GUI suite under Xvfb.
- `CodeQL` analyzes Python and GitHub Actions on push, pull request, schedule, and manual dispatch using pinned current action commits and least-privilege permissions.
- No PyPI publishing, cloud deployment, Conda, Django, release upload, signing, or provenance workflow was added. Installer and checksum outputs remain local release artifacts unless a separate release decision publishes them.

### Point 27 limitations

- OpenAI advice depends on network access, API credentials/quota, and a configured model. The test suite uses controlled transports; no live request was made.
- Cancelling OpenAI stops ARX waiting and ignores a late result but cannot retract a request already received by the remote service.
- Codex advice depends on an installed, authenticated, compatible CLI. Detection/version behavior and the subprocess boundary were tested; a live advisory was not sent.
- Browser opening depends on OS associations and network availability. URL/query generation was tested without importing web content.

## Remaining limitations

- Run every unchecked item in `docs/windows-desktop-acceptance.md` on an approved visible Windows 10/11 system or disposable VM before a release claim.
- Exercise interactive/silent install, launch-after-install, same-AppId upgrade, uninstall, and clean removal before marking Point 16 tested.
- Review screen-reader exposure, visible focus, real contrast, and 100/150/200% DPI behavior with representative hardware.
- Development installers are unsigned and use the default setup icon. Signing and branded icon work require an approved publisher identity, certificate handling policy, and assets.
- Core scanner cancellation safely ignores late results but cannot interrupt every in-progress bounded probe.
- No external AI or web output becomes deterministic ARX evidence, even when useful.

## Point-by-point final audit

| Point | Status | Main implementation | Tests | Remaining limitation |
|---:|---|---|---|---|
| 1 | TESTED | Repository/desktop/packaging audit and clean 105-test baseline. | Baseline suite. | None. |
| 2 | TESTED | Selectable, searchable, saveable reports and interactive results. | Desktop integration/UX tests. | Visible acceptance pending. |
| 3 | TESTED | Context-sensitive text, JSON, row, path, evidence, AI, and web menus. | Menu/action integration tests. | Native menu feel is manual. |
| 4 | TESTED | Ctrl+C/A/F/S, Enter, Esc, focusable controls and Edit routing. | Binding/widget tests. | Physical traversal is manual. |
| 5 | TESTED | Meaningful disabled text replaced with read-only selectable panels. | Text panel tests. | Decorative labels remain non-selectable. |
| 6 | TESTED | Safe reveal/open/details activation for double-click and Enter. | Existing/missing path activation tests. | OS visual result is manual. |
| 7 | TESTED | Selectable/focusable/copyable rows with textual status and actions. | Tree/status tests. | Display contrast is manual. |
| 8 | TESTED | Background work, busy states, status, cancel/ignore, and lifecycle cleanup. | Busy/cancel/shutdown/advisory tests. | Some bounded core probes cannot be interrupted mid-call. |
| 9 | TESTED | Parented dialogs, useful filters, cancellation, session directory memory. | Dialog integration tests. | Native appearance is manual. |
| 10 | TESTED | Human errors plus selectable/copyable technical details. | Error-surface tests. | Source exception detail varies. |
| 11 | TESTED | Concise tooltips on primary controls. | Tooltip coverage test. | Timing/readability is manual. |
| 12 | PARTIALLY IMPLEMENTED | Resizable panes/dialogs, scrollbars, DPI awareness, bounded geometry/tab state. | Geometry/state/scrollbar tests. | Maximize, real DPI, multi-monitor, and small-display behavior not manually run. |
| 13 | PARTIALLY IMPLEMENTED | Textual status, focusable controls, keyboard actions, contrast theme. | Structural accessibility tests. | Screen-reader, visible-focus, and real-display review not run. |
| 14 | TESTED | Central exact Unicode clipboard strategy with redaction-preserving exports. | Clipboard/redaction/export tests. | Users should still review shared exports. |
| 15 | TESTED | Existing-path-only Windows navigation without shell strings. | Path/Explorer/injection tests. | Native associations are manual. |
| 16 | PARTIALLY IMPLEMENTED | Portable build plus Inno x64 installer, stable upgrade identity, uninstall entries, and checksum. | Real Inno 7.1 compile, checksum verification, four packaging tests. | Install, silent install, upgrade, launch-after-install, uninstall, signing, and icon not exercised/completed. |
| 17 | TESTED | Factual About dialog with version, description, MIT, copyright, repository. | About content test. | Repository reference is text, not a dedicated link control. |
| 18 | TESTED | Useful File/Edit/Help menus with no empty View menu. | Menu structure test. | None. |
| 19 | TESTED | Reusable widgets, UX/path/state helpers, and advisory panel/provider abstractions. | Focused helper and integration suites. | None. |
| 20 | TESTED | Read-only observation, bounded input/output, redaction, safe subprocess/path/URL boundaries. | Hardening, advisory, web, workflow, and secret scans. | OpenAI transport cannot retract received requests. |
| 21 | TESTED | Meaningful deterministic tests plus isolated Windows GUI nodes and Linux Xvfb. | 170-test local/hosted suite. | Visible OS behavior remains manual by design. |
| 22 | TESTED | Complete Windows manual acceptance record including installer lifecycle. | Documentation completeness test. | Checklist actions remain unchecked/not tested. |
| 23 | TESTED | Usability-as-correctness regression principle in contribution policy. | Documentation test. | None. |
| 24 | PARTIALLY IMPLEMENTED | Audited all 15 Definition-of-Done conditions. | Table above and complete suite. | Visible resize/DPI/accessibility and installer lifecycle acceptance remain. |
| 25 | TESTED | Incremental reusable stages, focused tests, small commits, no history rewrite. | Checkpoint log, diffs, full suite. | Branch intentionally remains unmerged. |
| 26 | TESTED | This final engineering report covers problems, changes, files, tests, manual work, limitations, and security. | Report completeness test. | None. |
| 27 | TESTED | Optional redacted advisory/web bridges, contextual actions, consent/cancel, CI/package verification, and CodeQL. | AI/Codex/context/redaction/web/GUI/failure/workflow/hosted tests. | External services and OS browser behavior depend on configuration; no live OpenAI request was made. |

The implementation/audit task is closed with Points 12, 13, 16, and 24 explicitly incomplete for the concrete reasons above. The branch is not merged into `main`.
