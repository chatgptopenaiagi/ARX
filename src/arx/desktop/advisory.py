"""Advisory-only assistant panel for explicit OpenAI or Codex requests."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Mapping

from arx.advisory.context import ANALYSIS_MODES, AdvisoryContext, build_advisory_prompt, redact_external
from arx.advisory.providers import (
    AIProvider,
    AdvisoryCancelled,
    AdvisoryResponse,
    AdvisoryTimeout,
    ProviderError,
)

from .ux import copy_to_clipboard
from .widgets import ReadOnlyText, set_text


def render_conversation(turns: list[dict[str, str]]) -> str:
    """Render only redacted conversation content for display/export."""

    blocks = []
    for turn in turns:
        if turn.get("role") == "user":
            role = "YOU"
            label = ""
        else:
            role = str(redact_external(turn.get("provider") or "AI PROVIDER")).upper()
            label = "AI ADVISORY — NON-AUTHORITATIVE\n"
        blocks.append(f"{role}\n{label}{redact_external(str(turn.get('text', '')))}")
    return "\n\n".join(blocks)


class PromptPreview(tk.Toplevel):
    """Inspectable prompt preview; opening it never transmits information."""

    def __init__(self, parent: tk.Misc, prompt: str):
        super().__init__(parent)
        self.title("Preview What Will Be Sent")
        self.geometry("850x620")
        self.minsize(560, 360)
        self.transient(parent.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text="Redacted advisory prompt. Nothing is sent from this preview.",
            style="Muted.TLabel",
        ).pack(fill="x", pady=(0, 8))
        self.view = ReadOnlyText(body, content_type="text")
        self.view.pack(fill="both", expand=True)
        set_text(self.view, prompt)
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Button(controls, text="Copy Prompt", command=self.view.copy_all).pack(side="left")
        ttk.Button(controls, text="Close", command=self.destroy).pack(side="right")


class AdvisoryWindow(tk.Toplevel):
    """Context-bound conversation UI that never mutates deterministic ARX data."""

    def __init__(
        self,
        parent: tk.Misc,
        context: AdvisoryContext,
        providers: Mapping[str, AIProvider],
        *,
        initial_provider: str | None = None,
        initial_mode: str = "Explain Technically",
        consent_command: Callable[[str, AdvisoryContext], bool] | None = None,
        save_command: Callable[[str, str], object] | None = None,
        view_context_command: Callable[[AdvisoryContext], object] | None = None,
        change_context_command: Callable[[], object] | None = None,
        status_command: Callable[[str], object] | None = None,
    ):
        super().__init__(parent)
        self.context = context
        self.providers = dict(providers)
        self.consent_command = consent_command
        self.save_command = save_command
        self.view_context_command = view_context_command
        self.change_context_command = change_context_command
        self.status_command = status_command
        self.turns: list[dict[str, str]] = []
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel: threading.Event | None = None
        self._running = False
        self._last_prompt = ""
        self._last_response = ""
        self._closed = False
        self._poll_id: str | None = None

        self.title("ARX AI Assistant — Advisory Only")
        self.geometry("980x760")
        self.minsize(700, 520)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self._build(initial_provider, initial_mode)
        self._poll_id = self.after(100, self._poll)

    def _build(self, initial_provider: str | None, initial_mode: str) -> None:
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="AI ADVISORY — NON-AUTHORITATIVE", style="Advisory.TLabel").pack(fill="x")
        ttk.Label(
            body,
            text=(
                "AI responses may interpret attached ARX evidence but cannot modify deterministic ARX evidence, "
                "compatibility, or readiness."
            ),
            style="Muted.TLabel",
        ).pack(fill="x", pady=(2, 10))

        context_group = ttk.LabelFrame(body, text="Current source context", padding=8)
        context_group.pack(fill="x")
        self.context_view = ReadOnlyText(context_group, content_type="text")
        self.context_view.pack(fill="x")
        self.context_view.text.configure(height=4)
        set_text(self.context_view, self.context.summary())
        context_controls = ttk.Frame(context_group)
        context_controls.pack(fill="x", pady=(6, 0))
        ttk.Button(context_controls, text="View Context", command=self._view_context).pack(side="left")
        ttk.Button(context_controls, text="Copy Context", command=lambda: copy_to_clipboard(self, self.context.preview())).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(context_controls, text="Change Context", command=self._change_context).pack(side="left", padx=(6, 0))
        ttk.Button(context_controls, text="Clear Conversation", command=self.clear_conversation).pack(side="right")

        choices = ttk.Frame(body)
        choices.pack(fill="x", pady=(10, 6))
        ttk.Label(choices, text="Provider:").grid(row=0, column=0, sticky="w")
        provider_names = tuple(self.providers)
        default_provider = initial_provider if initial_provider in self.providers else (provider_names[0] if provider_names else "")
        self.provider_name = tk.StringVar(value=default_provider)
        self.provider_box = ttk.Combobox(
            choices,
            textvariable=self.provider_name,
            values=provider_names,
            state="readonly",
            width=24,
        )
        self.provider_box.grid(row=1, column=0, padx=(0, 10), sticky="ew")
        self.provider_box.bind("<<ComboboxSelected>>", lambda _event: self._provider_changed())
        ttk.Label(choices, text="Analysis mode:").grid(row=0, column=1, sticky="w")
        self.mode = tk.StringVar(value=initial_mode if initial_mode in ANALYSIS_MODES else "Explain Technically")
        self.mode_box = ttk.Combobox(
            choices,
            textvariable=self.mode,
            values=tuple(ANALYSIS_MODES),
            state="readonly",
            width=28,
        )
        self.mode_box.grid(row=1, column=1, padx=(0, 10), sticky="ew")
        self.mode_box.bind("<<ComboboxSelected>>", lambda _event: self._mode_changed())
        self.availability = ttk.Label(choices, text="", style="Muted.TLabel")
        self.availability.grid(row=1, column=2, sticky="w")
        choices.columnconfigure(2, weight=1)

        question_frame = ttk.LabelFrame(body, text="Question", padding=8)
        question_frame.pack(fill="x")
        self.question = ttk.Entry(question_frame)
        self.question.pack(fill="x")
        self.question.insert(0, ANALYSIS_MODES[self.mode.get()])
        self.question.bind("<Return>", lambda _event: self.ask())
        controls = ttk.Frame(question_frame)
        controls.pack(fill="x", pady=(7, 0))
        self.preview_button = ttk.Button(controls, text="Preview What Will Be Sent", command=self.preview)
        self.preview_button.pack(side="left")
        self.ask_button = ttk.Button(controls, text="Ask", command=self.ask, style="Accent.TButton")
        self.ask_button.pack(side="right")
        self.cancel_button = ttk.Button(controls, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 7))

        self.operation_status = ttk.Label(body, text="Ready", style="Muted.TLabel")
        self.operation_status.pack(fill="x", pady=(7, 4))
        self.conversation = ReadOnlyText(body, content_type="text", save_command=self._save)
        self.conversation.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Copy Response", command=self.copy_response).pack(side="left")
        ttk.Button(footer, text="Copy Conversation", command=self.copy_conversation).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Save Conversation…", command=self.save_conversation).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Copy Diagnostic Prompt", command=self.copy_prompt).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Close", command=self._close).pack(side="right")
        self._provider_changed()
        self.question.focus_set()

    def selected_provider(self) -> AIProvider | None:
        return self.providers.get(self.provider_name.get())

    def _provider_changed(self) -> None:
        provider = self.selected_provider()
        if provider is None:
            self.availability.configure(text="No advisory provider is configured.")
            self.ask_button.configure(state="disabled")
            return
        state = provider.availability()
        detail = state.version or state.reason
        self.availability.configure(text=detail)
        self.ask_button.configure(state="normal" if state.available and not self._running else "disabled")

    def _mode_changed(self) -> None:
        current = self.question.get().strip()
        if not current or current in ANALYSIS_MODES.values():
            self.question.delete(0, "end")
            self.question.insert(0, ANALYSIS_MODES[self.mode.get()])

    def prompt(self) -> str:
        return build_advisory_prompt(
            self.context,
            self.question.get(),
            mode=self.mode.get(),
            conversation=self.turns,
        )

    def preview(self) -> PromptPreview:
        self._last_prompt = self.prompt()
        return PromptPreview(self, self._last_prompt)

    def ask(self) -> str:
        if self._running:
            return "break"
        provider = self.selected_provider()
        if provider is None:
            self._show_provider_error("No advisory provider is configured.")
            return "break"
        availability = provider.availability()
        if not availability.available:
            self._show_provider_error(availability.reason)
            return "break"
        if self.consent_command is not None and not self.consent_command(self.provider_name.get(), self.context):
            self._set_status("Cancelled — no information was sent.")
            return "break"
        safe_question = str(redact_external(self.question.get())).strip() or ANALYSIS_MODES[self.mode.get()]
        analysis_mode = self.mode.get()
        self._last_prompt = self.prompt()
        prior_turns = list(self.turns)
        self.turns.append({"role": "user", "text": safe_question})
        self._render_turns()
        cancellation = threading.Event()
        self._cancel = cancellation
        self._running = True
        self._set_controls(True)
        status = "Running Codex analysis…" if "Codex" in self.provider_name.get() else "Contacting AI…"
        self._set_status(status)

        def worker() -> None:
            try:
                response = provider.ask(
                    self.context,
                    safe_question,
                    mode=analysis_mode,
                    conversation=prior_turns,
                    cancel=cancellation,
                    timeout=90,
                )
                self._events.put(("ok", response))
            except AdvisoryCancelled as exc:
                self._events.put(("cancelled", exc))
            except AdvisoryTimeout as exc:
                self._events.put(("timeout", exc))
            except ProviderError as exc:
                self._events.put(("error", exc))
            except Exception:
                self._events.put(("error", ProviderError("The advisory provider failed unexpectedly.")))

        threading.Thread(target=worker, daemon=True, name="arx-advisory-worker").start()
        return "break"

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                self._running = False
                self._cancel = None
                self._set_controls(False)
                if kind == "ok":
                    response: AdvisoryResponse = payload  # type: ignore[assignment]
                    self._last_response = response.display_text()
                    self.turns.append({"role": "assistant", "provider": response.provider, "text": response.text})
                    self._render_turns()
                    self._set_status("Completed")
                elif kind == "cancelled":
                    self._set_status("Cancelled")
                elif kind == "timeout":
                    self._set_status("Timed out")
                    self._show_provider_error(str(payload), dialog=False)
                else:
                    self._set_status("Failed")
                    self._show_provider_error(str(payload))
        except queue.Empty:
            pass
        if not self._closed and self.winfo_exists():
            self._poll_id = self.after(100, self._poll)

    def _set_controls(self, running: bool) -> None:
        self.ask_button.configure(state="disabled" if running else "normal")
        self.preview_button.configure(state="disabled" if running else "normal")
        self.provider_box.configure(state="disabled" if running else "readonly")
        self.mode_box.configure(state="disabled" if running else "readonly")
        self.question.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        if not running:
            self._provider_changed()

    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
            self.cancel_button.configure(state="disabled")
            self._set_status("Cancelling…")

    def _set_status(self, value: str) -> None:
        self.operation_status.configure(text=value)
        if self.status_command:
            self.status_command(value)

    def _show_provider_error(self, value: str, *, dialog: bool = True) -> None:
        safe = str(redact_external(value))
        if dialog:
            messagebox.showerror("ARX AI Assistant", safe, parent=self)
        self.availability.configure(text=safe)

    def _render_turns(self) -> None:
        set_text(self.conversation, render_conversation(self.turns))

    def clear_conversation(self) -> None:
        if self._running:
            return
        self.turns.clear()
        self._last_response = ""
        self._last_prompt = ""
        self._render_turns()
        self._set_status("Ready")

    def copy_response(self) -> None:
        if self._last_response:
            copy_to_clipboard(self, redact_external(self._last_response))

    def copy_conversation(self) -> None:
        copy_to_clipboard(self, render_conversation(self.turns))

    def copy_prompt(self) -> None:
        self._last_prompt = self.prompt()
        copy_to_clipboard(self, self._last_prompt)

    def _save(self, _content_type: str, _content: str) -> None:
        self.save_conversation()

    def save_conversation(self) -> None:
        if self.save_command:
            self.save_command("text", render_conversation(self.turns))

    def _view_context(self) -> None:
        if self.view_context_command:
            self.view_context_command(self.context)
        else:
            PromptPreview(self, self.context.preview())

    def _change_context(self) -> None:
        if self.change_context_command:
            self.change_context_command()
        self._close()

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
