# Report schemas

Application and data-contract versions are independent.

- ARX 0.3.0 preserves the legacy schema 0.1 envelope for `quick`, `deep`, `inspect`, `compare`, and bare `codex` workflows.
- Project DNA and project preflight structured output use schema 0.2 wrappers.
- `codex --project` uses the AI contract schema 0.2 described in [AI contract 0.2](ai-contract-0.2.md).

Evidence remains declared, observed, inferred, or unknown and carries confidence from zero to one. Project-aware public output replaces the project root with `%PROJECT_ROOT%` and applies existing user-profile redaction.

Canonical JSON schemas are in `schemas/project-dna.schema.json`, `schemas/project-preflight.schema.json`, and `schemas/ai-contract.schema.json`. GUI widgets are not schemas.

Schema `0.1` is the legacy machine/software scan envelope. Schema `0.2` is a separate project-intelligence and AI semantic contract, not a backward-compatible extension that a `0.1` parser can consume blindly. Downstream tools must inspect `schema_version` and the envelope shape before parsing: use `0.1` readers for machine/software reports and `0.2` readers for Project DNA, Project Preflight, and AI Contract output. Application version `0.3.x` is independent from either schema version.

AI Contract 0.2 is frozen around the canonical project domain: typed requirements and provenance, execution-context-scoped resolution, resolved/compatible/pinned/preferred roles, current-context satisfaction, recoverability, structured findings, plan identity, and freshness fingerprints. Empty blocker/warning/unknown collections remain arrays; absent singular provider roles are `null`.

