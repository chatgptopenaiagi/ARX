"""Operational provider health with evidence-backed, validated states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from arx.core.models import Evidence

from .credentials import CredentialState


class ProviderHealthStatus(str, Enum):
    NO_CREDENTIAL = "NO_CREDENTIAL"
    CREDENTIAL_UNREADABLE = "CREDENTIAL_UNREADABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    TLS_HTTPS_FAILURE = "TLS_HTTPS_FAILURE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    SERVER_FAILURE = "SERVER_FAILURE"
    PARSE_FAILURE = "PARSE_FAILURE"
    READY = "READY"


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    status: ProviderHealthStatus
    credential_state: CredentialState
    model: str | None
    latency_ms: int | None
    checked_at: str
    category: str
    message: str
    claims: tuple[Evidence, ...]
    validated_by: str = "provider-health-state-v1"

    @property
    def ready(self) -> bool:
        return self.status is ProviderHealthStatus.READY


def checked_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_provider_health(health: ProviderHealth) -> ProviderHealth:
    """Reject composed operational states that overclaim their supporting facts."""

    if not health.claims:
        raise ValueError("Provider health requires at least one supporting claim.")
    if health.status is ProviderHealthStatus.READY:
        if health.credential_state is not CredentialState.CONFIGURED:
            raise ValueError("READY requires a configured credential.")
        if not health.model or health.latency_ms is None or health.latency_ms < 0:
            raise ValueError("READY requires an observed model and non-negative latency.")
    if health.status is ProviderHealthStatus.NO_CREDENTIAL and health.credential_state is not CredentialState.NOT_CONFIGURED:
        raise ValueError("NO_CREDENTIAL requires NOT_CONFIGURED credential state.")
    if (
        health.status is ProviderHealthStatus.CREDENTIAL_UNREADABLE
        and health.credential_state is not CredentialState.CREDENTIAL_UNREADABLE
    ):
        raise ValueError("CREDENTIAL_UNREADABLE requires the matching credential state.")
    return health
