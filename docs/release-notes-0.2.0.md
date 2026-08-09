# ARX 0.2.0

## Windows Desktop Release

ARX 0.2.0 is the first validated Windows desktop release generation of ARX.

ARX provides read-only pre-installation compatibility intelligence by examining both the host workstation and software artifacts.

## Main workflows

- Quick Machine Scan
- Deep Machine Scan
- Inspect Software
- Compare Software With This PC
- Export Report
- Codex / AI Report

## Main analytical views

- Machine DNA
- Capabilities
- Software DNA
- Compatibility
- Evidence Inspector

## Validated functionality

- 19 automated tests passing
- Windows host scanning
- multiple Python installation detection
- Java/JDK detection
- Node.js/npm detection
- Git detection
- GitHub CLI detection
- .NET detection
- Visual Studio/MSBuild detection
- CUDA detection
- Docker detection
- static software inspection
- compatibility comparison
- evidence rendering
- JSON export
- text export
- AI-oriented export
- portable execution outside the source repository

## Portable Windows distribution

```text
ARX-Desktop-win-x64/
|
+-- ARX.exe
+-- _internal/
```

Keep the `_internal` directory beside `ARX.exe`.

## Known limitations

- MSI table/action analysis is incomplete
- APK binary manifests are not yet decoded
- PE import discovery is not yet a complete RVA/import-table parser
- complex semantic-version ranges may remain unknown
- ARX is not a malware scanner
- compatibility does not guarantee installation or execution

## Next architectural direction

ARX 0.3.x will focus on semantic intelligence:

```text
Provider Discovery
      ->
Capability Graph
      ->
Requirement Graph
      ->
Compatibility Predicates
      ->
Explainable Resolution Chains
```
