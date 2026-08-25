"""Typed local-AI configuration and operational state models."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

MAX_CONFIGURED_PROFILES = 8
MAX_PROFILE_TEXT = 256
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,47}")
_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}")


class LocalAIState(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    DISCOVERED = "DISCOVERED"
    STARTING = "STARTING"
    HEALTH_CHECK = "HEALTH_CHECK"
    READY = "READY"
    BUSY = "BUSY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class LocalAIFailure(str, Enum):
    MODEL_MISSING = "MODEL_MISSING"
    EXECUTABLE_MISSING = "EXECUTABLE_MISSING"
    PORT_CONFLICT = "PORT_CONFLICT"
    STARTUP_TIMEOUT = "STARTUP_TIMEOUT"
    API_INCOMPATIBLE = "API_INCOMPATIBLE"
    AUTH_FAILURE = "AUTH_FAILURE"
    MODEL_LOAD_FAILURE = "MODEL_LOAD_FAILURE"
    INSUFFICIENT_RESOURCES = "INSUFFICIENT_RESOURCES"
    PROCESS_CRASHED = "PROCESS_CRASHED"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    REQUEST_FAILED = "REQUEST_FAILED"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    REQUEST_CANCELLED = "REQUEST_CANCELLED"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"


class AssistanceProfile(str, Enum):
    GUIDED = "GUIDED"
    BALANCED = "BALANCED"
    EXPERT = "EXPERT"
    AUTOMATED = "AUTOMATED"


class BackendKind(str, Enum):
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    LLAMA_CPP = "LLAMA_CPP"
    GENERIC = "GENERIC"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_loopback_url(value: str) -> str:
    """Validate an explicit HTTP(S) loopback endpoint without resolving DNS."""

    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("A bounded localhost endpoint is required.")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Local AI endpoints must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Local AI endpoints cannot contain credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("Local AI endpoints cannot contain a query or fragment.")
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The local AI endpoint port is invalid.") from exc
    if port is None or not 1 <= port <= 65_535:
        raise ValueError("Local AI endpoints require an explicit valid port.")
    if hostname == "localhost":
        # Preserve the user-facing localhost spelling as an accepted input, but
        # use a literal loopback address at the transport boundary so no DNS or
        # hosts-file resolution can redirect the request elsewhere.
        normalized_host = "127.0.0.1"
    else:
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as exc:
            raise ValueError("Local AI endpoints must use localhost or a literal loopback address.") from exc
        if not address.is_loopback:
            raise ValueError("Local AI endpoints must remain loopback-only.")
        normalized_host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    path = parsed.path.rstrip("/")
    if path and any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("The local AI endpoint path is invalid.")
    return f"{parsed.scheme}://{normalized_host}:{port}{path}"


@dataclass(frozen=True)
class LocalEndpoint:
    """One explicit loopback API root; never a wildcard or network range."""

    base_url: str = "http://127.0.0.1:8000"

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _normalized_loopback_url(self.base_url))

    @property
    def host(self) -> str:
        return str(urllib.parse.urlsplit(self.base_url).hostname)

    @property
    def port(self) -> int:
        value = urllib.parse.urlsplit(self.base_url).port
        if value is None:  # guarded again because endpoint configuration is a security boundary
            raise ValueError("The validated local AI endpoint no longer has an explicit port.")
        return value

    def api_url(self, path: str) -> str:
        if not path.startswith("/") or "?" in path or "#" in path or ".." in path:
            raise ValueError("Local AI API paths must be absolute, bounded paths.")
        return f"{self.base_url}{path}"


@dataclass(frozen=True)
class BackendProfile:
    """A bounded, typed profile from which ARX can construct a safe launch."""

    profile_id: str
    display_name: str
    backend: BackendKind
    endpoint: LocalEndpoint
    assistance: AssistanceProfile = AssistanceProfile.BALANCED
    model_id: str | None = None
    executable: Path | None = None
    model_path: Path | None = None
    session_capability: bool = False

    def __post_init__(self) -> None:
        if _PROFILE_ID.fullmatch(self.profile_id) is None:
            raise ValueError("Local AI profile identifiers must be bounded lowercase tokens.")
        if not self.display_name.strip() or len(self.display_name) > MAX_PROFILE_TEXT:
            raise ValueError("The local AI profile display name is invalid.")
        if self.model_id is not None and _MODEL_ID.fullmatch(self.model_id) is None:
            raise ValueError("The local AI model identifier is invalid.")
        if self.backend is BackendKind.LLAMA_CPP and (self.executable is None or self.model_path is None):
            raise ValueError("A llama.cpp profile requires an executable and model file.")
        if self.backend is not BackendKind.LLAMA_CPP and (self.executable is not None or self.model_path is not None):
            raise ValueError("Only the typed llama.cpp adapter may launch a configured executable.")
        for value in (self.executable, self.model_path):
            if value is not None and ("\x00" in str(value) or len(str(value)) > 1_024):
                raise ValueError("A local AI path is invalid or exceeds its bound.")

    @property
    def launchable(self) -> bool:
        return self.backend is BackendKind.LLAMA_CPP

    def fingerprint(self) -> str:
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        """Return local configuration only; session capabilities can never appear."""

        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "backend": self.backend.value,
            "endpoint": self.endpoint.base_url,
            "assistance": self.assistance.value,
            "model_id": self.model_id,
            "executable": str(self.executable) if self.executable is not None else None,
            "model_path": str(self.model_path) if self.model_path is not None else None,
            "session_capability": self.session_capability,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BackendProfile:
        allowed = {
            "profile_id",
            "display_name",
            "backend",
            "endpoint",
            "assistance",
            "model_id",
            "executable",
            "model_path",
            "session_capability",
        }
        if set(value) - allowed:
            raise ValueError("The local AI profile contains unsupported fields.")
        executable = value.get("executable")
        model_path = value.get("model_path")
        return cls(
            profile_id=str(value["profile_id"]),
            display_name=str(value["display_name"]),
            backend=BackendKind(str(value["backend"])),
            endpoint=LocalEndpoint(str(value["endpoint"])),
            assistance=AssistanceProfile(str(value.get("assistance", AssistanceProfile.BALANCED.value))),
            model_id=str(value["model_id"]) if value.get("model_id") is not None else None,
            executable=Path(str(executable)) if executable is not None else None,
            model_path=Path(str(model_path)) if model_path is not None else None,
            session_capability=value.get("session_capability", False) is True,
        )


@dataclass(frozen=True)
class LocalAIRuntime:
    """Safe operational snapshot; intentionally excludes session secrets."""

    profile_id: str
    state: LocalAIState
    endpoint: str
    model_identity: str | None = None
    executable_identity: str | None = None
    executable_sha256: str | None = None
    pid: int | None = None
    started_at: str | None = None
    backend_version: str | None = None
    failure: LocalAIFailure | None = None
    message: str = ""
    exit_code: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "state": self.state.value,
            "endpoint": self.endpoint,
            "model_identity": self.model_identity,
            "executable_identity": self.executable_identity,
            "executable_sha256": self.executable_sha256,
            "pid": self.pid,
            "started_at": self.started_at,
            "backend_version": self.backend_version,
            "failure": self.failure.value if self.failure is not None else None,
            "message": self.message,
            "exit_code": self.exit_code,
        }
