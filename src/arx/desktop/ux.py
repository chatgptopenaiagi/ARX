"""UI-neutral Windows UX helpers for ARX Desktop.

The functions in this module deliberately do not inspect or reinterpret ARX
evidence.  They format information already visible to the user and implement
explicit, user-requested navigation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


MAX_UI_STATE_BYTES = 16 * 1024
_GEOMETRY = re.compile(r"^(?P<width>\d{3,5})x(?P<height>\d{3,5})(?P<x>[+-]\d{1,6})(?P<y>[+-]\d{1,6})$")


@dataclass(frozen=True)
class PathCapabilities:
    """Actions that are meaningful for a path at the time a menu opens."""

    path: Path
    exists: bool
    is_file: bool
    is_directory: bool

    @property
    def can_open(self) -> bool:
        return self.exists

    @property
    def can_reveal(self) -> bool:
        return self.exists

    @property
    def can_inspect(self) -> bool:
        return self.exists


def path_capabilities(value: str | os.PathLike[str] | None) -> PathCapabilities | None:
    """Return current path capabilities, or ``None`` for empty/invalid input."""

    if value is None:
        return None
    try:
        text = os.fspath(value).strip()
    except (TypeError, ValueError):
        return None
    if not text or "\x00" in text:
        return None
    path = Path(text)
    try:
        exists = path.exists()
        is_file = path.is_file() if exists else False
        is_directory = path.is_dir() if exists else False
    except OSError:
        exists = is_file = is_directory = False
    return PathCapabilities(path=path, exists=exists, is_file=is_file, is_directory=is_directory)


def find_path_value(columns: Sequence[str], values: Sequence[object]) -> str | None:
    """Find a non-empty value from an explicitly path-named result column."""

    for column, value in zip(columns, values):
        if "path" in str(column).casefold() or str(column).casefold() in {"file", "directory", "location"}:
            text = str(value or "").strip()
            if text:
                return text
    return None


def format_result_row(columns: Sequence[str], values: Sequence[object]) -> str:
    """Format a result row as readable, exact visible key/value text."""

    parts = []
    for column, value in zip(columns, values):
        text = str(value or "")
        if text:
            label = str(column).replace("_", " ").strip().title()
            parts.append(f"{label}: {text}")
    return "\n".join(parts)


def explorer_arguments(path: Path, action: str) -> list[str]:
    """Build an argument array for Explorer; never returns a shell string."""

    action = action.casefold()
    if action == "reveal":
        target = path if path.is_file() else path.parent if not path.is_dir() else path
        if path.is_file():
            return ["explorer.exe", f"/select,{target}"]
        return ["explorer.exe", str(target)]
    if action in {"open", "containing_folder"}:
        target = path.parent if action == "containing_folder" and path.is_file() else path
        return ["explorer.exe", str(target)]
    raise ValueError(f"Unsupported path action: {action}")


def open_path(
    value: str | os.PathLike[str],
    action: str = "open",
    *,
    platform: str | None = None,
    launcher: Callable[..., object] = subprocess.Popen,
    startfile: Callable[[str], object] | None = None,
) -> None:
    """Open or reveal an existing path after an explicit user action.

    On Windows, files are opened through ``os.startfile`` and Explorer is
    launched with an argument list for folder/reveal actions.  No shell is used.
    The injectable callables keep the security boundary directly testable.
    """

    capabilities = path_capabilities(value)
    if capabilities is None or not capabilities.exists:
        raise FileNotFoundError(f"Path does not exist: {value}")
    path = capabilities.path
    action = action.casefold()
    current_platform = platform or os.name
    if current_platform == "nt":
        if action == "open" and capabilities.is_file:
            opener = startfile or getattr(os, "startfile", None)
            if opener is None:
                raise OSError("Windows file opening is unavailable.")
            opener(str(path))
            return
        arguments = explorer_arguments(path, action)
        launcher(arguments, shell=False)
        return
    target = path.parent if action == "containing_folder" and capabilities.is_file else path
    launcher(["xdg-open", str(target)], shell=False)


def sanitize_geometry(value: object, *, minimum: tuple[int, int] = (900, 600)) -> str | None:
    """Validate persisted Tk geometry and reject unusable/off-format values."""

    match = _GEOMETRY.fullmatch(str(value or ""))
    if not match:
        return None
    width = int(match.group("width"))
    height = int(match.group("height"))
    if width < minimum[0] or height < minimum[1] or width > 10000 or height > 10000:
        return None
    return str(value)


class UIStateStore:
    """Persist only non-sensitive window geometry and tab selection."""

    allowed_keys = frozenset({"geometry", "selected_tab"})

    def __init__(self, path: Path | None = None):
        local = os.environ.get("LOCALAPPDATA")
        self.path = path or Path(local or Path.home()) / "ARX" / "ui-state.json"

    def load(self) -> dict[str, object]:
        try:
            if not self.path.is_file() or self.path.stat().st_size > MAX_UI_STATE_BYTES:
                return {}
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        state: dict[str, object] = {}
        geometry = sanitize_geometry(raw.get("geometry"))
        if geometry:
            state["geometry"] = geometry
        selected_tab = raw.get("selected_tab")
        if isinstance(selected_tab, int) and 0 <= selected_tab <= 50:
            state["selected_tab"] = selected_tab
        return state

    def save(self, state: Mapping[str, object]) -> None:
        safe: dict[str, object] = {}
        geometry = sanitize_geometry(state.get("geometry"))
        if geometry:
            safe["geometry"] = geometry
        selected_tab = state.get("selected_tab")
        if isinstance(selected_tab, int) and 0 <= selected_tab <= 50:
            safe["selected_tab"] = selected_tab
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)


def copy_to_clipboard(owner: object, text: object) -> str:
    """Copy exact visible Unicode text and return the copied value."""

    value = str(text)
    owner.clipboard_clear()
    owner.clipboard_append(value)
    # Tk keeps clipboard ownership alive after a window closes on Windows.
    updater = getattr(owner, "update_idletasks", None)
    if callable(updater):
        updater()
    return value


def selected_tree_text(tree: object) -> str:
    """Format selected Treeview rows without including hidden UI state."""

    columns: Iterable[str] = tree.cget("columns")
    rows = []
    for item_id in tree.selection():
        values = tree.item(item_id, "values")
        rows.append(format_result_row(tuple(columns), tuple(values)))
    return "\n\n".join(item for item in rows if item)


def enable_windows_dpi_awareness(*, platform: str | None = None, windll: object | None = None) -> bool:
    """Enable process DPI awareness on Windows as a best-effort startup step."""

    if (platform or os.name) != "nt":
        return False
    try:
        if windll is None:
            import ctypes

            windll = ctypes.windll
        shcore = getattr(windll, "shcore", None)
        if shcore is not None:
            shcore.SetProcessDpiAwareness(1)
        else:
            windll.user32.SetProcessDPIAware()
        return True
    except (AttributeError, OSError):
        return False
