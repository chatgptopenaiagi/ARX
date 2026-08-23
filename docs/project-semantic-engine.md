# Project-aware semantic engine

ARX 0.3 introduced project context without replacing the validated Machine DNA, Software DNA, capability, evidence, compatibility, exporter, CLI, or desktop foundations. ARX 3 retains that compatibility and promotes the same canonical project semantics across its expanded Windows and advisory surfaces.

## Data flow

```text
Project DNA -> requirement graph -------------------------+
                                                           |
Machine DNA -> provider graph -> execution context         |
                                  -> execution resolution --+
                                                           v
                                         relevance + satisfaction
                                                   + conflicts
                                                        |
                                                        v
                                               GREEN/YELLOW/RED
                                                        |
                                                        v
                                            read-only policy + plan
                                                        |
                                                        v
                                                explanation graph
                                                        |
                                                        v
                                             human and AI contracts
```

The models are presentation-independent typed Python data. The graphs are small typed node and edge collections, not a graph database.

## Project DNA

Project DNA is independent from Machine DNA and Software DNA. The first vertical slice recognizes Python projects through bounded, static reads of `pyproject.toml`, `.python-version`, `uv.lock`, `setup.cfg`, `setup.py` AST metadata, root `requirements.txt`/`requirements-*.txt`, and direct `requirements/*.txt` files. It records project identity, root, languages, ecosystems, build systems, manifests, requirements, optional requirements, entrypoint hints, evidence, provenance, purpose, and confidence.

Inspected files are never executed. Oversized, malformed, undecodable, missing, unsupported, or symbolic-link inputs remain explicit evidence or unknowns. `RequirementEvidence` retains capability, semantic evidence type, source kind/path/key, bounded raw value, confidence, and provenance. Confidence describes evidence quality; it cannot grant a selection record authority to overwrite a requirement record. Requirements retain their source manifest and field. Requirement edges distinguish `requires`, `selects`, and future causal dependencies.

`RequirementGraph` groups source claims by capability and identifies the effective requirement without deleting competing or complementary claims. Its provenance map, conflict IDs, and unknowns answer what ARX believes, which source supports that conclusion, and where interpretation is unsafe. For Python, `pyproject.toml` `[project].requires-python` is authoritative requirement evidence; `.python-version` is selection evidence; lockfiles are dependency-environment evidence; CI and inferred evidence remain separate question types. The effective Python requirement aggregates the typed evidence while source-claim records remain available for conflict analysis.

## Provider graph and identity

Machine DNA Python observations become providers. A provider identity is derived from its normalized absolute executable path, executable identity, version, provider kind, and discovery method. Equal versions at different paths remain different providers. Initial provider kinds include CPython, Conda, uv-managed, virtual-environment, WindowsApps alias, and unknown.

Raw paths remain internal evidence. Public and AI output passes through ARX redaction, including replacement of the inspected project root.

## Execution context and resolver

Resolution is scoped to an `ExecutionContext`: shell, working directory, command, effective PATH fingerprint, relevant-process-environment fingerprint, optional account-identity fingerprint, active virtual/Conda environment indicators, and uv indicators. Account identity is never exported in raw form. ARX fingerprints context-sensitive values instead of exporting the complete environment.

The Windows Python resolver uses fixed, timeout-bound, argument-array probes with `shell=False`, plus deterministic path lookup. `python`, `python3`, and `py` are resolved independently in a named context. It retains the first factual command path even when that path cannot be mapped to a usable interpreter provider; “found but unmapped/unparseable” is not rewritten as “not found.” It maps known command results to providers without executing project scripts. A context fingerprint change invalidates the meaning of a previous resolution.

The following remain separate:

- resolved provider: what the current command invokes;
- compatible providers: healthy existing providers satisfying the project constraint;
- pinned runtime/provider candidates: discovered providers matching explicit project selection evidence such as `.python-version`, regardless of whether they are currently usable;
- preferred provider: the healthy, policy-ranked compatible provider ARX recommends.

`PINNED` is project-derived intent. `PREFERRED` is an ARX policy decision. Neither proves that the current shell uses that provider; only `RESOLVED` answers that question for a named `ExecutionContext`. ARX does not add a `SELECTED` or `ACTIVE_FOR_PROJECT` role because it has no independent observation that a recommendation has been activated. Inventing that state would collapse intent or advice into execution fact.

Provider identity retains normalized executable path, observed version, kind, architecture, discovery method, and scope. Equal versions at different paths or architectures remain distinct. Scope is `user`, `machine`, or `unknown` only when path evidence supports that classification; ARX does not enumerate other user accounts.

Provider health is `HEALTHY`, `DEGRADED`, `UNHEALTHY`, or `UNKNOWN`. Only `HEALTHY` providers enter the usable compatible set. The fixed bounded probe verifies startup, version, interpreter bitness, and standard-library imports of `sys`, `ssl`, and `ctypes`. Timeouts, access failures, and potentially transient invocation failures remain `UNKNOWN`; malformed fixed-probe output is `DEGRADED`; a completed probe with a confirmed failure is `UNHEALTHY`. Found-but-unparseable providers retain `exists`, status, reason, and evidence rather than disappearing as if not found.

## Semantic engines

Relevance is one of `REQUIRED`, `OPTIONAL`, `CONDITIONALLY_REQUIRED`, `NOT_REQUIRED`, or `UNKNOWN_RELEVANCE`. Absence from one manifest never proves irrelevance.

Satisfaction is one of `SATISFIED`, `UNSATISFIED`, `PARTIAL`, `CONFLICT`, `AMBIGUOUS`, `UNKNOWN`, `OPTIONAL_UNAVAILABLE`, or `NOT_APPLICABLE`. Provider presence alone never proves satisfaction.

Conflicts are explicit records containing a stable ID, participants, evidence references, consequence, confidence, and blocking impact. Initial Python conflicts cover an incompatible default resolution and disagreement between `pyproject.toml` `project.requires-python` and `.python-version`.

Unknown is a successful result. Unsupported constraints, unreadable requirements, missing resolution, unverifiable provider health, and prerelease admission without an explicit prerelease boundary are not converted to certainty.

### Evidence authority and purpose

Evidence purpose is independent from confidence:

- `requirement`: an executable-version requirement, with `pyproject.toml` `project.requires-python` highest, then `uv.lock`, statically parsed `setup.cfg`, and statically parsed `setup.py`;
- `selection`: project runtime intent such as `.python-version`;
- `dependency_resolution`: lockfile evidence, which does not identify the current executable;
- `dependency_requirement`: package declarations, outside interpreter-only GREEN;
- future `ci` and `inferred_environment` evidence remain distinct from local execution truth.

Only a `requires` record can be the primary Python requirement. A selection-only project stays UNKNOWN/YELLOW. Lower-authority declarations cannot silently override the primary declaration. Identical constraints corroborate; safely detected overlapping but non-identical constraints produce a review warning without manufacturing an intersection; safely detected disjoint constraints produce `ARX-PROJECT-REQUIREMENT-CONFLICT`; unsupported expressions stay UNKNOWN. `setup.py` is parsed as bounded static AST and is never executed.

## Severity

The public semaphore is a compression of retained semantics:

- GREEN: required capabilities are satisfied, or an unavailable capability is only optional;
- YELLOW: uncertainty, ambiguity, partial satisfaction, or a mismatched default with an existing compatible provider;
- RED: a required capability is unsatisfied with no compatible provider, or an authoritative blocking requirement conflict exists.

`ARX-PYTHON-NO-COMPATIBLE-PROVIDER` is scoped to the authoritative primary Python runtime requirement. Secondary manifest records and selectors retain their own satisfaction evidence and can produce an explicit source conflict, but they cannot claim that no compatible provider exists when a healthy provider already satisfies the primary project constraint.

The aggregation rules are:

1. Evaluate the current resolution against the primary requirement; existence elsewhere does not make the current context satisfied.
2. Build the compatible set from healthy providers only. A degraded, unhealthy, unknown, or unavailable provider cannot justify GREEN or preference.
3. If the current provider satisfies, the interpreter verdict is GREEN unless explicit conflict, pin mismatch, overlapping declaration, or uncertainty contributes a warning/blocker.
4. If the current provider does not satisfy and a healthy compatible provider exists, emit `ARX-PYTHON-DEFAULT-MISMATCH`, select a preferred provider, and return YELLOW with zero provider-absence blockers.
5. If no healthy compatible provider exists but a potentially compatible provider has unknown/degraded usability, emit `ARX-PYTHON-PROVIDER-USABILITY-UNKNOWN` and abstain with YELLOW rather than claiming confirmed absence.
6. Emit `ARX-PYTHON-NO-COMPATIBLE-PROVIDER` and RED only when no healthy compatible or usability-unknown candidate can satisfy the required interpreter constraint.
7. A stale/unusable project-local pinned candidate with another healthy compatible candidate is recoverable YELLOW; preference is recomputed and the planner uses the alternative.

The canonical `ProjectReadinessResult` (the domain alias for `ProjectPreflight`) carries both `current_context_satisfaction` and `recoverability`. `UNSATISFIED` means the recorded command context does not meet the effective constraint; it does not mean the machine is incapable of meeting it. `RECOVERABLE` means a confirmed healthy compatible provider already exists. `BLOCKED` means at least one actual blocker remains. CLI, AI Contract, and desktop projections consume these fields and do not recalculate them.

Construction enforces constitutional invariants: preferred implies membership in the healthy compatible set; `ARX-PYTHON-NO-COMPATIBLE-PROVIDER` implies that set is empty; provider roles must match the effective evaluation and execution resolution; and GREEN cannot contain an unsatisfied evaluated required capability or any warning/blocker. Contradictory readiness results raise a semantic invariant error before presentation.

GREEN is deliberately narrow: it proves only that evaluated Python interpreter/toolchain requirements are satisfied in the recorded execution context. It does not prove dependency installation, lock synchronization, active virtual-environment correctness, importability of project packages, or successful application execution.

Interfaces always render a textual status as well as color.

## Policy and planner

The default policy prefers existing and project-local providers, forbids host mutation, global PATH changes, global runtime upgrades, security changes, and removal of alternative providers, and favors reversible recommendations.

The planner emits recommendations only. It never installs, uninstalls, changes PATH, modifies the registry, alters security, or executes remediation. A compatible existing provider is selected before an installation recommendation is considered. ARX reports that an absent provider needs human-managed provisioning, but does not perform it.

For recoverable YELLOW, the planner uses the healthy preferred existing provider and requests another preflight in the intended context. It does not install a duplicate runtime, edit global PATH, remove the current provider, or claim that the recommendation is already active. For pin disagreement it preserves the pin separately and either recommends a healthy pinned candidate or asks a human to review stale selection evidence. For RED it may recommend human-controlled provisioning, never automatic installation.

## Explanation graph

Stable typed nodes and edges preserve causal chains from evidence to requirement, provider resolution, satisfaction, finding/conflict, severity, and recommendation. Only the primary satisfaction and actual warning/blocker nodes cause the severity node; incidental satisfaction rows do not acquire blocking meaning merely by appearing in the graph. This supports the Evidence Inspector and the question “Why is this RED?” without coupling canonical data to GUI widgets.

## Contracts and versioning

The ARX application version and schema version evolve independently. ARX 2.0.0 retained legacy machine/software commands and their schema `0.1` envelopes; ARX 3.0.0rc1 retains that compatibility. Project-aware AI output continues to use schema `0.2` and separates facts, decisions, selected providers, blockers, warnings, recommendations, policy constraints, unknowns, and evidence references. See [AI contract 0.2](ai-contract-0.2.md).
