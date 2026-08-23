# Security model
Targets and inspected project contents are untrusted and are never executed, loaded as code, or extracted. Python Project DNA reads only recognized manifest paths, limits each file to 1 MiB, requires supported text encoding, does not follow manifest/directory symbolic links, and treats launch scripts as evidence rather than commands.

Trusted machine diagnostics and execution-resolution checks use fixed argument arrays, `shell=False`, captured output, hidden windows, working-directory scoping, and timeouts. ARX does not interpolate project content into a shell command. Provider discovery may run fixed health/version diagnostics against runtime executables found by Machine DNA; it never runs scripts from an inspected project.

Project-aware reports fingerprint effective PATH and relevant process-environment state rather than exporting their raw values. They expose only environment-presence indicators, replace project roots with `%PROJECT_ROOT%`, and retain active-profile redaction. ARX never reads credential stores, password/token variables, browser data, Wi-Fi secrets, or private keys.

The Resolution Planner is advisory. Normal ARX analysis does not install or uninstall software, modify PATH or the registry, alter execution aliases, change Windows security/firewall/antivirus settings, remove runtimes, or execute remediation. A valid signature is integrity evidence, not a safety verdict.

## External-boundary invariant

Every optional external adapter follows the same one-way sequence:

```text
select canonical evidence -> filter for relevance -> redact -> bound -> preview/consent -> transmit -> label as unverified
```

Selection and filtering happen before transport, redaction is reapplied to copy/save paths, and size limits are enforced after serialization. Prompts or queries travel as standard input or encoded request data, never as shell syntax. Processes use argument arrays, `shell=False`, bounded time, cancellation, and the least authority available. If any stage cannot be satisfied, the adapter fails closed without changing the deterministic report. External responses are displayed separately and are not fed back into evidence, severity, or remediation.

Optional AI advice is a separate trust domain from deterministic ARX evidence. It is invoked only by an explicit user action, receives one bounded relevant context packet after external-boundary redaction, and is visibly labeled unverified. OpenAI credentials are read from process configuration and are never placed in prompts, reports, saved conversations, URLs, or subprocess arguments. Codex runs through its supported non-interactive interface in an empty temporary directory with a read-only sandbox, an argument array, `shell=False`, a timeout, and cancellation. AI output never changes the evidence graph or executes remediation.

Public web research is a third trust domain. ARX constructs a short redacted query, URL-encodes it, restricts generated URLs to known HTTPS search hosts, and opens the user's browser only after a direct search command. ARX does not scrape search results or merge them into evidence. See [AI assistance and external-boundary security](ai-assistance-security.md) for the provider, consent, privacy, and failure model.

