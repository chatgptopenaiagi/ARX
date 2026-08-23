import json
from pathlib import Path

import pytest

from arx.desktop.ux import (
    UIStateStore,
    explorer_arguments,
    find_path_value,
    format_result_row,
    open_path,
    path_capabilities,
    sanitize_geometry,
)


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
