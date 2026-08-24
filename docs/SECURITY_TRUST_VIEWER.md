# Security & Trust viewer design

Status: design only; no production UI is introduced by this release-engineering phase.

A future read-only `Help > Security & Trust` view may display independent rows for:

- ARX version, release channel, build commit, architecture, and SHA-256;
- Authenticode status, publisher subject, issuer, and timestamp status;
- GitHub attestation availability and verified repository/workflow/commit;
- SBOM availability and format;
- release-security report availability;
- named malware-scan evidence and observation times.

Each row must expose its evidence source and observation time. Unknown, unavailable, blocked, and not-applicable states remain distinct. The UI must not combine the rows into a single `TRUSTED` or `NOT TRUSTED` badge, silently upgrade provenance, modify Windows policy, contact external services automatically, or change deterministic ARX evidence.
