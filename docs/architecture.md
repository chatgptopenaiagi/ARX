# Architecture
ARX separates machine observation, static software inspection, derived capabilities, deterministic compatibility rules, and report exporters. Functions in these modules are the 0.1 plugin seam for future `MachineScanner`, `SoftwareScanner`, `CapabilityProvider`, `CompatibilityRule`, and `Exporter` registrations. Python owns normalization; PowerShell is a read-only Windows evidence source.

