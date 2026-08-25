"""Adapter for an explicitly configured, already-running localhost API."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import BackendKind, BackendProfile
from ..session import SessionCapability


@dataclass(frozen=True)
class LaunchSpec:
    arguments: tuple[str, ...]
    environment: dict[str, str]
    executable_identity: str


class OpenAICompatibleBackendAdapter:
    kind = BackendKind.OPENAI_COMPATIBLE

    def launch_spec(self, profile: BackendProfile, capability: SessionCapability) -> LaunchSpec | None:
        del capability
        if profile.backend is not self.kind:
            raise ValueError("The OpenAI-compatible adapter received the wrong backend profile.")
        return None
