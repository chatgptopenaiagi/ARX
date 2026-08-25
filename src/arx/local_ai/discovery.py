"""Explicit, bounded discovery for localhost OpenAI-compatible APIs."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .models import BackendProfile, LocalAIFailure, LocalAIState, LocalEndpoint
from .session import CapabilityExpired, SessionCapability

MAX_DISCOVERY_ENDPOINTS = 8
MAX_MODELS = 128
MAX_MODELS_RESPONSE_BYTES = 256_000
KNOWN_LOCAL_ENDPOINTS = (
    LocalEndpoint("http://127.0.0.1:8000"),
    LocalEndpoint("http://127.0.0.1:8080"),
    LocalEndpoint("http://127.0.0.1:1234"),
    LocalEndpoint("http://127.0.0.1:11434"),
)


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class LocalModel:
    model_id: str
    owned_by: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    endpoint: LocalEndpoint
    state: LocalAIState
    models: tuple[LocalModel, ...] = ()
    failure: LocalAIFailure | None = None
    message: str = ""
    latency_ms: int | None = None
    backend_version: str | None = None

    @property
    def ready(self) -> bool:
        return self.state is LocalAIState.READY


def parse_models_response(payload: object) -> tuple[LocalModel, ...]:
    """Parse the bounded `/v1/models` shape without accepting arbitrary data."""

    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
        raise TypeError("The local endpoint did not return an OpenAI-compatible model list.")
    models: list[LocalModel] = []
    for item in payload["data"][:MAX_MODELS]:
        if not isinstance(item, Mapping):
            raise TypeError("The local endpoint returned malformed model metadata.")
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 256:
            raise ValueError("The local endpoint returned an invalid model identity.")
        owner = item.get("owned_by")
        if owner is not None and (not isinstance(owner, str) or len(owner) > 128):
            raise ValueError("The local endpoint returned invalid model ownership metadata.")
        models.append(LocalModel(model_id.strip(), owner))
    if not models:
        raise ValueError("The local endpoint reported no usable models.")
    return tuple(models)


class LocalAIDiscovery:
    """Probe only endpoints the caller explicitly supplies or selects from a fixed list."""

    def __init__(
        self,
        *,
        transport: Callable[[urllib.request.Request, float], bytes] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._transport = transport or self._default_transport
        self._monotonic = monotonic

    @staticmethod
    def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
        # Ambient HTTP(S)_PROXY configuration must never route a provider that
        # ARX represents as local through an external proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())
        with opener.open(request, timeout=timeout) as response:
            value = response.read(MAX_MODELS_RESPONSE_BYTES + 1)
        if len(value) > MAX_MODELS_RESPONSE_BYTES:
            raise ValueError("The local endpoint returned oversized model metadata.")
        return value

    def probe(
        self,
        profile: BackendProfile,
        *,
        timeout: float = 3,
        capability: SessionCapability | None = None,
    ) -> DiscoveryResult:
        if timeout <= 0 or timeout > 30:
            raise ValueError("Local AI discovery timeout must be between 0 and 30 seconds.")
        request = urllib.request.Request(
            profile.endpoint.api_url("/v1/models"),
            headers={"Accept": "application/json", "User-Agent": "ARX-Local-AI/4"},
            method="GET",
        )
        if profile.session_capability:
            if capability is None:
                return DiscoveryResult(
                    profile.endpoint,
                    LocalAIState.FAILED,
                    failure=LocalAIFailure.AUTH_FAILURE,
                    message="The configured local session capability is unavailable.",
                )
            try:
                request.add_unredirected_header("X-ARX-Session-Capability", capability.header_value())
            except CapabilityExpired:
                return DiscoveryResult(
                    profile.endpoint,
                    LocalAIState.FAILED,
                    failure=LocalAIFailure.AUTH_FAILURE,
                    message="The local AI session capability expired.",
                )
        started = self._monotonic()
        try:
            raw = self._transport(request, timeout)
            if len(raw) > MAX_MODELS_RESPONSE_BYTES:
                raise ValueError("The local endpoint returned oversized model metadata.")
            payload = json.loads(raw.decode("utf-8"))
            models = parse_models_response(payload)
        except urllib.error.HTTPError as exc:
            failure = LocalAIFailure.AUTH_FAILURE if exc.code in (401, 403) else LocalAIFailure.API_INCOMPATIBLE
            return DiscoveryResult(
                profile.endpoint,
                LocalAIState.FAILED,
                failure=failure,
                message=(
                    "The local endpoint rejected ARX authentication."
                    if failure is LocalAIFailure.AUTH_FAILURE
                    else "The local endpoint did not provide a compatible model API."
                ),
                latency_ms=max(0, round((self._monotonic() - started) * 1_000)),
            )
        except (urllib.error.URLError, ConnectionError, TimeoutError, ssl.SSLError):
            return DiscoveryResult(
                profile.endpoint,
                LocalAIState.NOT_FOUND,
                message="No compatible local AI endpoint responded at the configured loopback address.",
                latency_ms=max(0, round((self._monotonic() - started) * 1_000)),
            )
        except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return DiscoveryResult(
                profile.endpoint,
                LocalAIState.FAILED,
                failure=LocalAIFailure.API_INCOMPATIBLE,
                message="The local endpoint returned malformed or incompatible model metadata.",
                latency_ms=max(0, round((self._monotonic() - started) * 1_000)),
            )
        finally:
            request.remove_header("X-ARX-Session-Capability")
        model_ids = {item.model_id for item in models}
        if profile.model_id and profile.model_id not in model_ids:
            return DiscoveryResult(
                profile.endpoint,
                LocalAIState.FAILED,
                models=models,
                failure=LocalAIFailure.MODEL_MISSING,
                message="The configured model was not reported by the local endpoint.",
                latency_ms=max(0, round((self._monotonic() - started) * 1_000)),
            )
        version = payload.get("version") if isinstance(payload, Mapping) else None
        safe_version = version if isinstance(version, str) and len(version) <= 128 else None
        return DiscoveryResult(
            profile.endpoint,
            LocalAIState.READY,
            models=models,
            message="A compatible loopback-only local AI endpoint is ready.",
            latency_ms=max(0, round((self._monotonic() - started) * 1_000)),
            backend_version=safe_version,
        )

    def probe_profiles(
        self,
        profiles: Iterable[BackendProfile],
        *,
        timeout: float = 1,
    ) -> tuple[DiscoveryResult, ...]:
        selected = tuple(profiles)
        if len(selected) > MAX_DISCOVERY_ENDPOINTS:
            raise ValueError("Local AI discovery is limited to eight explicit endpoints.")
        return tuple(self.probe(profile, timeout=timeout) for profile in selected)
