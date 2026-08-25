import time
import urllib.parse

import pytest

from arx.advisory.audit import MemoryTransmissionAudit
from arx.advisory.context import (
    ANALYSIS_MODES,
    ContextSelection,
    build_advisory_context,
    build_general_chat_context,
    build_intelligence_context,
)
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryResponse,
    ProviderAvailability,
)
from arx.desktop.advisory import (
    AdvisoryWindow,
    ContextInspectorWindow,
    render_conversation,
)
from arx.desktop.app import ARXDesktopApp
from arx.desktop.ux import UIStateStore


@pytest.fixture(autouse=True)
def _avoid_modal_error_dialogs(monkeypatch):
    monkeypatch.setattr("arx.desktop.advisory.messagebox.showerror", lambda *args, **kwargs: None)


class FakeProvider:
    name = "Fake"

    def __init__(self, *, available=True, response="A bounded explanation", wait_for_cancel=False):
        self.available = available
        self.response = response
        self.wait_for_cancel = wait_for_cancel
        self.calls = []

    def availability(self):
        return ProviderAvailability(
            self.available,
            "Fake provider is available." if self.available else "Fake provider is offline.",
            "fake-1.0" if self.available else None,
        )

    def ask(self, context, question, *, mode, conversation, cancel, timeout):
        self.calls.append(
            {
                "context": context,
                "question": question,
                "mode": mode,
                "conversation": list(conversation),
                "cancel": cancel,
                "timeout": timeout,
            }
        )
        if self.wait_for_cancel:
            while not cancel.wait(0.01):
                pass
            raise AdvisoryCancelled("Cancelled by the test user.")
        return AdvisoryResponse(self.name, self.response)


def _context():
    return build_advisory_context(
        "Compatibility finding",
        ("check", "status", "required", "observed", "reason"),
        ("Python", "RED", "<3.12", "3.13", r"C:\Private\build.log: provider mismatch"),
        project={"identity": "Example", "constraint": "<3.12"},
        evidence=[{"kind": "observed", "source": r"C:\Private\report.json", "value": "3.13"}],
    )


def _drain(root, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    root.update()
    assert predicate()


def test_advisory_window_requires_consent_before_provider_call(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    provider = FakeProvider()
    window = AdvisoryWindow(
        app,
        _context(),
        {"Fake": provider},
        consent_command=lambda _provider, _context: False,
    )
    window.withdraw()

    window.ask()

    assert provider.calls == []
    assert window.operation_status.cget("text") == "Cancelled — no information was sent."
    window._close()
    app.destroy()


def test_advisory_window_runs_in_background_and_keeps_ai_output_separate(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    provider = FakeProvider(response="Technical interpretation")
    saved = []
    window = AdvisoryWindow(
        app,
        _context(),
        {"Fake": provider},
        consent_command=lambda _provider, _context: True,
        save_command=lambda kind, content: saved.append((kind, content)),
    )
    window.withdraw()
    window.question.delete(0, "end")
    window.question.insert(0, r"Explain C:\Private\source.py TOKEN=abcdefghijklmnop")

    window.ask()
    assert window._running
    _drain(app, lambda: not window._running)

    assert provider.calls
    assert r"C:\Private" not in provider.calls[0]["question"]
    assert "abcdefghijklmnop" not in provider.calls[0]["question"]
    conversation = window.conversation.get("1.0", "end-1c")
    assert "AI ADVISORY — NON-AUTHORITATIVE" in conversation
    assert "FAKE" in conversation
    assert "Technical interpretation" in conversation
    assert window.operation_status.cget("text") == "Completed"
    window.save_conversation()
    assert saved and "AI ADVISORY" in saved[0][1]
    window._close()
    app.destroy()


def test_advisory_window_cancels_cooperatively_without_freezing(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    provider = FakeProvider(wait_for_cancel=True)
    window = AdvisoryWindow(app, _context(), {"Fake": provider})
    window.withdraw()

    window.ask()
    _drain(app, lambda: bool(provider.calls))
    window.cancel()
    _drain(app, lambda: not window._running)

    assert provider.calls[0]["cancel"].is_set()
    assert window.operation_status.cget("text") == "Cancelled"
    window._close()
    app.destroy()


def test_advisory_modes_construct_prompts_and_preserve_custom_questions(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    window = AdvisoryWindow(app, _context(), {"Fake": FakeProvider()})
    window.withdraw()

    window.mode.set("Suggest Safe Fix")
    window._mode_changed()
    assert window.question.get() == ANALYSIS_MODES["Suggest Safe Fix"]
    assert "Do not execute anything" in window.prompt()
    window.question.delete(0, "end")
    window.question.insert(0, "My specific question")
    window.mode.set("Compare Alternatives")
    window._mode_changed()
    assert window.question.get() == "My specific question"
    window._close()
    app.destroy()


def test_unavailable_or_empty_provider_configuration_does_not_break_core_ui(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    app.machine_tree.insert("", "end", iid="row", values=("Python", "RED", "3.13", "", "", "provider mismatch"))
    app.machine_tree.selection_set("row")

    labels = [action.label for action in app._tree_menu_actions(app.machine_tree) if action.label]

    assert not any(label.startswith(("Ask OpenAI", "Ask Codex")) for label in labels)
    assert "Search Web About This…" in labels
    assert "View Raw Data" in labels
    offline = AdvisoryWindow(app, _context(), {"Offline": FakeProvider(available=False)})
    offline.withdraw()
    assert str(offline.ask_button.cget("state")) == "disabled"
    assert "offline" in offline.availability.cget("text").casefold()
    offline._close()
    app.destroy()


def test_app_consent_is_remembered_only_for_the_current_provider_session(monkeypatch, tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    prompts = []
    monkeypatch.setattr(
        "arx.desktop.app.messagebox.askyesno",
        lambda *args, **kwargs: prompts.append((args, kwargs)) or True,
    )

    assert app._confirm_advisory_consent("Fake", _context())
    assert app._confirm_advisory_consent("Fake", _context())

    assert len(prompts) == 1
    assert "bounded, redacted diagnostic context" in prompts[0][0][1]
    app.destroy()


def test_web_search_bridge_is_explicit_redacted_and_url_encoded(monkeypatch, tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    opened = []
    monkeypatch.setattr("arx.desktop.app.open_search", lambda url: opened.append(url))

    app._search_context(_context(), "exact_error", "google")

    assert len(opened) == 1
    parsed = urllib.parse.urlparse(opened[0])
    query = urllib.parse.parse_qs(parsed.query)["q"][0]
    assert parsed.hostname == "www.google.com"
    assert r"C:\Private" not in query
    assert "provider mismatch" in query
    app.destroy()


def test_rendered_conversation_reapplies_redaction_before_export(monkeypatch):
    monkeypatch.setenv("USERNAME", "PrivateUser")
    rendered = render_conversation(
        [
            {"role": "user", "text": r"Read C:\Secret\report.txt TOKEN=abcdefghijklmnop"},
            {"role": "assistant", "text": "PrivateUser should inspect it"},
        ]
    )

    assert r"C:\Secret" not in rendered
    assert "abcdefghijklmnop" not in rendered
    assert "PrivateUser" not in rendered
    assert "YOU" in rendered and "AI ADVISORY" in rendered


def test_provider_switching_preserves_independent_multi_turn_conversations(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    openai = FakeProvider(response="OpenAI-only response")
    codex = FakeProvider(response="Codex-only response")
    window = AdvisoryWindow(
        app,
        _context(),
        {"OpenAI Chat": openai, "Codex CLI": codex},
        consent_command=lambda _provider, _context: True,
    )
    window.withdraw()

    window.provider_name.set("OpenAI Chat")
    window._provider_changed()
    window.question.delete(0, "end")
    window.question.insert(0, "OpenAI question")
    window.ask()
    _drain(app, lambda: not window._running)

    window.provider_name.set("Codex CLI")
    window._provider_changed()
    assert "OpenAI-only response" not in window.conversation.get("1.0", "end-1c")
    window.question.delete(0, "end")
    window.question.insert(0, "Codex question")
    window.ask()
    _drain(app, lambda: not window._running)

    assert [turn["text"] for turn in window.sessions.history("OpenAI Chat")] == [
        "OpenAI question",
        "OpenAI-only response",
    ]
    assert [turn["text"] for turn in window.sessions.history("Codex CLI")] == [
        "Codex question",
        "Codex-only response",
    ]
    assert "CODEX-ONLY RESPONSE" not in window.sessions.history("OpenAI Chat")[1]["text"].upper()
    window._close()
    app.destroy()


def test_ask_both_runs_two_flat_unranked_provider_responses(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    openai = FakeProvider(response="Python mismatch may require inspection")
    openai.provider_id = "openai-api"
    codex = FakeProvider(response="Inspect the Python mismatch and verify the runtime")
    codex.provider_id = "codex-cli"
    window = AdvisoryWindow(
        app,
        _context(),
        {"OpenAI Chat": openai, "Codex CLI": codex},
        consent_command=lambda _provider, _context: True,
    )
    window.withdraw()
    window.question.delete(0, "end")
    window.question.insert(0, "What should I inspect?")

    window.ask_both()
    _drain(app, lambda: not window._running)

    assert len(openai.calls) == len(codex.calls) == 1
    assert openai.calls[0]["context"] is codex.calls[0]["context"]
    assert window._result_windows
    result = window._result_windows[0].result
    result_window = window._result_windows[0]
    assert [item.provider_label for item in result.outcomes] == ["OpenAI Chat", "Codex CLI"]
    assert all(item.completed for item in result.outcomes)
    assert "winner" not in repr(result).casefold()
    assert "consensus" not in repr(result).casefold()
    assert not result_window.comparison_visible
    result_window.show_comparison()
    assert result_window.comparison_visible
    window._close()
    app.destroy()


def test_general_chat_can_attach_preview_and_detach_bounded_arx_context(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    captured = []

    def build(selection):
        captured.append(selection)
        return build_intelligence_context(
            selected={"finding": "Python mismatch", "status": "YELLOW"},
            evidence=[{"kind": "observed", "source": r"C:\Private\report.json", "value": "3.13"}],
            selection=selection,
        )

    window = AdvisoryWindow(
        app,
        build_general_chat_context(),
        {"Fake": FakeProvider()},
        context_builder=build,
        audit=MemoryTransmissionAudit(),
    )
    window.withdraw()

    assert not window.context.has_arx_evidence
    assert "NONE" in window.context.summary()
    for variable in window._scope_variables.values():
        variable.set(False)
    window._scope_variables["selected_finding"].set(True)
    window._scope_variables["relevant_evidence"].set(True)
    window.attach_selected_context()
    assert captured == [
        ContextSelection(
            selected_finding=True,
            relevant_evidence=True,
            machine_dna=False,
            software_dna=False,
            project_dna=False,
            conclusions=False,
            contradictions=False,
            unknowns=False,
        )
    ]
    assert window.context.has_arx_evidence
    assert r"C:\Private" not in window.context.preview()
    window.detach_context()
    assert not window.context.has_arx_evidence
    window._close()
    app.destroy()


def test_context_inspector_keeps_evidence_contradictions_and_unknowns_separate(tmp_path):
    app = ARXDesktopApp(advisory_providers={}, state_store=UIStateStore(tmp_path / "ui-state.json"))
    app.withdraw()
    context = build_intelligence_context(
        selected={"finding": "Mismatch", "status": "YELLOW"},
        evidence=[{"kind": "observed", "source": "fixture", "value": "3.13"}],
        contradictions=[{"id": "conflict-1", "description": "constraint mismatch"}],
        unknowns=["project-local runtime health"],
    )

    inspector = ContextInspectorWindow(app, context, initial_tab="Contradictions")
    inspector.withdraw()

    assert [inspector.tabs.tab(item, "text") for item in inspector.tabs.tabs()] == [
        "Overview",
        "Evidence",
        "Contradictions",
        "Unknowns",
    ]
    assert inspector.tabs.tab(inspector.tabs.select(), "text") == "Contradictions"
    assert "observed" in inspector.views["Evidence"].get("1.0", "end")
    assert "conflict-1" in inspector.views["Contradictions"].get("1.0", "end")
    assert "runtime health" in inspector.views["Unknowns"].get("1.0", "end")
    inspector.destroy()
    app.destroy()
