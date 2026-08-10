# ARX Phase II benchmark infrastructure

This directory defines benchmark protocols and evidence containers. It does not
contain performance conclusions. A claim remains `HYPOTHESIS` or `UNVERIFIED`
until a completed protocol, reviewable raw observations, and a generated
comparison are available.

The `.yaml` documents are deliberately written as JSON-compatible YAML 1.2 so
the comparison generator can validate them with the Python standard library.
This avoids adding a runtime dependency to ARX.

`ARX-BENCH-PY-001` is a matched-arm benchmark for the canonical recoverable
Python mismatch. Both arms receive the same scenario and task. The treatment is
only the availability of ARX semantic assistance.

Raw benchmark observations belong in each arm's `results.json`. Do not replace
the empty arrays with estimates, recollections, or inferred values. The
generator emits JSON to stdout unless `--output` is supplied:

```powershell
python benchmarks/generate_comparison.py ARX-BENCH-PY-001
```

No Energy, Token Savings, Time Savings, or Economic report is defined here.
