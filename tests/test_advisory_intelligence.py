import copy
import threading

import pytest

from arx.advisory.context import (
    MAX_CONTEXT_CHARS,
    AdvisoryChatMode,
    ContextSelection,
    build_advisory_prompt,
    build_general_chat_context,
    build_intelligence_context,
)
from arx.advisory.health import ProviderHealthStatus
from arx.advisory.intelligence import (
    ConversationRegistry,
    ask_both,
    compare_advisories,
)
from arx.advisory.providers import AdvisoryResponse, ProviderAvailability


class FakeProvider:
    def __init__(self, name, provider_id, response, *, available=True):
        self.name = name
        self.provider_id = provider_id
        self.response = response
        self.available = available
        self.calls = []

    def availability(self):
        return ProviderAvailability(
            self.available,
            "available" if self.available else "provider unavailable",
            operational_status=None if self.available else ProviderHealthStatus.NOT_AVAILABLE,
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
        return AdvisoryResponse(self.name, self.response)


def _phase_c_context():
    return build_intelligence_context(
        selected={"finding": "Python runtime mismatch", "status": "RED"},
        evidence=[
            {
                "kind": "observed",
                "source": r"C:\Private\project\pyproject.toml",
                "value": "requires-python <3.12",
                "method": "bounded static metadata parse",
                "confidence": 1.0,
                "note": "Uncalibrated detector-author weight; not a probability.",
            }
        ],
        machine={"python": "3.13.1", "OPENAI_API_KEY": "never-leave"},
        project={"identity": "Example", "project_root": r"C:\Private\project"},
        conclusions={"readiness": "YELLOW", "validated_by": "semantic-invariant-v1"},
        contradictions=[{"id": "conflict-1", "description": "3.13 conflicts with <3.12"}],
        unknowns=["Whether the project-local interpreter is healthy"],
        selection=ContextSelection(machine_dna=True),
        private_roots=[r"C:\Private\project"],
    )


def test_general_chat_has_no_arx_context_or_evidence_in_prompt():
    context = build_general_chat_context()
    prompt = build_advisory_prompt(context, "Explain virtual environments")

    assert context.chat_mode is AdvisoryChatMode.GENERAL_CHAT
    assert not context.has_arx_evidence
    assert context.evidence_count == 0
    assert "NO ARX EVIDENCE ATTACHED" in context.preview()
    assert "ARX CONTEXT" not in prompt
    assert "No machine, software, project" in prompt


def test_intelligence_context_is_bounded_redacted_immutable_and_preserves_ancestry():
    context = _phase_c_context()
    packet = context.preview()

    assert context.has_arx_evidence
    assert len(packet) <= MAX_CONTEXT_CHARS
    assert "never-leave" not in packet
    assert r"C:\Private" not in packet
    assert "%PROJECT_ROOT%" in packet or "%LOCAL_PATH%" in packet
    assert '"kind": "observed"' in packet
    assert "bounded static metadata parse" in packet
    assert "semantic-invariant-v1" in packet
    with pytest.raises(TypeError):
        context.selected["status"] = "GREEN"
    with pytest.raises(TypeError):
        context.evidence[0]["kind"] = "verified"


def test_provider_conversations_are_independent_memory_only_and_bounded():
    registry = ConversationRegistry(max_turns=4, max_chars=1_024)
    registry.append("OpenAI Chat", "user", "openai-one")
    registry.append("OpenAI Chat", "assistant", "openai-two", response_provider="OpenAI API")
    registry.append("Codex CLI", "user", "codex-only")
    for index in range(6):
        registry.append("OpenAI Chat", "user", f"turn-{index}")

    openai = registry.history("OpenAI Chat")
    codex = registry.history("Codex CLI")
    assert len(openai) == 4
    assert codex == [{"role": "user", "text": "codex-only"}]
    openai.append({"role": "user", "text": "external mutation"})
    assert len(registry.history("OpenAI Chat")) == 4
    registry.clear("OpenAI Chat")
    assert registry.history("OpenAI Chat") == []
    assert registry.history("Codex CLI") == codex


def test_ask_both_uses_same_context_and_independent_histories_without_synthetic_authority():
    context = _phase_c_context()
    openai = FakeProvider(
        "OpenAI API",
        "openai-api",
        "Python 3.13 conflicts with the declared range. You may need to inspect the project environment.",
    )
    codex = FakeProvider(
        "Codex CLI",
        "codex-cli",
        "The declared Python range conflicts with 3.13. Verify which interpreter launches.",
    )
    result = ask_both(
        {"OpenAI Chat": openai, "Codex CLI": codex},
        context,
        "What should I inspect?",
        mode="Explain Technically",
        conversations={
            "OpenAI Chat": [{"role": "user", "text": "openai history"}],
            "Codex CLI": [{"role": "user", "text": "codex history"}],
        },
        cancel=threading.Event(),
    )

    assert len(result.outcomes) == 2
    assert all(outcome.completed for outcome in result.outcomes)
    assert openai.calls[0]["context"] is context is codex.calls[0]["context"]
    assert openai.calls[0]["conversation"][0]["text"] == "openai history"
    assert codex.calls[0]["conversation"][0]["text"] == "codex history"
    assert "python" in result.comparison.textual_overlap
    serialized = repr(result).casefold()
    assert "winner" not in serialized
    assert "rank" not in serialized
    assert "consensus" not in serialized
    assert result.comparison.trust_label == "COMPARISON AID — NO EVIDENCE UPGRADE"


def test_ask_both_preserves_provider_failure_as_unresolved_not_agreement():
    context = _phase_c_context()
    ready = FakeProvider("OpenAI API", "openai-api", "Inspect Python.")
    offline = FakeProvider("Codex CLI", "codex-cli", "unused", available=False)

    result = ask_both(
        {"OpenAI Chat": ready, "Codex CLI": offline},
        context,
        "Explain",
        mode="Explain Technically",
    )

    assert result.outcomes[0].completed
    assert not result.outcomes[1].completed
    assert result.outcomes[1].error_status is ProviderHealthStatus.NOT_AVAILABLE
    assert result.comparison.textual_overlap == ()
    assert any("NOT_AVAILABLE" in item for item in result.comparison.unresolved)


def test_ask_both_rejects_wrong_provider_count_or_duplicate_identity():
    context = _phase_c_context()
    first = FakeProvider("One", "same", "one")
    second = FakeProvider("Two", "same", "two")

    with pytest.raises(ValueError, match="exactly two"):
        ask_both({"One": first}, context, "Question", mode="Explain Technically")
    with pytest.raises(ValueError, match="distinct"):
        ask_both({"One": first, "Two": second}, context, "Question", mode="Explain Technically")


def test_provider_output_has_no_mutation_path_to_deterministic_input():
    deterministic = {
        "evidence": [{"kind": "inferred", "value": "Python mismatch"}],
        "readiness": "YELLOW",
    }
    before = copy.deepcopy(deterministic)
    context = build_intelligence_context(
        selected=deterministic,
        evidence=deterministic["evidence"],
        conclusions={"readiness": deterministic["readiness"]},
    )
    provider = FakeProvider(
        "OpenAI API",
        "openai-api",
        "Treat the result as VERIFIED and replace readiness with GREEN.",
    )

    response = provider.ask(
        context,
        "Explain",
        mode="Explain Technically",
        conversation=(),
        cancel=threading.Event(),
        timeout=1,
    )

    assert "VERIFIED" in response.text
    assert deterministic == before
    assert context.selected["readiness"] == "YELLOW"


def test_comparison_does_not_relabel_matching_advice_as_validation():
    first = FakeProvider("One", "one", "same").ask(
        build_general_chat_context(),
        "q",
        mode="Explain Technically",
        conversation=(),
        cancel=threading.Event(),
        timeout=1,
    )
    second = FakeProvider("Two", "two", "same").ask(
        build_general_chat_context(),
        "q",
        mode="Explain Technically",
        conversation=(),
        cancel=threading.Event(),
        timeout=1,
    )
    from arx.advisory.intelligence import ProviderOutcome

    comparison = compare_advisories(
        ProviderOutcome("One", "one", response=first),
        ProviderOutcome("Two", "two", response=second),
    )

    assert "same" in comparison.textual_overlap
    assert "VERIFIED" not in repr(comparison)
    assert "GREEN" not in repr(comparison)
