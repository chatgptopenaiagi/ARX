# Agent DNA (experimental foundation)

Agent DNA is ARX's evidence-backed description of what an agent could actually demonstrate in a particular execution context. It is vendor-neutral: a snapshot may describe a CLI agent, GUI agent, local model, hosted agent, restricted sandbox, or a future system that ARX does not yet know by name.

Agent DNA is not a list of claims made by an AI. Its central law is:

> Self-report is not capability. Availability is not resolution; resolution is not permission; permission is not authorization; authorization is not execution; execution is not success; and a scoped success is not a general capability.

This Phase 1 foundation imports evidence. It does not scan agents, execute their output, or decide whether an agent can satisfy a Project DNA requirement.

## Phase 0 design analysis

The first empirical input contained a pre-test declaration, a time-bound execution context, capability families, bounded command receipts, contradictions, calibration, and operator interventions. Those shapes generalized well. Vendor labels, workstation paths, one CLI's sandbox terminology, raw command prose, and tool-specific failure messages did not. The canonical model therefore uses generic identity/context records, typed operational states, open scope qualifiers, evidence references, and graph edges. Original vocabulary that has no canonical meaning is retained only as bounded extensions.

The post-intervention Phase 0 file has 129 capability records: 102 PASS, 10 FAIL, 5 UNKNOWN, 8 NOT_TESTED, 3 NOT_APPLICABLE, and 1 BLOCKED. Its earlier 115-record census remains historical evidence rather than being rewritten. Provider changes such as Ninja or Android Platform-Tools are interventions, not agent achievements.

## Evidence and operational state

Agent evidence reuses ARX's canonical `EvidenceKind` exactly:

- `DECLARED`: a subject or operator claim.
- `OBSERVED`: bounded observation.
- `INFERRED`: a conclusion derived from cited evidence.
- `UNKNOWN`: provenance cannot be established.

`VERIFIED` is deliberately not an evidence kind. Operational state is independent:

- `PASS`: the operation succeeded in its stated scope.
- `FAIL`: an authorized attempt ran and failed.
- `BLOCKED`: a prerequisite or policy prevented completion; this is not FAIL.
- `UNKNOWN`: evidence cannot decide the outcome.
- `NOT_TESTED`: no operational test was performed.
- `NOT_APPLICABLE`: a prerequisite or context makes the operation inapplicable.

A PASS requires a non-empty scope. Dangerous operations that were not authorized remain NOT_TESTED; ARX does not guess whether they would pass.

## Capability dimensions and scope

Each capability can independently retain declared expectation, provider availability, resolution, permission, authorization, attempt, execution, success, limitations, dependencies, evidence, timestamps, and result. Fields may remain UNKNOWN.

Scope has a generic kind, target, and optional qualifiers. It can describe a workspace, project, user, machine, container, WSL distribution, remote repository, network target, or Python environment without making that list a closed universe. A workspace write PASS cannot imply a system-wide write. A local Git commit PASS cannot imply a GitHub push PASS.

## Capability graph

Capabilities are nodes. `requires` edges preserve incomplete chains rather than flattening them into a Boolean.

Phase 0 demonstrated these valid combinations:

- `clang++` resolved, while the C++ standard library was unavailable and compilation failed.
- CMake and Ninja resolved, while configuration failed because the selected toolchain could not link its compiler test.
- A .NET SDK was available, while offline build was BLOCKED because `project.assets.json` was absent and restore was outside policy.
- CUDA Toolkit 13.3 and `nvcc` were visible, while CUDA compilation failed because the host compiler was unresolved.
- CUDA runtime initialization nevertheless passed for one RTX 3050 device with compute capability 8.6.
- The NVIDIA driver advertised CUDA capability 13.4. That is not evidence that Toolkit 13.4 was installed.

Runtime capability and compiler capability are therefore separate graph branches.

## Permission and authorization

Permission answers what the environment or remote metadata appears to allow. Authorization answers what the governing user request or policy permits this experiment to do. Execution records what was actually attempted.

For example, GitHub metadata may expose push permission while policy prohibits remote mutation. The canonical result is permission observed, action not authorized, execution NOT_TESTED, result NOT_TESTED. Mere permission is never an instruction to mutate anything.

## Machine DNA relationship

Machine DNA owns host facts: operating system identity, GPU inventory, installed providers, CPU, and memory. Agent DNA owns context-specific interactions: which provider the agent resolved, which action it attempted, and what happened.

An agent-reported host label is retained separately in execution-context evidence. It cannot overwrite Machine DNA. Thus `Windows NT 10.0.29639` and Machine DNA's `Microsoft Windows 11 Pro Insider Preview, build 29639` can coexist as differently sourced descriptions. Linking them requires an explicit Machine DNA reference.

Project DNA integration is future work. A later evaluator may relate Machine DNA + Agent DNA + Project DNA, but Phase 1 does not manufacture that verdict.

## Calibration and time

Calibration is a categorical comparison between declaration and observation, never a probability or intelligence score. An UNKNOWN declaration followed by PASS becomes `UNKNOWN_RESOLVED_AVAILABLE`; comparable outcomes exist for unavailable, blocked, and still-unresolved observations. It is not a false negative.

Snapshots include identity, generation time, agent identity, execution context, policy, and an optional Machine DNA reference. Operator interventions preserve before/action/after/effect data. This permits later comparison without building a temporal database or erasing earlier observations.

### Supported developer-environment transitions

A failed operation in one shell is not a permanent machine incapability. Phase 0 follow-up established this with an installed Visual Studio Build Tools provider. In the original Codex process, `cl.exe` was unresolved, so C++ and CUDA compilation correctly failed while CUDA runtime initialization passed. After the human activated the supported x64 Visual Studio developer environment through `vcvars64.bat`, the coordinated `PATH`, `INCLUDE`, `LIB`, `VCToolsInstallDir`, and `WindowsSdkDir` environment resolved MSVC, C++ compilation and execution passed, and CUDA compilation and runtime execution passed.

Agent DNA preserves T0 and T1 as separate context-scoped outcomes using an intervention with explicit before/after context descriptors and per-capability transitions. It does not rewrite T0, describe activation as merely adding `cl.exe` to PATH, or generalize T1 beyond the activated developer environment. Machine DNA owns the installed MSVC/Windows SDK providers; Agent DNA owns whether the agent resolved and used them in each context.

ARX may safely detect known entry points such as `vcvars64.bat` or `VsDevCmd.bat` and explain a recoverable context transition. Detection does not authorize ARX to activate a shell, mutate persistent environment variables, or execute builds.

## Import and CLI

Phase 1 safely imports `agent-dna-experiment/0.1`. Import is bounded to 8 MiB and 5,000 capabilities, parses JSON without executing it, rejects invalid structure/statuses/duplicate IDs, and redacts private roots in normalized output. Unknown input fields may survive only as bounded extensions; they cannot redefine canonical semantics.

```powershell
arx agent validate .\codex-capability-baseline.json
arx -o normalized.json agent import .\codex-capability-baseline.json
arx agent summary .\codex-capability-baseline.json
```

The repository schema is `schemas/agent-dna.schema.json` (JSON Schema Draft 2020-12). Agent DNA remains experimental and additive.

## Challenge protocol boundary

The future challenge protocol has typed challenge and receipt seams: challenge ID, capability, scope, allowed and forbidden operations, timeout, expected evidence, artifact expectations, result claim, evidence references, and artifact hashes. An adapter only transports a challenge or receipt. ARX must independently validate receipts.

Phase 1 does not execute arbitrary AI output, implement vendor adapters, or automate challenges. The default security profile remains bounded and read-only where possible, uses disposable workspaces for permitted mutation tests, never exposes credentials, never weakens controls, and never probes destructive capabilities merely because an administrator permission exists.
