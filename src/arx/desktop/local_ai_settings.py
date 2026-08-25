"""Explicit local-AI configuration, discovery, and process-control surface."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from arx.local_ai import (
    ApprovalRequired,
    AssistanceProfile,
    BackendKind,
    BackendProfile,
    LocalAIConfigurationError,
    LocalAIManager,
    LocalAIProvider,
    LocalAIState,
    LocalEndpoint,
)


class LocalAISettingsWindow(tk.Toplevel):
    """Mouse-accessible local provider setup; opening it has no network side effect."""

    def __init__(
        self,
        parent: tk.Misc,
        manager: LocalAIManager,
        provider: LocalAIProvider,
        *,
        open_chat_command: Callable[[], object],
    ):
        super().__init__(parent)
        self.manager = manager
        self.provider = provider
        self.open_chat_command = open_chat_command
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel: threading.Event | None = None
        self._poll_id: str | None = None
        self._running = False
        self._closed = False

        self.title("Settings — Intelligence Providers — Local AI")
        self.geometry("820x700")
        self.minsize(680, 560)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self._build()
        self._load_profile()
        self.refresh_status()
        self._poll_id = self.after(100, self._poll)

    def _build(self) -> None:
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Local AI Bridge", style="Title.TLabel").pack(fill="x")
        ttk.Label(
            body,
            text=(
                "Opening this view does not probe, start, or contact a model. Local output remains "
                "AI ADVISORY — NON-AUTHORITATIVE."
            ),
            style="Muted.TLabel",
            wraplength=760,
        ).pack(fill="x", pady=(2, 10))

        form = ttk.LabelFrame(body, text="Approved localhost profile", padding=10)
        form.pack(fill="x")
        self.profile_name = tk.StringVar()
        self.backend = tk.StringVar()
        self.endpoint = tk.StringVar()
        self.model = tk.StringVar()
        self.executable = tk.StringVar()
        self.model_path = tk.StringVar()
        self.assistance = tk.StringVar()

        fields = (
            ("Profile name", self.profile_name),
            ("Loopback API root", self.endpoint),
            ("Model identity (optional)", self.model),
            ("Backend executable", self.executable),
            ("Model file", self.model_path),
        )
        ttk.Label(form, text="Backend type").grid(row=0, column=0, sticky="w", pady=3)
        self.backend_box = ttk.Combobox(
            form,
            textvariable=self.backend,
            values=tuple(item.value for item in BackendKind),
            state="readonly",
        )
        self.backend_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.backend_box.bind("<<ComboboxSelected>>", lambda _event: self._backend_changed())
        ttk.Label(form, text="Assistance profile").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(
            form,
            textvariable=self.assistance,
            values=tuple(item.value for item in AssistanceProfile),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=3)
        self._entries: dict[str, ttk.Entry] = {}
        for row, (label, variable) in enumerate(fields, start=2):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self._entries[label] = entry
            if label == "Backend executable":
                ttk.Button(form, text="Browse…", command=self._browse_executable).grid(row=row, column=2, padx=(6, 0))
            elif label == "Model file":
                ttk.Button(form, text="Browse…", command=self._browse_model).grid(row=row, column=2, padx=(6, 0))
        form.columnconfigure(1, weight=1)
        ttk.Label(
            form,
            text=(
                "GUIDED explains setup; BALANCED exposes safe defaults; EXPERT keeps backend detail visible; "
                "AUTOMATED permits later startup only after this exact profile has been explicitly approved once."
            ),
            style="Muted.TLabel",
            wraplength=730,
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))

        actions = ttk.LabelFrame(body, text="Explicit actions", padding=10)
        actions.pack(fill="x", pady=(10, 0))
        self.save_button = ttk.Button(actions, text="Save Profile", command=self.save_profile)
        self.save_button.pack(side="left")
        self.discover_button = ttk.Button(actions, text="Discover / Check Health", command=self.discover)
        self.discover_button.pack(side="left", padx=(6, 0))
        self.start_button = ttk.Button(actions, text="Start / Connect", command=self.start_backend)
        self.start_button.pack(side="left", padx=(6, 0))
        self.stop_button = ttk.Button(actions, text="Stop / Disconnect", command=self.stop_backend)
        self.stop_button.pack(side="left", padx=(6, 0))
        self.chat_button = ttk.Button(actions, text="Open Local AI Chat", command=self.open_chat_command)
        self.chat_button.pack(side="right")

        status = ttk.LabelFrame(body, text="Operational state", padding=10)
        status.pack(fill="both", expand=True, pady=(10, 0))
        self._status_values: dict[str, tk.StringVar] = {}
        for row, (key, label) in enumerate(
            (
                ("state", "State"),
                ("failure", "Failure"),
                ("endpoint", "Endpoint"),
                ("model", "Model"),
                ("process", "Process"),
                ("version", "Backend version"),
                ("capability", "Session capability"),
            )
        ):
            ttk.Label(status, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=3)
            variable = tk.StringVar(value="—")
            self._status_values[key] = variable
            ttk.Label(status, textvariable=variable, wraplength=590).grid(row=row, column=1, sticky="nw", pady=3)
        status.columnconfigure(1, weight=1)
        self.message = tk.StringVar(value="No local provider contact has occurred.")
        ttk.Label(status, textvariable=self.message, style="Muted.TLabel", wraplength=730).grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(10, 0),
        )
        ttk.Button(body, text="Close", command=self._close).pack(side="right", pady=(10, 0))

    def _load_profile(self) -> None:
        profile = self.manager.profile(self.provider.profile_id)
        self.profile_name.set(profile.display_name)
        self.backend.set(profile.backend.value)
        self.endpoint.set(profile.endpoint.base_url)
        self.model.set(profile.model_id or "")
        self.executable.set(str(profile.executable) if profile.executable is not None else "")
        self.model_path.set(str(profile.model_path) if profile.model_path is not None else "")
        self.assistance.set(profile.assistance.value)
        self._backend_changed()

    def _backend_changed(self) -> None:
        launchable = self.backend.get() == BackendKind.LLAMA_CPP.value
        state = "normal" if launchable else "disabled"
        self._entries["Backend executable"].configure(state=state)
        self._entries["Model file"].configure(state=state)

    def _browse_executable(self) -> None:
        selected = filedialog.askopenfilename(parent=self, title="Choose an approved local AI backend executable")
        if selected:
            self.executable.set(selected)

    def _browse_model(self) -> None:
        selected = filedialog.askopenfilename(parent=self, title="Choose a local model file")
        if selected:
            self.model_path.set(selected)

    def _profile_from_form(self) -> BackendProfile:
        backend = BackendKind(self.backend.get())
        executable_text = self.executable.get().strip()
        model_path_text = self.model_path.get().strip()
        if backend is BackendKind.LLAMA_CPP and (not executable_text or not model_path_text):
            raise ValueError("A llama.cpp profile requires an executable and model file.")
        executable = Path(executable_text) if backend is BackendKind.LLAMA_CPP else None
        model_path = Path(model_path_text) if backend is BackendKind.LLAMA_CPP else None
        return BackendProfile(
            profile_id=self.provider.profile_id,
            display_name=self.profile_name.get().strip(),
            backend=backend,
            endpoint=LocalEndpoint(self.endpoint.get().strip()),
            assistance=AssistanceProfile(self.assistance.get()),
            model_id=self.model.get().strip() or None,
            executable=executable,
            model_path=model_path,
        )

    def save_profile(self) -> bool:
        if self._running:
            return False
        try:
            profile = self._profile_from_form()
            self.manager.save_profile(profile)
        except (LocalAIConfigurationError, OSError, TypeError, ValueError) as exc:
            messagebox.showerror("Local AI profile", str(exc), parent=self)
            return False
        self.message.set("Profile saved locally. No provider contact occurred.")
        self.refresh_status()
        return True

    def _run(
        self,
        operation: str,
        call: Callable[[], object],
        *,
        cancellation: threading.Event | None = None,
    ) -> None:
        if self._running:
            return
        self._running = True
        self._cancel = cancellation or threading.Event()
        self._set_controls(True)
        self.message.set(f"{operation}…")

        def worker() -> None:
            try:
                self._events.put(("ok", call()))
            except Exception as exc:  # noqa: BLE001 - isolated lifecycle boundary
                self._events.put(("error", exc))

        threading.Thread(target=worker, daemon=True, name="arx-local-ai-settings").start()

    def discover(self) -> None:
        if not self.save_profile():
            return
        self._run("Checking the explicit loopback endpoint", lambda: self.manager.discover(self.provider.profile_id))

    def start_backend(self) -> None:
        if not self.save_profile():
            return
        profile = self.manager.profile(self.provider.profile_id)
        explicit_approval = False
        if profile.launchable and not self.manager.approval_store.approved(profile):
            explicit_approval = messagebox.askyesno(
                "Approve first local backend execution",
                (
                    "ARX will start the selected backend executable with a typed loopback-only profile and the selected "
                    "model file. No AI-generated command text is executed. Approve this exact profile?"
                ),
                parent=self,
            )
            if not explicit_approval:
                self.message.set("Local backend startup was not approved; nothing was launched.")
                return
        cancellation = threading.Event()
        self._cancel = cancellation
        self._run(
            "Starting or connecting to local AI",
            lambda: self.manager.start(
                self.provider.profile_id,
                explicit_approval=explicit_approval,
                cancel=cancellation,
            ),
            cancellation=cancellation,
        )

    def stop_backend(self) -> None:
        self._run("Stopping or disconnecting local AI", lambda: self.manager.stop(self.provider.profile_id))

    def refresh_status(self) -> None:
        runtime = self.manager.runtime(self.provider.profile_id)
        profile = self.manager.profile(self.provider.profile_id)
        self._status_values["state"].set(runtime.state.value)
        self._status_values["failure"].set(runtime.failure.value if runtime.failure is not None else "NONE")
        self._status_values["endpoint"].set(runtime.endpoint)
        self._status_values["model"].set(runtime.model_identity or "NOT_SELECTED")
        self._status_values["process"].set(
            f"PID {runtime.pid} · {runtime.executable_identity or 'approved backend'}"
            if runtime.pid is not None
            else "NO ARX-SUPERVISED PROCESS"
        )
        self._status_values["version"].set(runtime.backend_version or "NOT_OBSERVED")
        self._status_values["capability"].set(
            "MEMORY-ONLY · SESSION-SCOPED · VALUE HIDDEN"
            if profile.session_capability and runtime.state in {LocalAIState.READY, LocalAIState.BUSY}
            else "NOT IN USE"
        )
        if runtime.message:
            self.message.set(runtime.message)
        self.chat_button.configure(state="normal" if runtime.state is LocalAIState.READY else "disabled")

    def _set_controls(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.save_button.configure(state=state)
        self.discover_button.configure(state=state)
        self.start_button.configure(state=state)
        self.stop_button.configure(state=state)

    def _poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                kind, value = self._events.get_nowait()
                self._running = False
                self._set_controls(False)
                if kind == "error":
                    if isinstance(
                        value,
                        (ApprovalRequired, LocalAIConfigurationError, OSError, TypeError, ValueError),
                    ):
                        self.message.set(str(value))
                    else:
                        self.message.set("The local AI operation failed unexpectedly.")
                self.refresh_status()
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._cancel is not None:
            self._cancel.set()
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        self.destroy()
