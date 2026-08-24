# ARX 4 foundation baseline

Baseline date: 2026-08-24 (Europe/Vienna)

Baseline commit: `11a1d76d1dd7225622cb41d862c8cb129ab4db80`

Repository: `chatgptopenaiagi/ARX`

## Checkout and toolchain gate

- The working copy is the separate, ordinary directory `C:\Codex-Projects\ARX-4`; it is not a link or Git worktree alias of `C:\Codex-Projects\ARX`.
- The checkout was clean on `main`, tracking `origin/main`, before Phase A began.
- `origin` fetch and push URLs are `https://github.com/chatgptopenaiagi/ARX.git`; the GitHub default branch is `main`.
- GitHub CLI authentication is active for the expected `chatgptopenaiagi` account. No credential value was copied into the checkout or report.
- PowerShell `7.6.5`, Git `2.55.0.windows.3`, GitHub CLI `2.98.0`, Codex CLI `0.149.0`, and Python `3.10.8` were available.
- Branches and tags were fetched with pruning. Existing tags were `v3.0.0-rc1`, `v2.0.0`, and `v0.2.0`; no stable `v3.0.0` tag existed.
- The latest `main` ARX CI and CodeQL runs for the baseline commit completed successfully. The Python publishing workflow for the same commit also completed successfully.

No `.env`, credential blob, browser state, token, protected file, or arbitrary untracked content was copied from the ARX 3 checkout.

## Epistemic model

The real `EvidenceKind` implementation in `src/arx/core/models.py` contains exactly:

```text
DECLARED / OBSERVED / INFERRED / UNKNOWN
```

`VERIFIED` is not an enum member. `Evidence` contains `kind`, `source`, `value`, `method`, `confidence`, and optional `note`. Fact provenance is therefore represented by `kind` and its supporting fields.

Decision/relation verification is implemented separately. `validate_readiness_result` rejects contradictory canonical composed state through semantic invariants. The project Codex exporter consumes that canonical result and applies an additional cross-field semantic guard. The test suite checks serialized project contracts against JSON Schema. These validation layers do not mutate supporting fact provenance.

The numeric-confidence scan found no calibration evidence. All production assignments, defaults, propagation, schema ranges, displays, and fixture values are catalogued in [Confidence semantics and assignment audit](confidence-semantics.md). Their current meaning is an uncalibrated detector-author weight, not probability, accuracy, or statistical confidence.

## Import graph and boundary enforcement

The current source imports form this effective layer graph, where `A -> B` means layer A imports layer B:

```text
core -> no other ARX layer
machine -> core
software -> core
project -> core
exporters -> core + project
advisory -> core
cli -> core + machine + software + project + exporters
desktop -> core + machine + software + project + exporters + advisory + cli
```

`core` imports no other ARX layer. `machine`, `software`, and `project` do not import `advisory`. Direct source inspection found no current cycle.

There is no dedicated automated architectural-boundary/import-cycle test in the baseline repository. Documentation describes the separation and semantic tests protect canonical ownership, but CI does not yet enforce the dependency graph or prove a forbidden import fails. That gap belongs to Phase B, including the required FAIL → revert → PASS mutation demonstration; it is not claimed complete in Phase A.

## Baseline tests

The Windows CI-equivalent topology passed from the clean baseline:

- `python -m compileall -q src tests`: PASS;
- non-GUI pytest collection: 143 passed;
- each Tk-backed GUI node in a fresh interpreter: 38 passed;
- total executed checks: 181 passed, none skipped in the isolated GUI run.

The repository was therefore safe to begin Phase A on the dedicated `arx3-final-acceptance` branch. No ARX 4 implementation began during this baseline gate.
