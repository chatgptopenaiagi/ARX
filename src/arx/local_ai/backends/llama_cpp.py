"""Typed llama.cpp server launch construction."""

from __future__ import annotations

from ..models import BackendKind, BackendProfile
from ..session import SessionCapability
from .openai_compatible import LaunchSpec


class LlamaCppBackendAdapter:
    kind = BackendKind.LLAMA_CPP

    def launch_spec(self, profile: BackendProfile, capability: SessionCapability) -> LaunchSpec:
        if profile.backend is not self.kind or profile.executable is None or profile.model_path is None:
            raise ValueError("The llama.cpp adapter requires a complete llama.cpp profile.")
        environment: dict[str, str] = {}
        if profile.session_capability:
            # This opt-in is only valid for a backend wrapper that explicitly consumes
            # the variable and enforces the corresponding request header.
            environment["ARX_LOCAL_AI_SESSION_CAPABILITY"] = capability.header_value()
        return LaunchSpec(
            arguments=(
                str(profile.executable),
                "--host",
                "127.0.0.1",
                "--port",
                str(profile.endpoint.port),
                "--model",
                str(profile.model_path),
            ),
            environment=environment,
            executable_identity=profile.executable.name,
        )
