"""Provider-neutral in-session conversation and two-provider comparison models."""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .context import MAX_FIELD_CHARS, AdvisoryContext, redact_external
from .health import ProviderHealthStatus
from .providers import (
    AdvisoryCancelled,
    AdvisoryResponse,
    AdvisoryTimeout,
    AIProvider,
    ProviderError,
)

MAX_CONVERSATION_TURNS = 16
MAX_CONVERSATION_CHARS = 24_000
MAX_COMPARISON_ITEMS = 8
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{2,}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
_UNCERTAINTY = re.compile(
    r"\b(?:assum(?:e|ed|ing|ption)|cannot|could|may|might|need(?:s|ed)?|unclear|unknown|unresolved|verify)\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "about",
    "after",
    "also",
    "because",
    "before",
    "could",
    "from",
    "have",
    "into",
    "might",
    "should",
    "that",
    "their",
    "there",
    "these",
    "this",
    "with",
    "would",
}


class ConversationRegistry:
    """Bounded, memory-only conversations isolated by provider label."""

    def __init__(
        self,
        *,
        max_turns: int = MAX_CONVERSATION_TURNS,
        max_chars: int = MAX_CONVERSATION_CHARS,
    ):
        if max_turns < 2 or max_chars < 1_024:
            raise ValueError("Conversation bounds are too small for safe multi-turn use.")
        self.max_turns = max_turns
        self.max_chars = max_chars
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def history(self, provider: str) -> list[dict[str, str]]:
        return [dict(turn) for turn in self._sessions.get(provider, ())]

    def append(self, provider: str, role: str, text: str, *, response_provider: str | None = None) -> None:
        normalized_role = "assistant" if role.casefold() == "assistant" else "user"
        safe_text = str(redact_external(text, max_text_chars=MAX_FIELD_CHARS * 2)).strip()
        if not safe_text:
            return
        turn = {"role": normalized_role, "text": safe_text}
        if normalized_role == "assistant":
            turn["provider"] = str(redact_external(response_provider or provider))
        session = self._sessions.setdefault(provider, [])
        session.append(turn)
        self._trim(session)

    def _trim(self, session: list[dict[str, str]]) -> None:
        while len(session) > self.max_turns:
            session.pop(0)
        while session and sum(len(turn.get("text", "")) for turn in session) > self.max_chars:
            session.pop(0)

    def clear(self, provider: str) -> None:
        self._sessions.pop(provider, None)

    def clear_all(self) -> None:
        self._sessions.clear()

    def providers(self) -> tuple[str, ...]:
        return tuple(self._sessions)


@dataclass(frozen=True)
class ProviderOutcome:
    provider_label: str
    provider_identity: str
    response: AdvisoryResponse | None = None
    error_status: ProviderHealthStatus | None = None
    error_message: str | None = None

    @property
    def completed(self) -> bool:
        return self.response is not None

    def display_text(self) -> str:
        if self.response is not None:
            return str(redact_external(self.response.text))
        return str(redact_external(self.error_message or "The provider did not return a response."))


@dataclass(frozen=True)
class AdvisoryComparison:
    """Presentation aids only; this object is not ARX evidence or validation."""

    textual_overlap: tuple[str, ...]
    differences: tuple[str, ...]
    unresolved: tuple[str, ...]
    trust_label: str = "COMPARISON AID — NO EVIDENCE UPGRADE"


@dataclass(frozen=True)
class AskBothResult:
    outcomes: tuple[ProviderOutcome, ProviderOutcome]
    comparison: AdvisoryComparison
    trust_label: str = "AI ADVISORY — NON-AUTHORITATIVE"


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in _SENTENCE.split(text) if item.strip()]


def _terms(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _WORD.findall(text)
        if token.casefold() not in _STOP_WORDS and len(token) > 3
    }


def compare_advisories(first: ProviderOutcome, second: ProviderOutcome) -> AdvisoryComparison:
    """Compare surface text without ranking, synthesis, or provenance changes."""

    if not first.completed or not second.completed:
        unavailable = tuple(
            f"{outcome.provider_label}: {outcome.error_status.value if outcome.error_status else 'NO_RESPONSE'}"
            for outcome in (first, second)
            if not outcome.completed
        )
        return AdvisoryComparison((), (), unavailable or ("Both provider responses are required for textual comparison.",))

    first_text = first.display_text()
    second_text = second.display_text()
    shared_terms = tuple(sorted(_terms(first_text) & _terms(second_text))[:MAX_COMPARISON_ITEMS])
    first_sentences = _sentences(first_text)
    second_sentences = _sentences(second_text)
    first_term_sets = [_terms(item) for item in first_sentences]
    second_term_sets = [_terms(item) for item in second_sentences]

    def distinctive(sentences: Sequence[str], own: Sequence[set[str]], other: Sequence[set[str]], label: str) -> list[str]:
        result: list[str] = []
        other_union = set().union(*other) if other else set()
        for sentence, terms in zip(sentences, own):
            if terms and len(terms - other_union) >= max(1, len(terms) // 2):
                result.append(f"{label}: {sentence[:500]}")
            if len(result) >= MAX_COMPARISON_ITEMS // 2:
                break
        return result

    differences = tuple(
        [
            *distinctive(first_sentences, first_term_sets, second_term_sets, first.provider_label),
            *distinctive(second_sentences, second_term_sets, first_term_sets, second.provider_label),
        ][:MAX_COMPARISON_ITEMS]
    )
    unresolved = tuple(
        f"{outcome.provider_label}: {sentence[:500]}"
        for outcome, sentences in ((first, first_sentences), (second, second_sentences))
        for sentence in sentences
        if _UNCERTAINTY.search(sentence)
    )[:MAX_COMPARISON_ITEMS]
    if not unresolved:
        unresolved = (
            "No explicit uncertainty phrase was detected; deterministic ARX evidence is still required to resolve either advisory.",
        )
    return AdvisoryComparison(shared_terms, differences, unresolved)


def _provider_identity(label: str, provider: AIProvider) -> str:
    identity = str(getattr(provider, "provider_id", "") or getattr(provider, "name", "") or label)
    return str(redact_external(identity))[:128]


def ask_both(
    providers: Mapping[str, AIProvider],
    context: AdvisoryContext,
    question: str,
    *,
    mode: str,
    conversations: Mapping[str, Sequence[Mapping[str, str]]] | None = None,
    cancel: threading.Event | None = None,
    timeout: float = 90,
) -> AskBothResult:
    """Request exactly two independent advisories using the same approved context."""

    configured = tuple(providers.items())
    if len(configured) != 2:
        raise ValueError("Ask Both requires exactly two configured providers.")
    identities = tuple(_provider_identity(label, provider) for label, provider in configured)
    if len(set(identities)) != 2:
        raise ValueError("Ask Both requires two distinct provider identities.")
    cancellation = cancel or threading.Event()
    histories = conversations or {}

    def invoke(label: str, provider: AIProvider, identity: str) -> ProviderOutcome:
        availability = provider.availability()
        if not availability.available:
            return ProviderOutcome(
                label,
                identity,
                error_status=availability.operational_status or ProviderHealthStatus.NOT_AVAILABLE,
                error_message=availability.reason,
            )
        try:
            response = provider.ask(
                context,
                question,
                mode=mode,
                conversation=tuple(histories.get(label, ())),
                cancel=cancellation,
                timeout=timeout,
            )
            return ProviderOutcome(label, identity, response=response)
        except (AdvisoryCancelled, AdvisoryTimeout, ProviderError) as exc:
            return ProviderOutcome(label, identity, error_status=exc.status, error_message=str(exc))
        except Exception:  # noqa: BLE001 - provider plugins are isolated at this boundary
            return ProviderOutcome(
                label,
                identity,
                error_status=ProviderHealthStatus.SERVER_FAILURE,
                error_message="The advisory provider failed unexpectedly.",
            )

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="arx-ask-both") as executor:
        futures = [
            executor.submit(invoke, label, provider, identity)
            for (label, provider), identity in zip(configured, identities)
        ]
        outcomes = tuple(future.result() for future in futures)
    first, second = outcomes
    return AskBothResult((first, second), compare_advisories(first, second))
