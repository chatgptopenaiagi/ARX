# Roadmap

ARX 4.0.0 Beta 2 preserves the Phase B trust foundation on top of the ARX deterministic compatibility engine and adds bounded fuzz remediation, index-download hardening, reproducible-build controls, release provenance, and trusted Windows installation preparation. The foundation still includes expanded fact provenance, dependency enforcement, provider-neutral credentials, Windows DPAPI storage, OpenAI provider health/transport, metadata-only transmission audit, and minimal provider settings.

## Phase C and future ARX 4 work

- Build the full Intelligence Console and expanded contextual multi-turn conversation architecture.
- Add Ask Both as an explicit additional operation with flat, unranked provider responses.
- Keep comparison limited to textual overlap, differences, and unresolved items without consensus, confidence boosts, or provenance upgrades.
- Preserve independent OpenAI and Codex conversations and the one-way advisory boundary.

Phase C is not part of ARX 4.0.0 Beta 2.

## Manual release evidence still required

- Complete visible DPI and multi-monitor acceptance on representative Windows 10/11 systems.
- Complete screen-reader, keyboard, focus, contrast, and accessibility acceptance.
- Exercise interactive/silent install, launch-after-install, same-AppId upgrade, uninstall, and clean removal on an approved test system or disposable VM.
- Resolve any defects found by those manual checks and repeat the deterministic release gate.
- Establish an approved publisher identity, icon, and code-signing process if signed final artifacts are required.

## Candidate deterministic extensions after the release gate

- pip-to-interpreter mismatch detection and richer PowerShell alias/function resolution evidence;
- cross-source range intersection beyond exact `.python-version` selection conflicts;
- uv project-environment and virtual-environment discovery scoped to the selected project;
- Python package/environment satisfaction after runtime selection;
- cautious context-keyed provider observation caching;
- Project DNA adapters for Node, CMake, Gradle, .NET, Cargo, Go, Docker, and CI workflows;
- richer explanation traversal and robust PE imports/resources, exact .NET targets, MSI tables, and APK manifests.

Machine-remediation execution, global PATH mutation, runtime removal/upgrades, security changes, autonomous repair, graph databases, and distributed services remain outside ARX's role. Predictive or external analysis remains separate from deterministic local evidence.
