# Contributing

Use Python 3.10+, install `.[dev]`, and run `pytest`. Detectors must remain read-only, return evidence, survive absent tools, and include deterministic fixture tests. Project parsers must use bounded static reads and never execute discovered files. Semantic changes must preserve availability, resolution, compatibility, relevance, satisfaction, severity, and remediation as separate dimensions. Never disable a failing test to obtain green output.

ARX correctness includes both analytical correctness and human usability. A result that is technically correct but unnecessarily difficult to inspect, copy, navigate, export, or understand is an incomplete desktop result. Test reusable interaction logic directly and reserve manual acceptance for behavior that genuinely depends on Windows, a visible desktop, DPI, file associations, or installer state.

New presentation surfaces must consume the canonical report model rather than reimplement compatibility or severity decisions. Keep desktop state persistence to an explicit non-sensitive allowlist. External integrations must preserve the `select -> filter -> redact -> bound -> consent -> transmit -> unverified` boundary and must never promote advice or web content into ARX evidence. Match verification claims to the layer actually exercised: a built and checksummed installer is not an install, upgrade, or uninstall test.

