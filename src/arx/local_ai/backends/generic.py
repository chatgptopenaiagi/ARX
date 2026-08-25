"""Conservative adapter for a configured localhost endpoint with no launcher."""

from __future__ import annotations

from ..models import BackendKind, BackendProfile
from ..session import SessionCapability
from .openai_compatible import LaunchSpec


class GenericBackendAdapter:
    """Generic means API-only; it never turns free-form configuration into a command."""

    kind = BackendKind.GENERIC

    def launch_spec(self, profile: BackendProfile, capability: SessionCapability) -> LaunchSpec | None:
        del capability
        if profile.backend is not self.kind:
            raise ValueError("The generic adapter received the wrong backend profile.")
        return None
