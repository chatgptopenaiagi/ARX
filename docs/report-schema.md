# Report schemas

Application and data-contract versions are independent.

- ARX 0.3.0 preserves the legacy schema 0.1 envelope for `quick`, `deep`, `inspect`, `compare`, and bare `codex` workflows.
- Project DNA and project preflight structured output use schema 0.2 wrappers.
- `codex --project` uses the AI contract schema 0.2 described in [AI contract 0.2](ai-contract-0.2.md).

Evidence remains declared, observed, inferred, or unknown and carries confidence from zero to one. Project-aware public output replaces the project root with `%PROJECT_ROOT%` and applies existing user-profile redaction.

Canonical JSON schemas are in `schemas/project-dna.schema.json`, `schemas/project-preflight.schema.json`, and `schemas/ai-contract.schema.json`. GUI widgets are not schemas.

