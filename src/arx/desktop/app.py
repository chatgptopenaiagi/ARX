"""ARX Desktop: a responsive, Windows-friendly view over deterministic ARX data."""

from __future__ import annotations

import json
import queue
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Mapping

from arx import PRODUCT_NAME, RELEASE_NAME, __version__
from arx.advisory.context import AdvisoryContext, build_advisory_context
from arx.advisory.providers import AIProvider, CodexCLIProvider, OpenAIProvider
from arx.advisory.web import build_search_query, build_search_url, open_search
from arx.core.models import serialize

from .advisory import AdvisoryWindow
from .controllers import DesktopController, project_readiness_view_model
from .theme import COLORS, apply_theme
from .ux import (
    UIStateStore,
    copy_to_clipboard,
    enable_windows_dpi_awareness,
    find_path_value,
    format_result_row,
    open_path,
    path_capabilities,
)
from .widgets import (
    ErrorDetailsDialog,
    MenuAction,
    ReadOnlyText,
    StatusBadge,
    ToolTip,
    set_text,
    show_context_menu,
    text_panel,
    tree,
)


class ARXDesktopApp(tk.Tk):
    """Tk desktop shell; scanner and compatibility semantics remain in ARX core."""

    def __init__(
        self,
        controller=None,
        *,
        state_store: UIStateStore | None = None,
        advisory_providers: Mapping[str, AIProvider] | None = None,
    ):
        super().__init__()
        self.controller = controller or DesktopController()
        self._state_store = state_store or UIStateStore()
        self._events: queue.Queue[tuple] = queue.Queue()
        self._started: float | None = None
        self._operation_cancel: threading.Event | None = None
        self._selected_target: str | None = None
        self._last_directory: str | None = None
        self._last_error_details: str | None = None
        self._last_error_summary: str | None = None
        self._action_buttons: list[ttk.Button] = []
        self._tooltips: list[ToolTip] = []
        self._advisory_providers = (
            dict(advisory_providers)
            if advisory_providers is not None
            else {
                "ChatGPT / OpenAI": OpenAIProvider(),
                "Codex CLI": CodexCLIProvider(),
            }
        )
        self._advisory_consent: set[str] = set()
        self._advisory_windows: list[AdvisoryWindow] = []
        self._poll_id: str | None = None
        self._closed = False

        self.title(f"{RELEASE_NAME} — Project-Aware Compatibility Intelligence")
        self.geometry("1280x800")
        self.minsize(900, 600)
        apply_theme(self)
        self._build()
        self._restore_ui_state()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._poll_id = self.after(100, self._poll)

    def _build(self) -> None:
        self._build_menu()
        header = ttk.Frame(self, padding=(18, 14))
        header.pack(fill="x")
        title = ttk.Frame(header)
        title.pack(side="left")
        ttk.Label(title, text=PRODUCT_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title,
            text="Project-Aware Compatibility Intelligence · Release Candidate",
            style="Subtitle.TLabel",
        ).pack(anchor="w")
        self.details_button = ttk.Button(
            header,
            text="Technical details…",
            command=self._show_last_error,
            state="disabled",
        )
        self.details_button.pack(side="right", padx=(10, 0))
        self.activity = ttk.Label(header, text="Ready — read-only scanning", style="Muted.TLabel")
        self.activity.pack(side="right", anchor="e")

        actions = ttk.Frame(self, padding=(18, 0, 18, 12))
        actions.pack(fill="x")
        button_specs = (
            ("PROJECT PREFLIGHT", self._project_preflight, "Accent.TButton", "Inspect a project without executing its scripts."),
            ("QUICK SCAN", lambda: self._scan(False), "TButton", "Run the bounded quick Machine DNA scan."),
            ("DEEP SCAN", lambda: self._scan(True), "TButton", "Run the deeper read-only Machine DNA scan."),
            ("INSPECT FILE", self._inspect_file, "TButton", "Statically inspect a file without executing it."),
            ("COMPARE", self._compare, "TButton", "Compare inspected software with the current machine."),
            ("EXPORT", self._export, "TButton", "Save a redacted JSON, text, or agent report."),
            ("AGENT REPORT", self._show_codex, "TButton", "View the redacted structured report intended for an assistant."),
        )
        for text, command, style, tip in button_specs:
            button = ttk.Button(actions, text=text, command=command, style=style)
            button.pack(side="left", padx=(0, 7))
            self._action_buttons.append(button)
            self._tooltips.append(ToolTip(button, tip))
        directory_button = ttk.Button(actions, text="Inspect directory…", command=self._inspect_directory)
        directory_button.pack(side="right")
        self._action_buttons.append(directory_button)
        self._tooltips.append(ToolTip(directory_button, "Statically inspect a directory without running its contents."))
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self._cancel_operation, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 7))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=18)
        self.tabs = ttk.Notebook(self, takefocus=True)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(10, 14))
        self._dashboard_tab()
        self._capability_tab()
        self._software_tab()
        self._compatibility_tab()
        self._evidence_tab()
        self._project_tab()

    def _build_menu(self) -> None:
        menu = tk.Menu(self, tearoff=False)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open Project…", command=self._project_preflight, accelerator="Ctrl+O")
        file_menu.add_command(label="Inspect File…", command=self._inspect_file)
        file_menu.add_command(label="Inspect Directory…", command=self._inspect_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Export Report…", command=self._export, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._close, accelerator="Alt+F4")
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Copy", command=lambda: self._focused_event("<Control-c>"), accelerator="Ctrl+C")
        edit_menu.add_command(label="Select All", command=lambda: self._focused_event("<Control-a>"), accelerator="Ctrl+A")
        edit_menu.add_command(label="Find…", command=lambda: self._focused_event("<Control-f>"), accelerator="Ctrl+F")
        menu.add_cascade(label="Edit", menu=edit_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About ARX", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)
        self.bind("<Control-o>", lambda _event: self._project_preflight())
        self.bind("<Control-Shift-S>", lambda _event: self._export())

    def _text_panel(self, parent: tk.Misc, *, content_type: str = "text", wrap: str = "word") -> ReadOnlyText:
        return text_panel(
            parent,
            content_type=content_type,
            wrap=wrap,
            save_command=self._save_visible_report,
            status_command=self._set_status,
        )

    def _result_tree(self, parent: tk.Misc, columns, widths, name: str) -> ttk.Treeview:
        view = tree(parent, columns, widths, status_command=self._set_status)
        view.bind("<Button-3>", lambda event, item=view: self._show_tree_context(item, event))
        view.bind("<Double-1>", lambda event, item=view: self._tree_activate(item, event))
        view.bind("<Return>", lambda event, item=view: self._tree_activate(item, event))
        view._arx_surface_name = name  # type: ignore[attr-defined]
        return view

    def _dashboard_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Machine DNA")
        summary = ttk.Frame(tab)
        summary.pack(fill="x", pady=(0, 10))
        self.os_label = ttk.Label(summary, text="Run a machine scan to begin", font=("Segoe UI Semibold", 13))
        self.os_label.pack(side="left")
        self.machine_badge = StatusBadge(summary, "unknown")
        self.machine_badge.pack(side="right")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        self.machine_tree = self._result_tree(
            holder,
            ("component", "status", "version", "path", "health", "evidence"),
            {"component": 190, "status": 90, "version": 120, "path": 300, "health": 100, "evidence": 260},
            "Machine DNA finding",
        )
        self.machine_tree.bind("<<TreeviewSelect>>", self._machine_selected)

    def _capability_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Capabilities")
        split = ttk.Panedwindow(tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=3)
        split.add(right, weight=2)
        self.cap_tree = self._result_tree(
            left,
            ("capability", "status", "reason"),
            {"capability": 230, "status": 100, "reason": 430},
            "Capability finding",
        )
        self.cap_tree.bind("<<TreeviewSelect>>", self._capability_selected)
        self.cap_detail = self._text_panel(right)
        self.cap_detail.pack(fill="both", expand=True, padx=(12, 0))

    def _software_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Software DNA")
        self.software_heading = ttk.Label(tab, text="Choose a supported file or directory", font=("Segoe UI Semibold", 13))
        self.software_heading.pack(anchor="w", pady=(0, 8))
        split = ttk.Panedwindow(tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=2)
        split.add(right, weight=3)
        self.software_detail = self._text_panel(left)
        self.software_detail.pack(fill="both", expand=True)
        self.import_tree = self._result_tree(
            right,
            ("kind", "value", "classification"),
            {"kind": 170, "value": 430, "classification": 110},
            "Software evidence",
        )

    def _compatibility_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Compatibility")
        banner = ttk.Frame(tab)
        banner.pack(fill="x", pady=(0, 10))
        ttk.Label(banner, text="OVERALL COMPATIBILITY", font=("Segoe UI Semibold", 13)).pack(side="left")
        self.compat_badge = StatusBadge(banner, "unknown")
        self.compat_badge.pack(side="right")
        split = ttk.Panedwindow(tab, orient="vertical")
        split.pack(fill="both", expand=True)
        upper, lower = ttk.Frame(split), ttk.Frame(split)
        split.add(upper, weight=3)
        split.add(lower, weight=2)
        self.check_tree = self._result_tree(
            upper,
            ("check", "status", "required", "observed", "reason"),
            {"check": 180, "status": 90, "required": 150, "observed": 150, "reason": 430},
            "Compatibility finding",
        )
        self.compat_detail = self._text_panel(lower)
        self.compat_detail.pack(fill="both", expand=True, pady=(10, 0))

    def _evidence_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Evidence Inspector")
        split = ttk.Panedwindow(tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=3)
        split.add(right, weight=2)
        self.evidence_tree = self._result_tree(
            left,
            ("classification", "source", "value", "confidence"),
            {"classification": 120, "source": 300, "value": 330, "confidence": 100},
            "ARX evidence",
        )
        self.evidence_tree.bind("<<TreeviewSelect>>", self._evidence_selected)
        self.evidence_detail = self._text_panel(right)
        self.evidence_detail.pack(fill="both", expand=True, padx=(12, 0))
        self._evidence_items: list[dict] = []

    def _project_tab(self) -> None:
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Project Readiness")
        banner = ttk.Frame(tab)
        banner.pack(fill="x", pady=(0, 10))
        self.project_heading = ttk.Label(banner, text="Choose a project directory", font=("Segoe UI Semibold", 13))
        self.project_heading.pack(side="left")
        self.project_badge = StatusBadge(banner, "unknown")
        self.project_badge.pack(side="right")
        split = ttk.Panedwindow(tab, orient="vertical")
        split.pack(fill="both", expand=True)
        upper, lower = ttk.Frame(split), ttk.Frame(split)
        split.add(upper, weight=3)
        split.add(lower, weight=2)
        self.project_tree = self._result_tree(
            upper,
            ("capability", "relevance", "satisfaction", "resolved", "preferred", "reason"),
            {"capability": 190, "relevance": 110, "satisfaction": 120, "resolved": 130, "preferred": 130, "reason": 380},
            "Project requirement",
        )
        self.project_detail = self._text_panel(lower)
        self.project_detail.pack(fill="both", expand=True, pady=(10, 0))

    def _run(
        self,
        label: str,
        work: Callable[[], object],
        complete: Callable[[object], object],
        *,
        completed_status: str = "Completed",
    ) -> None:
        if self._started is not None:
            self._set_status("An operation is already running.")
            return
        token = threading.Event()
        self._operation_cancel = token
        self._started = time.monotonic()
        self._set_busy(True)
        self._set_status(f"{label.capitalize()}…")
        self.progress.start(12)

        def worker() -> None:
            try:
                result = work()
                self._events.put(("ok", complete, result, token, completed_status))
            except Exception as exc:  # Tk presents a human summary and keeps the trace copyable.
                self._events.put(("error", label, (exc, traceback.format_exc()), token, "Failed"))

        threading.Thread(target=worker, daemon=True, name="arx-desktop-worker").start()

    def _poll(self) -> None:
        if self._started is not None:
            elapsed = time.monotonic() - self._started
            current = self.activity.cget("text").split(" — ", 1)[0]
            self.activity.configure(text=f"{current} — {elapsed:.1f}s elapsed")
        try:
            while True:
                kind, callback, payload, token, completed_status = self._events.get_nowait()
                if token is not self._operation_cancel:
                    continue
                self.progress.stop()
                self._started = None
                self._operation_cancel = None
                self._set_busy(False)
                if token.is_set():
                    self._set_status("Cancelled")
                elif kind == "ok":
                    callback(payload)
                    self._set_status(completed_status)
                else:
                    self._show_error(callback, *payload)
        except queue.Empty:
            pass
        if not self._closed:
            self._poll_id = self.after(100, self._poll)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def _cancel_operation(self) -> None:
        if self._operation_cancel is not None:
            self._operation_cancel.set()
            self.cancel_button.configure(state="disabled")
            self._set_status("Cancelling…")

    def _set_status(self, message: str) -> None:
        self.activity.configure(text=str(message))

    def _scan(self, deep: bool) -> None:
        label = "Deep machine scan" if deep else "Quick machine scan"
        self._run(label, lambda: self.controller.scan(deep), lambda _result: self._render_machine(), completed_status="Scan complete")

    def _dialog_directory(self) -> str:
        return self._last_directory or str(Path.cwd())

    def _remember_target(self, value: str, *, directory: bool = False) -> None:
        path = Path(value)
        self._last_directory = str(path if directory else path.parent)

    def _project_preflight(self) -> None:
        target = filedialog.askdirectory(
            parent=self,
            title="Choose a project for read-only preflight",
            initialdir=self._dialog_directory(),
            mustexist=True,
        )
        if target:
            self._remember_target(target, directory=True)
            self._run(
                "Project preflight",
                lambda: self.controller.preflight(target),
                lambda _result: self._render_project(),
                completed_status="Project preflight complete",
            )

    def _inspect_file(self) -> None:
        target = filedialog.askopenfilename(
            parent=self,
            title="Inspect software without running it",
            initialdir=self._dialog_directory(),
            filetypes=(
                ("Supported software", "*.exe *.dll *.msi *.zip *.jar *.apk *.ps1 *.bat *.cmd *.py *.js"),
                ("Executables", "*.exe"),
                ("All files", "*.*"),
            ),
        )
        if target:
            self._remember_target(target)
            self._start_inspect(target)

    def _inspect_directory(self) -> None:
        target = filedialog.askdirectory(
            parent=self,
            title="Inspect an application directory",
            initialdir=self._dialog_directory(),
            mustexist=True,
        )
        if target:
            self._remember_target(target, directory=True)
            self._start_inspect(target)

    def _start_inspect(self, target: str) -> None:
        self._selected_target = target
        self._run(
            "Static software inspection",
            lambda: self.controller.inspect(target),
            lambda _result: self._render_software(),
            completed_status="Inspection complete",
        )

    def _compare(self) -> None:
        if self.controller.software is None:
            target = filedialog.askopenfilename(
                parent=self,
                title="Choose software to compare",
                initialdir=self._dialog_directory(),
                filetypes=(
                    ("Supported software", "*.exe *.dll *.msi *.zip *.jar *.apk"),
                    ("All files", "*.*"),
                ),
            )
            if not target:
                return
            self._remember_target(target)
        else:
            target = None
        self._run(
            "Machine/software comparison",
            lambda: self.controller.compare(target),
            lambda _result: self._render_all(),
            completed_status="Comparison complete",
        )

    def _show_codex(self) -> None:
        self._run(
            "Preparing redacted agent report",
            self.controller.codex,
            lambda report: self._show_report_window(
                "Agent Report (redacted JSON)", json.dumps(report, indent=2, ensure_ascii=False), content_type="json"
            ),
            completed_status="Agent report ready",
        )

    def _export(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Export redacted ARX report",
            initialdir=self._dialog_directory(),
            defaultextension=".json",
            filetypes=(
                ("ARX JSON", "*.json"),
                ("Human-readable text", "*.txt"),
                ("Agent JSON", "*.codex.json"),
                ("All files", "*.*"),
            ),
        )
        if not selected:
            return
        self._remember_target(selected)
        kind = "codex" if selected.lower().endswith(".codex.json") else "text" if selected.lower().endswith(".txt") else "json"
        self._run(
            "Report export",
            lambda: self.controller.export(selected, kind),
            self._export_complete,
            completed_status="Export complete",
        )

    def _export_complete(self, path: object) -> None:
        messagebox.showinfo("ARX — Export complete", f"Redacted report exported to:\n{path}", parent=self)

    def _save_visible_report(self, content_type: str, content: str) -> None:
        is_json = content_type == "json"
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Save current report",
            initialdir=self._dialog_directory(),
            defaultextension=".json" if is_json else ".txt",
            filetypes=(("JSON", "*.json"), ("Text", "*.txt"), ("All files", "*.*")) if is_json else (("Text", "*.txt"), ("All files", "*.*")),
        )
        if not selected:
            return
        try:
            Path(selected).write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._show_error("saving the report", exc, traceback.format_exc())
            return
        self._remember_target(selected)
        self._set_status("Export complete")

    def _render_all(self) -> None:
        self._render_machine()
        self._render_software()
        self._render_compatibility()
        self.tabs.select(3)

    @staticmethod
    def _clear(view: ttk.Treeview) -> None:
        for item in view.get_children():
            view.delete(item)

    def _render_machine(self) -> None:
        machine = self.controller.machine or {}
        osinfo = machine.get("os", {})
        self.os_label.configure(
            text=(
                f"{osinfo.get('edition') or osinfo.get('system', 'Windows')}  •  "
                f"{osinfo.get('architecture', 'unknown')}  •  build {osinfo.get('build', 'unknown')}"
            )
        )
        self.machine_badge.set("ready")
        self._clear(self.machine_tree)
        tools = machine.get("tools", {})
        tool_names = (
            ("Git", "git"),
            ("GitHub CLI", "github_cli"),
            ("Java / JDK", "javac"),
            ("Node.js", "node"),
            ("npm", "npm"),
            (".NET", "dotnet"),
            ("Visual Studio / MSBuild", "msbuild"),
            ("CMake", "cmake"),
            ("Ninja", "ninja"),
            ("Android SDK / ADB", "adb"),
            ("Flutter", "flutter"),
            ("CUDA", "cuda"),
            ("Docker", "docker"),
            ("WSL", "wsl"),
        )
        for label, key in tool_names:
            record = tools.get(key)
            status = "ready" if record and record.detected else "missing"
            evidence = record.evidence[0].method if record and record.evidence else "PATH / known locations"
            self.machine_tree.insert(
                "",
                "end",
                iid=f"tool:{key}",
                values=(
                    label,
                    status.upper(),
                    record.version if record else "",
                    record.path if record else "",
                    "Healthy" if record and record.detected else "Unavailable",
                    evidence,
                ),
                tags=(status,),
            )
        for index, item in enumerate(machine.get("python_installations", [])):
            health = item.get("health_status") or (
                "healthy" if item.get("healthy") else "unhealthy" if item.get("healthy") is False else "unknown"
            )
            status = "ready" if health == "healthy" else "blocked" if health == "unhealthy" else "unknown"
            self.machine_tree.insert(
                "",
                "end",
                iid=f"python:{index}",
                values=(
                    f"Python {item.get('version') or 'unknown'}",
                    status.upper(),
                    item.get("version"),
                    item.get("path"),
                    str(health).upper(),
                    item.get("health_reason") or item.get("health_probe"),
                ),
                tags=(status,),
            )
        self._render_capabilities()
        self._render_evidence()

    def _render_capabilities(self) -> None:
        self._clear(self.cap_tree)
        for name, capability in self.controller.capabilities.items():
            self.cap_tree.insert(
                "",
                "end",
                iid=name,
                values=(
                    name.replace(".", " ").replace("_", " ").title(),
                    capability.status.value.upper(),
                    capability.reason,
                ),
                tags=(capability.status.value,),
            )

    def _render_software(self) -> None:
        software = self.controller.software or {}
        self.software_heading.configure(text=software.get("filename", "Software DNA"))
        pe = software.get("pe", {})
        signature = software.get("signature", {})
        application = software.get("application", {})
        detail = (
            f"FILE\n{software.get('absolute_path', '')}\n\n"
            f"Type: {software.get('detected_file_type', 'unknown')}\n"
            f"Size: {software.get('size', 'n/a')} bytes\n"
            f"SHA-256: {software.get('sha256', 'n/a')}\n\n"
            "BINARY-LEVEL EVIDENCE\n"
            f"Architecture: {pe.get('architecture', 'unknown')}\n"
            f"PE CLR header: {'Present' if pe.get('is_dotnet') else 'Not present'}\n"
            f"Subsystem: {pe.get('subsystem', 'unknown')}\n"
            f"Execution level: {pe.get('requested_execution_level') or 'not detected'}\n"
            f"Signature: {signature.get('Status', signature.get('status', 'not inspected'))}\n"
            f"Publisher: {signature.get('SignerSubject') or 'not detected'}\n\n"
            "APPLICATION-LEVEL RUNTIME EVIDENCE\n"
            f".NET application: {application.get('dotnet', 'not detected')}\n"
            f"Evidence: {', '.join(application.get('evidence', [])) or 'none'}"
        )
        if software.get("inspection_error"):
            detail += f"\n\nWARNING\n{software['inspection_error']}"
        set_text(self.software_detail, detail)
        self._clear(self.import_tree)
        for item in pe.get("imports", []):
            self.import_tree.insert("", "end", values=("Imported library", item, "OBSERVED"))
        for item in software.get("runtime_indicators", []):
            self.import_tree.insert(
                "", "end", values=("Runtime", item.get("runtime"), str(item.get("status", "inferred")).upper())
            )
        for item in software.get("requirements", []):
            self.import_tree.insert(
                "",
                "end",
                values=(
                    "Requirement",
                    f"{item.get('capability')} {item.get('version', '')}",
                    str(item.get("status", "unknown")).upper(),
                ),
            )
        self._render_evidence()

    def _render_compatibility(self) -> None:
        report = self.controller.compatibility or {}
        self.compat_badge.set(report.get("status", "unknown"))
        self._clear(self.check_tree)
        for check in report.get("checks", []):
            self.check_tree.insert(
                "",
                "end",
                values=(
                    check.get("name"),
                    str(check.get("status", "unknown")).upper(),
                    check.get("required", ""),
                    check.get("observed", ""),
                    check.get("reason", ""),
                ),
                tags=(check.get("status", "unknown"),),
            )
        lines = [
            f"Confidence: {report.get('confidence', 'unknown')}",
            f"Score: {report.get('score', 'unknown')}",
            "",
            "PRIMARY BLOCKERS",
            *(report.get("blockers") or ["None"]),
            "",
            "WARNINGS",
            *(report.get("warnings") or ["None"]),
        ]
        set_text(self.compat_detail, "\n".join(map(str, lines)))

    def _render_project(self) -> None:
        report = getattr(self.controller, "project_preflight", None)
        if report is None:
            return
        view_model = project_readiness_view_model(report)
        project = report.project
        providers = {item.id: item for item in report.providers}
        requirements = {item.id: item for item in [*project.requirements, *project.optional_requirements]}
        self.project_heading.configure(text=f"{project.identity}  •  Python interpreter readiness")
        self.project_badge.set(view_model["decision"].lower())
        self._clear(self.project_tree)
        tags = {
            "satisfied": "ready",
            "unsatisfied": "blocked",
            "partial": "partial",
            "conflict": "blocked",
            "ambiguous": "unknown",
            "unknown": "unknown",
            "optional_unavailable": "not_applicable",
            "not_applicable": "not_applicable",
        }
        primary_requirement = project.primary_python_requirement
        for evaluation in report.evaluations:
            requirement = requirements[evaluation.requirement_id]
            resolved = providers.get(report.provider_roles.resolved_provider_id or "")
            preferred_id = (
                report.provider_roles.preferred_provider_id
                if primary_requirement and evaluation.requirement_id == primary_requirement.id
                else evaluation.preferred_provider_id
            )
            preferred = providers.get(preferred_id or "")
            self.project_tree.insert(
                "",
                "end",
                values=(
                    requirement.capability,
                    evaluation.relevance.value.upper(),
                    evaluation.satisfaction.value.upper(),
                    resolved.version if resolved else "",
                    preferred.version if preferred else "",
                    evaluation.reason,
                ),
                tags=(tags[evaluation.satisfaction.value],),
            )
        issues = [
            *(f"BLOCKER  {item}" for item in view_model["blocker_ids"]),
            *(f"WARNING  {item}" for item in view_model["warning_ids"]),
        ]
        steps = [f"{index}. {step.action}" for index, step in enumerate(report.plan.steps, 1)]
        detail = [
            f"PYTHON INTERPRETER READINESS: {view_model['decision']}",
            f"Satisfaction: {view_model['satisfaction']}",
            f"Current-context satisfaction: {view_model['current_context_satisfaction']}",
            f"Recoverability: {view_model['recoverability']}",
            f"Satisfied: {report.severity.satisfied_count}",
            f"Warnings: {report.severity.warning_count}",
            f"Blockers: {report.severity.blocker_count}",
            "",
            "Scope: Python interpreter/toolchain requirements only; dependency installation and application execution are not verified.",
            "",
            "What is wrong?",
            *(issues or ["Nothing blocking was found."]),
            "",
            "Why?",
            report.severity.reason,
            "",
            "Shortest trusted path to GREEN:",
            *(steps or ["0 actions — current evaluated state is GREEN."]),
        ]
        set_text(self.project_detail, "\n".join(map(str, detail)))
        self._render_evidence()
        self.tabs.select(5)

    def _render_evidence(self) -> None:
        self._clear(self.evidence_tree)
        self._evidence_items = []

        def add(evidence: object, context: str) -> None:
            data = serialize(evidence)
            data["context"] = context
            self._evidence_items.append(data)
            index = len(self._evidence_items) - 1
            self.evidence_tree.insert(
                "",
                "end",
                iid=f"e:{index}",
                values=(
                    str(data.get("kind", "unknown")).upper(),
                    data.get("source", ""),
                    str(data.get("value", ""))[:180],
                    data.get("confidence", ""),
                ),
                tags=(str(data.get("kind", "unknown")).lower(),),
            )

        for item in (self.controller.machine or {}).get("evidence", []):
            add(item, "Machine DNA")
        for record in (self.controller.machine or {}).get("tools", {}).values():
            for item in record.evidence:
                add(item, f"Tool: {record.name}")
        for runtime in (self.controller.machine or {}).get("python_installations", []):
            for item in runtime.get("evidence", []):
                add(item, f"Python: {runtime.get('path')}")
        for item in (self.controller.software or {}).get("evidence", []):
            add(item, "Software DNA")
        project_report = getattr(self.controller, "project_preflight", None)
        if project_report:
            for item in project_report.project.evidence:
                add(item, "Project DNA")
            for provider in project_report.providers:
                for item in provider.evidence:
                    add(item, f"Provider: {provider.id}")
            for item in project_report.resolution.evidence:
                add(item, "Execution resolution")

    def _machine_selected(self, _event: tk.Event | None) -> None:
        selection = self.machine_tree.selection()
        if selection and selection[0].startswith("tool:"):
            key = selection[0].split(":", 1)[1]
            record = (self.controller.machine or {}).get("tools", {}).get(key)
            if record:
                self._select_evidence_source(f"Tool: {record.name}")

    def _capability_selected(self, _event: tk.Event | None) -> None:
        selection = self.cap_tree.selection()
        if not selection:
            return
        capability = self.controller.capabilities.get(selection[0])
        if capability is None:
            return
        dependencies = []
        for dependency in capability.dependencies:
            child = self.controller.capabilities.get(dependency)
            dependencies.append(
                f"{dependency:<28} {child.status.value.upper() if child else 'UNKNOWN'} — "
                f"{child.reason if child else 'No provider'}"
            )
        blockers = [line for line in dependencies if " READY " not in f" {line} "]
        set_text(
            self.cap_detail,
            f"{capability.name}\n{capability.status.value.upper()}\n\nWHY\n{capability.reason}\n\n"
            f"DEPENDENCIES\n{chr(10).join(dependencies) or 'No dependencies'}\n\n"
            f"PRIMARY BLOCKERS\n{chr(10).join(blockers) or 'None'}",
        )

    def _evidence_selected(self, _event: tk.Event | None) -> None:
        selection = self.evidence_tree.selection()
        if selection:
            item = self._evidence_items[int(selection[0].split(":")[1])]
            set_text(
                self.evidence_detail,
                "\n".join(
                    (
                        f"Context: {item.get('context')}",
                        f"Classification: {str(item.get('kind', 'unknown')).upper()}",
                        f"Source: {item.get('source')}",
                        f"Value: {item.get('value')}",
                        f"Detection method: {item.get('method')}",
                        f"Confidence: {item.get('confidence')}",
                        f"Notes: {item.get('note') or 'None'}",
                    )
                ),
            )

    def _select_evidence_source(self, context: str) -> None:
        for index, item in enumerate(self._evidence_items):
            if item.get("context") == context:
                self.tabs.select(4)
                self.evidence_tree.selection_set(f"e:{index}")
                self.evidence_tree.see(f"e:{index}")
                self._evidence_selected(None)
                break

    def _tree_row(self, view: ttk.Treeview, event: tk.Event | None = None) -> tuple[str, tuple, tuple[str, ...]] | None:
        item_id = view.identify_row(event.y) if event is not None and hasattr(event, "y") else ""
        if item_id:
            if item_id not in view.selection():
                view.selection_set(item_id)
            view.focus(item_id)
        else:
            selection = view.selection()
            item_id = selection[0] if selection else ""
        if not item_id:
            return None
        return item_id, tuple(view.item(item_id, "values")), tuple(str(item) for item in view.cget("columns"))

    def _tree_menu_actions(self, view: ttk.Treeview, event: tk.Event | None = None) -> list[MenuAction]:
        row = self._tree_row(view, event)
        if row is None:
            return []
        item_id, values, columns = row
        details = format_result_row(columns, values)
        column_value = ""
        if event is not None and hasattr(event, "x"):
            identifier = view.identify_column(event.x)
            if identifier.startswith("#") and identifier[1:].isdigit():
                index = int(identifier[1:]) - 1
                if 0 <= index < len(values):
                    column_value = str(values[index] or "")
        path_value = find_path_value(columns, values)
        capabilities = path_capabilities(path_value)
        advisory_context = self._context_for_row(view, item_id, columns, values)
        actions = [
            MenuAction("Copy Row", lambda: self._copy(details)),
            MenuAction("Copy Details", lambda: self._copy(details)),
        ]
        if column_value:
            actions.append(MenuAction("Copy Value", lambda value=column_value: self._copy(value)))
        if path_value:
            actions.append(MenuAction("Copy Path", lambda value=path_value: self._copy(value)))
        if capabilities and capabilities.exists:
            actions.append(MenuAction(None))
            actions.append(MenuAction("Open", lambda value=path_value: self._open_user_path(value, "open")))
            if capabilities.is_file:
                actions.append(
                    MenuAction("Open Containing Folder", lambda value=path_value: self._open_user_path(value, "containing_folder"))
                )
            actions.append(MenuAction("Reveal in File Explorer", lambda value=path_value: self._open_user_path(value, "reveal")))
            actions.append(MenuAction("Inspect with ARX", lambda value=path_value: self._start_inspect(str(value))))
        if self._advisory_providers:
            actions.append(MenuAction(None))
            if "ChatGPT / OpenAI" in self._advisory_providers:
                actions.append(
                    MenuAction(
                        "Ask ChatGPT About This…",
                        lambda context=advisory_context: self._open_advisory(context, "ChatGPT / OpenAI"),
                    )
                )
            if "Codex CLI" in self._advisory_providers:
                actions.append(
                    MenuAction(
                        "Ask Codex About This…",
                        lambda context=advisory_context: self._open_advisory(context, "Codex CLI"),
                    )
                )
            actions.append(
                MenuAction(
                    "Suggest Safe Fix with AI…",
                    lambda context=advisory_context: self._open_advisory(context, self._default_provider(), "Suggest Safe Fix"),
                )
            )
            if advisory_context.project:
                actions.append(
                    MenuAction(
                        "Compare With Project Requirements…",
                        lambda context=advisory_context: self._open_advisory(
                            context, self._default_provider(), "Compatibility Interpretation"
                        ),
                    )
                )
        actions.extend(
            (
                MenuAction(None),
                MenuAction("Search Web About This…", lambda context=advisory_context: self._search_context(context, "web", "web")),
                MenuAction(
                    "Search Google About This…", lambda context=advisory_context: self._search_context(context, "web", "google")
                ),
            )
        )
        if any(key.casefold() in {"error", "reason", "evidence", "value"} for key in columns):
            actions.append(
                MenuAction(
                    "Search Exact Error Message…",
                    lambda context=advisory_context: self._search_context(context, "exact_error", "web"),
                )
            )
        actions.append(
            MenuAction(
                "Search Official Documentation…",
                lambda context=advisory_context: self._search_context(context, "official", "web"),
            )
        )
        actions.append(MenuAction(None))
        if advisory_context.evidence:
            actions.append(MenuAction("View Evidence", lambda context=advisory_context: self._view_context_evidence(context)))
        actions.append(MenuAction("View Raw Data", lambda context=advisory_context: self._view_advisory_context(context)))
        actions.append(MenuAction("View Details", lambda: self._show_report_window("Result details", details)))
        return actions

    def _show_tree_context(self, view: ttk.Treeview, event: tk.Event) -> str:
        view.focus_set()
        show_context_menu(view, event, self._tree_menu_actions(view, event))
        return "break"

    def _tree_activate(self, view: ttk.Treeview, event: tk.Event | None = None) -> str:
        row = self._tree_row(view, event)
        if row is None:
            return "break"
        _item_id, values, columns = row
        path_value = find_path_value(columns, values)
        capabilities = path_capabilities(path_value)
        if capabilities and capabilities.exists:
            action = "open" if capabilities.is_directory else "reveal"
            self._open_user_path(path_value, action)
        else:
            self._show_report_window("Result details", format_result_row(columns, values))
        return "break"

    def _open_user_path(self, value: str | None, action: str) -> None:
        try:
            open_path(value or "", action)
            self._set_status("Location opened")
        except (OSError, ValueError) as exc:
            self._show_error("opening this path", exc, traceback.format_exc())

    def _copy(self, value: object) -> None:
        copy_to_clipboard(self, value)
        self._set_status("Copy complete")

    def _project_advisory_context(self) -> tuple[dict[str, object], list[Path]]:
        report = getattr(self.controller, "project_preflight", None)
        if report is None:
            return {}, []
        view = project_readiness_view_model(report)
        primary = report.project.primary_python_requirement
        context: dict[str, object] = {
            "identity": report.project.identity,
            "project_root": str(report.project.root),
            "decision": view["decision"],
            "requirement": primary.constraint if primary else None,
            "satisfaction": view["satisfaction"],
            "current_context_satisfaction": view["current_context_satisfaction"],
            "recoverability": view["recoverability"],
            "resolved_version": (view["resolved"] or {}).get("version"),
            "resolved_path": view["resolved_path"],
            "preferred_version": (view["preferred"] or {}).get("version"),
            "finding_ids": [*view["blocker_ids"], *view["warning_ids"]],
        }
        return context, [report.project.root]

    def _row_evidence(self, view: ttk.Treeview, item_id: str) -> list[dict]:
        if view is self.evidence_tree and item_id.startswith("e:"):
            index = int(item_id.split(":", 1)[1])
            return [self._evidence_items[index]] if index < len(self._evidence_items) else []
        if view is self.machine_tree and item_id.startswith("tool:"):
            key = item_id.split(":", 1)[1]
            record = (self.controller.machine or {}).get("tools", {}).get(key)
            return [serialize(item) for item in record.evidence] if record else []
        if view is self.machine_tree and item_id.startswith("python:"):
            index = int(item_id.split(":", 1)[1])
            installations = (self.controller.machine or {}).get("python_installations", [])
            if index < len(installations):
                return [serialize(item) for item in installations[index].get("evidence", [])]
            return []
        if view is self.cap_tree:
            capability = self.controller.capabilities.get(item_id)
            return [serialize(item) for item in capability.evidence] if capability else []
        if view is self.import_tree:
            return [serialize(item) for item in (self.controller.software or {}).get("evidence", [])]
        report = getattr(self.controller, "project_preflight", None)
        if view is self.project_tree and report is not None:
            return [
                *(serialize(item) for item in report.project.evidence),
                *(serialize(item) for item in report.resolution.evidence),
            ]
        return []

    def _context_for_row(
        self,
        view: ttk.Treeview,
        item_id: str,
        columns: tuple[str, ...],
        values: tuple,
    ) -> AdvisoryContext:
        project, private_roots = self._project_advisory_context()
        return build_advisory_context(
            getattr(view, "_arx_surface_name", "ARX finding"),
            columns,
            values,
            project=project,
            evidence=self._row_evidence(view, item_id),
            private_roots=private_roots,
        )

    def _default_provider(self) -> str:
        if "ChatGPT / OpenAI" in self._advisory_providers:
            return "ChatGPT / OpenAI"
        return next(iter(self._advisory_providers), "")

    def _open_advisory(self, context: AdvisoryContext, provider: str, mode: str = "Explain Technically") -> None:
        window = AdvisoryWindow(
            self,
            context,
            self._advisory_providers,
            initial_provider=provider,
            initial_mode=mode,
            consent_command=self._confirm_advisory_consent,
            save_command=self._save_visible_report,
            view_context_command=self._view_advisory_context,
            change_context_command=lambda: self._set_status("Right-click another finding to change AI context."),
            status_command=self._set_status,
        )
        self._advisory_windows.append(window)

    def _confirm_advisory_consent(self, provider: str, _context: AdvisoryContext) -> bool:
        if provider in self._advisory_consent:
            return True
        accepted = messagebox.askyesno(
            "ARX — External advisory consent",
            (
                f"You chose {provider}. ARX will send only the selected, bounded, redacted diagnostic context and your "
                "question to that provider. It will not send a complete machine scan, credentials, or unrelated project files.\n\n"
                "The response is unverified advice and cannot change ARX evidence or modify this computer. You can preview "
                "the exact diagnostic prompt before sending.\n\nContinue?"
            ),
            parent=self,
        )
        if accepted:
            self._advisory_consent.add(provider)
        return bool(accepted)

    def _view_advisory_context(self, context: AdvisoryContext) -> None:
        self._show_report_window("Redacted ARX context", context.preview(), content_type="json")

    def _view_context_evidence(self, context: AdvisoryContext) -> None:
        self._show_report_window(
            "Relevant ARX evidence",
            json.dumps(list(context.evidence), indent=2, ensure_ascii=False, sort_keys=True),
            content_type="json",
        )

    def _search_context(self, context: AdvisoryContext, kind: str, engine: str) -> None:
        try:
            query = build_search_query(context, kind)
            url = build_search_url(query, engine)
            open_search(url)
            self._set_status("Search opened in the default browser")
        except (OSError, ValueError) as exc:
            self._show_error("opening a web search", exc, traceback.format_exc())

    def _focused_event(self, sequence: str) -> None:
        focused = self.focus_get()
        if focused is None:
            self._set_status("Choose a text or result surface first.")
            return
        focused.event_generate(sequence)

    def _show_report_window(self, title: str, content: str, *, content_type: str = "text") -> tk.Toplevel:
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("900x650")
        window.minsize(560, 360)
        window.configure(bg=COLORS["bg"])
        window.transient(self)
        window.bind("<Escape>", lambda _event: window.destroy())
        view = self._text_panel(window, content_type=content_type, wrap="none" if content_type == "json" else "word")
        view.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        set_text(view, content)
        buttons = ttk.Frame(window, padding=(12, 6, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Copy All", command=view.copy_all).pack(side="left")
        ttk.Button(buttons, text="Save As…", command=view.save).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        return window

    def _show_error(self, operation: str, exc: Exception, details: str) -> None:
        self.progress.stop()
        self._started = None
        self._operation_cancel = None
        self._set_busy(False)
        summary = f"ARX could not complete {operation}."
        self._last_error_summary = summary
        self._last_error_details = f"{summary}\n\n{exc}\n\nTECHNICAL DETAILS\n{details}"
        self.details_button.configure(state="normal")
        self._set_status("Failed")
        messagebox.showerror(
            "ARX — Operation failed",
            f"{summary}\n\n{exc}\n\nNo software was installed or executed. Use Technical details to copy the diagnostic context.",
            parent=self,
        )

    def _show_last_error(self) -> None:
        if self._last_error_details:
            ErrorDetailsDialog(
                self,
                "ARX — Technical details",
                self._last_error_summary or "ARX operation failed.",
                self._last_error_details,
            )

    def _show_about(self) -> None:
        self._show_report_window(
            "About ARX",
            (
                f"{PRODUCT_NAME}\n"
                f"{RELEASE_NAME}\n"
                f"Package version: {__version__}\n\n"
                "Project-Aware Compatibility Intelligence for Windows.\n\n"
                "ARX performs deterministic, read-only observation and explainable compatibility analysis. "
                "It is not a malware scanner and does not certify software as safe.\n\n"
                "License: MIT\n"
                "Copyright (c) 2026 chatgptopenaiagi\n\n"
                "Project: https://github.com/chatgptopenaiagi/ARX"
            ),
        )

    def _restore_ui_state(self) -> None:
        state = self._state_store.load()
        if state.get("geometry"):
            self.geometry(str(state["geometry"]))
        selected_tab = state.get("selected_tab")
        if isinstance(selected_tab, int) and selected_tab < len(self.tabs.tabs()):
            self.tabs.select(selected_tab)

    def _close(self) -> None:
        try:
            selected_tab = self.tabs.index(self.tabs.select())
            self._state_store.save({"geometry": self.geometry(), "selected_tab": selected_tab})
        except (OSError, tk.TclError):
            pass
        self.destroy()

    def destroy(self) -> None:
        """Cancel root-owned work before destroying the Tcl interpreter."""

        if self._closed:
            return
        self._closed = True
        if self._operation_cancel is not None:
            self._operation_cancel.set()
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        for window in tuple(self._advisory_windows):
            try:
                window._close()
            except tk.TclError:
                pass
        super().destroy()


def run() -> None:
    enable_windows_dpi_awareness()
    app = ARXDesktopApp()
    app.mainloop()


def ui_smoke_test(target, output, timeout=180):
    """Exercise packaged Tk view/controller paths without human interaction."""
    app = ARXDesktopApp()
    app.withdraw()
    started = time.monotonic()

    def wait():
        while app._started is not None:
            app.update()
            if time.monotonic() - started > timeout:
                raise TimeoutError("ARX desktop UI smoke test timed out")
            time.sleep(0.02)
        app.update()

    app._scan(False)
    wait()
    quick_rows = len(app.machine_tree.get_children())
    app._scan(True)
    wait()
    deep_rows = len(app.machine_tree.get_children())
    app._start_inspect(target)
    wait()
    software_title = app.software_heading.cget("text")
    app._compare()
    wait()
    checks = len(app.check_tree.get_children())
    compatibility = app.compat_badge.cget("text")
    app.controller.export(output, "json")
    result = {
        "quick_machine_rows": quick_rows,
        "deep_machine_rows": deep_rows,
        "software_title": software_title,
        "compatibility": compatibility,
        "compatibility_checks": checks,
        "evidence_rows": len(app.evidence_tree.get_children()),
        "export_exists": Path(output).is_file(),
    }
    app.destroy()
    return result


def project_ui_smoke_test(target, output, timeout=180):
    """Exercise the packaged Project Preflight UI and schema 0.2 export."""
    app = ARXDesktopApp()
    app.withdraw()
    started = time.monotonic()

    def wait():
        while app._started is not None:
            app.update()
            if time.monotonic() - started > timeout:
                raise TimeoutError("ARX project UI smoke test timed out")
            time.sleep(0.02)
        app.update()

    try:
        app._run("Project preflight", lambda: app.controller.preflight(target), lambda _result: app._render_project())
        wait()
        report = app.controller.project_preflight
        view_model = project_readiness_view_model(report)
        providers = {item.id: item for item in report.providers}
        evaluation = report.evaluation
        resolved = providers.get(report.provider_roles.resolved_provider_id or "")
        preferred = providers.get(report.provider_roles.preferred_provider_id or "")
        compatible = [providers[item].version for item in report.provider_roles.compatible_provider_ids]
        app.controller.export(output, "codex")
        contract = json.loads(Path(output).read_text(encoding="utf-8"))
        project_tab_selected = app.tabs.tab(app.tabs.select(), "text") == "Project Readiness"
        evidence_items = app.evidence_tree.get_children()
        if evidence_items:
            app.evidence_tree.selection_set(evidence_items[0])
            app._evidence_selected(None)
        evidence_detail = app.evidence_detail.get("1.0", "end")
        app.tabs.select(4)
        return {
            "app_version": __version__,
            "window_title": app.title(),
            "tabs": [app.tabs.tab(item, "text") for item in app.tabs.tabs()],
            "project": report.project.identity,
            "requirement": report.project.primary_python_requirement.constraint if report.project.primary_python_requirement else None,
            "decision": app.project_badge.cget("text"),
            "relevance": evaluation.relevance.value.upper(),
            "satisfaction": evaluation.satisfaction.value.upper(),
            "current_context_satisfaction": report.severity.current_context_satisfaction.value.upper(),
            "recoverability": report.severity.recoverability.value.upper(),
            "resolved_version": resolved.version if resolved else None,
            "compatible_versions": compatible,
            "preferred_version": preferred.version if preferred else None,
            "finding_ids": [*report.severity.blocker_ids, *report.severity.warning_ids],
            "plan_step_ids": [item.id for item in report.plan.steps],
            "project_rows": len(app.project_tree.get_children()),
            "evidence_rows": len(evidence_items),
            "evidence_detail_populated": "Classification:" in evidence_detail and "Source:" in evidence_detail,
            "evidence_tab_accessible": app.tabs.tab(app.tabs.select(), "text") == "Evidence Inspector",
            "project_tab_selected": project_tab_selected,
            "ai_schema_version": contract.get("schema_version"),
            "ai_decision": contract.get("decision"),
            "view_model": view_model,
            "export_exists": Path(output).is_file(),
        }
    finally:
        app.destroy()
