# ARX 0.3.0

## Project-aware semantic compatibility and resolution

ARX 0.3.0 extends the validated ARX 0.2 foundation with the first Python Project DNA vertical slice. Existing Machine DNA, Software DNA, capability, compatibility, evidence, CLI, exporter, and desktop workflows remain available.

## What is new

- bounded static inspection of `pyproject.toml`, `.python-version`, `uv.lock`, root requirements files, and direct `requirements/*.txt` files;
- sourced typed requirements and causal requirement edges;
- stable provider identities that keep equal-version executables distinct;
- CPython, Conda, uv-managed, virtual-environment, WindowsApps alias, and unknown provider kinds;
- execution contexts with working directory and PATH/environment fingerprints;
- fixed-probe Python command resolution without project-script execution;
- independent resolved, compatible, and preferred provider roles;
- relevance, satisfaction, conflict, unknown, and GREEN/YELLOW/RED severity semantics;
- stable Python/project finding IDs;
- a no-host-mutation policy and recommendation-only resolution planner;
- explanation nodes/edges from evidence through severity and recommendation;
- AI contract schema 0.2 with facts and advice kept separate;
- additive `project`, `resolve`, `preflight`, and `codex --project` CLI workflows;
- desktop Project Preflight and Project Readiness views with text in addition to color.

## Version compatibility

The application version is 0.3.0. Project-aware structured and AI contracts use schema version 0.2. Existing ARX 0.2 machine/software report commands retain schema version 0.1.

## Security and privacy

Project inspection is static, size-bounded, encoding-checked, and does not follow recognized manifest symlinks. Scripts are evidence, never commands. Resolver diagnostics are fixed argument-array subprocesses with `shell=False` and timeouts. The planner does not execute remediation. Project roots and user profiles are redacted from AI/public project output, and raw PATH/environment values are replaced by fingerprints or presence indicators.

## Known limitations

- Python is the only project ecosystem implemented in this release.
- The constraint evaluator intentionally supports a conservative subset; unsupported forms remain UNKNOWN.
- `.python-version` conflicts with `project.requires-python` are explicit, while general range-intersection reasoning is deferred.
- pip-to-interpreter mismatch detection is deferred.
- Provider discovery reuses current Machine DNA observations; project-local environment discovery will expand later.
- The planner recommends human-controlled provisioning when no provider exists but never performs it.
- Rich GUI traversal of every explanation edge is deferred; canonical graph data and evidence remain available in reports and the inspector.
