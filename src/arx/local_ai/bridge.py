"""AIProvider implementation for an approved loopback OpenAI-compatible API."""

from __future__ import annotations

import json
import queue
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from arx.advisory.audit import (
    AuditError,
    TransmissionEvent,
    TransportState,
    default_transmission_audit,
)
from arx.advisory.context import (
    MAX_CONTEXT_CHARS,
    AdvisoryContext,
    build_advisory_prompt,
    redact_external,
)
from arx.advisory.health import ProviderHealthStatus, checked_now
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryResponse,
    AdvisoryTimeout,
    AuditSink,
    ProviderAvailability,
    ProviderError,
)

from .health import provider_availability
from .manager import LocalAIManager
from .models import LocalAIFailure, LocalAIState
from .session import CapabilityExpired

MAX_LOCAL_REQUEST_BYTES = MAX_CONTEXT_CHARS + 16_000
MAX_LOCAL_RESPONSE_BYTES = 1_000_000
MAX_LOCAL_RESPONSE_CHARS = 64_000
_AUDIT_MODEL = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_local_chat_response(payload: object) -> str:
    """Accept the narrow OpenAI-compatible chat completion response shape."""

    if not isinstance(payload, Mapping):
        raise TypeError("The local AI endpoint returned a malformed response.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise ValueError("The local AI endpoint returned no compatible advisory choice.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise TypeError("The local AI endpoint returned malformed advisory content.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The local AI endpoint returned no advisory text.")
    return content.strip()


def _run_cancellable(call: Callable[[], bytes], cancel: threading.Event, timeout: float) -> bytes:
    if timeout <= 0 or timeout > 600:
        raise AdvisoryTimeout("The local advisory timeout must be between 0 and 600 seconds.")
    if cancel.is_set():
        raise AdvisoryCancelled("The local advisory request was cancelled.")
    result: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result.put(("ok", call()))
        except Exception as exc:  # noqa: BLE001 - passed back to the bounded caller
            result.put(("error", exc))

    threading.Thread(target=worker, daemon=True, name="arx-local-ai-transport").start()
    deadline = time.monotonic() + timeout
    while True:
        if cancel.is_set():
            raise AdvisoryCancelled("The local advisory request was cancelled.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AdvisoryTimeout(f"The local advisory request timed out after {timeout:g} seconds.")
        try:
            kind, value = result.get(timeout=min(0.05, remaining))
        except queue.Empty:
            continue
        if kind == "error":
            raise value  # type: ignore[misc]
        return value  # type: ignore[return-value]


class LocalAIProvider:
    """Provider-neutral local advisory adapter; it has no deterministic mutation API."""

    name = "Local AI"

    def __init__(
        self,
        manager: LocalAIManager,
        *,
        profile_id: str | None = None,
        transport: Callable[[urllib.request.Request, float], bytes] | None = None,
        audit: AuditSink | None = None,
    ):
        self.manager = manager
        self.profile_id = profile_id or manager.active_profile_id
        self.provider_id = f"local-ai-{self.profile_id}"
        self._transport = transport or self._default_transport
        self._audit = audit or default_transmission_audit()

    @staticmethod
    def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
        # Keep the loopback advisory boundary independent of ambient proxy
        # configuration; redirects are rejected separately below.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(MAX_LOCAL_RESPONSE_BYTES + 1)
        if len(payload) > MAX_LOCAL_RESPONSE_BYTES:
            raise ValueError("The local AI endpoint returned an oversized response.")
        return payload

    def availability(self) -> ProviderAvailability:
        return provider_availability(self.manager.runtime(self.profile_id))

    def _audit_model(self) -> str | None:
        value = self.manager.runtime(self.profile_id).model_identity
        return value if value is not None and _AUDIT_MODEL.fullmatch(value) else ("local-model" if value else None)

    def _audit_event(
        self,
        attempt_id: str,
        state: TransportState,
        *,
        request_bytes: int | None = None,
        response_bytes: int | None = None,
        latency_ms: int | None = None,
        status: ProviderHealthStatus | None = None,
    ) -> None:
        try:
            self._audit.record(
                TransmissionEvent(
                    timestamp=checked_now(),
                    attempt_id=attempt_id,
                    provider_id=self.provider_id,
                    operation="advisory",
                    state=state,
                    model=self._audit_model(),
                    request_bytes=request_bytes,
                    response_bytes=response_bytes,
                    latency_ms=latency_ms,
                    error_category=status.value if status is not None else None,
                )
            )
        except (AuditError, OSError, ValueError) as exc:
            raise ProviderError(
                "ARX could not maintain the required local metadata-only transmission audit.",
                ProviderHealthStatus.SERVER_FAILURE,
                audit_failure=True,
            ) from exc

    def _terminal(
        self,
        attempt_id: str,
        state: TransportState,
        started: float,
        *,
        status: ProviderHealthStatus | None = None,
        response_bytes: int | None = None,
    ) -> None:
        self._audit_event(
            attempt_id,
            state,
            response_bytes=response_bytes,
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            status=status,
        )

    def _request(self, body: bytes, cancel: threading.Event, timeout: float) -> tuple[Any, int, str]:
        if len(body) > MAX_LOCAL_REQUEST_BYTES:
            raise ProviderError("The redacted local AI request exceeds the ARX input bound.", ProviderHealthStatus.NOT_AVAILABLE)
        profile = self.manager.profile(self.profile_id)
        attempt_id = uuid.uuid4().hex
        started = time.monotonic()
        self._audit_event(attempt_id, TransportState.REQUEST_PREPARED, request_bytes=len(body))
        if cancel.is_set():
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.REQUEST_CANCELLED,
                "The local advisory request was cancelled.",
            )
            self._terminal(
                attempt_id,
                TransportState.CANCELLED,
                started,
                status=ProviderHealthStatus.CANCELLED,
            )
            raise AdvisoryCancelled("The local advisory request was cancelled.")
        request = urllib.request.Request(
            profile.endpoint.api_url("/v1/chat/completions"),
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "ARX-Local-AI/4"},
            method="POST",
        )
        if profile.session_capability:
            capability = self.manager.launcher.capability
            try:
                if capability is None:
                    raise CapabilityExpired
                request.add_unredirected_header("X-ARX-Session-Capability", capability.header_value())
            except CapabilityExpired:
                self.manager.mark_failed(
                    self.profile_id,
                    LocalAIFailure.AUTH_FAILURE,
                    "The local AI session capability is unavailable or expired.",
                )
                self._terminal(
                    attempt_id,
                    TransportState.REQUEST_FAILED,
                    started,
                    status=ProviderHealthStatus.AUTHENTICATION_FAILURE,
                )
                raise ProviderError(
                    "The local AI session capability is unavailable or expired.",
                    ProviderHealthStatus.AUTHENTICATION_FAILURE,
                ) from None
        try:
            self._audit_event(attempt_id, TransportState.OUTBOUND_REQUEST_INITIATED, request_bytes=len(body))
            raw = _run_cancellable(lambda: self._transport(request, timeout), cancel, timeout)
            if len(raw) > MAX_LOCAL_RESPONSE_BYTES:
                raise ValueError("The local AI endpoint returned an oversized response.")
            payload = json.loads(raw.decode("utf-8"))
        except AdvisoryCancelled:
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.REQUEST_CANCELLED,
                "The local advisory request was cancelled.",
            )
            self._terminal(attempt_id, TransportState.CANCELLED, started, status=ProviderHealthStatus.CANCELLED)
            raise
        except AdvisoryTimeout:
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.REQUEST_TIMEOUT,
                "The local advisory request timed out.",
            )
            self._terminal(attempt_id, TransportState.REQUEST_FAILED, started, status=ProviderHealthStatus.TIMEOUT)
            raise
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                status = ProviderHealthStatus.AUTHENTICATION_FAILURE
                failure = LocalAIFailure.AUTH_FAILURE
                message = "The local AI endpoint rejected the session authentication policy."
            elif exc.code == 404:
                status = ProviderHealthStatus.MODEL_NOT_AVAILABLE
                failure = LocalAIFailure.MODEL_MISSING
                message = "The configured local model or compatible chat endpoint is unavailable."
            else:
                status = ProviderHealthStatus.SERVER_FAILURE
                failure = LocalAIFailure.API_INCOMPATIBLE
                message = "The local AI endpoint could not complete the advisory request."
            self.manager.mark_failed(self.profile_id, failure, message)
            self._terminal(attempt_id, TransportState.REQUEST_FAILED, started, status=status)
            raise ProviderError(message, status) from None
        except (TimeoutError, urllib.error.URLError, ConnectionError, ssl.SSLError, OSError):
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.NETWORK_FAILURE,
                "The configured loopback local AI endpoint could not be reached.",
            )
            self._terminal(attempt_id, TransportState.REQUEST_FAILED, started, status=ProviderHealthStatus.NETWORK_FAILURE)
            raise ProviderError(
                "The configured loopback local AI endpoint could not be reached.",
                ProviderHealthStatus.NETWORK_FAILURE,
            ) from None
        except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.MALFORMED_RESPONSE,
                "The local AI endpoint returned a malformed or oversized response.",
            )
            self._terminal(attempt_id, TransportState.REQUEST_FAILED, started, status=ProviderHealthStatus.PARSE_FAILURE)
            raise ProviderError(
                "The local AI endpoint returned a malformed or oversized response.",
                ProviderHealthStatus.PARSE_FAILURE,
            ) from None
        except Exception:  # noqa: BLE001 - isolate and sanitize an injected/backend transport failure
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.REQUEST_FAILED,
                "The local AI endpoint failed unexpectedly.",
            )
            self._terminal(attempt_id, TransportState.REQUEST_FAILED, started, status=ProviderHealthStatus.SERVER_FAILURE)
            raise ProviderError(
                "The local AI endpoint failed unexpectedly.",
                ProviderHealthStatus.SERVER_FAILURE,
            ) from None
        finally:
            request.remove_header("X-ARX-Session-Capability")
        latency = max(0, round((time.monotonic() - started) * 1_000))
        self._terminal(
            attempt_id,
            TransportState.RESPONSE_RECEIVED,
            started,
            response_bytes=len(raw),
        )
        return payload, latency, attempt_id

    def ask(
        self,
        context: AdvisoryContext,
        question: str,
        *,
        mode: str = "Explain Technically",
        conversation: Sequence[Mapping[str, str]] = (),
        cancel: threading.Event | None = None,
        timeout: float = 90,
    ) -> AdvisoryResponse:
        availability = self.availability()
        if not availability.available:
            raise ProviderError(
                availability.reason,
                availability.operational_status or ProviderHealthStatus.NOT_AVAILABLE,
            )
        cancellation = cancel or threading.Event()
        prompt = str(
            redact_external(
                build_advisory_prompt(context, question, mode=mode, conversation=conversation),
                max_text_chars=MAX_CONTEXT_CHARS + 8_000,
            )
        )[: MAX_CONTEXT_CHARS + 8_000]
        profile = self.manager.profile(self.profile_id)
        model = self.manager.runtime(self.profile_id).model_identity or profile.model_id
        if not model:
            raise ProviderError("No local model is selected.", ProviderHealthStatus.MODEL_NOT_AVAILABLE)
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 1_500,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.manager.mark_busy(self.profile_id)
        try:
            payload, latency, attempt_id = self._request(body, cancellation, timeout)
            text = parse_local_chat_response(payload)
        except ProviderError as exc:
            if self.manager.runtime(self.profile_id).state is LocalAIState.BUSY:
                self.manager.mark_failed(
                    self.profile_id,
                    LocalAIFailure.REQUEST_FAILED,
                    str(exc),
                )
            raise
        except (TypeError, ValueError):
            self.manager.mark_failed(
                self.profile_id,
                LocalAIFailure.MALFORMED_RESPONSE,
                "The local AI endpoint returned no compatible advisory text.",
            )
            self._audit_event(
                attempt_id,
                TransportState.REQUEST_FAILED,
                latency_ms=latency,
                status=ProviderHealthStatus.PARSE_FAILURE,
            )
            raise ProviderError(
                "The local AI endpoint returned no compatible advisory text.",
                ProviderHealthStatus.PARSE_FAILURE,
            ) from None
        response = str(redact_external(text, max_text_chars=MAX_LOCAL_RESPONSE_CHARS))[:MAX_LOCAL_RESPONSE_CHARS]
        self.manager.mark_ready(self.profile_id)
        return AdvisoryResponse(self.name, response)
