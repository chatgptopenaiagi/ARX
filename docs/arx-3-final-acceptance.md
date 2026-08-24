# ARX 3 final acceptance — Phase A

Acceptance date: 2026-08-24 (Europe/Vienna)

Branch: `arx3-final-acceptance`

Starting commit: `11a1d76d1dd7225622cb41d862c8cb129ab4db80`

Candidate: ARX `3.0.0rc1` / tag `v3.0.0-rc1`

## Decision

ARX 3 remains a release candidate. Stable `v3.0.0` is **not approved and was not created** because required visible multi-DPI, screen-reader, isolated installer lifecycle, and code-signing acceptance evidence is incomplete. Successful automated tests, geometry calculations, artifact compilation, smoke workflows, and checksums are not promoted into evidence for those missing activities.

No ARX 4 feature implementation is part of this branch.

## Automated and package validation

- Python source/test compilation passed.
- The Windows CI-equivalent split passed 146 non-GUI tests and all 38 Tk-backed nodes in fresh interpreters: 184 tests total.
- The source distribution and wheel built successfully; strict Twine metadata/README validation and `check-wheel-contents` passed.
- A fresh Python 3.10 virtual environment outside the checkout installed the wheel and successfully exercised import/version isolation, `arx --help`, `arx quick`, and the `arx-desktop` entry point.
- `pip check` reported no broken requirements.
- The tracked-file scan found no forbidden credential filenames and no high-signal credential/private-key value patterns.

## Point 12 — Window and DPI

Result: **PARTIAL / BLOCKED FOR FINAL ACCEPTANCE**

- Structural Tk tests for bounded geometry, best-effort Windows DPI-awareness startup, resizable panes/dialogs, scrolling, minimum sizes, and allowlisted UI-state persistence pass.
- The workstation exposed a visible Windows 10 console session at 1680×1050. A portable-window inspection was attempted with Windows UI control, but state capture failed and then detected concurrent user input; automation stopped immediately.
- No visible resize/maximize result was recorded. No 100%/150%/200% comparison, real multi-monitor placement test, or visual DPI claim was produced.

Geometry arithmetic and headless/widget state remain structural evidence only.

## Point 13 — Accessibility

Result: **PARTIAL / BLOCKED FOR FINAL ACCEPTANCE**

- Structural tests cover descriptive text, textual status alongside color, focusability, keyboard bindings, selectable content, and standard actions.
- Windows Narrator is installed, but no valid Narrator/NVDA session was completed and no spoken-name, role, state, focus-order, or contrast result was observed.

Screen-reader verification and accessibility certification are not claimed.

## Point 16 — Installer lifecycle and signing

Result: **PARTIAL / BLOCKED FOR FINAL ACCEPTANCE**

Artifact construction passed:

- PyInstaller `6.22.2` built the complete portable payload from the Phase A source.
- Both packaged UI smoke workflows exited successfully. The software workflow populated machine, software, compatibility, evidence, and export results; the project workflow reported application version `3.0.0rc1`, schema `0.2`, populated project/evidence views, and a successful export.
- Inno Setup `7.1.0` compiled the RC installer.
- Independent SHA-256 calculation matched every manifest entry.

| Artifact | Bytes | Independent SHA-256 | Authenticode |
|---|---:|---|---|
| `ARX.exe` | 1,601,531 | `bb1351c38db3bd9aff0b27c5e55be0a5a23e66589af51bb7c4914dd7173f5284` | `NotSigned` |
| `ARX-Desktop-win-x64-v3.0.0-rc1.zip` | 10,554,009 | `70fee05d96f17ceaf25a7d39b6327d9787ac143c9d632f210e912c0c93264193` | Not an Authenticode target |
| `ARX-Desktop-Setup-win-x64-v3.0.0-rc1.exe` | 9,254,815 | `0a5e3b49fe3e230e0b6c604e2433759b33764c0fd885f2b406a3b9bc2e33971c` | `NotSigned` |

Lifecycle result: **BLOCKED / NOT RUN**. The host is Windows 10 Home and exposed no Windows Sandbox disposable-client feature. It also contained pre-existing installed ARX state. Interactive install, launch-after-install, silent install, same-AppId upgrade, uninstall, and clean-removal were therefore not run on this workstation. Existing installed state was not altered for acceptance.

Code-signing readiness: **BLOCKED**. No code-signing certificate was found in the current-user or local-machine personal certificate stores. No approved external signing service or publisher certificate was supplied. The executable and installer are truthfully reported as unsigned; matching hashes do not substitute for Authenticode.

Generated artifacts remain in the ignored local `release/` directory and were not published by Phase A.

## Point 24 — Definition of Done

Result: **PARTIAL / NOT SATISFIED FOR STABLE RELEASE**

Canonical behavior, semantic invariants, cross-surface consistency, security boundaries, packaging construction, documentation, redaction, and deterministic test coverage pass. The following acceptance conditions remain open:

- visible resize/maximize and real multi-DPI/multi-monitor behavior;
- screen-reader and hands-on accessibility behavior;
- install/silent-install/upgrade/uninstall lifecycle in an approved disposable environment;
- code signing with an approved certificate and independent signature verification.

These are missing evidence, not passing results inferred from neighboring checks. Point 24 and the aggregate release Definition of Done remain partial.

## Epistemic corrections completed

- Documentation and the external-advisory prompt now state that fact provenance is exactly `DECLARED`, `OBSERVED`, `INFERRED`, or `UNKNOWN`.
- `VERIFIED` is not presented as a peer per-fact state. Decision/relation validation remains semantic-invariant and schema/composed-state validation.
- The `Evidence` value, provenance, and basis fields are documented separately from decision validation.
- Every numeric confidence assignment is catalogued as an uncalibrated detector-author weight; no probability or measured-accuracy claim is made.
- A regression test locks the exact `EvidenceKind` membership and explicitly excludes `VERIFIED`.

## Review gate

Phase A stops here after validation, commit, and branch publication. Human review is required before any Phase B branch is created. Approval of this Phase A branch would approve the final ARX 3 evidence boundary and documented blocked items; it would not silently convert the RC into stable `v3.0.0`.
