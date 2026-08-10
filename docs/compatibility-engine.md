# Compatibility engine
Rules emit READY, PARTIAL, BLOCKED, UNKNOWN, or NOT_APPLICABLE; missing capability leaves use MISSING. Version 0.1 evaluates PE architecture, .NET host presence, declared capabilities, and a conservative subset of version constraints. Composite capabilities preserve their dependency names and explain gaps.

The version evaluator supports only exact numeric versions and `>`, `>=`, `=`, or `==`. Compound ranges, caret ranges, prerelease semantics, and vendor-specific schemes are reported as unknown. A detected executable alone does not prove an unsupported version constraint.

## Project semantic engine

ARX 0.3 preserves the Software DNA compatibility engine above and adds an independent Python project pipeline. Its conservative Python evaluator supports comma-separated exact, equality, inequality, and ordered numeric/prerelease constraints. Unsupported operators and vendor schemes remain UNKNOWN.

The project pipeline does not reuse a single compatibility status. It records the resolved provider, all compatible providers, a policy-ranked preferred provider, requirement relevance, satisfaction, explicit conflicts, and severity separately. A mismatched resolution with an existing compatible provider is YELLOW; a required mismatch with no compatible provider is RED; an optional unavailable capability is not automatically RED.
