# Testing and acceptance boundaries

The normal `pytest` suite is deterministic. It uses temporary files, fixed provider inventories, monkeypatched subprocess results, and explicit execution-resolution evidence. It must not depend on the workstation having a particular Python layout, WindowsApps state, Flutter, CUDA, CMake, Java, or PATH.

Pytest markers are reserved for two non-default categories:

- `integration`: deterministic component integration that still uses controlled inputs;
- `live_workstation`: opt-in acceptance that observes the current workstation.

The release gate runs deterministic focused semantics, reusable cross-surface consistency tests, and the full deterministic suite first. Source CLI and packaged acceptance then run separately against the current Windows workstation. Packaged tests execute from a temporary directory outside the repository and record the observed versions; environment-specific results are acceptance evidence, not regression fixtures.

The cross-surface category constructs one Machine DNA provider inventory, Project DNA, Provider Graph, ExecutionContext, and engine report. CLI structured output, AI Contract 0.2, and the desktop view model must match the engine's verdict, blocker/warning IDs, resolved/compatible/pinned/preferred roles, current-context satisfaction, recoverability, provider health, and plan IDs. Presentation surfaces consume canonical semantics and do not own severity rules.

Schema tests use deterministic GREEN/YELLOW/RED fixtures and Draft 2020-12 validation for Project DNA, Project Preflight, and AI Contract 0.2. Separate semantic-guard tests deliberately construct cross-field contradictions that JSON Schema cannot express and require rejection.

## Runtime-shaped GUI testing

Test topology follows runtime topology. ARX creates one Tk root per application process, so a shared interpreter must not accumulate independent GUI test applications whose toolkit-global event state can leak between nodes. On Windows, every GUI test node runs in a fresh interpreter; this is isolation, not a skip, and the wrapper fails unless every collected node executes successfully. Linux runs the full GUI suite under Xvfb. UI-neutral selection, formatting, clipboard, path, and state-validation helpers remain ordinary deterministic unit tests.

Visible desktop acceptance remains a separate layer because a headless widget assertion cannot prove focus order, clipping, DPI behavior, Explorer integration, or native installer state.

## Phase C boundary testing

Pure tests cover general-chat emptiness, context selection, redaction, immutable detachment from canonical objects, provenance-field preservation, conversation bounds, provider-session isolation, Ask Both's exact two-provider rule, partial provider failure, and non-authoritative comparison output. GUI tests run each Intelligence Console node in the same fresh-interpreter topology as the rest of the desktop suite. They exercise consent refusal, background provider work, cancellation, independent provider switching, context attach/detach, preview, flat Ask Both results, and the explicit Compare Responses reveal.

Bounded Hypothesis properties generate local JSON-compatible context values and conversation text. They require every context preview to remain valid JSON under the 16,000-character cap, every context mapping to reject mutation, every session to honor turn/character bounds, and every comparison category to honor item bounds. These properties do not call external providers.

Tests also snapshot or deep-copy deterministic inputs before adversarial provider output. A response that says `VERIFIED` or asks ARX to change readiness may be displayed as advisory text, but cannot change the original object or create an `EvidenceKind` value.

## Evidence levels must not be promoted

Artifact construction evidence is not lifecycle evidence. The following claims remain distinct:

- unit and component tests verify deterministic implementation behavior;
- a portable smoke test verifies that the built payload launches and performs its bounded workflow outside the source tree;
- installer compilation and checksum verification establish that a reproducible artifact was created intact;
- install, upgrade, file-association, and uninstall behavior are tested only by exercising those transitions on Windows.

A lower layer may be a prerequisite for a higher one, but it cannot be reported as proof of the higher layer. An unchecked manual acceptance item is incomplete evidence, not a passing result.

GitHub CI runs the deterministic suite on Windows and Linux for Python 3.10, 3.12, and 3.14. Linux GUI tests run under Xvfb. A separate package job builds the sdist and wheel without publishing, while CodeQL analyzes Python and GitHub Actions. The visible Windows behaviors that are intentionally outside stable unit tests are recorded in the [ARX Desktop manual acceptance checklist](windows-desktop-acceptance.md); unchecked items must not be reported as tested.

## Python distribution release evidence

The Python package gate keeps these claims separate:

- `python -m build` proves that the source tree can produce the expected wheel and source distribution;
- `python -m twine check --strict` validates package metadata and PyPI README rendering compatibility;
- installing the wheel into a fresh environment outside the checkout proves that its imports and console entry points do not depend on editable local source;
- a TestPyPI upload plus a new TestPyPI environment proves the Trusted Publishing rehearsal and index installation path;
- production publication is verified only by comparing the production-index wheel and source distribution with the reviewed GitHub Release files and installing the exact approved version in another fresh environment.

The manual publishing workflow consumes the reviewed GitHub Release wheel and source distribution. A TestPyPI-target dispatch publishes and verifies them first; a separate production-target dispatch requires the exact files to already exist on TestPyPI before it can reach the protected production environment. Only the mutually exclusive publishing jobs have OIDC permission. A GitHub Release event cannot trigger either index. See [Python package publishing](python-package-publishing.md) for the trust boundary and release procedure.
