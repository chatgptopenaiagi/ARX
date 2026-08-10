# Project-aware semantic engine

ARX 0.3 adds project context without replacing the validated ARX 0.2 Machine DNA, Software DNA, capability, evidence, compatibility, exporter, CLI, or desktop foundations.

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

Project DNA is independent from Machine DNA and Software DNA. The first vertical slice recognizes Python projects through bounded, static reads of `pyproject.toml`, `.python-version`, `uv.lock`, root `requirements.txt`/`requirements-*.txt`, and direct `requirements/*.txt` files. It records project identity, root, languages, ecosystems, build systems, manifests, requirements, optional requirements, entrypoint hints, evidence, provenance, and confidence.

Inspected files are never executed. Oversized, malformed, undecodable, missing, unsupported, or symbolic-link inputs remain explicit evidence or unknowns. Requirements retain their source manifest and field. Requirement edges distinguish `requires`, `selects`, and future causal dependencies.

## Provider graph and identity

Machine DNA Python observations become providers. A provider identity is derived from its normalized absolute executable path, executable identity, version, provider kind, and discovery method. Equal versions at different paths remain different providers. Initial provider kinds include CPython, Conda, uv-managed, virtual-environment, WindowsApps alias, and unknown.

Raw paths remain internal evidence. Public and AI output passes through ARX redaction, including replacement of the inspected project root.

## Execution context and resolver

Resolution is scoped to an `ExecutionContext`: shell, working directory, command, effective PATH fingerprint, relevant-process-environment fingerprint, active virtual/Conda environment indicators, and uv indicators. ARX fingerprints context-sensitive values instead of exporting the complete environment.

The Windows Python resolver uses fixed, timeout-bound, argument-array probes with `shell=False`, plus deterministic path lookup. It maps the first command result to a provider without executing project scripts. A context fingerprint change invalidates the meaning of a previous resolution.

The following remain separate:

- resolved provider: what the current command invokes;
- compatible providers: healthy existing providers satisfying the project constraint;
- preferred provider: the policy-ranked compatible provider ARX recommends.

## Semantic engines

Relevance is one of `REQUIRED`, `OPTIONAL`, `CONDITIONALLY_REQUIRED`, `NOT_REQUIRED`, or `UNKNOWN_RELEVANCE`. Absence from one manifest never proves irrelevance.

Satisfaction is one of `SATISFIED`, `UNSATISFIED`, `PARTIAL`, `CONFLICT`, `AMBIGUOUS`, `UNKNOWN`, `OPTIONAL_UNAVAILABLE`, or `NOT_APPLICABLE`. Provider presence alone never proves satisfaction.

Conflicts are explicit records containing a stable ID, participants, evidence references, consequence, confidence, and blocking impact. Initial Python conflicts cover an incompatible default resolution and disagreement between `pyproject.toml` `project.requires-python` and `.python-version`.

Unknown is a successful result. Unsupported constraints, unreadable requirements, missing resolution, and unverifiable provider health are not converted to certainty.

## Severity

The public semaphore is a compression of retained semantics:

- GREEN: required capabilities are satisfied, or an unavailable capability is only optional;
- YELLOW: uncertainty, ambiguity, partial satisfaction, or a mismatched default with an existing compatible provider;
- RED: a required capability is unsatisfied with no compatible provider, or an authoritative blocking requirement conflict exists.

Interfaces always render a textual status as well as color.

## Policy and planner

The default policy prefers existing and project-local providers, forbids host mutation, global PATH changes, global runtime upgrades, security changes, and removal of alternative providers, and favors reversible recommendations.

The planner emits recommendations only. It never installs, uninstalls, changes PATH, modifies the registry, alters security, or executes remediation. A compatible existing provider is selected before an installation recommendation is considered. ARX 0.3 reports that an absent provider needs human-managed provisioning, but does not perform it.

## Explanation graph

Stable typed nodes and edges preserve causal chains from evidence to requirement, provider resolution, satisfaction, conflict, consequence, severity, and recommendation. This supports the Evidence Inspector and the question “Why is this RED?” without coupling canonical data to GUI widgets.

## Contracts and versioning

The ARX application version and schema version evolve independently. ARX 0.3.0 retains legacy ARX 0.2 commands and their schema `0.1` envelopes. Project-aware AI output uses schema `0.2` and separates facts, decisions, selected providers, blockers, warnings, recommendations, policy constraints, unknowns, and evidence references. See [AI contract 0.2](ai-contract-0.2.md).
