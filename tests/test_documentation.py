from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_manual_windows_checklist_covers_every_required_interaction():
    checklist = _read("docs/windows-desktop-acceptance.md")
    required = (
        "Right-click it",
        "Copy All JSON",
        "Ctrl+A",
        "Ctrl+C",
        "Ctrl+F",
        "Save JSON As",
        "right-click a colored result row",
        "Copy Row",
        "Copy Path",
        "Open Containing Folder",
        "Inspect with ARX",
        "Resize the main window",
        "Maximize",
        "Scroll long",
        "Tab and Shift+Tab",
        "Unicode fixture",
        "path no longer exists",
        "Copy Details",
        "DPI scaling",
        "code-signing release gate",
        "checksum is not a signature",
        "interactive install",
        "Uninstall",
        "newer test version over an older build",
    )

    for phrase in required:
        assert phrase.casefold() in checklist.casefold()
    assert "An unchecked item is not tested" in checklist


def test_phase_a_acceptance_keeps_blocked_release_gates_explicit():
    acceptance = _read("docs/arx-3-final-acceptance.md")

    for phrase in (
        "Stable `v3.0.0` is **not approved and was not created**",
        "Geometry arithmetic and headless/widget state remain structural evidence only",
        "Screen-reader verification and accessibility certification are not claimed",
        "Lifecycle result: **BLOCKED / NOT RUN**",
        "Code-signing readiness: **BLOCKED**",
        "matching hashes do not substitute for Authenticode",
        "Human review is required before any Phase B branch is created",
    ):
        assert phrase in acceptance


def test_regression_principle_treats_usability_as_correctness():
    contributing = _read("CONTRIBUTING.md")

    assert "ARX correctness includes both analytical correctness and human usability" in contributing
    assert "incomplete desktop result" in contributing


def test_durable_arx3_lessons_are_architectural_invariants_not_run_history():
    architecture = _read("docs/architecture.md")
    testing = _read("docs/testing.md")
    security = _read("docs/security-model.md")
    contributing = _read("CONTRIBUTING.md")

    assert "canonical report model is the sole owner" in architecture
    assert "path syntax carried by the evidence, not the host process" in architecture
    assert "one Tk root per application process" in architecture
    assert "portable desktop payload is the canonical Windows application artifact" in architecture
    assert "every GUI test node runs in a fresh interpreter" in testing
    assert "Artifact construction evidence is not lifecycle evidence" in testing
    assert "select canonical evidence -> filter for relevance -> redact -> bound" in security
    assert "not fed back into evidence, severity, or remediation" in security
    assert "must consume the canonical report model" in contributing


def test_external_boundary_document_preserves_three_separate_trust_domains():
    security = _read("docs/ai-assistance-security.md")

    assert "ARX deterministic local evidence" in security
    assert "External AI advice" in security
    assert "Public web search" in security
    assert "never the command line" in security
    assert "shell=False" in security
    assert "cannot modify the workstation or become ARX evidence" in security
    assert "%PROJECT_ROOT%" in security and "%USERPROFILE%" in security and "%LOCAL_PATH%" in security
    assert "does not grant publishing" in security


def test_phase_b_security_document_covers_credentials_health_audit_and_uninstall():
    security = _read("docs/ai-assistance-security.md")
    phase_b = _read("docs/arx-4-phase-b-trust-foundation.md")
    installer = _read("packaging/INSTALLER.md")

    for phrase in (
        "Settings → Intelligence Providers → OpenAI API",
        "Windows DPAPI",
        "CREDENTIAL_UNREADABLE",
        "configured credential is not provider readiness",
        "GET /v1/models/{model}",
        "REQUEST_PREPARED",
        "OUTBOUND_REQUEST_INITIATED",
        "RESPONSE_RECEIVED",
        "REQUEST_FAILED",
        "CANCELLED",
        "never stores the API key",
        "no implicit export",
        "automatic ARX cloud synchronization",
        "30 days",
        "Clear History",
    ):
        assert phrase.casefold() in security.casefold()
    assert "Phase C remains blocked" in phase_b
    assert "does not silently delete `%LOCALAPPDATA%\\ARX`" in phase_b
    assert "%LOCALAPPDATA%\\ARX" in installer


def test_phase_c_document_preserves_advisory_and_provenance_boundaries():
    phase_c = _read("docs/PHASE_C.md")

    for phrase in (
        "AI ADVISORY — NON-AUTHORITATIVE",
        "ARX remains useful without an AI provider",
        "GENERAL CHAT",
        "ARX EVIDENCE CHAT",
        "OpenAI Chat and Codex CLI keep independent",
        "at most 16 turns and 24,000 characters",
        "View Redacted Context",
        "Preview What Will Be Sent",
        "Ask Both requires exactly two distinct",
        "two flat panels",
        "Compare Responses",
        "TEXTUAL OVERLAP",
        "DIFFERENCES",
        "UNRESOLVED",
        "COMPARISON AID — NO EVIDENCE UPGRADE",
        "`VERIFIED` is not an `EvidenceKind`",
        "REQUEST_PREPARED",
        "OUTBOUND_REQUEST_INITIATED",
        "RESPONSE_RECEIVED",
        "REQUEST_FAILED",
        "CANCELLED",
        "30 days",
        "QUOTA_EXHAUSTED",
        "There is deliberately no return path",
    ):
        assert phrase in phase_c

    assert "winner, ranking, confidence boost" in phase_c
    assert "does not claim AI independence" in phase_c


def test_readme_is_the_complete_arx4_beta_landing_page():
    readme = _read("README.md")

    for phrase in (
        "# ARX 4",
        "ARX 4.0.0 Beta 3",
        "Project-Aware Compatibility Intelligence",
        "## Why ARX 4 is different",
        "Machine DNA",
        "Software DNA",
        "Project DNA",
        "Requirement Graph",
        "Provider Graph",
        "Execution Context",
        "Fact provenance and decision validation",
        "VERIFIED is not an `EvidenceKind`",
        "GREEN, YELLOW, and RED",
        "shortest trusted path to GREEN",
        "There is no return path from external advice into ARX evidence",
        "The human remains the final decision-maker",
        "ARX-Desktop-win-x64-v4.0.0-b3.zip",
        "ARX-Desktop-Setup-win-x64-v4.0.0-b3.exe",
        "SHA256SUMS.txt",
        "Phase C",
        "Real DPI and multi-monitor acceptance is incomplete",
        "aggregate Definition of Done remains partial",
    ):
        assert phrase in readme
    for workflow in ("actions/workflows/ci.yml", "actions/workflows/codeql.yml"):
        assert workflow in readme
    for document in (
        "docs/release-notes-4.0.0-b3.md",
        "docs/release-notes-4.0.0-b2.md",
        "docs/release-notes-4.0.0-b1.md",
        "docs/architecture.md",
        "docs/arx-4-phase-b-trust-foundation.md",
        "docs/confidence-semantics.md",
        "docs/security-model.md",
        "docs/testing.md",
        "docs/python-package-publishing.md",
        "docs/arx-3-implementation-report.md",
        "docs/windows-desktop-acceptance.md",
    ):
        assert document in readme


def test_confidence_document_disclaims_calibration_and_audits_assignments():
    confidence = _read("docs/confidence-semantics.md")

    for phrase in (
        "detector-author weight",
        "not a probability",
        "measured accuracy",
        "statistical confidence",
        "Evidence and ToolRecord defaults",
        "Machine and provider discovery",
        "Software inspection",
        "Project inspection",
        "Resolution and conflicts",
        "Legacy compatibility aggregation",
        "Fixtures and schemas",
    ):
        assert phrase.casefold() in confidence.casefold()


def test_fact_provenance_is_not_collapsed_into_decision_validation():
    architecture = _read("docs/architecture.md")
    prompt = _read("docs/ARX_CODEX_MASTER_PROMPT.md")
    advisory = _read("docs/ai-assistance-security.md")

    assert "DECLARED / OBSERVED / INFERRED / ESTIMATED / SIMULATED / STRUCTURAL / UNKNOWN" in architecture
    assert "VERIFIED is not an `EvidenceKind`" in architecture
    assert "VALIDATION" in architecture
    assert "claim semantic/schema validation" in advisory
    assert "VERIFIED\n\n\nGREEN" not in prompt
    assert "ARX fact evidence" in prompt


def test_rc_release_notes_preserve_history_and_disclose_manual_limits():
    notes = _read("docs/release-notes-3.0.0-rc1.md")
    historical = _read("docs/release-notes-2.0.0.md")

    assert notes.startswith("# ARX 3.0 Release Candidate")
    assert "Package version: `3.0.0rc1`" in notes
    assert "Planned Git tag: `v3.0.0-rc1`" in notes
    assert "What changed since ARX 2" in notes
    assert "schema `0.1` and project/AI contract schema `0.2`" in notes
    assert "Real DPI and multi-monitor acceptance is incomplete" in notes
    assert "Screen-reader and complete accessibility acceptance is incomplete" in notes
    assert "same-AppId upgrade" in notes
    assert "aggregate Definition of Done remains partial" in notes
    assert historical.startswith("# ARX 2.0.0")


def test_arx4_beta_release_notes_define_security_remediation_and_exclude_phase_c():
    notes = _read("docs/release-notes-4.0.0-b2.md")

    for phrase in (
        "# ARX 4.0.0 Beta 2",
        "Package version: `4.0.0b2`",
        "Git tag: `v4.0.0-b2`",
        "DECLARED",
        "OBSERVED",
        "INFERRED",
        "UNKNOWN",
        "ESTIMATED",
        "SIMULATED",
        "STRUCTURAL",
        "`VERIFIED` remains outside `EvidenceKind`",
        "Windows per-user DPAPI",
        "CREDENTIAL_UNREADABLE",
        "Responses API",
        "rejects redirects",
        "metadata-only transmission audit",
        "Settings -> Intelligence Providers -> OpenAI API",
        "Test Connection",
        "Codex CLI advisory provider remains",
        "NON-AUTHORITATIVE",
        "Phase C is **NOT included**",
        "Ask Both",
        "QUOTA_EXHAUSTED",
        "does not relabel that failure as invalid authentication",
        "unsigned",
        "Hypothesis",
        "SOURCE_DATE_EPOCH",
        "GitHub Artifact Attestations",
        "RFC 3161",
        "No trust store was modified",
    ):
        assert phrase in notes


def test_beta3_release_notes_define_phase_c_without_upgrading_advice():
    notes = _read("docs/release-notes-4.0.0-b3.md")

    for phrase in (
        "# ARX 4.0.0 Beta 3",
        "Package version: `4.0.0b3`",
        "Git tag: `v4.0.0-b3`",
        "AI ADVISORY — NON-AUTHORITATIVE",
        "`VERIFIED` remains outside `EvidenceKind`",
        "GENERAL CHAT",
        "ARX EVIDENCE CHAT",
        "OpenAI Responses API",
        "Windows current-user DPAPI",
        "View Redacted Context",
        "Ask Both requires exactly two distinct",
        "two flat, unranked provider panels",
        "COMPARISON AID — NO EVIDENCE UPGRADE",
        "TEXTUAL OVERLAP",
        "DIFFERENCES",
        "UNRESOLVED",
        "CREDENTIAL_UNREADABLE",
        "QUOTA_EXHAUSTED",
        "REQUEST_PREPARED",
        "OUTBOUND_REQUEST_INITIATED",
        "RESPONSE_RECEIVED",
        "REQUEST_FAILED",
        "CANCELLED",
        "UNSIGNED_EXPECTED_PRE_SIGNING",
        "production PyPI",
    ):
        assert phrase in notes

    assert "There is no winner, provider ranking" in notes
    assert "cannot modify Evidence, EvidenceKind" in notes


def test_python_publishing_document_preserves_release_and_credential_boundaries():
    publishing = _read("docs/python-package-publishing.md")

    for phrase in (
        "arx-prescanner",
        "existing package identity",
        "both PyPI and TestPyPI",
        "TestPyPI",
        "Trusted Publishing",
        "id-token: write",
        "short-lived OIDC",
        "publish-pypi.yml",
        "`testpypi` and `pypi`",
        "reviewed wheel and source distribution",
        "outside the checkout",
        "target=testpypi",
        "target=production",
        "python -m pip install arx-prescanner==4.0.0b3",
    ):
        assert phrase.casefold() in publishing.casefold()
    assert "long-lived API token" in publishing
    assert "pull_request_target" in publishing
    assert "Creating or publishing a GitHub Release does not trigger" in publishing
    assert "production pypi remains blocked" in publishing.casefold()


def test_final_report_contains_every_point_and_required_engineering_sections():
    report = _read("docs/arx-3-implementation-report.md")

    for point in range(1, 28):
        assert f"| {point} |" in report
    for section in (
        "## UX problems found",
        "## Changes implemented",
        "## Files changed",
        "## Tests and verification",
        "## Manual verification",
        "## Remaining limitations",
        "## Point 24 Definition of Done audit",
        "## Point 27 final implementation report",
        "## Point-by-point final audit",
        "| Point | Status | Main implementation | Tests | Remaining limitation |",
    ):
        assert section in report
