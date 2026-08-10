# Architecture
ARX separates machine observation, static software and project inspection, derived capabilities, deterministic compatibility rules, semantic project preflight, and report exporters. Functions in these modules are the lean extension seam for future `MachineScanner`, `SoftwareScanner`, `CapabilityProvider`, `CompatibilityRule`, and `Exporter` registrations. Python owns normalization; PowerShell is a read-only Windows evidence source.

## Decision record: lean extension contracts

Version 0.1 uses Python `Protocol` contracts rather than runtime plugin discovery. This keeps installation dependency-free while making detector, rule, and exporter boundaries explicit. Entry-point discovery and detector isolation are deferred until third-party plugins exist.

## Decision record: generic provider-resolution roles

The proven cross-ecosystem seam is `assign_provider_roles`: it separates resolved fact, compatible-set predicate, deterministic preference policy, and pinned-intent predicate into a presentation-independent `ProviderRoles` result. Python supplies version/health and `.python-version` predicates; the role assignment does not encode Python syntax. This is the minimal generic contract required before ecosystem #2. No speculative adapter hierarchy or new ecosystem was added.

An `ACTIVE_FOR_PROJECT`/`SELECTED` fact was rejected for 0.3: ARX observes current execution resolution, project pin evidence, and its own preference, but does not observe that a recommendation was activated. Future adapters must not copy Python aggregation into presentation layers; they should feed ecosystem predicates through the shared role contract.

## Decision record: locked project semantic domain

ARX uses one canonical model rather than JSON-shaped parallel types. `RequirementEvidence` types provenance by the question it answers; `Requirement` retains an effective specifier, interpretation state, conflicts, and unknowns; `RequirementGraph` groups claims by capability; `Provider`/`ProviderRoles` represent records and resolution roles; `ExecutionContext` scopes command truth; `SeverityDecision` separates current-context satisfaction from recoverability; and `ProjectPreflight` is the canonical `ProjectReadinessResult` consumed by all surfaces. Domain-language aliases document these mappings without introducing duplicate serialization models.

Runtime guards validate the canonical result before a CLI, GUI, or AI serializer can consume it. The AI Contract 0.2 serializer then derives its structure from that result and applies a second cross-field guard after redaction. JSON Schema 0.2 freezes the serialized shape but does not own semantic decision logic.

## Decision record: bounded static reads

PE targets are parsed as bytes, archives are listed without extraction, and only bounded (1 MiB or smaller) recognized manifests are read. Unknown targets are never launched. PowerShell and developer-tool execution is restricted to fixed diagnostic commands with argument arrays, timeouts, captured streams, and `shell=False`.

## Data flow

```text
fixed probes/CIM -> Machine DNA -> capability graph
static bytes/manifests -> Software DNA -> compatibility rules -> exporters
static project manifests -> Project DNA -> requirement graph
Machine DNA -> provider graph -> execution context -> execution resolution
requirements + resolution -> semantic engines -> severity -> policy-aware plan
```

Every inferred requirement retains its evidence classification and confidence. Unsupported constraints remain unknown rather than being treated as satisfied.

## ARX 0.3 semantic law

ARX 0.3 keeps each analytical question independent:

```text
availability != resolution
resolution != compatibility
compatibility != relevance
relevance != satisfaction
satisfaction != severity
severity != remediation
```

Availability records what providers exist. Resolution records what a command invokes in one execution context. Compatibility compares a provider with a requirement. Relevance establishes whether the project needs the capability. Satisfaction combines the relevant requirement with the selected resolution. Severity compresses the consequence to GREEN, YELLOW, or RED. Remediation is a separate, non-executing plan constrained by policy.

See [Project-aware semantic engine](project-semantic-engine.md) for the ARX 0.3 data flow and decision rules.
