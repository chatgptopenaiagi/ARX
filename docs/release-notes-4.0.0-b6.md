# ARX 4.0.0 Beta 6

Package version: `4.0.0b6`

Artifact version: `4.0.0-b6`

Windows file/product version: `4.0.0.6`

Reserved Git tag: `v4.0.0-b6`

Release channel: Beta / GitHub prerelease; not ARX 4 stable

ARX 4.0.0 Beta 6 adds the first vendor-neutral Agent DNA foundation and hardens GPU and Windows execution-context evidence using findings from real bounded workstation scans. This Beta remains read-only and evidence-first. It does not claim universal GPU compatibility, autonomous remediation, or stable-release readiness.

## Agent DNA foundation

Agent DNA represents a capability as a contextual relation among an agent, machine reference, execution context, provider resolution, policy, scope, evidence, and time. A self-report is not proof of capability, and every demonstrated PASS has a scope.

The additive experimental domain includes:

- vendor-neutral agent identity, execution context, policy, capability, evidence, graph, contradiction, intervention, calibration, and snapshot types;
- independent declared, availability, resolution, permission, authorization, attempt, execution, outcome, and operational-state dimensions;
- the permanent rule that technical permission does not imply task or human authorization;
- dependency graphs that preserve usable providers, unresolved prerequisites, and cycle validation instead of flattening a toolchain to one Boolean;
- explicit PASS, FAIL, BLOCKED, UNKNOWN, NOT_TESTED, and NOT_APPLICABLE states;
- contextual before/after snapshots and interventions without building a temporal database;
- non-probabilistic self-assessment calibration, including UNKNOWN predictions later resolved by observation;
- safe import and normalization of the Phase 0 `agent-dna-experiment/0.1` baseline;
- experimental `arx agent validate`, `arx agent import`, and `arx agent summary` CLI surfaces.

Beta 6 does **not** include the active Agent Challenge Engine, autonomous agent scanning, vendor-specific Codex/Qwen/Claude adapters, agent ranking, or automatic remediation.

## Execution-context capability intelligence

The Phase 0 MSVC/CUDA follow-up demonstrated why capability must remain contextual. The agent and installed machine software stayed the same while the execution context changed:

- T0, normal PowerShell/Codex context: the physical MSVC provider existed, `cl.exe` was unresolved, C++ compilation failed, CUDA compilation failed, and CUDA runtime initialization passed.
- T1, supported Visual Studio x64 Developer Environment: `cl.exe` resolved, C++ compilation passed, CUDA compilation passed, and CUDA runtime initialization continued to pass.

The transition was produced by the human activating `vcvars64.bat`, which establishes a coordinated Visual Studio environment including `PATH`, `INCLUDE`, `LIB`, `VCToolsInstallDir`, and `WindowsSdkDir`. It was not a permanent manual PATH edit and did not install new software.

> Machine provider presence is not current execution resolution. Current execution failure is not permanent machine incapability.

Machine DNA now keeps the installed MSVC provider, physical compiler path, current-process `cl.exe` resolution, Windows SDK provider, and observed supported developer-environment entry point separate. ARX may explain the recoverable context, but it does not activate `vcvars64.bat`, modify PATH, or compile arbitrary probes during an ordinary machine scan.

## GPU and Windows hardening

- A frozen PyInstaller `ARX.exe` can no longer masquerade as a Python interpreter. Framework probing selects a healthy discovered real Python provider, excludes unhealthy WindowsApps aliases, identifies the tested provider, and remains NOT_TESTED when none is usable.
- Framework absence is scoped to the tested Python environment and is not promoted to global absence.
- Standalone TensorRT installations are discovered through bounded explicit environment, relevant PATH, and known NVIDIA AI roots. Normalized roots are deduplicated while discovery sources remain evidence.
- TensorRT versions such as `11.2.1.2` are extracted from bounded directory-name evidence with explicit provenance; version discovery does not imply compatibility.
- WMI `AdapterRAM` and healthy NVIDIA tooling VRAM remain separate observations. A material discrepancy on a safely correlated adapter emits `GPU_VRAM_SOURCE_DISAGREEMENT`, not a hardware-fault diagnosis.
- CUDA, cuDNN, and TensorRT runtime-loadable DLLs are separated from development import/link libraries. A `.lib` file does not establish runtime presence or usability.
- Shared Windows diagnostic decoding handles ASCII, UTF-8 and BOM, UTF-16 LE/BE, strong NUL patterns, incomplete trailing UTF-8 introduced by report bounding, and bounded Windows legacy fallbacks.
- Diagnostic subprocesses retain fixed trusted argument arrays, `shell=False`, timeouts, and bounded retained/report output. The implementation does not claim streaming-bounded OS pipe capture.
- CUDA Toolkit/provider resolution remains independent from the NVIDIA driver's advertised CUDA API/runtime ceiling.

## Bounded real-workstation evidence

A Beta 6 development scan on one Windows 11 Insider workstation observed an NVIDIA GeForce RTX 3050 with compute capability 8.6, NVIDIA driver 616.56, driver-advertised CUDA capability 13.4, CUDA Toolkit 13.3, standalone TensorRT native provider 11.2.1.2, WSL 2.7.12.0, and Flutter 3.48.0-0.3.pre. WMI reported approximately 4 GiB VRAM while NVIDIA tooling reported approximately 6 GiB; both facts and the structured source disagreement were preserved.

These observations validate the bounded detector behavior on that execution context. They do not prove that every machine, driver, Toolkit, framework, TensorRT/cuDNN combination, or project workload is compatible.

## Remaining UNKNOWN and limitations

- cuDNN presence remains UNKNOWN when no bounded provider evidence is observed.
- CUDA runtime DLL presence remains unobserved when only development import/link libraries are found.
- TensorRT/CUDA/cuDNN compatibility remains UNKNOWN without an explicit authoritative relationship.
- A framework absent from the tested Python provider may still exist in another untested environment.
- Project-specific GPU architecture and VRAM/resource feasibility remain UNKNOWN without static project requirements or supported explicit estimates.
- Ordinary Machine DNA scanning does not activate Visual Studio developer environments, modify system or process configuration, or run compilation workloads.
- Agent DNA import and summary are experimental foundations; there is no autonomous Agent Challenge Engine in this release.

## Security and release boundaries

ARX remains read-only and advisory. It does not install, uninstall, repair, activate developer environments, edit PATH or the registry, execute project code, import arbitrary inspected software, or apply recovery advice. Trusted probes remain fixed, timeout-bounded diagnostics with controlled output normalization. AI advisory output remains non-authoritative and cannot create observed evidence or mutate deterministic Machine, Software, Project, or Agent DNA.

Windows release-candidate binaries are expected to remain `UNSIGNED_EXPECTED_PRE_SIGNING` unless an approved publisher-controlled Authenticode identity is supplied. Hashes, SBOMs, CodeQL, and security gates do not constitute code signing.
