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
