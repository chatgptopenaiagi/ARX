# ARX Project History

## Origin

ARX began as an attempt to unify several traditionally separate classes of software tooling:

- prerequisite scanners
- dependency analyzers
- developer workstation doctors
- runtime and SDK discovery
- application compatibility analysis
- static software inspection

The central ARX idea became:

```text
Machine DNA
    +
Software DNA
    =
Explainable Compatibility Intelligence
```

## Architectural evolution

### Phase 1 - Machine discovery

Detect operating system, hardware, runtimes, SDKs, compilers, developer tools and environment configuration.

### Phase 2 - Capability interpretation

Transform physical discoveries into statements describing what the workstation can actually do.

### Phase 3 - Software DNA

Statically inspect software artifacts without executing them.

### Phase 4 - Requirement reconstruction

Infer runtime, architecture, dependency and build requirements from evidence.

### Phase 5 - Compatibility reasoning

Compare Software DNA requirements against Machine DNA capabilities.

### Phase 6 - Explainability

Preserve evidence, confidence and reasoning for every important conclusion.

## ARX 0.2.0

ARX 0.2.0 introduced the first validated Windows desktop release candidate.

Validated functionality includes:

- Quick Machine Scan
- Deep Machine Scan
- Machine DNA
- Capability analysis
- Software DNA
- Compatibility analysis
- Evidence Inspector
- EXE/DLL static inspection
- developer toolchain discovery
- multiple Python provider detection
- Java/JDK detection
- Visual Studio/MSBuild detection
- JSON export
- text export
- Codex/AI-oriented export
- portable Windows x64 executable

## Long-term direction

ARX is evolving from detection toward semantic compatibility intelligence:

```text
Physical Evidence
      |
      v
Providers
      |
      v
Capabilities
      |
      v
Requirements
      |
      v
Compatibility Predicates
      |
      v
Explanation Chains
```

## ARX 0.3.0

ARX 0.3.0 adds the first project-aware vertical slice for Python. Project DNA and requirement evidence are combined with distinct provider identities and an execution-context-specific resolver. Deterministic semantic engines retain relevance, satisfaction, conflict, severity, policy, plans, and explanation chains independently before compressing the result to GREEN, YELLOW, or RED.

The planner remains read-only, and project-aware AI reports use schema 0.2 without changing legacy schema 0.1 envelopes.
