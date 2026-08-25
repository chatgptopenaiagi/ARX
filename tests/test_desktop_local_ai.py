import time

from arx.advisory.audit import MemoryTransmissionAudit
from arx.desktop.advisory import AdvisoryWindow
from arx.desktop.app import ARXDesktopApp
from arx.desktop.local_ai_settings import LocalAISettingsWindow
from arx.desktop.ux import UIStateStore
from arx.local_ai import (
    LocalAIApprovalStore,
    LocalAIDiscovery,
    LocalAIManager,
    LocalAIProfileStore,
    LocalAIState,
)


def _manager(tmp_path, transport):
    discovery = LocalAIDiscovery(transport=transport)
    return LocalAIManager(
        profile_store=LocalAIProfileStore(tmp_path / "profiles.json"),
        approval_store=LocalAIApprovalStore(tmp_path / "approvals.json"),
        discovery=discovery,
    )


def _drain(root, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for the local AI desktop operation")


def _submenu(menu, label):
    for index in range(menu.index("end") + 1):
        if menu.entrycget(index, "label") == label:
            return menu.nametowidget(menu.entrycget(index, "menu"))
    raise AssertionError(f"Menu not found: {label}")


def test_local_ai_settings_and_console_are_mouse_accessible_without_open_side_effects(tmp_path):
    calls = []
    manager = _manager(tmp_path, lambda *_args: calls.append(True) or b'{"data":[{"id":"local-model"}]}')
    app = ARXDesktopApp(
        advisory_providers={},
        local_ai_manager=manager,
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        transmission_audit=MemoryTransmissionAudit(),
    )
    app.withdraw()
    root_menu = app.nametowidget(app.cget("menu"))
    settings = _submenu(root_menu, "Settings")
    providers = _submenu(settings, "Intelligence Providers")
    intelligence = _submenu(root_menu, "Intelligence")

    assert [providers.entrycget(index, "label") for index in range(providers.index("end") + 1)] == [
        "OpenAI API…",
        "Local AI…",
    ]
    assert "Local AI General Chat…" in [
        intelligence.entrycget(index, "label") for index in range(intelligence.index("end") + 1)
    ]

    app._open_local_ai_settings()
    window = app._provider_settings_windows[-1]
    window.withdraw()

    assert isinstance(window, LocalAISettingsWindow)
    assert calls == []
    assert manager.runtime().state is LocalAIState.NOT_FOUND
    assert window._status_values["capability"].get() == "NOT IN USE"
    assert "does not probe" in next(
        child.cget("text")
        for child in window.winfo_children()[0].winfo_children()
        if child.winfo_class() == "TLabel" and "does not probe" in str(child.cget("text"))
    )

    window._close()
    app.destroy()


def test_explicit_local_discovery_enables_existing_intelligence_console_path(tmp_path):
    calls = []

    def transport(request, _timeout):
        calls.append(request.full_url)
        return b'{"data":[{"id":"local-model"}],"version":"fixture"}'

    manager = _manager(tmp_path, transport)
    app = ARXDesktopApp(
        advisory_providers={},
        local_ai_manager=manager,
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        transmission_audit=MemoryTransmissionAudit(),
    )
    app.withdraw()
    app._open_local_ai_settings()
    settings = app._provider_settings_windows[-1]
    settings.withdraw()
    settings.discover()
    _drain(app, lambda: not settings._running)

    assert calls == ["http://127.0.0.1:8000/v1/models"]
    assert settings._status_values["state"].get() == "READY"
    assert str(settings.chat_button.cget("state")) == "normal"

    app._open_local_ai_chat()
    console = app._advisory_windows[-1]
    console.withdraw()

    assert isinstance(console, AdvisoryWindow)
    assert list(console.providers) == ["Local AI"]
    assert console.provider_name.get() == "Local AI"
    assert not console.context.has_arx_evidence
    assert str(console.ask_both_button.cget("state")) == "disabled"
    assert "local-ai-local-default" in str(console.availability.cget("text"))

    console._close()
    settings._close()
    app.destroy()


def test_invalid_non_loopback_profile_fails_closed_without_discovery(tmp_path, monkeypatch):
    calls = []
    manager = _manager(tmp_path, lambda *_args: calls.append(True) or b"{}")
    app = ARXDesktopApp(
        advisory_providers={},
        local_ai_manager=manager,
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        transmission_audit=MemoryTransmissionAudit(),
    )
    app.withdraw()
    app._open_local_ai_settings()
    settings = app._provider_settings_windows[-1]
    settings.withdraw()
    errors = []
    monkeypatch.setattr("arx.desktop.local_ai_settings.messagebox.showerror", lambda *args, **kwargs: errors.append(args))
    settings.endpoint.set("http://0.0.0.0:8000")

    settings.discover()

    assert errors
    assert calls == []
    assert manager.runtime().state is LocalAIState.NOT_FOUND
    settings._close()
    app.destroy()


def test_context_menu_exposes_local_ai_without_changing_two_provider_ask_both(tmp_path):
    manager = _manager(tmp_path, lambda *_args: b'{"data":[{"id":"local-model"}]}')
    app = ARXDesktopApp(
        local_ai_manager=manager,
        state_store=UIStateStore(tmp_path / "ui-state.json"),
        transmission_audit=MemoryTransmissionAudit(),
    )
    app.withdraw()
    app.machine_tree.insert("", "end", iid="row", values=("Tool", "READY", "1", "", "HEALTHY", "fixture"))
    app.machine_tree.selection_set("row")

    labels = [action.label for action in app._tree_menu_actions(app.machine_tree) if action.label]

    assert "Ask Local AI About This…" in labels
    assert "Open Ask Both…" in labels
    assert list(app._advisory_providers) == ["OpenAI Chat", "Codex CLI"]
    app.destroy()
