import io
import json
import socket
import ssl
import subprocess
import threading
import time
import urllib.error

import pytest

from arx.advisory.audit import MemoryTransmissionAudit, TransportState
from arx.advisory.context import build_advisory_context
from arx.advisory.credentials import (
    CredentialState,
    ProviderCredentialResolver,
    WindowsDPAPICredentialStore,
)
from arx.advisory.health import ProviderHealthStatus
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryTimeout,
    CodexCLIProvider,
    OpenAIProvider,
    ProviderError,
    parse_openai_response,
)


KEY = "sk-proj-this-is-a-test-key-not-a-real-secret"


def _context():
    return build_advisory_context(
        "Compatibility finding",
        ("check", "status", "required", "observed", "reason"),
        ("Python", "RED", "<3.12", "3.13", "Resolved provider does not satisfy the project"),
    )


def _provider(*, transport=None, model="gpt-test", key=KEY, audit=None):
    return OpenAIProvider(
        model=model,
        key_getter=lambda: key,
        transport=transport,
        audit=audit or MemoryTransmissionAudit(),
    )


def _http_error(code, error_code=""):
    body = json.dumps({"error": {"code": error_code, "message": f"unsafe {KEY}"}}).encode()
    return urllib.error.HTTPError(
        "https://api.openai.com/v1/responses",
        code,
        "fixture",
        {},
        io.BytesIO(body),
    )


def test_openai_provider_is_optional_when_api_configuration_is_absent():
    provider = _provider(key=None)

    availability = provider.availability()
    health = provider.health()

    assert not availability.available
    assert availability.credential_state is CredentialState.NOT_CONFIGURED
    assert health.status is ProviderHealthStatus.NO_CREDENTIAL
    with pytest.raises(ProviderError) as error:
        provider.ask(_context(), "Explain", cancel=threading.Event())
    assert error.value.status is ProviderHealthStatus.NO_CREDENTIAL


def test_openai_unreadable_credential_is_not_reported_as_missing(tmp_path):
    store = WindowsDPAPICredentialStore(
        "openai-api",
        path=tmp_path / "openai-api.dpapi",
        protector=lambda value: bytes(value),
        unprotector=lambda _value: (_ for _ in ()).throw(OSError("wrong user")),
    )
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_bytes(b"ARX4-DPAPI-CREDENTIAL\x00\x01opaque")
    resolver = ProviderCredentialResolver(
        "openai-api",
        "OPENAI_API_KEY",
        store,
        environment_getter=lambda _name: None,
    )
    provider = OpenAIProvider(credential_resolver=resolver, audit=MemoryTransmissionAudit())

    availability = provider.availability()
    health = provider.health()

    assert availability.credential_state is CredentialState.CREDENTIAL_UNREADABLE
    assert health.status is ProviderHealthStatus.CREDENTIAL_UNREADABLE
    assert "cannot be decrypted" in health.message


def test_openai_health_uses_minimal_model_get_and_reports_evidence_backed_ready():
    captured = {}
    audit = MemoryTransmissionAudit()

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = request.data
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return json.dumps({"id": "gpt-test", "object": "model", "owned_by": "openai"}).encode()

    provider = _provider(transport=transport, audit=audit)
    health = provider.health(timeout=3)

    assert health.status is ProviderHealthStatus.READY
    assert health.credential_state is CredentialState.CONFIGURED
    assert health.model == "gpt-test"
    assert health.latency_ms is not None and health.latency_ms >= 0
    assert health.claims and health.validated_by == "provider-health-state-v1"
    assert captured == {
        "url": "https://api.openai.com/v1/models/gpt-test",
        "method": "GET",
        "body": None,
        "authorization": f"Bearer {KEY}",
        "timeout": 3,
    }
    assert [event.state for event in audit.events] == [
        TransportState.REQUEST_PREPARED,
        TransportState.OUTBOUND_REQUEST_INITIATED,
        TransportState.RESPONSE_RECEIVED,
    ]
    assert KEY not in json.dumps(audit.history())


@pytest.mark.parametrize(
    ("code", "error_code", "expected"),
    [
        (401, "invalid_api_key", ProviderHealthStatus.AUTHENTICATION_FAILURE),
        (403, "permission_denied", ProviderHealthStatus.AUTHENTICATION_FAILURE),
        (429, "rate_limit_exceeded", ProviderHealthStatus.RATE_LIMIT),
        (429, "insufficient_quota", ProviderHealthStatus.QUOTA_EXHAUSTED),
        (404, "model_not_found", ProviderHealthStatus.MODEL_NOT_AVAILABLE),
        (500, "server_error", ProviderHealthStatus.SERVER_FAILURE),
    ],
)
def test_openai_health_classifies_http_failures_without_server_message(code, error_code, expected):
    def fail(_request, _timeout):
        raise _http_error(code, error_code)

    health = _provider(transport=fail).health()

    assert health.status is expected
    assert KEY not in health.message
    assert "unsafe" not in health.message


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (urllib.error.URLError("network unavailable"), ProviderHealthStatus.NETWORK_FAILURE),
        (urllib.error.URLError(ssl.SSLError("certificate failure")), ProviderHealthStatus.TLS_HTTPS_FAILURE),
        (socket.timeout("slow"), ProviderHealthStatus.TIMEOUT),
    ],
)
def test_openai_health_classifies_transport_failures(error, expected):
    def fail(_request, _timeout):
        raise error

    health = _provider(transport=fail).health()

    assert health.status is expected
    assert "network unavailable" not in health.message
    assert "certificate failure" not in health.message


def test_openai_health_cancellation_is_distinct_and_never_starts_transport():
    calls = []
    audit = MemoryTransmissionAudit()
    cancel = threading.Event()
    cancel.set()
    provider = _provider(transport=lambda *_args: calls.append(True) or b"{}", audit=audit)

    health = provider.health(cancel=cancel)

    assert health.status is ProviderHealthStatus.CANCELLED
    assert calls == []
    assert [event.state for event in audit.events] == [TransportState.REQUEST_PREPARED, TransportState.CANCELLED]


def test_openai_health_rejects_malformed_or_wrong_model_metadata():
    malformed = _provider(transport=lambda *_args: b"not-json").health()
    wrong_model = _provider(transport=lambda *_args: b'{"id":"other","object":"model"}').health()

    assert malformed.status is ProviderHealthStatus.PARSE_FAILURE
    assert wrong_model.status is ProviderHealthStatus.PARSE_FAILURE


def test_openai_provider_uses_responses_api_and_redacts_again_at_transport_boundary():
    captured = {}
    audit = MemoryTransmissionAudit()

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["body"] = request.data
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return json.dumps({"output_text": "Safe explanation"}).encode()

    provider = _provider(transport=transport, audit=audit)
    response = provider.ask(
        _context(),
        rf"Explain C:\Private\source.py TOKEN={KEY}",
        conversation=[{"role": "user", "text": f"password={KEY}"}],
        cancel=threading.Event(),
        timeout=3,
    )
    request_body = captured["body"].decode("utf-8")

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 3
    assert captured["authorization"] == f"Bearer {KEY}"
    assert json.loads(request_body)["store"] is False
    assert json.loads(request_body)["model"] == "gpt-test"
    assert KEY not in request_body
    assert r"C:\Private" not in request_body
    assert response.provider == "OpenAI API"
    assert response.display_text().startswith("AI ADVISORY — NON-AUTHORITATIVE")
    assert [event.state for event in audit.events] == [
        TransportState.REQUEST_PREPARED,
        TransportState.OUTBOUND_REQUEST_INITIATED,
        TransportState.RESPONSE_RECEIVED,
    ]
    assert KEY not in json.dumps(audit.history())


@pytest.mark.parametrize("payload", [{}, {"output": []}, "bad", {"error": {"message": "invalid response"}}])
def test_openai_response_parser_rejects_missing_or_malformed_output(payload):
    with pytest.raises(ProviderError):
        parse_openai_response(payload)


def test_openai_provider_error_never_exposes_key_or_raw_network_detail():
    def fail(_request, _timeout):
        raise urllib.error.URLError(f"network unavailable with {KEY}")

    provider = _provider(transport=fail)
    with pytest.raises(ProviderError) as error:
        provider.ask(_context(), "Explain", cancel=threading.Event())

    assert error.value.status is ProviderHealthStatus.NETWORK_FAILURE
    assert KEY not in str(error.value)
    assert "network unavailable" not in str(error.value)


def test_openai_provider_timeout_and_cancellation_are_bounded_and_audited():
    def slow(_request, _timeout):
        time.sleep(0.3)
        return b"{}"

    timeout_audit = MemoryTransmissionAudit()
    provider = _provider(transport=slow, audit=timeout_audit)
    with pytest.raises(AdvisoryTimeout):
        provider.ask(_context(), "Explain", cancel=threading.Event(), timeout=0.02)
    assert timeout_audit.events[-1].state is TransportState.REQUEST_FAILED
    assert timeout_audit.events[-1].error_category == "TIMEOUT"

    cancelled_audit = MemoryTransmissionAudit()
    cancelled = threading.Event()
    cancelled.set()
    provider = _provider(transport=slow, audit=cancelled_audit)
    with pytest.raises(AdvisoryCancelled):
        provider.ask(_context(), "Explain", cancel=cancelled, timeout=1)
    assert [event.state for event in cancelled_audit.events] == [
        TransportState.REQUEST_PREPARED,
        TransportState.CANCELLED,
    ]


def test_openai_conversation_history_sent_to_model_is_bounded():
    captured = {}

    def transport(request, _timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return b'{"output_text":"bounded"}'

    conversation = [
        {"role": "user", "text": f"turn-{index}"}
        for index in range(12)
    ]
    _provider(transport=transport).ask(
        _context(),
        "latest",
        conversation=conversation,
        cancel=threading.Event(),
    )
    prompt = captured["body"]["input"]

    assert "turn-0" not in prompt
    assert "turn-5" not in prompt
    assert "turn-6" in prompt
    assert "turn-11" in prompt


def test_codex_command_is_read_only_ephemeral_and_contains_no_prompt(tmp_path):
    provider = CodexCLIProvider(executable=r"C:\Tools\codex.cmd", audit=MemoryTransmissionAudit())
    command = provider.command(tmp_path)

    assert command[:2] == [r"C:\Tools\codex.cmd", "exec"]
    assert ["--sandbox", "read-only"] == command[2:4]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--skip-git-repo-check" in command
    assert command[-1] == "-"
    assert "Remove-Item" not in command


def test_codex_prompt_uses_stdin_never_shell_or_argv_and_is_audited():
    captured = {}
    audit = MemoryTransmissionAudit()

    class Process:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            captured["input"] = input
            captured["communicate_timeout"] = timeout
            return "Codex explanation", ""

        def poll(self):
            return 0

    def popen(arguments, **kwargs):
        captured.update(arguments=arguments, kwargs=kwargs)
        return Process()

    version = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 0.149.0\n", stderr="")
    provider = CodexCLIProvider(
        executable=r"C:\Tools\codex.cmd",
        popen_factory=popen,
        version_runner=version,
        audit=audit,
    )
    response = provider.ask(_context(), 'Explain "; Remove-Item C:\\"', cancel=threading.Event(), timeout=2)

    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == captured["arguments"][captured["arguments"].index("-C") + 1]
    assert "Remove-Item" not in " ".join(captured["arguments"])
    assert "Remove-Item" in captured["input"]
    assert response.provider == "Codex CLI"
    assert response.display_text().startswith("AI ADVISORY — NON-AUTHORITATIVE")
    assert [event.state for event in audit.events] == [
        TransportState.REQUEST_PREPARED,
        TransportState.OUTBOUND_REQUEST_INITIATED,
        TransportState.RESPONSE_RECEIVED,
    ]


def test_codex_provider_remains_independent_when_openai_is_not_configured():
    class Process:
        returncode = 0

        def communicate(self, **_kwargs):
            return "Independent Codex result", ""

        def poll(self):
            return 0

    version = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 1.0", stderr="")
    openai = _provider(key=None)
    codex = CodexCLIProvider(
        executable="codex",
        popen_factory=lambda *args, **kwargs: Process(),
        version_runner=version,
        audit=MemoryTransmissionAudit(),
    )

    assert openai.health().status is ProviderHealthStatus.NO_CREDENTIAL
    assert codex.ask(_context(), "Explain", cancel=threading.Event()).text == "Independent Codex result"


def test_codex_provider_unavailable_and_empty_output_are_understandable():
    unavailable = CodexCLIProvider(executable=None, finder=lambda _name: None, audit=MemoryTransmissionAudit())
    assert not unavailable.availability().available
    with pytest.raises(ProviderError, match="not currently available"):
        unavailable.ask(_context(), "Explain", cancel=threading.Event())

    class EmptyProcess:
        returncode = 0

        def communicate(self, **_kwargs):
            return "", ""

        def poll(self):
            return 0

    version = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 1.0", stderr="")
    empty = CodexCLIProvider(
        executable="codex",
        popen_factory=lambda *args, **kwargs: EmptyProcess(),
        version_runner=version,
        audit=MemoryTransmissionAudit(),
    )
    with pytest.raises(ProviderError, match="no advisory text"):
        empty.ask(_context(), "Explain", cancel=threading.Event())


def test_codex_cancellation_terminates_the_process():
    cancel = threading.Event()
    calls = []

    class SlowProcess:
        returncode = None

        def communicate(self, **_kwargs):
            cancel.set()
            raise subprocess.TimeoutExpired("codex", 0.1)

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")
            self.returncode = -1

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return self.returncode

    version = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 1.0", stderr="")
    provider = CodexCLIProvider(
        executable="codex",
        popen_factory=lambda *args, **kwargs: SlowProcess(),
        version_runner=version,
        audit=MemoryTransmissionAudit(),
    )

    with pytest.raises(AdvisoryCancelled):
        provider.ask(_context(), "Explain", cancel=cancel, timeout=2)

    assert calls[0] == "terminate"
