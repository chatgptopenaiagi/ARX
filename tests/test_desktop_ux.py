import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import pytest

from arx.desktop.ux import (
    UIStateStore,
    enable_windows_dpi_awareness,
    explorer_arguments,
    find_path_value,
    format_result_row,
    open_path,
    path_capabilities,
    sanitize_geometry,
)
from arx.desktop.widgets import ReadOnlyText, tree


def test_result_formatting_preserves_visible_unicode_and_omits_empty_values():
    text = format_result_row(
        ("component", "status", "path", "evidence"),
        ("Python – Werkzeug", "READY", "C:\\Nutzer\\Jörg\\python.exe", ""),
    )

    assert text == "Component: Python – Werkzeug\nStatus: READY\nPath: C:\\Nutzer\\Jörg\\python.exe"


def test_find_path_value_uses_only_path_named_columns():
    assert find_path_value(("status", "path", "reason"), ("RED", r"C:\Tools\python.exe", "bad")) == r"C:\Tools\python.exe"
    assert find_path_value(("status", "reason"), ("RED", r"C:\not-a-path-column")) is None


def test_path_capabilities_handle_existing_unicode_and_missing_paths(tmp_path):
    target = tmp_path / "Jörg 工具.txt"
    target.write_text("visible", encoding="utf-8")

    existing = path_capabilities(target)
    missing = path_capabilities(tmp_path / "missing.exe")

    assert existing and existing.exists and existing.is_file and existing.can_reveal
    assert missing and not missing.exists and not missing.can_open
    assert path_capabilities("bad\x00path") is None


def test_explorer_arguments_are_an_array_not_a_shell_string(tmp_path):
    target = tmp_path / "tool;not-a-command.exe"
    target.write_bytes(b"MZ")

    assert explorer_arguments(target, "reveal") == ["explorer.exe", f"/select,{target}"]
    assert explorer_arguments(target, "containing_folder") == ["explorer.exe", str(tmp_path)]
    with pytest.raises(ValueError):
        explorer_arguments(target, "delete")


def test_open_path_never_enables_shell_interpolation(tmp_path):
    directory = tmp_path / "folder & whoami"
    directory.mkdir()
    calls = []

    open_path(directory, "open", platform="nt", launcher=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert calls == [((["explorer.exe", str(directory)],), {"shell": False})]


def test_open_file_uses_injected_windows_file_api(tmp_path):
    target = tmp_path / "application.exe"
    target.write_bytes(b"MZ")
    opened = []

    open_path(target, "open", platform="nt", startfile=opened.append)

    assert opened == [str(target)]


def test_open_path_refuses_nonexistent_target(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_path(tmp_path / "missing", platform="nt")


def test_geometry_validation_accepts_only_bounded_tk_geometry():
    assert sanitize_geometry("1280x820+100-20") == "1280x820+100-20"
    assert sanitize_geometry("100x100+0+0") is None
    assert sanitize_geometry("1280x820; calc.exe") is None


def test_dpi_awareness_is_best_effort_and_platform_scoped():
    class Shcore:
        calls = []

        @classmethod
        def SetProcessDpiAwareness(cls, value):
            cls.calls.append(value)

    class Windll:
        shcore = Shcore()

    assert enable_windows_dpi_awareness(platform="nt", windll=Windll())
    assert Shcore.calls == [1]
    assert not enable_windows_dpi_awareness(platform="posix", windll=Windll())


def test_ui_state_store_persists_only_non_sensitive_allowlisted_state(tmp_path):
    path = tmp_path / "state.json"
    store = UIStateStore(path)

    store.save(
        {
            "geometry": "1280x820+10+20",
            "selected_tab": 4,
            "project_path": r"C:\Private\Project",
            "OPENAI_API_KEY": "must-not-persist",
        }
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw == {"geometry": "1280x820+10+20", "selected_tab": 4}
    assert store.load() == raw


def test_ui_state_store_rejects_malformed_or_oversized_content(tmp_path):
    path = tmp_path / "state.json"
    store = UIStateStore(path)
    path.write_text("not-json", encoding="utf-8")
    assert store.load() == {}

    path.write_text("x" * (17 * 1024), encoding="utf-8")
    assert store.load() == {}


def test_json_text_panel_exposes_standard_actions_and_exact_save_content():
    root = tk.Tk()
    root.withdraw()
    saved = []
    panel = ReadOnlyText(root, content_type="json", save_command=lambda kind, value: saved.append((kind, value)))
    panel.set_content('{\n  "name": "Jörg"\n}')

    labels = [action.label for action in panel.menu_actions() if action.label]
    panel.select_all()
    assert panel.selected_text() == '{\n  "name": "Jörg"\n}'
    panel.save()

    assert labels == ["Copy", "Select All", "Copy All JSON", "Find…", "Save JSON As…"]
    assert saved == [("json", '{\n  "name": "Jörg"\n}')]
    root.destroy()


def test_tree_supports_extended_selection_select_all_and_horizontal_scrollbar():
    root = tk.Tk()
    root.withdraw()
    holder = ttk.Frame(root)
    view = tree(holder, ("component", "status"))
    view.insert("", "end", iid="one", values=("Python", "READY"))
    view.insert("", "end", iid="two", values=("CMake", "MISSING"))

    view._arx_select_all()  # type: ignore[attr-defined]

    assert str(view.cget("selectmode")) == "extended"
    assert view.selection() == ("one", "two")
    assert any(
        isinstance(child, ttk.Scrollbar) and str(child.cget("orient")) == "horizontal"
        for child in holder.winfo_children()
    )
    root.destroy()
