# ARX

ARX is an evidence-based, Windows-first project-aware semantic compatibility and resolution engine:

```text
Project DNA -> Requirement Graph
Machine DNA -> Provider Graph -> Execution Context -> Resolution
Requirements + Resolution -> Satisfaction -> GREEN / YELLOW / RED -> Plan
```

It inspects the development machine, statically inspects software and Python projects without executing them, and explains what exists, what resolves, what satisfies the project, what matters, what blocks, and the shortest policy-compliant path to GREEN. ARX prioritizes deterministic rules, explicit uncertainty, and read-only observation.

ARX keeps these dimensions separate:

```text
availability != resolution != compatibility != relevance
relevance != satisfaction != severity != remediation
```

## ARX 0.3 features

- Windows OS, CPU, memory, GPU, storage, environment, SDK hints, and developer-tool discovery
- Fixed, timeout-bound tool version probes with no shell interpretation
- SHA-256 and magic-based EXE/PE, MSI, ZIP, JAR, APK, script, and directory detection
- Static PE architecture, subsystem, CLR, manifest-level, and DLL indicators
- Authenticode status through Windows PowerShell
- Explainable build capability graph and architecture/.NET compatibility rules
- Declared Node engine requirements from directory and ZIP `package.json` manifests
- Visual Studio/MSBuild discovery through `vswhere` even when it is absent from `PATH`
- Quick text, full JSON, agent-oriented JSON, inspect, and compare commands
- User-profile redaction and environment allowlisting
- Bounded static Python Project DNA from `pyproject.toml`, `.python-version`, `uv.lock`, and supported requirements files
- Sourced requirement graph with explicit relevance and unknown handling
- Stable, path-based identities for CPython, Conda, uv-managed, virtual-environment, and WindowsApps providers
- Context-scoped Python command resolution with PATH/environment fingerprints
- Separate resolved, compatible, and preferred provider roles
- Satisfaction, conflict, severity, policy, recommendation-only planning, and explanation models
- GREEN/YELLOW/RED project preflight in CLI and desktop, always accompanied by text
- Redacted project-aware AI contract schema 0.2

ARX is not a malware scanner and compatibility does not imply trust.

## Windows desktop

ARX Desktop provides a dark, capability-oriented interface for users who do not want to work in a terminal. It calls the same Machine DNA, Software DNA, compatibility, evidence, and exporter APIs as the CLI and performs scans on a background worker so the interface stays responsive.

From source:

```powershell
$env:PYTHONPATH = 'src'
python -m arx.desktop
```

Standalone experimental Windows builds are produced under `release/` and are intended for distribution through GitHub Releases rather than source control.

## Install and run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

arx quick
arx deep
arx codex
arx inspect C:\Path\To\Application.exe
arx compare C:\Path\To\Application.exe
arx project C:\Path\To\Project
arx resolve C:\Path\To\Project
arx preflight C:\Path\To\Project
arx codex --project C:\Path\To\Project
```

From a source checkout, set `$env:PYTHONPATH = 'src'` and use `python -m arx`.

Structured output can be written with the global option, for example `arx --output machine.json deep`.

Example from the development workstation (2026-08-09):

```text
[READY]   Git
[READY]   Python
[READY]   Node.js
[MISSING] Java JDK
[MISSING] Android SDK
[PARTIAL] Visual C++ Build     Missing: cmake
[READY]   CUDA Compute
```

Machine scan statuses are observations, not project prerequisites. Project preflight determines whether an observation matters to the selected project.

## Safety and privacy

Unknown targets and project scripts are never executed, loaded as libraries, or extracted. Project manifests are size-bounded and symbolic links are not followed. Reports replace the current profile path with `%USERPROFILE%`, project roots with `%PROJECT_ROOT%`, export only allowlisted or fingerprinted environment state, and exclude credentials, tokens, browser state, Wi-Fi secrets, and private keys. The planner recommends but never applies host remediation. See [the security model](docs/security-model.md).

## Architecture and development

Machine, software, and project scanners produce normalized evidence. Typed semantic models preserve provider identity, execution context, resolution, compatibility, relevance, satisfaction, conflict, severity, policy, plans, and explanations independently. See [architecture](docs/architecture.md), [project semantic engine](docs/project-semantic-engine.md), [AI contract 0.2](docs/ai-contract-0.2.md), [schemas](schemas), and [roadmap](docs/roadmap.md).

```powershell
python -m pip install -e .[dev]
pytest
```

Contributions are welcome under the MIT license; see [CONTRIBUTING.md](CONTRIBUTING.md).
