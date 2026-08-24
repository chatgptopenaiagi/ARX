# Release Security Black Box

The release-security record is a bounded public index of defined gates and their evidence. It is not a claim that ARX is secure. The only permitted lead claim is:

> ARX passed the following defined security gates.

The schema is `security/release-record/release-security-record.schema.json`; its unfilled template is adjacent. The provenance bundle has a separate schema under `security/provenance/` because build provenance is not a gate status or Windows signature.

Every final gate row contains its independent result, evidence reference, and limitation. Allowed results are `PASS`, `PASS WITH LIMITATION`, `REVIEWED`, `NOT APPLICABLE`, `BLOCKED`, and `FAIL`. The record also gives each release artifact an exact reproducibility classification; structural equivalence cannot be serialized as bit-for-bit reproducibility.

Validate a template explicitly:

```powershell
python scripts/validate-security-record.py `
  security/release-record/release-security-record.template.json `
  --schema security/release-record/release-security-record.schema.json `
  --allow-template
```

Omit `--allow-template` for a final record. Final validation rejects unresolved placeholders, invalid release identities or digests, duplicate gate/artifact names, absolute private local paths, secret-bearing field names, and credential-shaped values.

The public bundle may contain sanitized summaries and hashes. It must never contain raw credentials, DPAPI blobs, signing private material, private local paths, sensitive raw logs, provider request/response bodies, or user transmission history.
