# Security policy

## Report a vulnerability privately

Use the repository's [GitHub private vulnerability reporting](https://github.com/chatgptopenaiagi/ARX/security/advisories/new) flow. Do not attach credentials, private ARX reports, machine paths, protected credential blobs, transmission history, or exploit details to a public issue.

Include the affected ARX version, operating system, reproducible steps, expected impact, and the minimum redacted evidence needed to investigate. Maintainers will acknowledge the report, assess scope, and coordinate a fix and disclosure where appropriate.

## Supported release line

Security fixes focus on the current development line and newest published prerelease or stable release. Historical artifacts and package versions remain immutable; a fix is published as a new version rather than replacing an existing PyPI, TestPyPI, Git tag, or GitHub Release asset.

## Security boundaries

- ARX never executes inspected packages, unknown executables, or project scripts. Recognized project and software inputs are statically inspected with path, size, encoding, archive, and symlink bounds.
- Trusted diagnostic subprocesses use fixed argument arrays, `shell=False`, captured output, and timeouts. The resolution planner recommends actions but never applies remediation.
- Deterministic ARX evidence remains authoritative. External OpenAI API, Codex CLI, and web output is non-authoritative and has no path to mutate Evidence, EvidenceKind, compatibility, readiness, or semantic validation.
- OpenAI context crosses the provider boundary only after selection, filtering, redaction, bounding, preview, and explicit consent. Redaction is repeated at the real transport boundary.
- The packaged Windows credential store uses current-user DPAPI. Plaintext API keys must never enter configuration JSON, reports, logs, audit records, command arguments, URLs, release artifacts, or Git.
- External-transmission history is bounded, rotating, metadata-only, local to the user profile, explicitly clearable, and never implicitly exported or synchronized by ARX.
- Release publication uses reviewed full-SHA GitHub Actions and existing PyPI Trusted Publishers. GitHub Release creation does not authorize TestPyPI or production PyPI publication.

See [Security model](docs/security-model.md), [AI assistance security](docs/ai-assistance-security.md), and [Python package publishing](docs/python-package-publishing.md) for detailed trust boundaries.
