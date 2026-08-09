# Security model
Targets are untrusted bytes and are never executed, loaded, or extracted. Trusted diagnostics use fixed arguments, no shell, captured output, hidden windows, and timeouts. Reports allowlist environment variables and redact the active user profile. ARX never reads credential stores, password/token variables, browser data, Wi-Fi secrets, or private keys. A valid signature is integrity evidence, not a safety verdict.

