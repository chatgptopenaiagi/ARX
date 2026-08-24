"""Minimal Phase B provider configuration and operational-status surface."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from arx.advisory.audit import AuditError, TransmissionAudit
from arx.advisory.credentials import (
    CredentialError,
    CredentialSource,
    CredentialState,
    WindowsDPAPICredentialStore,
    import_openai_credential_file,
)
from arx.advisory.health import ProviderHealth, ProviderHealthStatus
from arx.advisory.providers import OpenAIProvider


OPENAI_API_KEYS_URL = "https://platform.openai.com/api-keys"
_UNREADABLE_MESSAGE = (
    "A saved OpenAI credential exists but cannot be decrypted in the current Windows context. "
    "Reconfigure or remove the stored credential."
)


class OpenAIProviderSettingsWindow(tk.Toplevel):
    """Safe OpenAI API settings; opening this window never performs a network request."""

    def __init__(
        self,
        parent: tk.Misc,
        provider: OpenAIProvider,
        credential_store: WindowsDPAPICredentialStore,
        audit: TransmissionAudit,
        *,
        open_chat_command: Callable[[], object],
        platform_opener: Callable[[str], object] = webbrowser.open_new_tab,
    ):
        super().__init__(parent)
        self.provider = provider
        self.credential_store = credential_store
        self.audit = audit
        self.open_chat_command = open_chat_command
        self.platform_opener = platform_opener
        self._events: queue.Queue[ProviderHealth] = queue.Queue()
        self._cancel: threading.Event | None = None
        self._poll_id: str | None = None
        self._closed = False
        self._last_health: ProviderHealth | None = None
        self._action_buttons: list[ttk.Button] = []

        self.title("Settings — Intelligence Providers — OpenAI API")
        self.geometry("720x650")
        self.minsize(620, 540)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self._build()
        self.refresh_status()
        self._poll_id = self.after(100, self._poll)

    def _build(self) -> None:
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="OpenAI API", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "ARX uses the supported OpenAI API. Create or manage a dedicated key on the official OpenAI Platform, "
                "then import it into the per-user Windows secure store. ARX does not control the ChatGPT app or website."
            ),
            style="Muted.TLabel",
            wraplength=670,
            justify="left",
        ).pack(fill="x", pady=(4, 12))

        status_group = ttk.LabelFrame(body, text="Provider status", padding=10)
        status_group.pack(fill="x")
        self._status_values: dict[str, tk.StringVar] = {}
        labels = (
            ("Credential", "credential"),
            ("Credential source", "source"),
            ("Authentication", "authentication"),
            ("API", "api"),
            ("Model", "model"),
            ("Overall", "overall"),
            ("Last check", "last_check"),
        )
        for row, (label, key) in enumerate(labels):
            ttk.Label(status_group, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=2)
            value = tk.StringVar(value="NOT_CHECKED")
            self._status_values[key] = value
            ttk.Label(status_group, textvariable=value).grid(row=row, column=1, sticky="w", pady=2)
        status_group.columnconfigure(1, weight=1)

        self.message = tk.StringVar(value="Opening Settings does not contact OpenAI or transmit ARX evidence.")
        ttk.Label(
            body,
            textvariable=self.message,
            style="Muted.TLabel",
            wraplength=670,
            justify="left",
        ).pack(fill="x", pady=(10, 8))

        actions = ttk.LabelFrame(body, text="Credential and provider actions", padding=10)
        actions.pack(fill="x")
        specifications = (
            ("Configure OpenAI API Key", self.configure_credential),
            ("Import OpenAI API Key", self.import_credential),
            ("Replace Credential", self.replace_credential),
            ("Remove Credential", self.remove_credential),
            ("Test Connection", self.test_connection),
            ("Open OpenAI Chat", self.open_chat),
        )
        for row, (label, command) in enumerate(specifications):
            button = ttk.Button(actions, text=label, command=command)
            button.grid(row=row // 2, column=row % 2, sticky="ew", padx=4, pady=4)
            self._action_buttons.append(button)
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        privacy = ttk.LabelFrame(body, text="Local transmission history", padding=10)
        privacy.pack(fill="x", pady=(10, 0))
        ttk.Label(
            privacy,
            text="Metadata only: no key, prompt body, response body, secret value, or full local path.",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(privacy, text="Clear History", command=self.clear_history).pack(side="right", padx=(8, 0))

        ttk.Label(
            body,
            text=(
                "AI responses are non-authoritative. They may interpret explicitly approved redacted ARX context, but cannot "
                "modify deterministic evidence, EvidenceKind, compatibility, or readiness."
            ),
            style="Advisory.TLabel",
            wraplength=670,
            justify="left",
        ).pack(fill="x", pady=(12, 8))
        ttk.Button(body, text="Close", command=self._close).pack(side="right")

    @staticmethod
    def _source_label(source: CredentialSource) -> str:
        return {
            CredentialSource.NONE: "NONE",
            CredentialSource.PROCESS_ENVIRONMENT: "Process environment",
            CredentialSource.SECURE_WINDOWS_STORE: "Secure Windows Store",
        }[source]

    def refresh_status(self) -> None:
        status = self.provider.credential_status()
        self._status_values["credential"].set(status.state.value)
        self._status_values["source"].set(self._source_label(status.source))
        if self._last_health is None or self._last_health.credential_state is not status.state:
            self._status_values["authentication"].set("NOT_CHECKED")
            self._status_values["api"].set("NOT_CHECKED")
            self._status_values["model"].set("NOT_CHECKED")
            self._status_values["overall"].set(
                status.state.value if status.state is not CredentialState.CONFIGURED else "NOT_CHECKED"
            )
            self._status_values["last_check"].set("NEVER")
            self._last_health = None
        if status.state is CredentialState.CREDENTIAL_UNREADABLE:
            self.message.set(_UNREADABLE_MESSAGE)
        elif status.state is CredentialState.CONFIGURED:
            self.message.set("Credential is configured. Its plaintext value is never displayed after import.")
        else:
            self.message.set("No OpenAI API credential is configured. Core ARX and Codex CLI remain independent.")

    def configure_credential(self) -> None:
        try:
            opened = self.platform_opener(OPENAI_API_KEYS_URL)
            if opened is False:
                raise OSError("The default browser did not accept the request.")
            self.message.set("Official OpenAI Platform key settings opened. Return here and use Import OpenAI API Key.")
        except OSError:
            messagebox.showerror(
                "OpenAI API",
                "The official OpenAI Platform API-key page could not be opened in the default browser.",
                parent=self,
            )

    def _import(self, *, replacing: bool) -> None:
        if replacing and self.credential_store.exists() and not messagebox.askyesno(
            "Replace OpenAI credential",
            "Replace the saved per-user OpenAI API credential? The old protected credential cannot be recovered afterward.",
            parent=self,
        ):
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="Select temporary OpenAI API key file",
            filetypes=(("Text files", "*.txt"), ("Environment files", ".env*"), ("All files", "*")),
        )
        if not selected:
            return
        try:
            import_openai_credential_file(selected, self.credential_store)
        except CredentialError as exc:
            messagebox.showerror("OpenAI API credential", str(exc), parent=self)
            return
        except OSError:
            messagebox.showerror(
                "OpenAI API credential",
                "The selected credential could not be imported safely.",
                parent=self,
            )
            return
        self._last_health = None
        self.refresh_status()
        messagebox.showinfo(
            "OpenAI API credential",
            (
                "Credential: CONFIGURED\n\nThe key is protected for the current Windows user and will not be displayed. "
                "The selected plaintext source file was not deleted; remove it only after successful connection testing."
            ),
            parent=self,
        )

    def import_credential(self) -> None:
        self._import(replacing=False)

    def replace_credential(self) -> None:
        self._import(replacing=True)

    def remove_credential(self) -> None:
        if not self.credential_store.exists():
            self.message.set("No saved Secure Windows Store credential exists to remove.")
            return
        if not messagebox.askyesno(
            "Remove OpenAI credential",
            "Remove the saved per-user OpenAI API credential from ARX?",
            parent=self,
        ):
            return
        try:
            self.credential_store.remove()
        except CredentialError as exc:
            messagebox.showerror("OpenAI API credential", str(exc), parent=self)
            return
        self._last_health = None
        self.refresh_status()
        self.message.set("The saved Secure Windows Store credential was removed.")

    def _set_busy(self, busy: bool) -> None:
        for button in self._action_buttons:
            button.configure(state="disabled" if busy else "normal")

    def test_connection(self) -> None:
        if self._cancel is not None:
            return
        cancellation = threading.Event()
        self._cancel = cancellation
        self._set_busy(True)
        self.message.set("Testing only authentication, API access, and the configured model; no ARX evidence is sent.")

        def worker() -> None:
            self._events.put(self.provider.health(cancel=cancellation, timeout=15))

        threading.Thread(target=worker, daemon=True, name="arx-openai-health").start()

    def _apply_health(self, health: ProviderHealth) -> None:
        self._last_health = health
        self._status_values["credential"].set(health.credential_state.value)
        self._status_values["source"].set(self._source_label(self.provider.credential_status().source))
        self._status_values["last_check"].set(self._format_check_time(health.checked_at))
        self._status_values["overall"].set(health.status.value)
        if health.ready:
            self._status_values["authentication"].set("READY")
            self._status_values["api"].set("READY")
            self._status_values["model"].set("READY")
        elif health.status is ProviderHealthStatus.AUTHENTICATION_FAILURE:
            self._status_values["authentication"].set(health.status.value)
            self._status_values["api"].set("NOT_VALIDATED")
            self._status_values["model"].set("NOT_VALIDATED")
        elif health.status in {
            ProviderHealthStatus.NETWORK_FAILURE,
            ProviderHealthStatus.TLS_HTTPS_FAILURE,
            ProviderHealthStatus.TIMEOUT,
            ProviderHealthStatus.SERVER_FAILURE,
            ProviderHealthStatus.RATE_LIMIT,
            ProviderHealthStatus.QUOTA_EXHAUSTED,
        }:
            self._status_values["authentication"].set("NOT_VALIDATED")
            self._status_values["api"].set(health.status.value)
            self._status_values["model"].set("NOT_VALIDATED")
        elif health.status is ProviderHealthStatus.MODEL_NOT_AVAILABLE:
            self._status_values["authentication"].set("NOT_VALIDATED")
            self._status_values["api"].set("NOT_VALIDATED")
            self._status_values["model"].set(health.status.value)
        else:
            self._status_values["authentication"].set("NOT_CHECKED")
            self._status_values["api"].set("NOT_CHECKED")
            self._status_values["model"].set("NOT_CHECKED")
        detail = health.message
        if health.ready and health.model is not None and health.latency_ms is not None:
            detail = f"{health.message} Model: {health.model}. Latency: {health.latency_ms} ms."
        self.message.set(detail)

    @staticmethod
    def _format_check_time(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            return "CHECKED"

    def _poll(self) -> None:
        try:
            health = self._events.get_nowait()
        except queue.Empty:
            pass
        else:
            self._cancel = None
            self._set_busy(False)
            self._apply_health(health)
        if not self._closed and self.winfo_exists():
            self._poll_id = self.after(100, self._poll)

    def open_chat(self) -> None:
        self.open_chat_command()

    def clear_history(self) -> None:
        if messagebox.askyesno(
            "Clear transmission history",
            "Clear the bounded local metadata-only external transmission history?",
            parent=self,
        ):
            try:
                self.audit.clear_history()
            except (AuditError, OSError):
                messagebox.showerror(
                    "Transmission history",
                    "The local external transmission history could not be cleared.",
                    parent=self,
                )
                return
            self.message.set("Local external transmission history cleared.")

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
