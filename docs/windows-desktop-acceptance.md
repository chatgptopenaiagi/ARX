# ARX Desktop manual Windows acceptance checklist

Use this checklist for a release candidate on a visible Windows 10 or Windows 11 desktop. It complements deterministic pytest coverage; it does not replace it. Record `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN` for every item and attach notes or screenshots to failures. An unchecked item is not tested.

## Run record

- ARX version/commit:
- Portable or installed build:
- Artifact filename and SHA-256:
- Windows edition/build and architecture:
- Display scale(s):
- Disposable/isolated lifecycle environment:
- Signing certificate and signature status:
- Tester and date:
- Test project/target (non-sensitive fixture preferred):

## Launch, window, and navigation

- [ ] Start `ARX.exe` from the complete portable folder. Confirm startup succeeds without a console window and `_internal` remains beside the executable.
- [ ] Resize the main window smaller and larger. Confirm controls remain reachable, panes do not overlap, and no important text is clipped without scrolling.
- [ ] Maximize and restore the window. Confirm the selected tab and layout remain usable.
- [ ] Exercise the interface at 100%, 150%, and 200% DPI scaling where hardware permits. Confirm labels, buttons, dialogs, menus, and status badges remain legible.
- [ ] Use Tab and Shift+Tab through primary controls, tabs, result trees, text reports, and dialogs. Confirm focus remains visible and activation with Enter/Space is sensible.
- [ ] Scroll long tree and text output vertically and horizontally. Confirm the scrollbars track the content and the UI stays responsive.

## Text and JSON interaction

- [ ] Open a JSON surface, for example `View Raw Data` on a populated result row. Right-click it and confirm the compact text menu opens.
- [ ] Select part of the JSON and choose `Copy`. Paste into a Unicode-aware editor and compare the selected text exactly.
- [ ] Choose `Copy All JSON`. Confirm the entire displayed JSON—not hidden credentials or unrelated machine data—is copied.
- [ ] Press Ctrl+A and then Ctrl+C in the JSON view. Confirm all displayed JSON is selected and copied.
- [ ] Press Ctrl+F where implemented, find a known value, wrap once, and confirm the match becomes selected.
- [ ] Press Ctrl+S or choose `Save JSON As…`. Save, reopen, and compare the UTF-8 content with the displayed report.
- [ ] Repeat selection, Ctrl+A, Ctrl+C, Ctrl+F, and save behavior on a long plain-text report.

## Result rows and paths

- [ ] Run a scan or project preflight, right-click a colored result row, and confirm only relevant commands are shown.
- [ ] Choose `Copy Row` and `Copy Details`; paste and confirm column labels, values, Unicode, and line endings are useful.
- [ ] On a row with a path, choose `Copy Path` and compare the exact path.
- [ ] Choose `Open Containing Folder` and `Reveal in File Explorer`; confirm Explorer opens the existing location and selects the file where applicable.
- [ ] Choose `Open` only for a controlled non-executable document/directory fixture. Confirm the normal Windows association is used.
- [ ] Choose `Inspect with ARX` on a supported existing target and confirm ARX performs static inspection rather than launching the target.
- [ ] Double-click or press Enter on an existing path row and confirm the safe reveal behavior. Repeat on a non-path row and confirm details open.
- [ ] Use a Unicode fixture such as `C:\ARX Test\Jörg 東京\sample.json`. Confirm choose, display, copy, save, reveal, inspect, and report operations preserve the path.
- [ ] Use or create a row whose path no longer exists. Confirm open/reveal/inspect commands are absent or fail with an understandable ARX error; the path must never be treated as a shell command.

## Feedback, errors, and cancellation

- [ ] Start each long-running operation and confirm the activity text, indeterminate progress, elapsed time, disabled conflicting actions, and Cancel control are visible.
- [ ] Cancel an operation where cancellation is supported. Confirm the UI remains responsive and reports cancellation without claiming underlying work stopped when it could not be interrupted safely.
- [ ] Trigger a controlled file/path error. Confirm the summary is understandable, technical details are selectable, and `Copy Details` preserves the diagnostic text.
- [ ] Verify file and directory pickers start in a useful recent in-session location, use appropriate filters, and allow cancellation without changing ARX state.

## Optional AI and web investigation

- [ ] Open `Settings → Intelligence Providers → OpenAI API`. Confirm Configure OpenAI API Key, Import OpenAI API Key, Replace Credential, Remove Credential, Test Connection, and Open OpenAI Chat are reachable with ordinary mouse clicks.
- [ ] Open OpenAI API Settings and confirm no network request or ARX evidence transmission occurs merely from opening the window. Confirm Credential, Credential source, Authentication, API, Model, Overall, and Last check remain separate safe fields.
- [ ] Choose Configure OpenAI API Key and confirm only the fixed official OpenAI Platform API-key page opens; ARX must not invent a key or automate the ChatGPT desktop application or website.
- [ ] With a dedicated non-production test key in a temporary file, choose Import. Confirm `Credential: CONFIGURED` and `Credential source: Secure Windows Store` appear and no plaintext key or show-key action appears anywhere. Confirm the plaintext source file remains until the user deliberately deletes it.
- [ ] Replace the protected test credential, then remove it. Confirm the prior key is never redisplayed and the safe state returns to `NOT_CONFIGURED`. If an unreadable protected-blob fixture is available, confirm `CREDENTIAL_UNREADABLE` is distinct from missing and rejected authentication.
- [ ] Run Test Connection with a permitted non-production API project. Confirm it sends no machine/project evidence and reports sanitized authentication/API/model/overall state. Record `READY` only after a real successful API response; otherwise record the exact safe failure category.
- [ ] Use Clear History and confirm the metadata-only local transmission history is removed without changing deterministic ARX reports. Confirm no audit record contains a key, prompt/response body, URL, full local path, or `SENT` boolean.
- [ ] Right-click a relevant finding and confirm OpenAI, Codex, safe-fix, project-comparison, web/Google, exact-error, official-documentation, evidence, and raw-data commands appear only where applicable.
- [ ] Open the advisory panel and verify the selected project/finding/status, provider availability, analysis modes, and `AI ADVISORY — NON-AUTHORITATIVE` label are visible.
- [ ] Choose `Preview What Will Be Sent`; confirm no request occurs and the prompt contains bounded redacted context rather than the complete machine scan.
- [ ] On first send to each provider, decline consent. Confirm no provider call occurs. Reopen, accept, and confirm consent is remembered only for that provider during the current process.
- [ ] With OpenAI unconfigured and with Codex unavailable, confirm a clear provider-specific explanation appears while core ARX remains usable.
- [ ] If a test provider is authorized, send a non-sensitive fixture question, cancel a second request, and verify Completed/Cancelled/Timed out/Failed states without GUI freezing.
- [ ] Copy a response, copy/save the conversation, and copy the diagnostic prompt. Inspect each output for the advisory label and redaction.
- [ ] Trigger web, Google, exact-error, and official-documentation searches with a non-sensitive fixture. Inspect the browser query and confirm private paths, usernames, tokens, and irrelevant identifiers are absent.

## Installer, uninstall, and upgrade

These items change Windows application state. Exercise them only on an approved test machine or disposable VM. Compilation alone does not satisfy them.

- [ ] Confirm the install/upgrade/uninstall target is an approved disposable or isolated Windows environment. If it is not, mark every lifecycle transition `BLOCKED`; do not use the development workstation as a substitute.
- [ ] Verify the published SHA-256 manifest against the installer before running it. Record whether the installer is signed; current development builds are expected to be unsigned.
- [ ] Complete the code-signing release gate: identify the approved publisher certificate, confirm private-key and timestamping policy, sign both the application executable and installer, and independently verify a valid Authenticode signature. If no approved certificate is available, record `BLOCKED`; a checksum is not a signature.
- [ ] Run an interactive install. Confirm the MIT license, x64 Program Files destination, Start Menu entry, optional unchecked desktop shortcut, and launch-at-finish choice behave as documented.
- [ ] Launch the installed application from the Start Menu and directly from its install directory. Repeat representative scan, report, path, and Unicode checks.
- [ ] Run a silent install and confirm it does not launch ARX unexpectedly.
- [ ] Install a newer test version over an older build with the same stable AppId. Confirm one product entry remains, expected files update, launch still works, and user-visible behavior is preserved.
- [ ] Uninstall from Windows Installed Apps and from the Start Menu uninstall entry. Confirm installed ARX files and shortcuts are removed without deleting unrelated files or portable copies.
- [ ] Verify uninstall does not silently enumerate profiles or remove `%LOCALAPPDATA%\ARX`. If complete provider-data cleanup is desired, use Remove Credential and Clear History before uninstall, then deliberately remove any remaining per-user ARX provider-data directory.

## Acceptance summary

- Passed:
- Failed:
- Blocked:
- Not run:
- Release decision and rationale:
