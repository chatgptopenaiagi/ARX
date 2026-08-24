# Confidence semantics and assignment audit

## Meaning and limits

Every numeric `confidence` currently emitted by ARX is an uncalibrated **detector-author weight** bounded to `[0, 1]`. No repository calibration dataset, reliability curve, measured-accuracy study, or statistical model supports these numbers. Consequently, a value is **not a probability**, measured accuracy, statistical confidence, likelihood of compatibility, or safety assurance.

The values retain relative branch strength chosen by the detector author. `1.0` means the implementation assigns its maximum heuristic weight to that branch; it does not mean certainty. `0.0` means the resolver has no command-resolution support in that result; it does not mean a zero-percent chance that a runtime exists. Confidence cannot change `EvidenceKind`, establish observation, validate a decision, or upgrade external advice. Provenance comes from `kind`; basis comes from `source`, `method`, and `note`; decision validation comes from semantic invariants and schema/composed-state guards.

Production code uses confidence only as emitted metadata, display/export data, conservative `min(...)` propagation into conflict records, and a legacy coverage aggregate. Status, relevance, satisfaction, severity, and remediation are determined by their own rules. This audit preserves the fields for schema compatibility while documenting their actual semantics.

## Evidence and ToolRecord defaults

| Location | Assignment | Current basis |
|---|---:|---|
| `core.models.Evidence` | `1.0` default | Maximum author weight when a detector does not override the field. |
| `core.models.ToolRecord` | `1.0` default | Maximum author weight when tool detection does not override it. |
| `project.models.Requirement` | `1.0` default | Maximum author weight for a constructed requirement unless its parser supplies another value. |
| `project.models.ProjectDNA` | `1.0` default | Maximum aggregate weight before scanner completeness adjustments. |
| `project.models.Provider` and `resolver.make_provider` | `1.0` default | Maximum provider-record weight unless discovery supplies another value. |
| `project.models.ExecutionResolution` | `0.0` default | No command-resolution support until the resolver supplies evidence. |
| `project.models.Conflict` | no numeric default | Receives the minimum supporting requirement/resolution weight. |

## Machine and provider discovery

| Detector branch | Assignment | Current basis |
|---|---:|---|
| Tool version probe exits zero | `1.0` ToolRecord; evidence default `1.0` | Fixed executable/argument probe completed successfully. |
| Tool version probe exits nonzero | `0.7` ToolRecord; evidence default `1.0` | Path and output were observed, but the tool did not complete successfully. |
| Tool probe raises an OS error or times out | `0.5` record and UNKNOWN evidence | Executable path was found, but the probe result is unavailable. |
| Python fixed probe confirms unhealthy via nonzero exit | `0.9` OBSERVED evidence | Invocation completed and supplied a failure result. |
| Python returns malformed or incomplete fixed-probe output | `0.6` UNKNOWN evidence | Provider started, but the expected health record was incomplete or invalid. |
| Python fixed probe confirms complete healthy data | `1.0` OBSERVED evidence | Startup, version, bitness, SSL, and fixed imports completed. |
| Python access, timeout, or OS invocation failure | `0.5` UNKNOWN evidence | Existence may be known, but health is not. |
| Machine Python record converted to Provider | `1.0` when healthy; otherwise `0.7` | Coarse provider-conversion weight; status and health fields retain the actual distinction. |
| Other observed Machine DNA records | evidence default `1.0` | Direct fixed probe, API, CIM, PATH, or runtime-list observation. |

## Software inspection

| Detector branch | Assignment | Current basis |
|---|---:|---|
| Magic/type observation | evidence default `1.0` | Static magic bytes and extension branch. |
| Archive/directory runtime filename indicator | `0.75` | Recognized manifest or artifact name, without runtime execution. |
| `package.json` engine declaration | `1.0` | Direct static declaration. |
| Neighboring .NET artifacts with parsed framework declaration | `0.9` | Static runtimeconfig/framework plus related artifact evidence. |
| Neighboring .NET artifacts without parsed framework declaration | `0.75` | Artifact-name inference only. |
| APK container runtime requirement | `0.7` | Container-type inference. |
| Static parser failure | `0.3` UNKNOWN evidence | Inspection failed before a supported result was obtained. |

## Project inspection

| Detector branch | Assignment | Current basis |
|---|---:|---|
| Confirmed symlink refusal, oversize file, unsupported encoding, malformed TOML, or no supported manifests | `1.0` UNKNOWN evidence | Maximum weight applies to the fact that the bounded detector encountered the stated limitation, not to the missing underlying value. |
| Metadata/read OS error | `0.5` UNKNOWN evidence | Failure may be transient or access-dependent. |
| Successful bounded manifest read | evidence default `1.0` | Direct byte-count/static-read observation. |
| `pyproject.toml` literal `requires-python` | `1.0` | Direct PEP 621 declaration. |
| Parsed `pyproject.toml` with no `requires-python` | `0.7` UNKNOWN requirement | Manifest parsed, field absent. |
| Unavailable or malformed `pyproject.toml` | `0.3` UNKNOWN requirement | Required field could not be inspected. |
| Non-empty `.python-version` selection | `1.0` | Direct selection declaration; it remains selection evidence, not runtime observation. |
| Empty/comment-only `.python-version` | `0.5` UNKNOWN requirement | File exists without a usable selection. |
| `uv.lock` literal `requires-python` | `1.0` | Direct lockfile declaration. |
| Parsed `uv.lock` without the field | `0.5` UNKNOWN requirement | Lockfile parsed, field absent. |
| Malformed `uv.lock` | `0.3` UNKNOWN requirement | Lockfile constraint could not be inspected. |
| Literal `setup.cfg` `python_requires` | `0.9` | Direct static INI field with slightly lower author weight than PEP 621/lock data. An empty value retains UNKNOWN provenance. |
| Malformed `setup.cfg` requirement | `0.3` | Static parser could not obtain the field. |
| Literal `setup.py` `python_requires` | `0.8` | Bounded AST literal; the file is never executed. |
| Dynamic/non-literal `setup.py` value | `0.3` UNKNOWN requirement | Static AST cannot safely evaluate the value. |
| Parsed requirements-file package line | `1.0` | Direct text declaration, outside interpreter-only GREEN. |
| ProjectDNA aggregate | `1.0` with no unknowns; otherwise `max(0.2, 1.0 - 0.15 × unknown_count)` | Hand-authored completeness penalty, not a reliability estimate. |

## Resolution and conflicts

| Detector branch | Assignment | Current basis |
|---|---:|---|
| Command path maps to a discovered provider | `1.0` resolution and evidence | Deterministic command-resolution evidence maps to a provider identity. |
| Command path exists but is not mapped to a provider | `0.5` resolution and evidence | Resolution path is retained, provider identity/health is unresolved. |
| No command path resolves | `0.0` resolution; `0.5` UNKNOWN evidence | No resolution support; the separate UNKNOWN evidence weight describes the detector result. |
| Source or default-resolution conflict | `min(...)` of supporting weights | Conservative propagation; it is not independent validation or calibration. |

## Legacy compatibility aggregation

`core.engine.compare` emits a separate legacy `confidence` value as `0.5 + 0.5 × known_checks / all_checks`, rounded to two decimals. It is a hand-authored coverage ratio mapped into `[0.5, 1.0]`, not the probability that the compatibility verdict is correct. The adjacent `score` is the fraction of known checks marked ready and is likewise not fact provenance or decision validation.

## Fixtures and schemas

- `tests/test_arx.py` uses `0.8` only to prove that serialization preserves an explicitly supplied fixture value.
- `examples/sample-machine-dna.json` uses `1.0` for a synthetic observed fixture.
- Project DNA, Project Preflight, and AI Contract schemas constrain confidence fields to numbers from zero through one. The range constraint validates shape only; it does not calibrate semantics.
- Desktop and CLI surfaces display or export these values without converting them into probabilities.

Any future claim that a confidence number represents probability, measured accuracy, or statistical confidence requires a versioned calibration method, representative dataset, evaluation results, and documented uncertainty. Until then, the detector-author-weight meaning is authoritative.
