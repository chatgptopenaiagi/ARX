# ARX AI contract 0.2

Schema `0.2` is semantic compression for project preflight, not a dump of process state. It is independent from application version `0.3.0`.

Top-level sections are:

- `producer`: ARX identity and application version;
- `decision`: textual GREEN, YELLOW, or RED;
- `facts`: deterministic project, requirement, resolution, and compatibility observations;
- `decisions`: relevance, satisfaction, severity, and their reasons;
- `selected_providers`: resolved, compatible, and preferred provider roles;
- `blockers`: stable finding IDs and consequences that prevent progress;
- `warnings`: stable finding IDs and non-blocking consequences;
- `recommendations`: non-executing policy-compliant plan steps;
- `constraints`: active policy limits;
- `unknowns`: unresolved analytical questions and reasons;
- `evidence_references`: referenced observations with classification, source, confidence, and method.

Facts and decisions are not recommendations. Provider availability, command resolution, version compatibility, project relevance, satisfaction, severity, and remediation remain separate fields.

All content passes through ARX redaction. The project root is represented as `%PROJECT_ROOT%`, user-profile paths as `%USERPROFILE%`, and unrestricted environment values are absent. PATH and relevant environment state appear only as fingerprints.
