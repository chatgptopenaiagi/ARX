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
        "interactive install",
        "Uninstall",
        "newer test version over an older build",
    )

    for phrase in required:
        assert phrase.casefold() in checklist.casefold()
    assert "An unchecked item is not tested" in checklist


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
    assert "does not enable PyPI publishing" in security


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
