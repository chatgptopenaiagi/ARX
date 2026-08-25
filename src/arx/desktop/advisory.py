"""Advisory-only assistant panel for explicit OpenAI or Codex requests."""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from collections.abc import Callable, Mapping
from tkinter import messagebox, ttk
from typing import Protocol, cast

from arx.advisory.audit import AuditError
from arx.advisory.context import (
    ANALYSIS_MODES,
    AdvisoryContext,
    ContextSelection,
    build_advisory_prompt,
    build_general_chat_context,
    redact_external,
)
from arx.advisory.intelligence import AskBothResult, ConversationRegistry, ask_both
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryResponse,
    AdvisoryTimeout,
    AIProvider,
    ProviderError,
)

from .theme import COLORS
from .ux import copy_to_clipboard
from .widgets import ReadOnlyText, set_text


def render_conversation(turns: list[dict[str, str]]) -> str:
    """Render only redacted conversation content for display/export."""

    blocks = ["AI ADVISORY — NON-AUTHORITATIVE"]
    for turn in turns:
        if turn.get("role") == "user":
            role = "YOU"
        else:
            role = str(redact_external(turn.get("provider") or "AI PROVIDER")).upper()
        blocks.append(f"{role}\n{redact_external(str(turn.get('text', '')))}")
    return "\n\n".join(blocks)


class AuditView(Protocol):
    def history(self) -> list[dict[str, object]]: ...

    def clear_history(self) -> None: ...


class ChatEditor(tk.Text):
    """Multi-line editor with Entry-compatible helpers used by older callers."""

    def __init__(self, parent: tk.Misc):
        super().__init__(
            parent,
            height=4,
            wrap="word",
            undo=True,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["selected"],
            selectforeground=COLORS["text"],
            relief="flat",
            padx=8,
            pady=8,
        )

    @staticmethod
    def _index(value: object, *, end: bool = False) -> str:
        if value in (None, 0, "0"):
            return "1.0"
        if value == "end":
            return "end" if end else "end-1c"
        return str(value)

    def get(self, index1: object = None, index2: object = None) -> str:  # type: ignore[override]
        return super().get(self._index(index1), self._index(index2, end=True) if index2 is not None else "end-1c")

    def delete(self, index1: object = None, index2: object = None) -> None:  # type: ignore[override]
        super().delete(self._index(index1), self._index(index2, end=True) if index2 is not None else "end")

    def insert(self, index: object, chars: object, *args: object) -> None:  # type: ignore[override]
        super().insert(self._index(index), str(chars), *args)


class AskBothResultWindow(tk.Toplevel):
    """Flat two-provider response panels plus non-authoritative text comparison."""

    def __init__(self, parent: tk.Misc, result: AskBothResult):
        super().__init__(parent)
        self.result = result
        self.title("Ask Both — Independent AI Advisories")
        self.geometry("1120x760")
        self.minsize(760, 520)
        self.transient(parent.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="AI ADVISORY — NON-AUTHORITATIVE", style="Advisory.TLabel").pack(fill="x")
        ttk.Label(
            body,
            text="Two responses are shown flat and unranked. Similar wording is not independent verification.",
            style="Muted.TLabel",
        ).pack(fill="x", pady=(2, 8))
        panels = ttk.Panedwindow(body, orient="horizontal")
        panels.pack(fill="both", expand=True)
        for outcome in result.outcomes:
            frame = ttk.LabelFrame(panels, text=outcome.provider_label.upper(), padding=8)
            panels.add(frame, weight=1)
            ttk.Label(frame, text=outcome.provider_identity, style="Muted.TLabel").pack(fill="x", pady=(0, 5))
            view = ReadOnlyText(frame, content_type="text")
            view.pack(fill="both", expand=True)
            state = "RESPONSE" if outcome.completed else (
                outcome.error_status.value if outcome.error_status is not None else "NO_RESPONSE"
            )
            set_text(view, f"Status: {state}\n\n{outcome.display_text()}")
        comparison = ttk.LabelFrame(body, text="Compare Responses — presentation aid only", padding=8)
        comparison.pack(fill="both", expand=False, pady=(10, 0))
        comparison_text = (
            f"{result.comparison.trust_label}\n\n"
            "TEXTUAL OVERLAP\n"
            f"{_render_items(result.comparison.textual_overlap)}\n\n"
            "DIFFERENCES\n"
            f"{_render_items(result.comparison.differences)}\n\n"
            "UNRESOLVED\n"
            f"{_render_items(result.comparison.unresolved)}"
        )
        comparison_view = ReadOnlyText(comparison, content_type="text")
        comparison_view.pack(fill="both", expand=True)
        comparison_view.text.configure(height=10)
        set_text(comparison_view, comparison_text)
        ttk.Button(body, text="Close", command=self.destroy).pack(side="right", pady=(8, 0))


def _render_items(items: tuple[str, ...]) -> str:
    return "\n".join(f"• {item}" for item in items) if items else "• None detected"


class TransmissionHistoryWindow(tk.Toplevel):
    """Inspection and explicit clearing for bounded metadata-only audit history."""

    def __init__(self, parent: tk.Misc, audit: AuditView):
        super().__init__(parent)
        self.audit = audit
        self.title("External Transmission Audit — Metadata Only")
        self.geometry("900x620")
        self.minsize(600, 400)
        self.transient(parent.winfo_toplevel())
        self.bind("<Escape>", lambda _event: self.destroy())
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text="Local bounded metadata only — no prompts, responses, credentials, secret values, or full local paths.",
            style="Muted.TLabel",
        ).pack(fill="x", pady=(0, 8))
        self.view = ReadOnlyText(body, content_type="json")
        self.view.pack(fill="both", expand=True)
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(controls, text="Clear History", command=self.clear).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Close", command=self.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        try:
            history = self.audit.history()
        except (AuditError, OSError):
            set_text(self.view, "The local transmission audit could not be read.")
            return
        set_text(self.view, json.dumps(redact_external(history), indent=2, ensure_ascii=False, sort_keys=True))

    def clear(self) -> None:
        if not messagebox.askyesno(
            "Clear transmission history",
            "Clear the bounded local metadata-only external transmission history?",
            parent=self,
        ):
            return
        try:
            self.audit.clear_history()
        except (AuditError, OSError):
            messagebox.showerror(
                "Transmission history",
                "The local external transmission history could not be cleared.",
                parent=self,
            )
            return
        self.refresh()


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
    """Phase C Intelligence Console with one-way advisory-only provider access."""

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
        context_builder: Callable[[ContextSelection], AdvisoryContext] | None = None,
        search_command: Callable[[AdvisoryContext, str], object] | None = None,
        audit: AuditView | None = None,
        status_command: Callable[[str], object] | None = None,
    ):
        super().__init__(parent)
        self.context = context
        self.providers = dict(providers)
        self.consent_command = consent_command
        self.save_command = save_command
        self.view_context_command = view_context_command
        self.change_context_command = change_context_command
        self.context_builder = context_builder
        self.search_command = search_command
        self.audit = audit
        self.status_command = status_command
        self.sessions = ConversationRegistry()
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel: threading.Event | None = None
        self._running = False
        self._last_prompt = ""
        self._last_response = ""
        self._closed = False
        self._poll_id: str | None = None
        self._active_provider = ""
        self._active_operation = ""
        self._last_question: dict[str, str] = {}
        self._scope_variables: dict[str, tk.BooleanVar] = {}
        self._result_windows: list[AskBothResultWindow] = []

        self.title("ARX Intelligence Console — Advisory Only")
        self.geometry("1120x860")
        self.minsize(780, 600)
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

        context_group = ttk.LabelFrame(body, text="Bounded advisory context", padding=8)
        context_group.pack(fill="x")
        self.context_view = ReadOnlyText(context_group, content_type="text")
        self.context_view.pack(fill="x")
        self.context_view.text.configure(height=3)
        set_text(self.context_view, self.context.summary())
        context_controls = ttk.Frame(context_group)
        context_controls.pack(fill="x", pady=(6, 0))
        ttk.Button(context_controls, text="View Redacted Context", command=self._view_context).pack(side="left")
        ttk.Button(context_controls, text="Copy Context", command=self._copy_context).pack(side="left", padx=(6, 0))
        ttk.Button(context_controls, text="View Evidence", command=self._view_evidence).pack(side="left", padx=(6, 0))
        self.attach_button = ttk.Button(
            context_controls,
            text="Attach Selected ARX Evidence",
            command=self.attach_selected_context,
        )
        self.attach_button.pack(side="left", padx=(6, 0))
        ttk.Button(context_controls, text="General Chat", command=self.detach_context).pack(side="right")

        scope = ttk.Frame(context_group)
        scope.pack(fill="x", pady=(6, 0))
        selection_values = self.context.selection.as_dict()
        for column, (key, label) in enumerate(
            (
                ("selected_finding", "Finding"),
                ("relevant_evidence", "Evidence"),
                ("machine_dna", "Machine DNA"),
                ("software_dna", "Software DNA"),
                ("project_dna", "Project DNA"),
                ("conclusions", "Conclusions"),
                ("contradictions", "Contradictions"),
                ("unknowns", "Unknowns"),
            )
        ):
            variable = tk.BooleanVar(value=bool(selection_values.get(key)))
            self._scope_variables[key] = variable
            ttk.Checkbutton(scope, text=label, variable=variable).grid(
                row=column // 4,
                column=column % 4,
                sticky="w",
                padx=(0, 12),
            )
        self.apply_scope_button = ttk.Button(scope, text="Apply Scope", command=self.apply_scope)
        self.apply_scope_button.grid(row=0, column=4, rowspan=2, sticky="e")
        scope.columnconfigure(4, weight=1)

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

        transcript_group = ttk.LabelFrame(body, text="Conversation transcript", padding=8)
        transcript_group.pack(fill="both", expand=True)
        self.conversation = ReadOnlyText(transcript_group, content_type="text", save_command=self._save)
        self.conversation.pack(fill="both", expand=True)

        question_frame = ttk.LabelFrame(body, text="Message", padding=8)
        question_frame.pack(fill="x")
        self.question = ChatEditor(question_frame)
        self.question.pack(fill="x")
        self.question.insert(0, ANALYSIS_MODES[self.mode.get()])
        self.question.bind("<Control-Return>", lambda _event: self.ask())
        controls = ttk.Frame(question_frame)
        controls.pack(fill="x", pady=(7, 0))
        self.preview_button = ttk.Button(controls, text="Preview What Will Be Sent", command=self.preview)
        self.preview_button.pack(side="left")
        self.retry_button = ttk.Button(controls, text="Retry", command=self.retry, state="disabled")
        self.retry_button.pack(side="left", padx=(6, 0))
        self.ask_both_button = ttk.Button(controls, text="Ask Both", command=self.ask_both)
        self.ask_both_button.pack(side="right", padx=(6, 0))
        self.ask_button = ttk.Button(controls, text="Send", command=self.ask, style="Accent.TButton")
        self.ask_button.pack(side="right")
        self.cancel_button = ttk.Button(controls, text="Stop / Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 7))

        self.operation_status = ttk.Label(body, text="Ready", style="Muted.TLabel")
        self.operation_status.pack(fill="x", pady=(7, 4))
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Copy Response", command=self.copy_response).pack(side="left")
        ttk.Button(footer, text="Copy Conversation", command=self.copy_conversation).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Save Conversation…", command=self.save_conversation).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="New Conversation", command=self.new_conversation).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Clear Conversation", command=self.clear_conversation).pack(side="left", padx=(6, 0))
        if self.audit is not None:
            ttk.Button(footer, text="Transmission Audit", command=self.view_transmission_audit).pack(
                side="left", padx=(6, 0)
            )
        ttk.Button(footer, text="Close", command=self._close).pack(side="right")
        if self.search_command is not None:
            ttk.Button(footer, text="Search Web", command=lambda: self.search_command(self.context, "web")).pack(
                side="right", padx=(0, 6)
            )
            ttk.Button(
                footer,
                text="Official Documentation",
                command=lambda: self.search_command(self.context, "official"),
            ).pack(side="right", padx=(0, 6))
        self._provider_changed()
        self.question.focus_set()

    def selected_provider(self) -> AIProvider | None:
        return self.providers.get(self.provider_name.get())

    @property
    def turns(self) -> list[dict[str, str]]:
        """Compatibility view of the currently selected provider session."""

        return self.sessions.history(self.provider_name.get())

    def _provider_changed(self) -> None:
        self._active_provider = self.provider_name.get()
        provider = self.selected_provider()
        if provider is None:
            self.availability.configure(text="No advisory provider is configured.")
            self.ask_button.configure(state="disabled")
            self.ask_both_button.configure(state="disabled")
            self._render_turns()
            return
        state = provider.availability()
        identity = str(getattr(provider, "provider_id", "") or getattr(provider, "name", self._active_provider))
        operational = state.operational_status.value if state.operational_status is not None else (
            "AVAILABLE" if state.available else "NOT_AVAILABLE"
        )
        detail = f"{identity} · {operational} · {state.version or state.reason}"
        self.availability.configure(text=detail)
        self.ask_button.configure(state="normal" if state.available and not self._running else "disabled")
        self.ask_both_button.configure(state="normal" if len(self.providers) == 2 and not self._running else "disabled")
        self.retry_button.configure(
            state="normal" if self._last_question.get(self._active_provider) and not self._running else "disabled"
        )
        self._render_turns()

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
            conversation=self.sessions.history(self.provider_name.get()),
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
        provider_label = self.provider_name.get()
        if self.consent_command is not None and not self.consent_command(provider_label, self.context):
            self._set_status("Cancelled — no information was sent.")
            return "break"
        safe_question = str(redact_external(self.question.get())).strip() or ANALYSIS_MODES[self.mode.get()]
        analysis_mode = self.mode.get()
        self._last_prompt = self.prompt()
        prior_turns = self.sessions.history(provider_label)
        self.sessions.append(provider_label, "user", safe_question)
        self._last_question[provider_label] = safe_question
        self._render_turns()
        cancellation = threading.Event()
        self._cancel = cancellation
        self._running = True
        self._active_operation = "single"
        self._set_controls(True)
        status = f"Contacting {provider_label}…"
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
                self._events.put(("ok", (provider_label, response)))
            except AdvisoryCancelled as exc:
                self._events.put(("cancelled", (provider_label, exc)))
            except AdvisoryTimeout as exc:
                self._events.put(("timeout", (provider_label, exc)))
            except ProviderError as exc:
                self._events.put(("error", (provider_label, exc)))
            except Exception:  # noqa: BLE001 - provider implementations are isolated here
                self._events.put(
                    ("error", (provider_label, ProviderError("The advisory provider failed unexpectedly.")))
                )

        threading.Thread(target=worker, daemon=True, name="arx-advisory-worker").start()
        return "break"

    def ask_both(self) -> str:
        if self._running:
            return "break"
        if len(self.providers) != 2:
            self._show_provider_error("Ask Both requires exactly two configured providers.")
            return "break"
        for provider_label in self.providers:
            if self.consent_command is not None and not self.consent_command(provider_label, self.context):
                self._set_status("Cancelled — no information was sent.")
                return "break"
        safe_question = str(redact_external(self.question.get())).strip() or ANALYSIS_MODES[self.mode.get()]
        analysis_mode = self.mode.get()
        histories = {label: self.sessions.history(label) for label in self.providers}
        for label in self.providers:
            self.sessions.append(label, "user", safe_question)
            self._last_question[label] = safe_question
        self._last_prompt = self.prompt()
        self._render_turns()
        cancellation = threading.Event()
        self._cancel = cancellation
        self._running = True
        self._active_operation = "both"
        self._set_controls(True)
        self._set_status("Contacting two independent providers…")

        def worker() -> None:
            try:
                result = ask_both(
                    self.providers,
                    self.context,
                    safe_question,
                    mode=analysis_mode,
                    conversations=histories,
                    cancel=cancellation,
                    timeout=90,
                )
                self._events.put(("both", result))
            except Exception as exc:  # noqa: BLE001 - Ask Both isolates provider implementations
                safe = exc if isinstance(exc, ProviderError) else ProviderError(
                    "Ask Both could not complete safely."
                )
                self._events.put(("error", (self.provider_name.get(), safe)))

        threading.Thread(target=worker, daemon=True, name="arx-ask-both-worker").start()
        return "break"

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                self._running = False
                self._cancel = None
                self._set_controls(False)
                if kind == "ok":
                    provider_label, response = cast(tuple[str, AdvisoryResponse], payload)
                    self._last_response = response.display_text()
                    self.sessions.append(
                        provider_label,
                        "assistant",
                        response.text,
                        response_provider=response.provider,
                    )
                    self._render_turns()
                    self._set_status("Completed")
                elif kind == "both":
                    result: AskBothResult = payload  # type: ignore[assignment]
                    for outcome in result.outcomes:
                        if outcome.response is not None:
                            self.sessions.append(
                                outcome.provider_label,
                                "assistant",
                                outcome.response.text,
                                response_provider=outcome.response.provider,
                            )
                            if outcome.provider_label == self.provider_name.get():
                                self._last_response = outcome.response.display_text()
                    self._render_turns()
                    window = AskBothResultWindow(self, result)
                    self._result_windows.append(window)
                    if all(outcome.completed for outcome in result.outcomes):
                        self._set_status("Ask Both completed — responses remain independent")
                    elif any(outcome.error_status is not None and outcome.error_status.value == "CANCELLED" for outcome in result.outcomes):
                        self._set_status("Ask Both cancelled")
                    else:
                        self._set_status("Ask Both completed with an explicit provider failure")
                elif kind == "cancelled":
                    self._set_status("Cancelled")
                elif kind == "timeout":
                    _provider_label, error = payload  # type: ignore[misc]
                    self._set_status("Timed out")
                    self._show_provider_error(str(error), dialog=False)
                else:
                    _provider_label, error = payload  # type: ignore[misc]
                    self._set_status("Failed")
                    self._show_provider_error(str(error))
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
        self.ask_both_button.configure(state="disabled" if running or len(self.providers) != 2 else "normal")
        self.retry_button.configure(state="disabled" if running else "normal")
        self.apply_scope_button.configure(state="disabled" if running or self.context_builder is None else "normal")
        self.attach_button.configure(state="disabled" if running or self.context_builder is None else "normal")
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
            messagebox.showerror("ARX Intelligence Console", safe, parent=self)
        self.availability.configure(text=safe)

    def _render_turns(self) -> None:
        set_text(self.conversation, render_conversation(self.sessions.history(self.provider_name.get())))

    def clear_conversation(self) -> None:
        if self._running:
            return
        provider = self.provider_name.get()
        self.sessions.clear(provider)
        self._last_question.pop(provider, None)
        self._last_response = ""
        self._last_prompt = ""
        self._render_turns()
        self._set_status("Ready")

    def new_conversation(self) -> None:
        if self._running:
            return
        self.clear_conversation()
        self.question.delete(0, "end")
        self.question.insert(0, ANALYSIS_MODES[self.mode.get()])
        self._set_status(f"New {self.provider_name.get()} conversation")

    def retry(self) -> None:
        if self._running:
            return
        question = self._last_question.get(self.provider_name.get())
        if not question:
            return
        self.question.delete(0, "end")
        self.question.insert(0, question)
        self.ask()

    def copy_response(self) -> None:
        if self._last_response:
            copy_to_clipboard(self, redact_external(self._last_response))

    def copy_conversation(self) -> None:
        copy_to_clipboard(self, render_conversation(self.sessions.history(self.provider_name.get())))

    def copy_prompt(self) -> None:
        self._last_prompt = self.prompt()
        copy_to_clipboard(self, self._last_prompt)

    def _save(self, _content_type: str, _content: str) -> None:
        self.save_conversation()

    def save_conversation(self) -> None:
        if self.save_command:
            self.save_command("text", render_conversation(self.sessions.history(self.provider_name.get())))

    def _view_context(self) -> None:
        if self.view_context_command:
            self.view_context_command(self.context)
        else:
            PromptPreview(self, self.context.preview())

    def _view_evidence(self) -> None:
        PromptPreview(
            self,
            json.dumps(redact_external(list(self.context.evidence)), indent=2, ensure_ascii=False, sort_keys=True),
        )

    def _copy_context(self) -> None:
        copy_to_clipboard(self, self.context.preview())

    def _current_selection(self) -> ContextSelection:
        return ContextSelection(**{key: bool(variable.get()) for key, variable in self._scope_variables.items()})

    def _set_context(self, context: AdvisoryContext) -> None:
        self.context = context
        enabled = context.selection.as_dict()
        for key, variable in self._scope_variables.items():
            variable.set(bool(enabled.get(key)))
        set_text(self.context_view, context.summary())
        mode = "ARX evidence attached" if context.has_arx_evidence else "General chat — no ARX evidence attached"
        self._set_status(mode)

    def apply_scope(self) -> None:
        if self._running or self.context_builder is None:
            return
        try:
            self._set_context(self.context_builder(self._current_selection()))
        except (TypeError, ValueError) as exc:
            self._show_provider_error(str(exc))

    def attach_selected_context(self) -> None:
        if self._running:
            return
        if self.context_builder is not None:
            selection = self._current_selection()
            if not any(selection.as_dict().values()):
                selection = ContextSelection()
            try:
                self._set_context(self.context_builder(selection))
            except (TypeError, ValueError) as exc:
                self._show_provider_error(str(exc))
            return
        if self.change_context_command is not None:
            result = self.change_context_command()
            if isinstance(result, AdvisoryContext):
                self._set_context(result)

    def detach_context(self) -> None:
        if not self._running:
            self._set_context(build_general_chat_context())

    def view_transmission_audit(self) -> None:
        if self.audit is not None:
            TransmissionHistoryWindow(self, self.audit)

    def _change_context(self) -> None:
        self.attach_selected_context()

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
        for window in tuple(self._result_windows):
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass
        self.destroy()
