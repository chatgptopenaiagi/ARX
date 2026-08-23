"""Reusable Tk widgets implementing familiar Windows interaction behavior."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable, Iterable, Sequence

from .theme import COLORS, status_color
from .ux import copy_to_clipboard, selected_tree_text


Command = Callable[[], object]


@dataclass(frozen=True)
class MenuAction:
    """One context-menu action; a ``None`` label represents a separator."""

    label: str | None
    command: Command | None = None
    enabled: bool = True


def show_context_menu(widget: tk.Misc, event: tk.Event, actions: Iterable[MenuAction]) -> tk.Menu | None:
    """Show a compact context menu containing only relevant actions."""

    normalized = list(actions)
    while normalized and normalized[0].label is None:
        normalized.pop(0)
    while normalized and normalized[-1].label is None:
        normalized.pop()
    compact: list[MenuAction] = []
    for action in normalized:
        if action.label is None and (not compact or compact[-1].label is None):
            continue
        compact.append(action)
    if not compact:
        return None
    menu = tk.Menu(widget, tearoff=False)
    for action in compact:
        if action.label is None:
            menu.add_separator()
        else:
            menu.add_command(
                label=action.label,
                command=action.command,
                state="normal" if action.enabled else "disabled",
            )
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
    return menu


class ToolTip:
    """Small delayed tooltip for controls whose purpose is not self-evident."""

    def __init__(self, widget: tk.Misc, text: str, delay_ms: int = 500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self.hide()
        self._after_id = self.widget.after(self.delay_ms, self.show)

    def show(self) -> None:
        if self._window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            background="#fffbd6",
            foreground="#111827",
            relief="solid",
            borderwidth=1,
            padx=7,
            pady=4,
            wraplength=420,
        )
        label.pack()
        self._window = window

    def hide(self, _event: tk.Event | None = None) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._window is not None:
            self._window.destroy()
            self._window = None


class FindDialog(tk.Toplevel):
    """Non-modal find bar for a read-only report surface."""

    def __init__(self, panel: "ReadOnlyText"):
        super().__init__(panel.winfo_toplevel())
        self.panel = panel
        self.title("Find")
        self.resizable(False, False)
        self.transient(panel.winfo_toplevel())
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Find what:").grid(row=0, column=0, sticky="w")
        self.query = ttk.Entry(body, width=44)
        self.query.grid(row=1, column=0, padx=(0, 8), pady=(4, 8), sticky="ew")
        ttk.Button(body, text="Find Next", command=self.find_next).grid(row=1, column=1, pady=(4, 8))
        self.status = ttk.Label(body, text="", style="Muted.TLabel")
        self.status.grid(row=2, column=0, columnspan=2, sticky="w")
        self.query.bind("<Return>", self.find_next)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.query.focus_set()

    def find_next(self, _event: tk.Event | None = None) -> str:
        needle = self.query.get()
        if not needle:
            self.status.configure(text="Enter text to find.")
            return "break"
        text = self.panel.text
        start = text.index("sel.last") if text.tag_ranges("sel") else text.index("insert")
        match = text.search(needle, start, stopindex="end", nocase=True)
        if not match:
            match = text.search(needle, "1.0", stopindex=start, nocase=True)
        if not match:
            self.status.configure(text="No match found.")
            return "break"
        end = f"{match}+{len(needle)}c"
        text.tag_remove("sel", "1.0", "end")
        text.tag_add("sel", match, end)
        text.mark_set("insert", end)
        text.see(match)
        text.focus_set()
        self.status.configure(text="Match selected.")
        return "break"


class ReadOnlyText(ttk.Frame):
    """Selectable report text with scrolling, shortcuts, find, save, and menu."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        content_type: str = "text",
        save_command: Callable[[str, str], object] | None = None,
        status_command: Callable[[str], object] | None = None,
        wrap: str = "word",
    ):
        super().__init__(parent, style="Panel.TFrame")
        self.content_type = content_type
        self.save_command = save_command
        self.status_command = status_command
        self._find_dialog: FindDialog | None = None
        self.text = tk.Text(
            self,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["selected"],
            selectforeground=COLORS["text"],
            relief="flat",
            wrap=wrap,
            font=("Consolas", 10),
            padx=12,
            pady=12,
            undo=False,
            takefocus=True,
        )
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set, state="disabled")
        self.text.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text.bind("<Control-c>", self.copy_selection)
        self.text.bind("<Control-a>", self.select_all)
        self.text.bind("<Control-f>", self.show_find)
        self.text.bind("<Control-s>", self.save)
        self.text.bind("<Button-3>", self._show_menu)

    def set_content(self, value: object) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", str(value))
        self.text.mark_set("insert", "1.0")
        self.text.configure(state="disabled")

    def get(self, start: str = "1.0", end: str = "end") -> str:
        return self.text.get(start, end)

    def focus_set(self) -> None:
        self.text.focus_set()

    def selected_text(self) -> str:
        try:
            return self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def copy_selection(self, _event: tk.Event | None = None) -> str:
        selected = self.selected_text()
        if selected:
            copy_to_clipboard(self, selected)
            self._status("Copy complete")
        return "break"

    def copy_all(self) -> str:
        copy_to_clipboard(self, self.text.get("1.0", "end-1c"))
        self._status("Copy complete")
        return "break"

    def select_all(self, _event: tk.Event | None = None) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "end-1c")
        self.text.see("insert")
        return "break"

    def show_find(self, _event: tk.Event | None = None) -> str:
        if self._find_dialog is None or not self._find_dialog.winfo_exists():
            self._find_dialog = FindDialog(self)
        else:
            self._find_dialog.deiconify()
            self._find_dialog.lift()
            self._find_dialog.query.focus_set()
        return "break"

    def save(self, _event: tk.Event | None = None) -> str:
        if self.save_command is not None:
            self.save_command(self.content_type, self.text.get("1.0", "end-1c"))
        return "break"

    def _status(self, message: str) -> None:
        if self.status_command is not None:
            self.status_command(message)

    def menu_actions(self) -> Sequence[MenuAction]:
        copy_all_label = "Copy All JSON" if self.content_type == "json" else "Copy All"
        save_label = "Save JSON As…" if self.content_type == "json" else "Save As…"
        return (
            MenuAction("Copy", self.copy_selection, bool(self.selected_text())),
            MenuAction("Select All", self.select_all),
            MenuAction(copy_all_label, self.copy_all),
            MenuAction(None),
            MenuAction("Find…", self.show_find),
            MenuAction(save_label, self.save, self.save_command is not None),
        )

    def _show_menu(self, event: tk.Event) -> str:
        self.text.focus_set()
        show_context_menu(self.text, event, self.menu_actions())
        return "break"


class StatusBadge(tk.Label):
    def __init__(self, parent: tk.Misc, status: str = "unknown", **kwargs):
        super().__init__(parent, font=("Segoe UI Semibold", 9), padx=9, pady=4, takefocus=True, **kwargs)
        self.set(status)

    def set(self, status: object) -> None:
        value = str(getattr(status, "value", status) or "unknown").upper()
        self.configure(
            text=value,
            bg=status_color(value),
            fg="#071018" if value not in {"BLOCKED", "MISSING", "RED"} else "white",
        )


def tree(
    parent: tk.Misc,
    columns: Sequence[str],
    widths: dict[str, int] | None = None,
    *,
    status_command: Callable[[str], object] | None = None,
) -> ttk.Treeview:
    view = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended", takefocus=True)
    for column in columns:
        view.heading(column, text=column.replace("_", " ").title())
        view.column(column, width=(widths or {}).get(column, 150), minwidth=70, anchor="w", stretch=True)
    vertical = ttk.Scrollbar(parent, orient="vertical", command=view.yview)
    horizontal = ttk.Scrollbar(parent, orient="horizontal", command=view.xview)
    view.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    view.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    parent.rowconfigure(0, weight=1)
    parent.columnconfigure(0, weight=1)
    for status, color in (
        (status, status_color(status))
        for status in ("ready", "partial", "missing", "blocked", "unknown", "not_applicable", "green", "yellow", "red")
    ):
        view.tag_configure(status, foreground=color)

    def select_all(_event: tk.Event | None = None) -> str:
        view.selection_set(view.get_children())
        return "break"

    def copy_rows(_event: tk.Event | None = None) -> str:
        value = selected_tree_text(view)
        if value:
            copy_to_clipboard(view, value)
            if status_command:
                status_command("Copy complete")
        return "break"

    view.bind("<Control-a>", select_all)
    view.bind("<Control-c>", copy_rows)
    view._arx_copy_rows = copy_rows  # type: ignore[attr-defined]
    view._arx_select_all = select_all  # type: ignore[attr-defined]
    return view


def text_panel(
    parent: tk.Misc,
    *,
    content_type: str = "text",
    save_command: Callable[[str, str], object] | None = None,
    status_command: Callable[[str], object] | None = None,
    wrap: str = "word",
) -> ReadOnlyText:
    return ReadOnlyText(
        parent,
        content_type=content_type,
        save_command=save_command,
        status_command=status_command,
        wrap=wrap,
    )


def set_text(widget: ReadOnlyText | tk.Text, value: object) -> None:
    if isinstance(widget, ReadOnlyText):
        widget.set_content(value)
        return
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", str(value))
    widget.configure(state="disabled")


class ErrorDetailsDialog(tk.Toplevel):
    """Understandable error summary with selectable, copyable details."""

    def __init__(self, parent: tk.Misc, title: str, summary: str, details: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("760x480")
        self.minsize(560, 360)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=summary, font=("Segoe UI Semibold", 11), wraplength=700).pack(fill="x", pady=(0, 10))
        self.details = ReadOnlyText(body, content_type="text")
        self.details.pack(fill="both", expand=True)
        self.details.set_content(details)
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Copy Details", command=self.details.copy_all).pack(side="left")
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right")
