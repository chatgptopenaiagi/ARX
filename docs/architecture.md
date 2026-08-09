# Architecture
ARX separates machine observation, static software inspection, derived capabilities, deterministic compatibility rules, and report exporters. Functions in these modules are the 0.1 plugin seam for future `MachineScanner`, `SoftwareScanner`, `CapabilityProvider`, `CompatibilityRule`, and `Exporter` registrations. Python owns normalization; PowerShell is a read-only Windows evidence source.

## Decision record: lean extension contracts

Version 0.1 uses Python `Protocol` contracts rather than runtime plugin discovery. This keeps installation dependency-free while making detector, rule, and exporter boundaries explicit. Entry-point discovery and detector isolation are deferred until third-party plugins exist.

## Decision record: bounded static reads

PE targets are parsed as bytes, archives are listed without extraction, and only bounded (1 MiB or smaller) recognized manifests are read. Unknown targets are never launched. PowerShell and developer-tool execution is restricted to fixed diagnostic commands with argument arrays, timeouts, captured streams, and `shell=False`.

## Data flow

```text
fixed probes/CIM -> Machine DNA -> capability graph
static bytes/manifests -> Software DNA -> compatibility rules -> exporters
```

Every inferred requirement retains its evidence classification and confidence. Unsupported constraints remain unknown rather than being treated as satisfied.
