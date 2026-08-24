import json
import time

import pytest

from arx.advisory.audit import TransmissionAudit, TransmissionEvent, TransportState
from arx.advisory.credentials import ProviderCredentialResolver, WindowsDPAPICredentialStore
from arx.advisory.health import checked_now
from arx.advisory.providers import OpenAIProvider
from arx.desktop.app import ARXDesktopApp
from arx.desktop.provider_settings import OPENAI_API_KEYS_URL, OpenAIProviderSettingsWindow
from arx.desktop.ux import UIStateStore


FIRST = b"sk-" + b"proj-arx4-settings-fixture-first"
SECOND = b"sk-" + b"proj-arx4-settings-fixture-second"


@pytest.fixture(autouse=True)
def _avoid_modal_dialogs(monkeypatch):
    monkeypatch.setattr("arx.desktop.provider_settings.messagebox.showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr("arx.desktop.provider_settings.messagebox.showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr("arx.desktop.provider_settings.messagebox.askyesno", lambda *args, **kwargs: True)


def _store(tmp_path, *, unreadable=False):
    def protect(value):
        return b"protected:" + bytes(reversed(value))

    def unprotect(value):
        if unreadable:
            raise OSError("wrong Windows user")
        return bytearray(reversed(value.removeprefix(b"protected:")))

    return WindowsDPAPICredentialStore(
        "openai-api",
        path=tmp_path / "openai-api.dpapi",
        protector=protect,
        unprotector=unprotect,
    )


def _provider(store, transport, audit):
    resolver = ProviderCredentialResolver(
        "openai-api",
        "OPENAI_API_KEY",
        store,
        environment_getter=lambda _name: None,
    )
    return OpenAIProvider(
        model="gpt-test",
        credential_resolver=resolver,
        transport=transport,
        audit=audit,
    )


def _drain(root, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    root.update()
    assert predicate()


def _button_texts(widget):
    found = []
    for child in widget.winfo_children():
        try:
            text = child.cget("text")
        except Exception:
            text = ""
        if text:
            found.append(str(text))
        found.extend(_button_texts(child))
    return found


def test_settings_menu_path_and_window_actions_are_visible_without_transmission(tmp_path):
    store = _store(tmp_path)
    calls = []
    audit = TransmissionAudit(tmp_path / "audit.jsonl")
    provider = _provider(store, lambda *_args: calls.append(True) or b"{}", audit)
    app = ARXDesktopApp(
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        advisory_providers={"OpenAI Chat": provider},
        openai_credential_store=store,
        transmission_audit=audit,
    )
    app.withdraw()
    menu = app.nametowidget(app.cget("menu"))
    settings_index = next(index for index in range(menu.index("end") + 1) if menu.entrycget(index, "label") == "Settings")
    settings = app.nametowidget(menu.entrycget(settings_index, "menu"))
    intelligence = app.nametowidget(settings.entrycget(0, "menu"))

    assert settings.entrycget(0, "label") == "Intelligence Providers"
    assert intelligence.entrycget(0, "label") == "OpenAI API…"
    app._open_openai_settings()
    window = app._provider_settings_windows[0]
    window.withdraw()

    assert calls == []
    assert window._status_values["credential"].get() == "NOT_CONFIGURED"
    assert {
        "Configure OpenAI API Key",
        "Import OpenAI API Key",
        "Replace Credential",
        "Remove Credential",
        "Test Connection",
        "Open OpenAI Chat",
    }.issubset(set(_button_texts(window)))
    window._close()
    app.destroy()


def test_settings_import_replace_test_remove_and_open_chat_never_display_plaintext(monkeypatch, tmp_path):
    store = _store(tmp_path)
    audit = TransmissionAudit(tmp_path / "audit.jsonl")
    captured = {}

    def transport(request, timeout):
        captured["method"] = request.method
        captured["body"] = request.data
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return json.dumps({"id": "gpt-test", "object": "model"}).encode()

    provider = _provider(store, transport, audit)
    app = ARXDesktopApp(
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        advisory_providers={"OpenAI Chat": provider},
        openai_credential_store=store,
        transmission_audit=audit,
    )
    app.withdraw()
    opened_urls = []
    opened_chats = []
    window = OpenAIProviderSettingsWindow(
        app,
        provider,
        store,
        audit,
        open_chat_command=lambda: opened_chats.append(True),
        platform_opener=lambda url: opened_urls.append(url) or True,
    )
    window.withdraw()
    first_file = tmp_path / "first.txt"
    first_file.write_bytes(FIRST)
    second_file = tmp_path / "second.txt"
    second_file.write_bytes(SECOND)

    window.configure_credential()
    assert opened_urls == [OPENAI_API_KEYS_URL]
    monkeypatch.setattr("arx.desktop.provider_settings.filedialog.askopenfilename", lambda **_kwargs: str(first_file))
    window.import_credential()

    assert window._status_values["credential"].get() == "CONFIGURED"
    assert window._status_values["source"].get() == "Secure Windows Store"
    visible = "\n".join(_button_texts(window) + [value.get() for value in window._status_values.values()] + [window.message.get()])
    assert FIRST.decode() not in visible
    assert FIRST not in store.path.read_bytes()

    window.test_connection()
    _drain(app, lambda: window._cancel is None)

    assert captured["method"] == "GET"
    assert captured["body"] is None
    assert captured["authorization"] == f"Bearer {FIRST.decode()}"
    assert window._status_values["authentication"].get() == "READY"
    assert window._status_values["api"].get() == "READY"
    assert window._status_values["model"].get() == "READY"
    assert window._status_values["overall"].get() == "READY"

    monkeypatch.setattr("arx.desktop.provider_settings.filedialog.askopenfilename", lambda **_kwargs: str(second_file))
    window.replace_credential()
    with store.lease() as secret:
        assert secret.text() == SECOND.decode()
    visible = "\n".join(_button_texts(window) + [value.get() for value in window._status_values.values()] + [window.message.get()])
    assert SECOND.decode() not in visible

    window.open_chat()
    assert opened_chats == [True]
    window.remove_credential()
    assert window._status_values["credential"].get() == "NOT_CONFIGURED"
    assert not store.exists()
    window._close()
    app.destroy()


def test_settings_unreadable_state_and_explicit_audit_clear_are_safe(tmp_path):
    store = _store(tmp_path, unreadable=True)
    store.path.write_bytes(b"ARX4-DPAPI-CREDENTIAL\x00\x01protected:opaque")
    audit = TransmissionAudit(tmp_path / "audit.jsonl")
    audit.record(
        TransmissionEvent(
            timestamp=checked_now(),
            attempt_id="fixture",
            provider_id="openai-api",
            operation="health_check",
            state=TransportState.REQUEST_PREPARED,
        )
    )
    provider = _provider(store, lambda *_args: b"{}", audit)
    app = ARXDesktopApp(
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        advisory_providers={"OpenAI Chat": provider},
        openai_credential_store=store,
        transmission_audit=audit,
    )
    app.withdraw()
    window = OpenAIProviderSettingsWindow(
        app,
        provider,
        store,
        audit,
        open_chat_command=lambda: None,
    )
    window.withdraw()

    assert window._status_values["credential"].get() == "CREDENTIAL_UNREADABLE"
    assert "cannot be decrypted in the current Windows context" in window.message.get()
    assert audit.history()
    window.clear_history()
    assert audit.history() == []
    window._close()
    app.destroy()
