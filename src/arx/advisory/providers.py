"""Optional provider adapters kept outside deterministic ARX conclusions."""

from __future__ import annotations

import json
import os
import queue
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from arx.core.models import Evidence, EvidenceKind

from .audit import (
    AuditError,
    TransmissionAudit,
    TransmissionEvent,
    TransportState,
    default_transmission_audit,
)
from .context import MAX_CONTEXT_CHARS, AdvisoryContext, build_advisory_prompt, redact_external
from .credentials import (
    CredentialNotConfigured,
    CredentialSource,
    CredentialState,
    CredentialStatus,
    CredentialUnreadable,
    ProviderCredentialResolver,
    default_openai_credential_resolver,
)
from .health import ProviderHealth, ProviderHealthStatus, checked_now, validate_provider_health


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DEFAULT_OPENAI_MODEL = "gpt-5.4"
MAX_ADVISORY_RESPONSE_CHARS = 64_000
MAX_PROVIDER_RESPONSE_BYTES = 1_000_000
MAX_PROVIDER_REQUEST_BYTES = MAX_CONTEXT_CHARS + 16_000
_ALLOWED_OPENAI_HOST = "api.openai.com"
_CONFIDENCE_NOTE = "Uncalibrated detector-author weight; not a probability or measured accuracy."


class ProviderError(RuntimeError):
    """A sanitized provider failure safe to present or persist as a category."""

    def __init__(
        self,
        message: str,
        status: ProviderHealthStatus = ProviderHealthStatus.SERVER_FAILURE,
        *,
        audit_failure: bool = False,
    ):
        super().__init__(str(redact_external(message)))
        self.status = status
        self.audit_failure = audit_failure


class AdvisoryCancelled(ProviderError):
    def __init__(self, message: str = "The advisory request was cancelled."):
        super().__init__(message, ProviderHealthStatus.CANCELLED)


class AdvisoryTimeout(ProviderError):
    def __init__(self, message: str = "The advisory request timed out."):
        super().__init__(message, ProviderHealthStatus.TIMEOUT)


@dataclass(frozen=True)
class ProviderAvailability:
    available: bool
    reason: str
    version: str | None = None
    credential_state: CredentialState | None = None
    operational_status: ProviderHealthStatus | None = None


@dataclass(frozen=True)
class AdvisoryResponse:
    provider: str
    text: str
    trust_label: str = "AI ADVISORY — NON-AUTHORITATIVE"

    def display_text(self) -> str:
        body = self.text.strip()
        if body.upper().startswith(self.trust_label):
            return body
        return f"{self.trust_label}\n\n{body}"


class AIProvider(Protocol):
    name: str

    def availability(self) -> ProviderAvailability: ...

    def ask(
        self,
        context: AdvisoryContext,
        question: str,
        *,
        mode: str,
        conversation: Sequence[Mapping[str, str]],
        cancel: threading.Event,
        timeout: float,
    ) -> AdvisoryResponse: ...


class AuditSink(Protocol):
    def record(self, event: TransmissionEvent) -> None: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Do not allow an authenticated OpenAI request to change endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _bounded(value: str) -> str:
    if len(value) <= MAX_ADVISORY_RESPONSE_CHARS:
        return value
    omitted = len(value) - MAX_ADVISORY_RESPONSE_CHARS
    return f"{value[:MAX_ADVISORY_RESPONSE_CHARS]}\n\n… <{omitted} response characters omitted by ARX>"


def _run_cancellable(call: Callable[[], bytes], cancel: threading.Event, timeout: float) -> bytes:
    if timeout <= 0:
        raise AdvisoryTimeout("The advisory timeout must be positive.")
    if cancel.is_set():
        raise AdvisoryCancelled()
    results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", call()))
        except Exception as exc:  # transported back to the calling thread
            results.put(("error", exc))

    threading.Thread(target=worker, daemon=True, name="arx-provider-transport").start()
    deadline = time.monotonic() + timeout
    while True:
        if cancel.is_set():
            raise AdvisoryCancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AdvisoryTimeout(f"The advisory request timed out after {timeout:g} seconds.")
        try:
            kind, payload = results.get(timeout=min(0.05, remaining))
        except queue.Empty:
            continue
        if kind == "error":
            raise payload  # type: ignore[misc]
        return payload  # type: ignore[return-value]


def _observed_claim(source: str, value: object, method: str, note: str | None = None) -> Evidence:
    return Evidence(
        EvidenceKind.OBSERVED,
        source,
        value,
        method,
        confidence=1.0,
        note=note or _CONFIDENCE_NOTE,
    )


def _credential_claim(status: CredentialStatus) -> Evidence:
    return _observed_claim(
        "provider-credential-resolver",
        {"state": status.state.value, "source": status.source.value},
        "bounded credential status inspection without revealing the secret",
    )


def parse_openai_response(payload: object) -> str:
    """Extract supported Responses API text while rejecting malformed data."""

    if not isinstance(payload, Mapping):
        raise ProviderError("OpenAI API returned a malformed response.", ProviderHealthStatus.PARSE_FAILURE)
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    fragments: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, Mapping) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    fragments.append(part["text"])
    text = "\n".join(fragment for fragment in fragments if fragment.strip())
    if text:
        return text
    if isinstance(payload.get("error"), Mapping):
        raise ProviderError("OpenAI API did not complete the response.", ProviderHealthStatus.SERVER_FAILURE)
    raise ProviderError("OpenAI API returned no advisory text.", ProviderHealthStatus.PARSE_FAILURE)


def _http_error_status(error: urllib.error.HTTPError) -> ProviderHealthStatus:
    error_code = ""
    try:
        raw = error.read(16_384)
        value = json.loads(raw.decode("utf-8"))
        if isinstance(value, Mapping) and isinstance(value.get("error"), Mapping):
            error_code = str(value["error"].get("code") or value["error"].get("type") or "").casefold()
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
        pass
    if error.code in (401, 403):
        return ProviderHealthStatus.AUTHENTICATION_FAILURE
    if error.code == 429:
        if any(token in error_code for token in ("quota", "billing", "credit")):
            return ProviderHealthStatus.QUOTA_EXHAUSTED
        return ProviderHealthStatus.RATE_LIMIT
    if error.code == 404 or "model" in error_code:
        return ProviderHealthStatus.MODEL_NOT_AVAILABLE
    if error.code in (408, 504):
        return ProviderHealthStatus.TIMEOUT
    return ProviderHealthStatus.SERVER_FAILURE


def _transport_error_status(error: BaseException) -> ProviderHealthStatus:
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return ProviderHealthStatus.TLS_HTTPS_FAILURE
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return ProviderHealthStatus.TIMEOUT
    return ProviderHealthStatus.NETWORK_FAILURE


_SAFE_STATUS_MESSAGES = {
    ProviderHealthStatus.NO_CREDENTIAL: "No OpenAI API credential is configured.",
    ProviderHealthStatus.CREDENTIAL_UNREADABLE: (
        "A saved OpenAI credential exists but cannot be decrypted in the current Windows context. "
        "Reconfigure or remove the stored credential."
    ),
    ProviderHealthStatus.NOT_AVAILABLE: "The OpenAI API provider configuration is not usable.",
    ProviderHealthStatus.NETWORK_FAILURE: "The OpenAI API could not be reached over the network.",
    ProviderHealthStatus.TLS_HTTPS_FAILURE: "The HTTPS/TLS connection to the OpenAI API could not be established safely.",
    ProviderHealthStatus.AUTHENTICATION_FAILURE: "The OpenAI API rejected the configured credential.",
    ProviderHealthStatus.RATE_LIMIT: "The OpenAI API rate limit was reached.",
    ProviderHealthStatus.QUOTA_EXHAUSTED: "The OpenAI API account or project has no available quota.",
    ProviderHealthStatus.MODEL_NOT_AVAILABLE: "The configured OpenAI model is not available to this API project.",
    ProviderHealthStatus.TIMEOUT: "The OpenAI API request timed out.",
    ProviderHealthStatus.CANCELLED: "The OpenAI API request was cancelled.",
    ProviderHealthStatus.SERVER_FAILURE: "The OpenAI API request failed at the service or local audit boundary.",
    ProviderHealthStatus.PARSE_FAILURE: "The OpenAI API returned a malformed or unsupported response.",
    ProviderHealthStatus.READY: "Authentication, API access, and the configured model were validated.",
}


class OpenAIProvider:
    """Supported OpenAI API adapter with DPAPI resolution, health, redaction, and audit."""

    name = "OpenAI API"
    provider_id = "openai-api"

    def __init__(
        self,
        *,
        model: str | None = None,
        credential_resolver: ProviderCredentialResolver | None = None,
        key_getter: Callable[[], str | None] | None = None,
        transport: Callable[[urllib.request.Request, float], bytes] | None = None,
        audit: AuditSink | None = None,
    ):
        self.model = model or os.environ.get("ARX_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        if credential_resolver is not None and key_getter is not None:
            raise ValueError("Use either credential_resolver or key_getter, not both.")
        if credential_resolver is not None:
            self._credentials = credential_resolver
        elif key_getter is not None:
            self._credentials = ProviderCredentialResolver(
                self.provider_id,
                "OPENAI_API_KEY",
                None,
                environment_getter=lambda _name: key_getter(),
            )
        else:
            self._credentials = default_openai_credential_resolver()
        self._transport = transport or self._default_transport
        self._audit = audit or default_transmission_audit()

    @staticmethod
    def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
        opener = urllib.request.build_opener(_RejectRedirects())
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        if len(payload) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ProviderError("OpenAI API returned an oversized response.", ProviderHealthStatus.PARSE_FAILURE)
        return payload

    @staticmethod
    def _validate_endpoint(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ProviderError("The OpenAI API endpoint is invalid.", ProviderHealthStatus.TLS_HTTPS_FAILURE) from exc
        if (
            parsed.scheme != "https"
            or parsed.hostname != _ALLOWED_OPENAI_HOST
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ProviderError("The OpenAI API endpoint failed the HTTPS allowlist.", ProviderHealthStatus.TLS_HTTPS_FAILURE)

    def _model_is_valid(self) -> bool:
        return bool(self.model) and len(self.model) <= 128 and all(
            character.isalnum() or character in "-._:" for character in self.model
        )

    def credential_status(self) -> CredentialStatus:
        return self._credentials.status()

    def availability(self) -> ProviderAvailability:
        credential = self.credential_status()
        if credential.state is CredentialState.NOT_CONFIGURED:
            return ProviderAvailability(
                False,
                _SAFE_STATUS_MESSAGES[ProviderHealthStatus.NO_CREDENTIAL],
                credential_state=credential.state,
                operational_status=ProviderHealthStatus.NO_CREDENTIAL,
            )
        if credential.state is CredentialState.CREDENTIAL_UNREADABLE:
            return ProviderAvailability(
                False,
                _SAFE_STATUS_MESSAGES[ProviderHealthStatus.CREDENTIAL_UNREADABLE],
                credential_state=credential.state,
                operational_status=ProviderHealthStatus.CREDENTIAL_UNREADABLE,
            )
        if not self._model_is_valid():
            return ProviderAvailability(
                False,
                "The OpenAI model configuration is empty or invalid.",
                credential_state=credential.state,
                operational_status=ProviderHealthStatus.NOT_AVAILABLE,
            )
        return ProviderAvailability(
            True,
            "Credential configured; use Test Connection to validate authentication, API, and model access.",
            self.model,
            credential.state,
            None,
        )

    def _audit_event(
        self,
        attempt_id: str,
        operation: str,
        state: TransportState,
        *,
        request_bytes: int | None = None,
        response_bytes: int | None = None,
        latency_ms: int | None = None,
        error_status: ProviderHealthStatus | None = None,
    ) -> None:
        try:
            self._audit.record(
                TransmissionEvent(
                    timestamp=checked_now(),
                    attempt_id=attempt_id,
                    provider_id=self.provider_id,
                    operation=operation,
                    state=state,
                    model=self.model,
                    request_bytes=request_bytes,
                    response_bytes=response_bytes,
                    latency_ms=latency_ms,
                    error_category=error_status.value if error_status is not None else None,
                )
            )
        except (AuditError, OSError, ValueError) as exc:
            raise ProviderError(
                "ARX could not maintain the required local metadata-only transmission audit.",
                ProviderHealthStatus.SERVER_FAILURE,
                audit_failure=True,
            ) from exc

    def _record_terminal(
        self,
        attempt_id: str,
        operation: str,
        state: TransportState,
        *,
        started_at: float,
        status: ProviderHealthStatus | None = None,
        response_bytes: int | None = None,
    ) -> int:
        latency = max(0, round((time.monotonic() - started_at) * 1_000))
        self._audit_event(
            attempt_id,
            operation,
            state,
            response_bytes=response_bytes,
            latency_ms=latency,
            error_status=status,
        )
        return latency

    def _request_json(
        self,
        url: str,
        *,
        operation: str,
        method: str,
        body: bytes | None,
        cancel: threading.Event,
        timeout: float,
    ) -> tuple[object, int, str]:
        self._validate_endpoint(url)
        request_size = len(body or b"")
        if request_size > MAX_PROVIDER_REQUEST_BYTES:
            raise ProviderError("The redacted OpenAI request exceeds the ARX input bound.", ProviderHealthStatus.NOT_AVAILABLE)
        attempt_id = uuid.uuid4().hex
        started_at = time.monotonic()
        self._audit_event(attempt_id, operation, TransportState.REQUEST_PREPARED, request_bytes=request_size)
        if cancel.is_set():
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.CANCELLED,
                started_at=started_at,
                status=ProviderHealthStatus.CANCELLED,
            )
            raise AdvisoryCancelled()
        try:
            with self._credentials.lease() as secret:
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "ARX-OpenAI-API/4"},
                    method=method,
                )
                authorization = f"Bearer {secret.text()}"
                request.add_unredirected_header("Authorization", authorization)
                try:
                    self._audit_event(
                        attempt_id,
                        operation,
                        TransportState.OUTBOUND_REQUEST_INITIATED,
                        request_bytes=request_size,
                    )
                    raw = _run_cancellable(lambda: self._transport(request, timeout), cancel, timeout)
                finally:
                    request.remove_header("Authorization")
                    authorization = "<released>"
        except CredentialNotConfigured:
            error = ProviderError(
                _SAFE_STATUS_MESSAGES[ProviderHealthStatus.NO_CREDENTIAL],
                ProviderHealthStatus.NO_CREDENTIAL,
            )
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=error.status,
            )
            raise error from None
        except CredentialUnreadable:
            error = ProviderError(
                _SAFE_STATUS_MESSAGES[ProviderHealthStatus.CREDENTIAL_UNREADABLE],
                ProviderHealthStatus.CREDENTIAL_UNREADABLE,
            )
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=error.status,
            )
            raise error from None
        except AdvisoryCancelled as exc:
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.CANCELLED,
                started_at=started_at,
                status=exc.status,
            )
            raise
        except AdvisoryTimeout as exc:
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=exc.status,
            )
            raise
        except urllib.error.HTTPError as exc:
            status = _http_error_status(exc)
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=status,
            )
            raise ProviderError(_SAFE_STATUS_MESSAGES[status], status) from None
        except (urllib.error.URLError, ssl.SSLError, ssl.CertificateError, TimeoutError, socket.timeout, OSError) as exc:
            status = _transport_error_status(exc)
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=status,
            )
            if status is ProviderHealthStatus.TIMEOUT:
                raise AdvisoryTimeout(_SAFE_STATUS_MESSAGES[status]) from None
            raise ProviderError(_SAFE_STATUS_MESSAGES[status], status) from None
        except ProviderError as exc:
            if not exc.audit_failure:
                self._record_terminal(
                    attempt_id,
                    operation,
                    TransportState.REQUEST_FAILED,
                    started_at=started_at,
                    status=exc.status,
                )
            raise

        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            error = ProviderError("OpenAI API returned an oversized response.", ProviderHealthStatus.PARSE_FAILURE)
            self._record_terminal(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                started_at=started_at,
                status=error.status,
            )
            raise error
        latency = self._record_terminal(
            attempt_id,
            operation,
            TransportState.RESPONSE_RECEIVED,
            started_at=started_at,
            response_bytes=len(raw),
        )
        try:
            return json.loads(raw.decode("utf-8")), latency, attempt_id
        except (UnicodeError, json.JSONDecodeError):
            error = ProviderError(_SAFE_STATUS_MESSAGES[ProviderHealthStatus.PARSE_FAILURE], ProviderHealthStatus.PARSE_FAILURE)
            self._audit_event(
                attempt_id,
                operation,
                TransportState.REQUEST_FAILED,
                latency_ms=latency,
                error_status=error.status,
            )
            raise error from None

    def _health_result(
        self,
        status: ProviderHealthStatus,
        credential: CredentialStatus,
        *,
        latency_ms: int | None = None,
        checked_model: str | None = None,
    ) -> ProviderHealth:
        claims = [_credential_claim(credential)]
        if checked_model is not None:
            claims.append(
                _observed_claim(
                    "openai-model-metadata",
                    checked_model,
                    "authenticated HTTPS GET model metadata response",
                )
            )
        if latency_ms is not None:
            claims.append(
                _observed_claim(
                    "openai-transport-timer",
                    latency_ms,
                    "local monotonic elapsed-time measurement in milliseconds",
                )
            )
        if status is not ProviderHealthStatus.READY:
            claims.append(
                _observed_claim(
                    "openai-provider-health",
                    status.value,
                    "sanitized provider failure classification",
                )
            )
        return validate_provider_health(
            ProviderHealth(
                provider_id=self.provider_id,
                status=status,
                credential_state=credential.state,
                model=checked_model if status is ProviderHealthStatus.READY else self.model,
                latency_ms=latency_ms,
                checked_at=checked_now(),
                category=status.value,
                message=_SAFE_STATUS_MESSAGES[status],
                claims=tuple(claims),
            )
        )

    def health(self, *, cancel: threading.Event | None = None, timeout: float = 15) -> ProviderHealth:
        """Explicit minimal-data health check; no ARX evidence or prompt is transmitted."""

        credential = self.credential_status()
        if credential.state is CredentialState.NOT_CONFIGURED:
            return self._health_result(ProviderHealthStatus.NO_CREDENTIAL, credential)
        if credential.state is CredentialState.CREDENTIAL_UNREADABLE:
            return self._health_result(ProviderHealthStatus.CREDENTIAL_UNREADABLE, credential)
        if not self._model_is_valid():
            return self._health_result(ProviderHealthStatus.NOT_AVAILABLE, credential)
        cancellation = cancel or threading.Event()
        url = f"{OPENAI_MODELS_URL}/{urllib.parse.quote(self.model, safe='-._:')}"
        try:
            payload, latency, attempt_id = self._request_json(
                url,
                operation="health_check",
                method="GET",
                body=None,
                cancel=cancellation,
                timeout=timeout,
            )
            if not isinstance(payload, Mapping) or payload.get("object") != "model" or payload.get("id") != self.model:
                self._audit_event(
                    attempt_id,
                    "health_check",
                    TransportState.REQUEST_FAILED,
                    latency_ms=latency,
                    error_status=ProviderHealthStatus.PARSE_FAILURE,
                )
                raise ProviderError(_SAFE_STATUS_MESSAGES[ProviderHealthStatus.PARSE_FAILURE], ProviderHealthStatus.PARSE_FAILURE)
            return self._health_result(
                ProviderHealthStatus.READY,
                credential,
                latency_ms=latency,
                checked_model=self.model,
            )
        except ProviderError as exc:
            return self._health_result(exc.status, credential)

    def ask(
        self,
        context: AdvisoryContext,
        question: str,
        *,
        mode: str = "Explain Technically",
        conversation: Sequence[Mapping[str, str]] = (),
        cancel: threading.Event | None = None,
        timeout: float = 60,
    ) -> AdvisoryResponse:
        cancellation = cancel or threading.Event()
        availability = self.availability()
        if not availability.available:
            raise ProviderError(
                availability.reason,
                availability.operational_status or ProviderHealthStatus.NOT_AVAILABLE,
            )
        prompt = build_advisory_prompt(context, question, mode=mode, conversation=conversation)
        boundary_prompt = str(
            redact_external(prompt, max_text_chars=MAX_CONTEXT_CHARS + 8_000)
        )[: MAX_CONTEXT_CHARS + 8_000]
        body = json.dumps(
            {
                "model": self.model,
                "input": boundary_prompt,
                "store": False,
                "max_output_tokens": 1_500,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        payload, latency, attempt_id = self._request_json(
            OPENAI_RESPONSES_URL,
            operation="advisory",
            method="POST",
            body=body,
            cancel=cancellation,
            timeout=timeout,
        )
        try:
            text = parse_openai_response(payload)
        except ProviderError as exc:
            self._audit_event(
                attempt_id,
                "advisory",
                TransportState.REQUEST_FAILED,
                latency_ms=latency,
                error_status=exc.status,
            )
            raise
        return AdvisoryResponse(self.name, _bounded(text))


class CodexCLIProvider:
    """Read-only, ephemeral, non-interactive Codex CLI adapter."""

    name = "Codex CLI"
    provider_id = "codex-cli"

    def __init__(
        self,
        *,
        executable: str | None = None,
        finder: Callable[[str], str | None] = shutil.which,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        version_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        audit: AuditSink | None = None,
    ):
        self.executable = executable or finder("codex")
        self._popen_factory = popen_factory
        self._version_runner = version_runner
        self._audit = audit or default_transmission_audit()

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

    def availability(self) -> ProviderAvailability:
        if not self.executable:
            return ProviderAvailability(False, "Codex CLI is not currently available.")
        try:
            result = self._version_runner(
                [self.executable, "--version"],
                shell=False,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return ProviderAvailability(False, "Codex CLI was found but could not be queried safely.")
        version = (result.stdout or "").strip()
        if result.returncode != 0 or not version:
            return ProviderAvailability(False, "Codex CLI did not report a usable version.")
        return ProviderAvailability(True, "Codex CLI is available.", version)

    def command(self, working_directory: Path) -> list[str]:
        if not self.executable:
            raise ProviderError("Codex CLI is not currently available.", ProviderHealthStatus.NOT_AVAILABLE)
        return [
            self.executable,
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--color",
            "never",
            "--skip-git-repo-check",
            "-C",
            str(working_directory),
            "-",
        ]

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

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
        cancellation = cancel or threading.Event()
        availability = self.availability()
        if not availability.available:
            raise ProviderError(availability.reason, ProviderHealthStatus.NOT_AVAILABLE)
        prompt = str(
            redact_external(
                build_advisory_prompt(context, question, mode=mode, conversation=conversation),
                max_text_chars=MAX_CONTEXT_CHARS + 8_000,
            )
        )[: MAX_CONTEXT_CHARS + 8_000]
        prompt_bytes = len(prompt.encode("utf-8"))
        attempt_id = uuid.uuid4().hex
        started_at = time.monotonic()
        self._audit_event(attempt_id, TransportState.REQUEST_PREPARED, request_bytes=prompt_bytes)
        if cancellation.is_set():
            self._audit_event(
                attempt_id,
                TransportState.CANCELLED,
                latency_ms=0,
                status=ProviderHealthStatus.CANCELLED,
            )
            raise AdvisoryCancelled("Codex analysis was cancelled.")
        with tempfile.TemporaryDirectory(prefix="arx-codex-advisory-") as temporary:
            working_directory = Path(temporary)
            arguments = self.command(working_directory)
            try:
                process = self._popen_factory(
                    arguments,
                    cwd=str(working_directory),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError:
                self._audit_event(
                    attempt_id,
                    TransportState.REQUEST_FAILED,
                    latency_ms=max(0, round((time.monotonic() - started_at) * 1_000)),
                    status=ProviderHealthStatus.NOT_AVAILABLE,
                )
                raise ProviderError("Codex CLI could not be started.", ProviderHealthStatus.NOT_AVAILABLE) from None
            self._audit_event(attempt_id, TransportState.OUTBOUND_REQUEST_INITIATED, request_bytes=prompt_bytes)
            deadline = time.monotonic() + timeout
            first = True
            while True:
                if cancellation.is_set():
                    self._stop(process)
                    self._audit_event(
                        attempt_id,
                        TransportState.CANCELLED,
                        latency_ms=max(0, round((time.monotonic() - started_at) * 1_000)),
                        status=ProviderHealthStatus.CANCELLED,
                    )
                    raise AdvisoryCancelled("Codex analysis was cancelled.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop(process)
                    self._audit_event(
                        attempt_id,
                        TransportState.REQUEST_FAILED,
                        latency_ms=max(0, round((time.monotonic() - started_at) * 1_000)),
                        status=ProviderHealthStatus.TIMEOUT,
                    )
                    raise AdvisoryTimeout(f"Codex analysis timed out after {timeout:g} seconds.")
                try:
                    stdout, stderr = process.communicate(input=prompt if first else None, timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    continue
            latency = max(0, round((time.monotonic() - started_at) * 1_000))
            if process.returncode != 0:
                self._audit_event(
                    attempt_id,
                    TransportState.REQUEST_FAILED,
                    latency_ms=latency,
                    status=ProviderHealthStatus.SERVER_FAILURE,
                )
                safe_error = _bounded(str(redact_external((stderr or "Codex CLI failed.").strip())))
                raise ProviderError(
                    f"Codex CLI could not complete the advisory request: {safe_error}",
                    ProviderHealthStatus.SERVER_FAILURE,
                )
            if not (stdout or "").strip():
                self._audit_event(
                    attempt_id,
                    TransportState.REQUEST_FAILED,
                    latency_ms=latency,
                    status=ProviderHealthStatus.PARSE_FAILURE,
                )
                raise ProviderError("Codex CLI returned no advisory text.", ProviderHealthStatus.PARSE_FAILURE)
            response = _bounded(str(redact_external(stdout.strip(), max_text_chars=MAX_ADVISORY_RESPONSE_CHARS)))
            self._audit_event(
                attempt_id,
                TransportState.RESPONSE_RECEIVED,
                response_bytes=len(response.encode("utf-8")),
                latency_ms=latency,
            )
            return AdvisoryResponse(self.name, response)
