# AI assistance and external-boundary security

ARX remains the deterministic evidence authority, safe local observer, and project-aware compatibility engine. AI and public web research are optional investigation instruments controlled by the user. External intelligence cannot modify the workstation or become ARX evidence.

## Three trust domains

1. **ARX deterministic local evidence** is produced by bounded static reads, fixed diagnostics, and the canonical compatibility/project engines.
2. **External AI advice** receives a deliberately selected, bounded, redacted packet only after a visible user action and provider consent. Responses are labeled `AI ADVISORY — UNVERIFIED AI ANALYSIS`.
3. **Public web search** receives only a short redacted, URL-encoded query after the user selects a search command. Search results stay in the browser and outside ARX evidence.

Information never crosses these boundaries automatically. AI output cannot set OBSERVED, VERIFIED, GREEN, YELLOW, or RED state and cannot execute a recommendation.

## Context selection and redaction

The desktop constructs context from the selected structured finding, a small project summary when one is active, and at most eight relevant evidence records. Fields and the complete packet are size-bounded. ARX does not send the complete Machine DNA report, arbitrary project files, browser state, Wi-Fi credentials, private keys, credential stores, or unrelated file contents.

Before provider or search use, ARX removes sensitive keys and recognizable API keys, bearer tokens, GitHub tokens, JWTs, password/token assignments, usernames, control characters, private roots, user-profile paths, and arbitrary absolute local paths. Project roots use `%PROJECT_ROOT%`, the active profile uses `%USERPROFILE%`, and other local paths use `%LOCAL_PATH%` where appropriate. The preview shows the exact advisory prompt that would be sent; opening it sends nothing.

Copying or saving context, prompts, responses, and conversations reapplies external-boundary redaction. Users should still review exported material before sharing it because no finite redactor can recognize every domain-specific secret.

## OpenAI provider

The optional OpenAI provider uses the supported Responses API over HTTPS. It reads `OPENAI_API_KEY` from the current process environment and never stores the key in ARX state or places it in a request body, prompt, URL, report, subprocess argument, or saved conversation. The model defaults to the repository's reviewed model and can be selected with `ARX_OPENAI_MODEL`. Requests set `store` to `false`.

ARX does not automate or scrape the ChatGPT website or desktop application. A ChatGPT subscription is not treated as an API credential. If configuration or the network is unavailable, only the provider action is unavailable; core ARX continues to work.

Cancellation stops ARX waiting and ignores a late response. With the current standard-library HTTPS transport, it cannot retract data after the remote service has already received the request. Timeout, HTTP, network, malformed-response, and empty-response failures are converted to bounded redacted messages.

## Codex CLI provider

ARX detects the official Codex CLI with executable lookup and verifies availability with an explicit `codex --version` argument array. Advisory execution uses the documented non-interactive `codex exec` interface with:

- prompt input through standard input, never the command line;
- `--sandbox read-only` and `--ephemeral`;
- `--ignore-user-config`, `--color never`, and `--skip-git-repo-check`;
- an empty temporary working directory rather than the inspected project;
- `shell=False`, hidden process creation on Windows, bounded output, timeout, terminate, and kill fallback.

The selected project is not granted to Codex as a working directory, so the process sees only the already filtered prompt by default. ARX never simulates typing into a terminal. A missing or unauthenticated Codex installation produces a provider explanation, not an application failure.

## Web research

Web, Google, exact-error, and official-documentation commands build concise queries from the selected finding. Exact-error search chooses the relevant bounded fragment and removes local paths and long random identifiers. Known technologies may add an official `site:` domain; uncertain mappings fall back to a general official-documentation query. Generated URLs are limited to HTTPS Google or DuckDuckGo search endpoints and opened in the user's default browser. ARX does not fetch, scrape, summarize, or import the result page.

## CI and release boundary

GitHub CI runs deterministic pytest coverage on Windows and Linux across the declared Python support range, verifies source and wheel builds without publishing, and runs CodeQL for Python and Actions. Workflow actions are pinned to reviewed commits, checkout credentials are not persisted, token permissions are minimal, and privileged pull-request triggers are absent. The repository does not enable PyPI publishing, cloud deployment, Django, Conda CI, artifact release, signing, or SLSA provenance without a separate release decision.
