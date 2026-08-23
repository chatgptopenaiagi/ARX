"""Deterministic, bounded context selection and external-boundary redaction."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping, Sequence

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


def _redact_text(value: str, private_roots: Sequence[str | os.PathLike[str]] = ()) -> str:
    result = redact_path(value, private_roots)
    username = os.environ.get("USERNAME")
    if username:
        result = re.sub(re.escape(username), "%USERNAME%", result, flags=re.IGNORECASE)
    result = _ASSIGNMENT_SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", result)
    result = _BEARER.sub("Bearer <redacted>", result)
    result = _OPENAI_KEY.sub("<redacted-openai-key>", result)
    result = _GITHUB_KEY.sub("<redacted-github-token>", result)
    result = _JWT.sub("<redacted-token>", result)
    result = _CONTROL.sub("", result)
    if len(result) > MAX_FIELD_CHARS:
        omitted = len(result) - MAX_FIELD_CHARS
        result = f"{result[:MAX_FIELD_CHARS]}\n… <{omitted} characters omitted by ARX>"
    return result


def _redact_path_field(value: str, private_roots: Sequence[str | os.PathLike[str]]) -> str:
    result = _redact_text(value, private_roots)
    if "%USERPROFILE%" in result or "%PROJECT_ROOT%" in result or "%LOCAL_PATH%" in result:
        return result
    try:
        windows_path = PureWindowsPath(value)
        if windows_path.drive and windows_path.root:
            return f"%LOCAL_PATH%/{windows_path.name or '<root>'}"
        path = Path(value)
        if path.is_absolute():
            return f"%LOCAL_PATH%{os.sep}{path.name or '<root>'}"
    except (OSError, TypeError, ValueError):
        pass
    return result


def redact_external(value: Any, private_roots: Sequence[str | os.PathLike[str]] = (), *, key: str = "") -> Any:
    """Redact data before it crosses the AI or public-web trust boundary."""

    if SENSITIVE.search(str(key)):
        return "<redacted>"
    if isinstance(value, str):
        return _redact_path_field(value, private_roots) if _PATH_KEY.search(key) else _redact_text(value, private_roots)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_external(item_value, private_roots, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_external(item, private_roots, key=key) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), private_roots)


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
    """A minimal redacted packet about one user-selected ARX object."""

    context_id: str
    surface: str
    title: str
    status: str
    selected: Mapping[str, Any]
    project: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]

    @property
    def trust_domain(self) -> str:
        return "ARX DETERMINISTIC LOCAL EVIDENCE"

    def as_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "trust_domain": self.trust_domain,
            "surface": self.surface,
            "title": self.title,
            "status": self.status,
            "selected_finding": dict(self.selected),
            "project_context": dict(self.project),
            "relevant_evidence": [dict(item) for item in self.evidence],
        }

    def preview(self) -> str:
        return json.dumps(self.as_dict(), indent=2, ensure_ascii=False, sort_keys=True)

    def summary(self) -> str:
        project = self.project.get("identity") or self.project.get("project") or "No project selected"
        return f"Project → {project}\nFinding → {self.title}\nStatus → {self.status or 'UNKNOWN'}"


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
    )


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
    packet = context.preview()
    prompt = (
        "ARX AI ADVISORY REQUEST\n\n"
        "Trust boundary: the JSON below is redacted deterministic ARX evidence. Your response is advisory only. "
        "Do not claim to have changed the machine, do not reinterpret your answer as OBSERVED/VERIFIED/GREEN/RED evidence, "
        "and do not recommend destructive actions without clearly explaining risk. If your assumptions conflict with the supplied "
        "evidence, state the conflict and defer to verified ARX observations.\n\n"
        f"Analysis mode: {mode}\nMode instruction: {instruction}\n\n"
        f"ARX CONTEXT\n{packet}\n\n"
    )
    if safe_turns:
        prompt += f"RECENT REDACTED CONVERSATION\n{json.dumps(safe_turns, ensure_ascii=False)}\n\n"
    prompt += f"USER QUESTION\n{safe_question}\n\nBegin the response with: AI ADVISORY"
    return prompt[:MAX_CONTEXT_CHARS + 8_000]
