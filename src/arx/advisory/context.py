"""Deterministic, bounded context selection and external-boundary redaction."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Any

from arx.core.evidence import SENSITIVE, redact_path

MAX_FIELD_CHARS = 2_000
MAX_CONTEXT_CHARS = 16_000
MAX_EVIDENCE_ITEMS = 8
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|private[_-]?key|credential|cookie)\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")
_OPENAI_KEY = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b")
_GITHUB_KEY = re.compile(r"\bgh[opusr]_[A-Za-z0-9]{12,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_PATH_KEY = re.compile(r"(?:^|_)(?:path|file|directory|root|location)(?:$|_)", re.IGNORECASE)
_QUOTED_LOCAL_PATH = re.compile(
    r'''(?P<quote>["'])(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|tmp|private/tmp)/).*?(?P=quote)''',
    re.IGNORECASE,
)
_WINDOWS_LOCAL_PATH = re.compile(r"(?i)(?<![\w%])(?:[A-Z]:[\\/]|\\\\)[^\s<>\"'|,;]+")
_POSIX_LOCAL_PATH = re.compile(r"(?<![\w%])/(?:home|Users|tmp|private/tmp)/[^\s<>\"'|,;]+")


ANALYSIS_MODES: Mapping[str, str] = {
    "Explain Simply": "Explain the finding in plain language and why it matters.",
    "Explain Technically": "Explain the technical cause, evidence, uncertainty, and compatibility impact.",
    "Why Is This Important?": "Explain the project-specific consequence and what would happen if it is ignored.",
    "Suggest Safe Fix": (
        "Explain the cause and suggest the shortest non-destructive remediation. Preserve working software, avoid unnecessary "
        "reinstallation, explain risks, and distinguish evidence from assumptions. Do not execute anything."
    ),
    "Security Interpretation": "Explain the security implications without treating compatibility as a trust verdict.",
    "Compatibility Interpretation": "Compare the finding with the supplied project requirements and compatibility evidence.",
    "Compare Alternatives": "Compare safe alternatives, trade-offs, prerequisites, and uncertainty without taking action.",
    "What Should I Check Next?": "List the smallest set of safe read-only checks that would reduce uncertainty.",
}


class AdvisoryChatMode(str, Enum):
    """User-visible chat modes; neither value is an evidence classification."""

    GENERAL_CHAT = "GENERAL_CHAT"
    ARX_EVIDENCE_CHAT = "ARX_EVIDENCE_CHAT"


@dataclass(frozen=True)
class ContextSelection:
    """Explicit allowlist for one bounded Intelligence Console packet."""

    selected_finding: bool = True
    relevant_evidence: bool = True
    machine_dna: bool = False
    software_dna: bool = False
    project_dna: bool = True
    conclusions: bool = True
    contradictions: bool = True
    unknowns: bool = True

    def as_dict(self) -> dict[str, bool]:
        values = {
            "selected_finding": self.selected_finding,
            "relevant_evidence": self.relevant_evidence,
            "machine_dna": self.machine_dna,
            "software_dna": self.software_dna,
            "project_dna": self.project_dna,
            "conclusions": self.conclusions,
            "contradictions": self.contradictions,
            "unknowns": self.unknowns,
        }
        return {key: True for key, enabled in values.items() if enabled}


def _freeze(value: Any) -> Any:
    """Detach a context packet from mutable deterministic application objects."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=str))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _redact_text(
    value: str,
    private_roots: Sequence[str | os.PathLike[str]] = (),
    *,
    max_chars: int = MAX_FIELD_CHARS,
) -> str:
    result = redact_path(value, private_roots)
    username = os.environ.get("USERNAME")
    if username:
        result = re.sub(re.escape(username), "%USERNAME%", result, flags=re.IGNORECASE)
    result = _QUOTED_LOCAL_PATH.sub('"%LOCAL_PATH%"', result)
    result = _WINDOWS_LOCAL_PATH.sub("%LOCAL_PATH%", result)
    result = _POSIX_LOCAL_PATH.sub("%LOCAL_PATH%", result)
    result = _ASSIGNMENT_SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", result)
    result = _BEARER.sub("Bearer <redacted>", result)
    result = _OPENAI_KEY.sub("<redacted-openai-key>", result)
    result = _GITHUB_KEY.sub("<redacted-github-token>", result)
    result = _JWT.sub("<redacted-token>", result)
    result = _CONTROL.sub("", result)
    if len(result) > max_chars:
        omitted = len(result) - max_chars
        result = f"{result[:max_chars]}\n… <{omitted} characters omitted by ARX>"
    return result


def _redact_path_field(
    value: str,
    private_roots: Sequence[str | os.PathLike[str]],
    *,
    max_chars: int = MAX_FIELD_CHARS,
) -> str:
    conventional = redact_path(value, private_roots)
    if conventional != value and ("%USERPROFILE%" in conventional or "%PROJECT_ROOT%" in conventional):
        return _redact_text(conventional, private_roots, max_chars=max_chars)
    try:
        windows_path = PureWindowsPath(value)
        if windows_path.drive and windows_path.root:
            return f"%LOCAL_PATH%/{_redact_text(windows_path.name or '<root>', private_roots, max_chars=max_chars)}"
        path = Path(value)
        if path.is_absolute():
            return f"%LOCAL_PATH%{os.sep}{_redact_text(path.name or '<root>', private_roots, max_chars=max_chars)}"
    except (OSError, TypeError, ValueError):
        pass
    return _redact_text(value, private_roots, max_chars=max_chars)


def redact_external(
    value: Any,
    private_roots: Sequence[str | os.PathLike[str]] = (),
    *,
    key: str = "",
    max_text_chars: int = MAX_FIELD_CHARS,
) -> Any:
    """Redact data before it crosses the AI or public-web trust boundary."""

    if SENSITIVE.search(str(key)):
        return "<redacted>"
    if isinstance(value, str):
        return (
            _redact_path_field(value, private_roots, max_chars=max_text_chars)
            if _PATH_KEY.search(key)
            else _redact_text(value, private_roots, max_chars=max_text_chars)
        )
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_external(
                item_value,
                private_roots,
                key=str(item_key),
                max_text_chars=max_text_chars,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            redact_external(item, private_roots, key=key, max_text_chars=max_text_chars)
            for item in value
        ]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), private_roots, max_chars=max_text_chars)


def _bounded_mapping(value: Mapping[str, Any], budget: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    used = 2
    for key, item in value.items():
        encoded = json.dumps({str(key): item}, ensure_ascii=False, sort_keys=True)
        if result and used + len(encoded) > budget:
            result["_arx_truncation"] = "Additional context omitted by ARX."
            break
        result[str(key)] = item
        used += len(encoded)
    return result


@dataclass(frozen=True)
class AdvisoryContext:
    """An immutable redacted packet detached from authoritative ARX state."""

    context_id: str
    surface: str
    title: str
    status: str
    selected: Mapping[str, Any]
    project: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]
    chat_mode: AdvisoryChatMode = AdvisoryChatMode.ARX_EVIDENCE_CHAT
    sections: Mapping[str, Any] = field(default_factory=dict)
    contradictions: tuple[Mapping[str, Any], ...] = ()
    unknowns: tuple[str, ...] = ()
    selection: ContextSelection = field(default_factory=ContextSelection)

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected", _freeze(self.selected))
        object.__setattr__(self, "project", _freeze(self.project))
        object.__setattr__(self, "evidence", tuple(_freeze(item) for item in self.evidence))
        object.__setattr__(self, "sections", _freeze(self.sections))
        object.__setattr__(self, "contradictions", tuple(_freeze(item) for item in self.contradictions))
        object.__setattr__(self, "unknowns", tuple(str(item) for item in self.unknowns))

    @property
    def trust_domain(self) -> str:
        if self.chat_mode is AdvisoryChatMode.GENERAL_CHAT:
            return "GENERAL CHAT — NO ARX EVIDENCE ATTACHED"
        return "ARX DETERMINISTIC LOCAL EVIDENCE"

    @property
    def has_arx_evidence(self) -> bool:
        return self.chat_mode is AdvisoryChatMode.ARX_EVIDENCE_CHAT and bool(
            self.selected or self.project or self.evidence or self.sections or self.contradictions or self.unknowns
        )

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    def as_dict(self) -> dict[str, Any]:
        result = {
            "context_id": self.context_id,
            "chat_mode": self.chat_mode.value,
            "trust_domain": self.trust_domain,
            "surface": self.surface,
            "title": self.title,
            "status": self.status,
            "selection": self.selection.as_dict(),
        }
        if self.chat_mode is AdvisoryChatMode.GENERAL_CHAT:
            return result
        result.update(
            {
                "selected_finding": _thaw(self.selected),
                "project_context": _thaw(self.project),
                "relevant_evidence": _thaw(self.evidence),
                "sections": _thaw(self.sections),
                "contradictions": _thaw(self.contradictions),
                "unknowns": list(self.unknowns),
            }
        )
        return result

    def preview(self) -> str:
        return json.dumps(self.as_dict(), indent=2, ensure_ascii=False, sort_keys=True)

    def summary(self) -> str:
        if self.chat_mode is AdvisoryChatMode.GENERAL_CHAT:
            return "Mode → GENERAL CHAT\nAttached ARX Context → NONE"
        project = self.project.get("identity") or self.project.get("project") or "No project selected"
        return (
            "Mode → ARX EVIDENCE CHAT\n"
            f"Project → {project}\n"
            f"Finding → {self.title}\n"
            f"Status → {self.status or 'UNKNOWN'}\n"
            f"Evidence items → {self.evidence_count} · REDACTED + BOUNDED"
        )


def build_advisory_context(
    surface: str,
    columns: Sequence[str],
    values: Sequence[Any],
    *,
    project: Mapping[str, Any] | None = None,
    evidence: Sequence[Mapping[str, Any]] = (),
    private_roots: Sequence[str | os.PathLike[str]] = (),
) -> AdvisoryContext:
    """Select one row plus bounded relevant project/evidence context."""

    selected = {
        str(column): value
        for column, value in zip(columns, values)
        if value is not None and str(value).strip()
    }
    redacted_selected = _bounded_mapping(redact_external(selected, private_roots), 7_500)
    redacted_project = _bounded_mapping(redact_external(dict(project or {}), private_roots), 4_000)
    redacted_evidence = tuple(
        _bounded_mapping(redact_external(dict(item), private_roots), 700)
        for item in tuple(evidence)[:MAX_EVIDENCE_ITEMS]
    )
    title = str(next(iter(redacted_selected.values()), surface))
    status = ""
    for key in ("status", "satisfaction", "classification", "relevance"):
        if redacted_selected.get(key):
            status = str(redacted_selected[key])
            break
    canonical = json.dumps(
        {
            "surface": surface,
            "selected": redacted_selected,
            "project": redacted_project,
            "evidence": redacted_evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(canonical) > MAX_CONTEXT_CHARS:
        redacted_evidence = ()
        canonical = json.dumps(
            {"surface": surface, "selected": redacted_selected, "project": redacted_project, "evidence": []},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )[:MAX_CONTEXT_CHARS]
    context_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return AdvisoryContext(
        context_id=context_id,
        surface=_redact_text(surface, private_roots),
        title=title,
        status=status,
        selected=redacted_selected,
        project=redacted_project,
        evidence=redacted_evidence,
        selection=ContextSelection(
            selected_finding=True,
            relevant_evidence=bool(redacted_evidence),
            project_dna=bool(redacted_project),
            conclusions=False,
            contradictions=False,
            unknowns=False,
        ),
    )


def build_general_chat_context() -> AdvisoryContext:
    """Create a provider-neutral chat context containing no ARX evidence."""

    canonical = "ARX:GENERAL_CHAT:NO_CONTEXT:v1"
    return AdvisoryContext(
        context_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        surface="General Chat",
        title="GENERAL CHAT",
        status="NO ARX EVIDENCE ATTACHED",
        selected={},
        project={},
        evidence=(),
        chat_mode=AdvisoryChatMode.GENERAL_CHAT,
        selection=ContextSelection(
            selected_finding=False,
            relevant_evidence=False,
            machine_dna=False,
            software_dna=False,
            project_dna=False,
            conclusions=False,
            contradictions=False,
            unknowns=False,
        ),
    )


def _bounded_sequence(value: Sequence[Any], budget: int) -> tuple[Any, ...]:
    result: list[Any] = []
    used = 2
    for item in value:
        encoded = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if result and used + len(encoded) > budget:
            result.append({"_arx_truncation": "Additional items omitted by ARX."})
            break
        if not result and len(encoded) > budget:
            if isinstance(item, Mapping):
                result.append(_bounded_mapping(item, budget))
            else:
                result.append(_redact_text(str(item), max_chars=max(64, budget - 64)))
            break
        result.append(item)
        used += len(encoded)
    return tuple(result)


def build_intelligence_context(
    *,
    selected: Mapping[str, Any] | None = None,
    evidence: Sequence[Mapping[str, Any]] = (),
    machine: Mapping[str, Any] | None = None,
    software: Mapping[str, Any] | None = None,
    project: Mapping[str, Any] | None = None,
    conclusions: Mapping[str, Any] | None = None,
    contradictions: Sequence[Mapping[str, Any]] = (),
    unknowns: Sequence[str] = (),
    selection: ContextSelection | None = None,
    private_roots: Sequence[str | os.PathLike[str]] = (),
    surface: str = "ARX Intelligence Console",
) -> AdvisoryContext:
    """Build one explicitly selected, redacted, size-budgeted Phase C packet."""

    chosen = selection or ContextSelection()
    safe_selected = (
        _bounded_mapping(redact_external(dict(selected or {}), private_roots), 2_500)
        if chosen.selected_finding
        else {}
    )
    safe_project = (
        _bounded_mapping(redact_external(dict(project or {}), private_roots), 1_800)
        if chosen.project_dna
        else {}
    )
    sections: dict[str, Any] = {}
    for enabled, key, value, budget in (
        (chosen.machine_dna, "machine_dna", machine, 1_800),
        (chosen.software_dna, "software_dna", software, 1_800),
        (chosen.conclusions, "deterministic_conclusions", conclusions, 1_800),
    ):
        if enabled and value:
            sections[key] = _bounded_mapping(redact_external(dict(value), private_roots), budget)
    safe_evidence = (
        tuple(
            _bounded_mapping(redact_external(dict(item), private_roots), 500)
            for item in tuple(evidence)[:MAX_EVIDENCE_ITEMS]
        )
        if chosen.relevant_evidence
        else ()
    )
    safe_contradictions = (
        _bounded_sequence(
            [redact_external(dict(item), private_roots) for item in tuple(contradictions)[:12]],
            1_200,
        )
        if chosen.contradictions
        else ()
    )
    safe_unknowns = (
        tuple(
            str(redact_external(item, private_roots, max_text_chars=500))
            for item in tuple(unknowns)[:16]
        )
        if chosen.unknowns
        else ()
    )
    title = str(next(iter(safe_selected.values()), "Selected ARX diagnostic scope"))
    status = ""
    for key in ("status", "satisfaction", "classification", "relevance", "decision"):
        if safe_selected.get(key):
            status = str(safe_selected[key])
            break
    canonical = json.dumps(
        {
            "surface": surface,
            "selected": safe_selected,
            "project": safe_project,
            "evidence": safe_evidence,
            "sections": sections,
            "contradictions": safe_contradictions,
            "unknowns": safe_unknowns,
            "selection": chosen.as_dict(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    context = AdvisoryContext(
        context_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        surface=_redact_text(surface, private_roots),
        title=title,
        status=status,
        selected=safe_selected,
        project=safe_project,
        evidence=safe_evidence,
        sections=sections,
        contradictions=safe_contradictions,
        unknowns=safe_unknowns,
        selection=chosen,
    )
    if len(context.preview()) > MAX_CONTEXT_CHARS:
        raise ValueError("The bounded ARX advisory context exceeded its deterministic size budget.")
    return context


def build_advisory_prompt(
    context: AdvisoryContext,
    question: str,
    *,
    mode: str = "Explain Technically",
    conversation: Sequence[Mapping[str, str]] = (),
) -> str:
    """Build a deterministic prompt that preserves ARX/AI semantic separation."""

    instruction = ANALYSIS_MODES.get(mode, ANALYSIS_MODES["Explain Technically"])
    safe_question = _redact_text(question).strip() or instruction
    safe_turns = []
    for turn in tuple(conversation)[-6:]:
        role = "assistant" if str(turn.get("role", "")).casefold() == "assistant" else "user"
        safe_turns.append({"role": role, "text": _redact_text(str(turn.get("text", "")))})
    prompt = "ARX AI ADVISORY REQUEST\n\n"
    if context.chat_mode is AdvisoryChatMode.GENERAL_CHAT:
        prompt += (
            "Chat mode: GENERAL CHAT. No machine, software, project, compatibility, readiness, finding, or ARX evidence "
            "is attached. Your response is advisory only and cannot modify ARX deterministic state.\n\n"
        )
    else:
        prompt += (
            "Trust boundary: the JSON below is redacted deterministic ARX evidence. Your response is advisory only. "
            "Do not claim to have changed the machine, assign ARX fact provenance, claim ARX decision validation, or set GREEN/RED state, "
            "and do not recommend destructive actions without clearly explaining risk. If your assumptions conflict with the supplied "
            "evidence, state the conflict and defer to the supplied ARX observations and validated decisions.\n\n"
            f"ARX CONTEXT\n{context.preview()}\n\n"
        )
    prompt += f"Analysis mode: {mode}\nMode instruction: {instruction}\n\n"
    if safe_turns:
        prompt += f"RECENT REDACTED CONVERSATION\n{json.dumps(safe_turns, ensure_ascii=False)}\n\n"
    prompt += f"USER QUESTION\n{safe_question}\n\nReturn advisory analysis only; ARX supplies the trust label in its UI."
    return prompt[:MAX_CONTEXT_CHARS + 8_000]
