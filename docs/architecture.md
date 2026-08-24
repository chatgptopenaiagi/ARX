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

## Decision record: canonical evidence and thin surfaces

The canonical report model is the sole owner of observed facts, compatibility, satisfaction, severity, and remediation. CLI output, desktop views, exports, context menus, and external-advisory context are projections of a validated report; they do not recalculate its semantics. Presentation and interaction code may select a canonical object, format it, copy it, or navigate to its source, but it must preserve the object's stable IDs, provenance, verdict, and trust classification.

Optional integrations attach after canonical validation and fail independently. They may receive a deliberately selected and redacted projection, but their output is never fed back into the evidence graph. This keeps a richer desktop or advisory surface from becoming a second evidence engine.

## Decision record: fact provenance is separate from decision validation

The fact-provenance enum is exactly `DECLARED / OBSERVED / INFERRED / UNKNOWN`. VERIFIED is not an `EvidenceKind` and must not be introduced as a peer fact state. An `Evidence` record makes these claim dimensions traceable:

- **VALUE**: `value`, the claim ARX records;
- **PROVENANCE**: `kind`, how the fact was obtained;
- **BASIS**: `source`, `method`, and optional `note`, which identify the detector, input, rule, or observation behind it.

For a relation or decision, ARX additionally records **VALIDATION**: the semantic invariant, composed-state guard, and, where serialized, schema validation that accepted the conclusion. Validation operates on the relation or decision; it never rewrites the provenance of supporting facts. Numeric `confidence` is an uncalibrated detector-author weight and cannot serve as provenance or validation. The assignment inventory and limitations are documented in [Confidence semantics and assignment audit](confidence-semantics.md).

## Decision record: path identity follows the evidence

Evidence can describe a Windows path while ARX tests or processes the report on another operating system. Absolute-path detection, containment, redaction, and stable identity therefore follow the path syntax carried by the evidence, not the host process. Foreign absolute paths use the matching pure-path semantics and must never be accidentally resolved beneath the host's current working directory. The same observed path must retain the same meaning and identifier across supported hosts.

## Decision record: owned desktop lifecycles

The desktop has one Tk root per application process. Potentially slow work runs outside the UI thread and communicates through an owned queue; only the UI thread touches widgets. The owning window tracks scheduled callbacks, cancellation signals, worker results, and child windows. Teardown cancels owned callbacks and operations, and late results are ignored safely. Persisted desktop state is an explicit allowlist of non-sensitive presentation values rather than a serialization of live application state.

This lifecycle ownership is part of correctness: it prevents destroyed widgets, queued callbacks, or optional integrations from outliving the surface that requested them.

## Decision record: portable payload before installer shell

The validated portable desktop payload is the canonical Windows application artifact. The installer consumes that payload and adds stable application identity, shortcuts, file associations, and uninstall metadata; it does not define a separate application build. Installer compilation and checksum generation prove artifact construction and integrity. Install, upgrade, association, and uninstall behavior are accepted only when those operating-system transitions are actually exercised.

## Data flow

```text
fixed probes/CIM -> Machine DNA -> capability graph
static bytes/manifests -> Software DNA -> compatibility rules -> exporters
static project manifests -> Project DNA -> requirement graph
Machine DNA -> provider graph -> execution context -> execution resolution
requirements + resolution -> semantic engines -> severity -> policy-aware plan
```

Every inferred requirement retains its evidence classification and confidence. Unsupported constraints remain unknown rather than being treated as satisfied.

## Semantic law

ARX keeps each analytical question independent:

```text
availability != resolution
resolution != compatibility
compatibility != relevance
relevance != satisfaction
satisfaction != severity
severity != remediation
```

Availability records what providers exist. Resolution records what a command invokes in one execution context. Compatibility compares a provider with a requirement. Relevance establishes whether the project needs the capability. Satisfaction combines the relevant requirement with the selected resolution. Severity compresses the consequence to GREEN, YELLOW, or RED. Remediation is a separate, non-executing plan constrained by policy.

See [Project-aware semantic engine](project-semantic-engine.md) for the data flow and decision rules.
