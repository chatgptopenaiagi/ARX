"""Privacy-aware, user-triggered public web-search bridge."""

from __future__ import annotations

import re
import urllib.parse
import webbrowser
from typing import Callable

from .context import AdvisoryContext, redact_external


MAX_SEARCH_CHARS = 240
_ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\(?:[^\s<>\"|]+\\)*[^\s<>\"|]*")
_RANDOM_IDENTIFIER = re.compile(r"\b[0-9a-f]{24,}\b", re.IGNORECASE)
_OFFICIAL_DOMAINS = {
    "python": "docs.python.org",
    "microsoft": "learn.microsoft.com",
    "windows": "learn.microsoft.com",
    "visual studio": "learn.microsoft.com",
    "cmake": "cmake.org",
    "nvidia": "docs.nvidia.com",
    "cuda": "docs.nvidia.com",
    "openai": "developers.openai.com",
    "codex": "developers.openai.com",
    "github": "docs.github.com",
}


def _terms(context: AdvisoryContext) -> str:
    selected = " ".join(str(value) for value in context.selected.values() if value)
    query = f"{context.title} {context.status} {selected}".strip()
    query = str(redact_external(query))
    query = _ABSOLUTE_WINDOWS_PATH.sub("%LOCAL_PATH%", query)
    query = _RANDOM_IDENTIFIER.sub("<identifier>", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:MAX_SEARCH_CHARS]


def exact_error_query(context: AdvisoryContext) -> str:
    for key in ("error", "reason", "evidence", "value"):
        value = context.selected.get(key)
        if value:
            text = str(redact_external(str(value)))
            text = _ABSOLUTE_WINDOWS_PATH.sub("%LOCAL_PATH%", text)
            text = _RANDOM_IDENTIFIER.sub("<identifier>", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:MAX_SEARCH_CHARS]
    return _terms(context)


def official_domain(context: AdvisoryContext) -> str | None:
    primary = " ".join(
        str(context.selected.get(key, ""))
        for key in ("component", "check", "capability", "kind")
    ).casefold()
    for haystack in (primary, _terms(context).casefold()):
        for technology, domain in _OFFICIAL_DOMAINS.items():
            if technology in haystack:
                return domain
    return None


def build_search_query(context: AdvisoryContext, kind: str = "web") -> str:
    kind = kind.casefold()
    if kind == "exact_error":
        return exact_error_query(context)
    terms = _terms(context)
    if kind == "official":
        domain = official_domain(context)
        return f"site:{domain} {terms}"[:MAX_SEARCH_CHARS] if domain else f"official documentation {terms}"[:MAX_SEARCH_CHARS]
    return terms


def build_search_url(query: str, engine: str = "web") -> str:
    safe_query = str(redact_external(query)).strip()[:MAX_SEARCH_CHARS]
    if not safe_query:
        raise ValueError("A search query could not be constructed from this finding.")
    base = "https://www.google.com/search" if engine.casefold() == "google" else "https://duckduckgo.com/"
    return f"{base}?{urllib.parse.urlencode({'q': safe_query})}"


def open_search(url: str, *, opener: Callable[..., object] = webbrowser.open) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.google.com", "duckduckgo.com"}:
        raise ValueError("ARX refused an unsupported search URL.")
    opener(url, new=2)
