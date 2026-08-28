# Agent capability challenges (experimental)

ARX Beta 7 development introduces the `agent-challenge/0.1` protocol. This is an additive development interface; it does not change the Beta 6 application version or claim autonomous agent scanning.

## Epistemic boundary

An agent's self-report and receipt are claims, not proof. The lifecycle is:

```text
ARX prepare
  -> disposable workspace + challenge.json + INSTRUCTIONS.md + ARX-owned fixtures
  -> external agent performs only authorized operations
  -> receipt.json + workspace artifacts
  -> ARX validates receipt structure and actual artifact bytes
  -> independent AgentChallengeValidation
```

The receipt's `claimed_state` remains separate from ARX's bounded outcome validation, execution provenance, and final `validated_state`. A PASS claim with a missing artifact, wrong content, wrong hash, escaped path, changed fixture, policy violation, identity mismatch, or inconsistent timeout is not a validated PASS. Validation establishes only the bounded result in the recorded scope and context; it does not establish universal competence.

Two rules are explicit in Phase 2.0.1:

```text
ARTIFACT VALIDATION != EXECUTION ATTRIBUTION
RECEIPT-REPORTED PROVIDER != OBSERVED PROVIDER
```

For an artifact-semantic proposition such as `artifact.create`, independently observing the exact authorized path, bytes, size, and SHA-256 can establish PASS. For execution-family propositions (`powershell`, `python`, `git`, `cpp`, and `cuda`), correct artifacts and markers establish a valid bounded outcome, but not which provider or process produced it. Receipt-authored tool observations, exit codes, output summaries, and execution-context labels remain useful claims; none upgrades execution provenance to `OBSERVED`.

An execution-family result requires an ARX-owned trusted execution observation before a validated provider-specific PASS is possible. With a valid outcome but only receipt-reported provenance, ARX reports `execution_provenance = RECEIPT_REPORTED` and `validated_state = UNKNOWN`, not FAIL. Lack of attribution does not erase the real artifact result.

Phase 2.0 introduced challenge, receipt, and independent bounded-outcome validation. Phase 2.0.1 tightens execution attribution before real-agent execution. Phase 2.1 will add the bounded ARX-owned observer that can record provider/process evidence against a real participating agent. This protocol does not mutate an `AgentDNASnapshot`; relating validated results to snapshots and eventually to Machine DNA + Project DNA remains deferred.

## Challenge identity and fixtures

Challenge identity is deterministic over the meaningful catalog definition. Timestamps, usernames, random workspace paths, credentials, and environment values do not enter the stable ID. Each prepared run has a separate workspace identity.

Fixtures are tiny ARX-owned byte sequences. Their relative paths, sizes, SHA-256 values, and fixture-set version are recorded in the challenge. An external agent may not replace a fixture with arbitrary source and ask ARX to execute it. Phase 2.0 preparation never executes a fixture or launches an AI.

## Scope, context, and dependencies

All permitted mutations are contained in an ARX-owned disposable workspace beneath the system temporary directory unless an explicit test workspace root is supplied. Artifact paths must be relative and remain inside that workspace. Absolute paths, traversal, symlink/reparse-point escape, duplicate artifact identities, oversized receipts, summaries, and artifacts are rejected.

Capability results retain context. Provider presence does not imply current resolution. A compiler PASS in a Visual Studio x64 Developer Environment does not erase a FAIL in a normal shell. ARX may explain that `vcvars64.bat` exists, but this protocol does not activate it.

Dependencies are explicit. For example:

```text
cpp.compiler.resolution -> cpp.compile -> cpp.binary.created -> cpp.execute

cuda.nvcc_resolution + cuda.host_compiler.resolution -> cuda.compile
cuda.runtime.fixture.available -> cuda.runtime_initialize (separate branch)
```

If compilation fails, binary creation and execution are BLOCKED, not NOT_APPLICABLE. UNKNOWN, NOT_TESTED, BLOCKED, FAIL, and NOT_APPLICABLE remain distinct.

## Initial catalog and CLI

The small `coding-core` profile contains:

- `artifact.create`
- `filesystem.workspace.write`
- `powershell.execute`
- `python.execute`
- `git.local.repository`
- `cpp.compile`
- `cpp.execute`
- `cuda.compile`
- `cuda.runtime_initialize`

Preparation is not execution:

```powershell
arx agent challenge catalog
arx agent challenge prepare artifact.create
arx agent challenge prepare coding-core
arx agent challenge validate <challenge.json> <receipt.json>
arx agent challenge summarize <validation.json>
```

An external Codex, Qwen, Claude, local model, CLI agent, GUI agent, or human-mediated system can participate manually without vendor logic in the core protocol. Vendor adapters remain deferred.

## Security exclusions

The default challenge policy does not authorize package installation, persistent PATH or registry changes, service or scheduled-task mutation, security-control changes, credential access, GitHub mutation, network scanning, unknown project-code execution, writes outside the disposable workspace, or self-modification. Technical permission never supplies authorization. Dangerous tests stay NOT_TESTED.

ARX does not execute commands embedded in a receipt. For any later execution validation, only artifacts originating from known ARX-owned fixtures inside the challenge workspace may be considered, under a separately explicit bounded execution policy.
