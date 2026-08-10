# Testing and acceptance boundaries

The normal `pytest` suite is deterministic. It uses temporary files, fixed provider inventories, monkeypatched subprocess results, and explicit execution-resolution evidence. It must not depend on the workstation having a particular Python layout, WindowsApps state, Flutter, CUDA, CMake, Java, or PATH.

Pytest markers are reserved for two non-default categories:

- `integration`: deterministic component integration that still uses controlled inputs;
- `live_workstation`: opt-in acceptance that observes the current workstation.

The release gate runs deterministic focused semantics, reusable cross-surface consistency tests, and the full deterministic suite first. Source CLI and packaged acceptance then run separately against the current Windows workstation. Packaged tests execute from a temporary directory outside the repository and record the observed versions; environment-specific results are acceptance evidence, not regression fixtures.

The cross-surface category constructs one Machine DNA provider inventory, Project DNA, Provider Graph, ExecutionContext, and engine report. CLI structured output, AI Contract 0.2, and the desktop view model must match the engine's verdict, blocker/warning IDs, resolved/compatible/pinned/preferred roles, current-context satisfaction, recoverability, provider health, and plan IDs. Presentation surfaces consume canonical semantics and do not own severity rules.

Schema tests use deterministic GREEN/YELLOW/RED fixtures and Draft 2020-12 validation for Project DNA, Project Preflight, and AI Contract 0.2. Separate semantic-guard tests deliberately construct cross-field contradictions that JSON Schema cannot express and require rejection.
