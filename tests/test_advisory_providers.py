import json
import subprocess
import threading
import time
import urllib.error

import pytest

from arx.advisory.context import build_advisory_context
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryTimeout,
    CodexCLIProvider,
    OpenAIProvider,
    ProviderError,
    parse_openai_response,
)


def _context():
    return build_advisory_context(
        "Compatibility finding",
        ("check", "status", "required", "observed", "reason"),
        ("Python", "RED", "<3.12", "3.13", "Resolved provider does not satisfy the project"),
    )


def test_openai_provider_is_optional_when_api_configuration_is_absent():
    provider = OpenAIProvider(key_getter=lambda: None)

    availability = provider.availability()

    assert not availability.available
    assert "OPENAI_API_KEY" in availability.reason
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        provider.ask(_context(), "Explain", cancel=threading.Event())


def test_openai_provider_uses_responses_api_without_putting_key_in_payload():
    captured = {}
    key = "sk-proj-this-is-a-test-key-not-a-real-secret"

    def transport(request, timeout):
        captured.update(request=request, timeout=timeout)
        return json.dumps({"output": [{"content": [{"type": "output_text", "text": "Safe explanation"}]}]}).encode()

    provider = OpenAIProvider(model="gpt-test", key_getter=lambda: key, transport=transport)
    response = provider.ask(_context(), "Explain", cancel=threading.Event(), timeout=3)
    request_body = captured["request"].data.decode("utf-8")

    assert captured["request"].full_url == "https://api.openai.com/v1/responses"
    assert captured["request"].method == "POST"
    assert captured["timeout"] == 3
    assert json.loads(request_body)["store"] is False
    assert json.loads(request_body)["model"] == "gpt-test"
    assert key not in request_body
    assert response.provider == "OpenAI"
    assert response.display_text().startswith("AI ADVISORY")


@pytest.mark.parametrize("payload", [{}, {"output": []}, "bad", {"error": {"message": "invalid response"}}])
def test_openai_response_parser_rejects_missing_or_malformed_output(payload):
    with pytest.raises(ProviderError):
        parse_openai_response(payload)


def test_openai_provider_handles_network_failure_without_exposing_key():
    key = "sk-proj-this-is-a-test-key-not-a-real-secret"

    def fail(_request, _timeout):
        raise urllib.error.URLError("network unavailable")

    provider = OpenAIProvider(key_getter=lambda: key, transport=fail)
    with pytest.raises(ProviderError, match="network unavailable") as error:
        provider.ask(_context(), "Explain", cancel=threading.Event())

    assert key not in str(error.value)


def test_openai_provider_timeout_and_cancellation_are_bounded():
    def slow(_request, _timeout):
        time.sleep(0.3)
        return b"{}"

    provider = OpenAIProvider(key_getter=lambda: "sk-proj-this-is-a-test-key-not-a-real-secret", transport=slow)
    with pytest.raises(AdvisoryTimeout):
        provider.ask(_context(), "Explain", cancel=threading.Event(), timeout=0.02)

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(AdvisoryCancelled):
        provider.ask(_context(), "Explain", cancel=cancelled, timeout=1)


def test_codex_command_is_read_only_ephemeral_and_contains_no_prompt(tmp_path):
    provider = CodexCLIProvider(executable=r"C:\Tools\codex.cmd")
    command = provider.command(tmp_path)

    assert command[:2] == [r"C:\Tools\codex.cmd", "exec"]
    assert ["--sandbox", "read-only"] == command[2:4]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--skip-git-repo-check" in command
    assert command[-1] == "-"
    assert "Remove-Item" not in command


def test_codex_prompt_uses_stdin_and_process_never_uses_shell():
    captured = {}

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
    provider = CodexCLIProvider(executable=r"C:\Tools\codex.cmd", popen_factory=popen, version_runner=version)
    response = provider.ask(_context(), 'Explain "; Remove-Item C:\\"', cancel=threading.Event(), timeout=2)

    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == captured["arguments"][captured["arguments"].index("-C") + 1]
    assert "Remove-Item" not in " ".join(captured["arguments"])
    assert "Remove-Item" in captured["input"]
    assert response.provider == "Codex CLI"
    assert response.display_text().startswith("AI ADVISORY")


def test_codex_provider_unavailable_and_empty_output_are_understandable():
    unavailable = CodexCLIProvider(executable=None, finder=lambda _name: None)
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
    empty = CodexCLIProvider(executable="codex", popen_factory=lambda *args, **kwargs: EmptyProcess(), version_runner=version)
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
    provider = CodexCLIProvider(executable="codex", popen_factory=lambda *args, **kwargs: SlowProcess(), version_runner=version)

    with pytest.raises(AdvisoryCancelled):
        provider.ask(_context(), "Explain", cancel=cancel, timeout=2)

    assert calls[0] == "terminate"
