# Roadmap

ARX 3.0 Release Candidate establishes the Windows presentation, deterministic project-awareness, portable/installer packaging, external-advisory boundary, and CI/security-analysis foundation.

## Before ARX 3.0 final

- Complete visible DPI and multi-monitor acceptance on representative Windows 10/11 systems.
- Complete screen-reader, keyboard, focus, contrast, and accessibility acceptance.
- Exercise interactive/silent install, launch-after-install, same-AppId upgrade, uninstall, and clean removal on an approved test system or disposable VM.
- Resolve any defects found by those manual checks and repeat the deterministic release gate.
- Establish an approved publisher identity, icon, and code-signing process if signed final artifacts are required.

## Candidate extensions after the release gate

- pip-to-interpreter mismatch detection and richer PowerShell alias/function resolution evidence;
- cross-source range intersection beyond exact `.python-version` selection conflicts;
- uv project-environment and virtual-environment discovery scoped to the selected project;
- Python package/environment satisfaction after runtime selection;
- cautious context-keyed provider observation caching;
- Project DNA adapters for Node, CMake, Gradle, .NET, Cargo, Go, Docker, and CI workflows;
- richer explanation traversal and robust PE imports/resources, exact .NET targets, MSI tables, and APK manifests.

Machine-remediation execution, global PATH mutation, runtime removal/upgrades, security changes, autonomous repair, graph databases, and distributed services remain outside ARX's role. Predictive or external analysis remains separate from deterministic local evidence.
