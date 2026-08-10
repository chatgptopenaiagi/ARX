# Security model
Targets and inspected project contents are untrusted and are never executed, loaded as code, or extracted. Python Project DNA reads only recognized manifest paths, limits each file to 1 MiB, requires supported text encoding, does not follow manifest/directory symbolic links, and treats launch scripts as evidence rather than commands.

Trusted machine diagnostics and execution-resolution checks use fixed argument arrays, `shell=False`, captured output, hidden windows, working-directory scoping, and timeouts. ARX does not interpolate project content into a shell command. Provider discovery may run fixed health/version diagnostics against runtime executables found by Machine DNA; it never runs scripts from an inspected project.

Project-aware reports fingerprint effective PATH and relevant process-environment state rather than exporting their raw values. They expose only environment-presence indicators, replace project roots with `%PROJECT_ROOT%`, and retain active-profile redaction. ARX never reads credential stores, password/token variables, browser data, Wi-Fi secrets, or private keys.

The Resolution Planner is advisory. Normal ARX analysis does not install or uninstall software, modify PATH or the registry, alter execution aliases, change Windows security/firewall/antivirus settings, remove runtimes, or execute remediation. A valid signature is integrity evidence, not a safety verdict.

