"""Local runtime health mapped onto the existing advisory provider contract."""

from __future__ import annotations

from arx.advisory.health import ProviderHealthStatus
from arx.advisory.providers import ProviderAvailability

from .models import LocalAIFailure, LocalAIRuntime, LocalAIState

_FAILURE_STATUS = {
    LocalAIFailure.MODEL_MISSING: ProviderHealthStatus.MODEL_NOT_AVAILABLE,
    LocalAIFailure.AUTH_FAILURE: ProviderHealthStatus.AUTHENTICATION_FAILURE,
    LocalAIFailure.API_INCOMPATIBLE: ProviderHealthStatus.PARSE_FAILURE,
    LocalAIFailure.MALFORMED_RESPONSE: ProviderHealthStatus.PARSE_FAILURE,
    LocalAIFailure.NETWORK_FAILURE: ProviderHealthStatus.NETWORK_FAILURE,
    LocalAIFailure.REQUEST_FAILED: ProviderHealthStatus.SERVER_FAILURE,
    LocalAIFailure.STARTUP_TIMEOUT: ProviderHealthStatus.TIMEOUT,
    LocalAIFailure.REQUEST_TIMEOUT: ProviderHealthStatus.TIMEOUT,
    LocalAIFailure.REQUEST_CANCELLED: ProviderHealthStatus.CANCELLED,
    LocalAIFailure.MODEL_LOAD_FAILURE: ProviderHealthStatus.MODEL_NOT_AVAILABLE,
    LocalAIFailure.EXECUTABLE_MISSING: ProviderHealthStatus.NOT_AVAILABLE,
    LocalAIFailure.PORT_CONFLICT: ProviderHealthStatus.NOT_AVAILABLE,
    LocalAIFailure.INSUFFICIENT_RESOURCES: ProviderHealthStatus.NOT_AVAILABLE,
    LocalAIFailure.PROCESS_CRASHED: ProviderHealthStatus.SERVER_FAILURE,
}


def provider_availability(runtime: LocalAIRuntime) -> ProviderAvailability:
    """Expose a safe operational state without triggering discovery or startup."""

    if runtime.state is LocalAIState.READY:
        return ProviderAvailability(
            True,
            runtime.message or "The configured local AI model is ready on loopback.",
            runtime.backend_version or runtime.model_identity,
            operational_status=ProviderHealthStatus.READY,
        )
    if runtime.state is LocalAIState.BUSY:
        return ProviderAvailability(
            False,
            "The local AI provider is processing another advisory request.",
            runtime.backend_version or runtime.model_identity,
            operational_status=ProviderHealthStatus.NOT_AVAILABLE,
        )
    if runtime.failure is not None:
        return ProviderAvailability(
            False,
            runtime.message or "The local AI provider is not ready.",
            runtime.backend_version or runtime.model_identity,
            operational_status=_FAILURE_STATUS.get(runtime.failure, ProviderHealthStatus.NOT_AVAILABLE),
        )
    return ProviderAvailability(
        False,
        runtime.message or "Use Local AI Settings to discover or start an approved loopback backend.",
        runtime.backend_version or runtime.model_identity,
        operational_status=ProviderHealthStatus.NOT_AVAILABLE,
    )
