# ARX AI contract 0.2

Schema `0.2` is semantic compression for project preflight, not a dump of process state. It is independent from the application version: it shipped with ARX 2.0.0, was preserved by ARX 3.0.0rc1, ARX 4.0.0b1, and ARX 4.0.0b2, and remains the project/AI contract for ARX 4.0.0b3.

Top-level sections are:

- `producer`: ARX identity and application version;
- `decision`: textual GREEN, YELLOW, or RED;
- `facts`: deterministic project, typed requirement evidence/graph, resolution, and compatibility observations;
- `decisions`: relevance, explicitly scoped current-context satisfaction, recoverability, severity, and their reasons;
- `selected_providers`: resolved, compatible, preferred, and pinned provider roles;
- `blockers`: stable finding IDs and consequences that prevent progress;
- `warnings`: stable finding IDs and non-blocking consequences;
- `recommendations`: non-executing policy-compliant plan steps;
- `constraints`: active policy limits;
- `unknowns`: unresolved analytical questions and reasons;
- `evidence_references`: referenced observations with classification, source, confidence, and method.

Facts and decisions are not recommendations. Provider availability, command resolution, version compatibility, project relevance, satisfaction, severity, and remediation remain separate fields.

`selected_providers` preserves `resolved`, `compatible`, `preferred`, `pinned`, and `pinned_constraints` separately. “Selected” is the historical section name; it does not assert that preferred or pinned providers are active. Provider records retain existence, health status/reason, architecture, and evidence-driven user/machine/unknown scope.

Every blocker and warning contains stable `id`/`finding_id`, `severity`, `category`, message, and evidence references (plus confidence for explicit conflicts). Arrays for `blockers`, `warnings`, and `unknowns` are always present, including when empty. The evaluated requirement is structured under `facts`, so a consumer can trace requirement -> current resolution -> compatible set -> preferred recommendation -> finding -> evidence without parsing prose.

The `decisions.scope` value is `python_interpreter_and_toolchain_requirements`. `decisions.current_context` says whether the effective requirement is satisfied by the recorded execution resolution. `decisions.recoverability` separately says `READY`, `RECOVERABLE`, `BLOCKED`, or `UNKNOWN` and carries compatible/preferred identities. A GREEN decision does not claim that dependencies are installed, a lockfile matches site-packages, project imports succeed, or the application runs.

`facts.requirements` preserves every source claim plus typed evidence (`requirement`, `selection`, `dependency_environment`, `dependency_requirement`, `ci_tested`, or `inferred`). `facts.requirement_graph` identifies the effective claim and retains provenance, conflicts, and interpretation unknowns. A `requires-python` range is never serialized as an executable identity, and project `PINNED` intent is never serialized as ARX `PREFERRED` advice.

The serializer runs schema-independent semantic validation because JSON Schema cannot express all cross-field laws. It rejects preferred providers outside the compatible set, a no-compatible blocker paired with compatible/preferred providers, GREEN with an unsatisfied required current context, mismatched decision/severity fields, and invalid recoverability claims.

## Freshness

The contract retains the report, project, and (when supplied by Machine DNA) provider-inventory observation timestamps; project-evidence fingerprint; provider-inventory fingerprint (including existence and health state); execution-context ID; PATH fingerprint; relevant-process-environment fingerprint; and optional one-way account fingerprint. These fields have operational meaning: a consumer can compare two reports and detect aged inventory, changed manifests, provider state, command context, account context, PATH, venv/Conda/uv indicators, or other relevant environment state. A null inventory timestamp honestly means the engine was given providers without scan-time metadata. These fields do not claim continuous freshness and do not trigger automatic rescans; a consumer should request a new preflight when the intended context or evidence fingerprints differ.

All content passes through ARX redaction. The project root is represented as `%PROJECT_ROOT%`, user-profile paths as `%USERPROFILE%`, and unrestricted environment values are absent. PATH and relevant environment state appear only as fingerprints.
