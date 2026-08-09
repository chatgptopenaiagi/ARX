# ARX

ARX is an evidence-based, Windows-first pre-installation compatibility intelligence tool:

```text
Machine DNA <-> Compatibility Engine <-> Software DNA
```

It inspects the development machine, statically inspects a package without executing it, and explains whether the two can coexist. ARX prioritizes deterministic rules, explicit uncertainty, and read-only observation.

## MVP features

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

These statuses are observations of one machine, not project prerequisites or promises about another host.

## Safety and privacy

Unknown targets are never executed, loaded as libraries, or extracted. Reports replace the current profile path with `%USERPROFILE%`, export only an environment allowlist, and exclude credentials, tokens, browser state, Wi-Fi secrets, and private keys. See [the security model](docs/security-model.md).

## Architecture and development

Machine scanners and static software scanners produce normalized evidence. A capability graph derives reusable abilities, compatibility rules compare requirements, and exporters create reports. Lightweight `Protocol` contracts define the extension seams without requiring a plugin framework dependency. See [architecture](docs/architecture.md), [schemas](schemas), and [roadmap](docs/roadmap.md).

```powershell
python -m pip install -e .[dev]
pytest
```

Contributions are welcome under the MIT license; see [CONTRIBUTING.md](CONTRIBUTING.md).
