# Compatibility engine
Rules emit READY, PARTIAL, BLOCKED, UNKNOWN, or NOT_APPLICABLE; missing capability leaves use MISSING. Version 0.1 evaluates PE architecture, .NET host presence, declared capabilities, and a conservative subset of version constraints. Composite capabilities preserve their dependency names and explain gaps.

The version evaluator supports only exact numeric versions and `>`, `>=`, `=`, or `==`. Compound ranges, caret ranges, prerelease semantics, and vendor-specific schemes are reported as unknown. A detected executable alone does not prove an unsupported version constraint.
