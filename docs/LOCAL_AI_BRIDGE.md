# ARX Local AI Bridge

The Local AI Bridge is part of the ARX 4.0.0 Beta 4 candidate for running optional advisory analysis through an explicitly configured model API on the same Windows computer. It does not change the immutable published Beta 3 artifacts, and Python-index publication remains a separate explicit gate.

The bridge does not replace ARX Core, the Phase C Intelligence Console, `AdvisoryContext`, `Evidence`, or `EvidenceKind`. It extends the existing `AIProvider` boundary and renders every response as:

> AI ADVISORY — NON-AUTHORITATIVE

Local execution does not make model output an observation, validation, compatibility result, readiness result, or verified fact.

## Desktop workflow

Users can open **Settings → Intelligence Providers → Local AI** with a normal mouse click. Opening Settings performs no endpoint probe, process launch, model load, or advisory request.

The explicit actions are:

- **Save Profile** — validate and locally store one bounded backend profile;
- **Discover / Check Health** — probe only that profile's explicit loopback `/v1/models` endpoint;
- **Start / Connect** — connect to an endpoint-only profile or start an approved typed backend;
- **Stop / Disconnect** — stop an ARX-supervised process or disconnect the ARX session from an external localhost endpoint;
- **Open Local AI Chat** — open the existing Phase C Intelligence Console with only the Local AI provider selected.

The Intelligence Console retains GENERAL CHAT and ARX EVIDENCE CHAT. GENERAL CHAT attaches no ARX state. ARX EVIDENCE CHAT uses the existing selection, redaction, bounds, preview, and consent controls. Opening the console never contacts the local provider.

Local AI is exposed as a separate single-provider console path so the published Phase C Ask Both contract remains exactly two distinct configured providers—OpenAI API and Codex CLI. This milestone does not silently turn a three-provider list into ranking, consensus, or provider selection. A later reviewed UI may explicitly select exactly two distinct providers without changing Ask Both semantics.

## Bounded discovery

Endpoints must use `http` or `https`, an explicit port, no embedded username/password, no query or fragment, and one of:

- `127.0.0.0/8` loopback;
- IPv6 loopback `::1`;
- the literal hostname `localhost`.

Wildcard `0.0.0.0`, LAN addresses, public hosts, URL credentials, ambiguous ports, arbitrary network ranges, and filesystem discovery are rejected. The accepted `localhost` spelling is normalized to literal `127.0.0.1`; ambient proxy settings are disabled for local discovery and advisory transport. ARX probes only a user-selected configured profile or a bounded fixed list selected by an explicit future discovery action. Redirects are rejected, response bytes and model counts are bounded, and malformed model metadata fails closed as `API_INCOMPATIBLE`.

## Typed process supervision

Endpoint-only `OPENAI_COMPATIBLE` and `GENERIC` profiles never produce a process command. `LLAMA_CPP` is the only launchable adapter in this milestone. Its argument array is constructed from typed fields:

```text
<approved executable> --host 127.0.0.1 --port <validated port> --model <selected model file>
```

ARX uses direct process creation with `shell=False`, no standard input, discarded backend streams, and `CREATE_NO_WINDOW` on Windows. It does not use PowerShell as a runtime control plane and never executes AI-generated or free-form response text. The child environment is a minimal operating-system allowlist and does not inherit `OPENAI_API_KEY` or arbitrary environment variables.

First execution of a launchable profile requires an explicit human confirmation. Approval stores only the exact profile fingerprint, timestamp, and whether that approved profile selected `AUTOMATED`. Changing the executable, model, endpoint, or assistance policy changes the fingerprint and requires approval again.

The assistance profiles describe interaction, not human ability:

- `GUIDED` explains setup and asks before configuration;
- `BALANCED` presents safe defaults and obvious actions;
- `EXPERT` keeps endpoint, process, model, and backend detail visible;
- `AUTOMATED` may later start only the exact previously approved profile.

## Session capabilities

Each supervised launch creates a cryptographically random, expiring capability in process memory. For an explicitly compatible backend wrapper, ARX supplies the value through the child process environment and sends it only in `X-ARX-Session-Capability` on loopback requests. Ordinary llama.cpp deployments should leave this opt-in disabled unless their approved wrapper actually enforces the header.

The capability is never placed in profile or approval JSON, Evidence, Machine DNA, Software DNA, Project DNA, deterministic exports, transmission audit, reports, command-line arguments, URLs, or UI text. The UI shows only `MEMORY-ONLY · SESSION-SCOPED · VALUE HIDDEN`. ARX overwrites its mutable in-process buffer and drops the reference at shutdown. As with any same-user localhost mechanism, this is a session isolation aid, not a claim that a hostile process with equivalent OS privileges can be cryptographically excluded.

## State and failure model

Operational states remain separate from provenance:

`NOT_FOUND / DISCOVERED / STARTING / HEALTH_CHECK / READY / BUSY / STOPPING / STOPPED / FAILED`

Explicit failures include:

`MODEL_MISSING / EXECUTABLE_MISSING / PORT_CONFLICT / STARTUP_TIMEOUT / API_INCOMPATIBLE / AUTH_FAILURE / MODEL_LOAD_FAILURE / INSUFFICIENT_RESOURCES / PROCESS_CRASHED / NETWORK_FAILURE / REQUEST_FAILED / REQUEST_TIMEOUT / REQUEST_CANCELLED / MALFORMED_RESPONSE`

The manager tracks the profile, loopback endpoint, selected model identity, safe executable name and SHA-256, PID, startup time, backend version where reported, process state, and exit state. It never stores the capability value in the runtime snapshot.

## Advisory and audit boundary

The local chat request is built with the same deterministic `build_advisory_prompt` function used by remote providers. The bridge reapplies redaction and size limits at the actual localhost HTTP boundary, rejects redirects, bounds responses, supports timeout/cancellation, and parses only the narrow OpenAI-compatible chat-completion shape.

The existing local transmission audit records only:

`REQUEST_PREPARED / OUTBOUND_REQUEST_INITIATED / RESPONSE_RECEIVED / REQUEST_FAILED / CANCELLED`

It may include safe provider/model identity, byte counts, latency, and sanitized error category. It never contains prompt/response bodies, capability values, API keys, credentials, raw local paths, or arbitrary URLs. The existing 30-day bounded retention, rotation, inspection, and explicit clear action remain unchanged.

## Epistemic and authority boundary

The fact-provenance enum remains exactly:

`DECLARED / OBSERVED / INFERRED / ESTIMATED / SIMULATED / STRUCTURAL / UNKNOWN`

`VERIFIED` is not an `EvidenceKind`. A local response cannot mutate Evidence, EvidenceKind, Machine DNA, Software DNA, Project DNA, compatibility, readiness, deterministic scanner results, semantic invariants, or provenance ancestry.

This milestone provides no autonomous remediation, action broker, shell bridge, authority router, or delegated machine authority. The future authority model remains deliberately unimplemented. Any later action architecture must return to an ARX rescan before changed machine state can become newly observed evidence.

## Current limitations

- No local backend or model is bundled or downloaded automatically.
- Only a typed llama.cpp server profile can be launched; other backends must expose an explicitly configured compatible loopback API.
- A model health lookup proves only that the local model-list API responded for that check; it does not prove a generation will fit available RAM/VRAM or complete successfully.
- Capability enforcement is opt-in and requires a compatible backend wrapper; loopback alone is not a Windows publisher or process-identity guarantee.
- Real integration validation covered one externally running llama.cpp/Qwen configuration; it does not establish universal backend or model compatibility.
- The observed ordinary llama.cpp endpoint did not enforce ARX's optional capability header. Capability enforcement therefore remains deterministically tested but was not proven by that live backend.
- Published Beta 3 remains unchanged. Beta 4 requires its own full release gates, artifacts, SBOM, provenance, and publication decision.

## Observed llama.cpp/Qwen integration

On 2026-08-25, the bridge was validated against an externally owned `llama-server` process on a literal loopback endpoint. The backend reported version `0.1.2-dev`, build `10545`, commit `a30273376`; `/v1/models` identified `Qwen/Qwen3-4B-GGUF:Q4_K_M`. Discovery reached READY, one bounded advisory request and response parsed successfully, the manager transitioned BUSY → READY, the metadata-only audit contained the expected transport events, canonical ARX objects remained unchanged, and disconnect did not terminate the external process.

This is OBSERVED integration-validation evidence, not model advice and not a deterministic compatibility claim. The advisory response body is deliberately absent from the record. The externally launched server accepted unauthenticated loopback requests and echoed an arbitrary preflight Origin, consistent with its broad CORS/no-key configuration. ARX did not weaken its loopback, redaction, consent, or provenance boundaries to match that backend. Mid-flight cancellation could not be exercised reliably because the local response completed too quickly; pre-transmission cancellation and deterministic cancellation paths remain covered separately. See the [safe validation record](../security/local-ai/evidence/qwen-live-validation-v4.0.0-b4.json).
