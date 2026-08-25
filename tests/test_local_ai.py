import copy
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request

import pytest

from arx.advisory.audit import MemoryTransmissionAudit, TransportState
from arx.advisory.context import ContextSelection, build_intelligence_context
from arx.advisory.health import ProviderHealthStatus
from arx.advisory.providers import (
    AdvisoryCancelled,
    AdvisoryTimeout,
    OpenAIProvider,
    ProviderError,
)
from arx.core.models import EvidenceKind
from arx.local_ai import (
    ApprovalRequired,
    AssistanceProfile,
    BackendKind,
    BackendProfile,
    CapabilityExpired,
    LocalAIApprovalStore,
    LocalAIDiscovery,
    LocalAIFailure,
    LocalAILauncher,
    LocalAIManager,
    LocalAIProfileStore,
    LocalAIProvider,
    LocalAIState,
    LocalEndpoint,
    SessionCapability,
)
from arx.local_ai.backends import LlamaCppBackendAdapter


class FakeProcess:
    def __init__(self, *, pid=4242, crash_code=None):
        self.pid = pid
        self.returncode = crash_code
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        del timeout
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def _stores(tmp_path):
    return (
        LocalAIProfileStore(tmp_path / "profiles.json"),
        LocalAIApprovalStore(tmp_path / "approvals.json"),
    )


def _external_profile(**overrides):
    values = {
        "profile_id": "local-test",
        "display_name": "Local test endpoint",
        "backend": BackendKind.OPENAI_COMPATIBLE,
        "endpoint": LocalEndpoint("http://127.0.0.1:8765"),
        "model_id": "model-test",
    }
    values.update(overrides)
    return BackendProfile(**values)


def _llama_profile(tmp_path, **overrides):
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"MZ-local-test")
    model.write_bytes(b"GGUF-local-test")
    values = {
        "profile_id": "llama-test",
        "display_name": "Approved llama.cpp",
        "backend": BackendKind.LLAMA_CPP,
        "endpoint": LocalEndpoint("http://127.0.0.1:8766"),
        "model_id": "model-test",
        "executable": executable,
        "model_path": model,
    }
    values.update(overrides)
    return BackendProfile(**values)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://0.0.0.0:8000",
        "http://192.168.1.20:8000",
        "https://example.com:443",
        "ftp://127.0.0.1:8000",
        "http://user:" + "secret@127.0.0.1:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000?token=secret",
    ],
)
def test_local_endpoint_rejects_non_loopback_wildcard_credentials_and_ambiguous_ports(endpoint):
    with pytest.raises(ValueError):
        LocalEndpoint(endpoint)


def test_local_endpoint_accepts_only_explicit_loopback_forms():
    assert LocalEndpoint("http://127.0.0.1:8000/").base_url == "http://127.0.0.1:8000"
    assert LocalEndpoint("http://localhost:8080").base_url == "http://127.0.0.1:8080"
    assert LocalEndpoint("http://[::1]:9000").port == 9000
    assert LocalEndpoint().host == "127.0.0.1"


def test_default_local_transports_disable_ambient_proxies(monkeypatch):
    captured: list[tuple[object, ...]] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b"{}"

    class Opener:
        def open(self, _request, *, timeout):
            assert timeout == 1
            return Response()

    def build_opener(*handlers):
        captured.append(handlers)
        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    request = urllib.request.Request("http://127.0.0.1:8765/v1/models")

    assert LocalAIDiscovery._default_transport(request, 1) == b"{}"
    assert LocalAIProvider._default_transport(request, 1) == b"{}"
    assert len(captured) == 2
    for handlers in captured:
        proxy = next(item for item in handlers if isinstance(item, urllib.request.ProxyHandler))
        assert proxy.proxies == {}


def test_session_capability_is_random_memory_only_bounded_and_expires():
    clock = [10.0]
    first = SessionCapability(ttl_seconds=2, now=lambda: clock[0])
    second = SessionCapability(ttl_seconds=2, now=lambda: clock[0])
    first_value = first.header_value()

    assert first_value != second.header_value()
    assert len(first_value) >= 32
    assert first_value not in repr(first)
    assert "redacted" in repr(first).casefold()
    clock[0] = 12.1
    assert first.expired
    with pytest.raises(CapabilityExpired):
        first.header_value()
    first.close()
    second.close()


def test_profile_and_approval_stores_never_persist_session_capability(tmp_path):
    profiles, approvals = _stores(tmp_path)
    profile = _external_profile(assistance=AssistanceProfile.AUTOMATED)
    capability = SessionCapability(token_factory=lambda _size: "S" * 48)

    profiles.save((profile,))
    approvals.approve(profile)
    stored = profiles.path.read_text(encoding="utf-8") + approvals.path.read_text(encoding="utf-8")

    assert capability.header_value() not in stored
    assert "OPENAI_API_KEY" not in stored
    assert approvals.approved(profile, automatic=True)
    changed = _external_profile(model_id="different-model", assistance=AssistanceProfile.AUTOMATED)
    assert not approvals.approved(changed)
    capability.close()


def test_manager_construction_does_not_contact_or_launch_a_provider(tmp_path):
    calls = []
    discovery = LocalAIDiscovery(transport=lambda *_args: calls.append(True) or b"{}")
    profiles, approvals = _stores(tmp_path)

    manager = LocalAIManager(profile_store=profiles, approval_store=approvals, discovery=discovery)

    assert calls == []
    assert manager.runtime().state is LocalAIState.NOT_FOUND
    assert manager.launcher.process is None


def test_explicit_discovery_enumerates_models_and_rejects_malformed_payload(tmp_path):
    requests = []

    def transport(request, timeout):
        requests.append((request.full_url, timeout, dict(request.header_items())))
        return b'{"data":[{"id":"model-test","owned_by":"local"}],"version":"1.2"}'

    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((_external_profile(),))
    manager = LocalAIManager(
        profile_store=profile_store,
        approval_store=approval_store,
        discovery=LocalAIDiscovery(transport=transport),
    )

    result = manager.discover(timeout=2)

    assert result.ready
    assert [model.model_id for model in result.models] == ["model-test"]
    assert requests[0][0] == "http://127.0.0.1:8765/v1/models"
    assert manager.runtime().state is LocalAIState.READY

    malformed = LocalAIDiscovery(transport=lambda *_args: b'{"data":"wrong"}').probe(_external_profile())
    assert malformed.state is LocalAIState.FAILED
    assert malformed.failure is LocalAIFailure.API_INCOMPATIBLE


def test_llama_start_requires_first_run_approval_and_uses_typed_hidden_process(tmp_path, monkeypatch):
    profile = _llama_profile(tmp_path)
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((profile,))
    captured = {}
    process = FakeProcess()

    def popen(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["kwargs"] = kwargs
        return process

    discovery = LocalAIDiscovery(
        transport=lambda *_args: b'{"data":[{"id":"model-test"}],"version":"fixture"}'
    )
    launcher = LocalAILauncher(discovery=discovery, popen_factory=popen, port_in_use=lambda _profile: False)
    manager = LocalAIManager(
        profile_store=profile_store,
        approval_store=approval_store,
        discovery=discovery,
        launcher=launcher,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-child")

    with pytest.raises(ApprovalRequired):
        manager.start(timeout=2)
    runtime = manager.start(explicit_approval=True, timeout=2)

    assert runtime.state is LocalAIState.READY
    assert runtime.pid == process.pid
    assert captured["arguments"] == [
        str(profile.executable),
        "--host",
        "127.0.0.1",
        "--port",
        "8766",
        "--model",
        str(profile.model_path),
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    assert captured["kwargs"]["stdout"] is subprocess.DEVNULL
    assert captured["kwargs"]["stderr"] is subprocess.DEVNULL
    assert "OPENAI_API_KEY" not in captured["kwargs"]["env"]
    assert "must-not-reach-child" not in repr(captured["kwargs"]["env"])
    assert approval_store.approved(profile)
    manager.save_profile(profile)
    refreshed = manager.discover()
    assert refreshed.ready
    assert manager.runtime().pid == process.pid
    stopped = manager.stop()
    assert stopped.state is LocalAIState.STOPPED
    assert process.terminated


def test_launcher_classifies_port_conflict_timeout_and_process_crash(tmp_path):
    profile = _llama_profile(tmp_path)
    discovery = LocalAIDiscovery(transport=lambda *_args: (_ for _ in ()).throw(urllib.error.URLError("offline")))

    conflict = LocalAILauncher(discovery=discovery, port_in_use=lambda _profile: True).start(
        profile,
        LlamaCppBackendAdapter(),
    )
    assert conflict.failure is LocalAIFailure.PORT_CONFLICT

    crashed_process = FakeProcess(crash_code=7)
    crashed = LocalAILauncher(
        discovery=discovery,
        popen_factory=lambda *_args, **_kwargs: crashed_process,
        port_in_use=lambda _profile: False,
    ).start(
        profile,
        LlamaCppBackendAdapter(),
        timeout=1,
    )
    assert crashed.failure is LocalAIFailure.PROCESS_CRASHED
    assert crashed.exit_code == 7

    clock = [0.0]

    def monotonic():
        clock[0] += 0.2
        return clock[0]

    timeout_process = FakeProcess()
    timed_out = LocalAILauncher(
        discovery=LocalAIDiscovery(
            transport=lambda *_args: (_ for _ in ()).throw(urllib.error.URLError("offline")),
            monotonic=monotonic,
        ),
        popen_factory=lambda *_args, **_kwargs: timeout_process,
        port_in_use=lambda _profile: False,
        monotonic=monotonic,
        sleeper=lambda _seconds: None,
    ).start(
        profile,
        LlamaCppBackendAdapter(),
        timeout=1,
    )
    assert timed_out.failure is LocalAIFailure.STARTUP_TIMEOUT
    assert timeout_process.terminated


def test_local_provider_reuses_bounded_redacted_context_and_metadata_only_audit(tmp_path):
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((_external_profile(),))
    discovery = LocalAIDiscovery(transport=lambda *_args: b'{"data":[{"id":"model-test"}]}')
    manager = LocalAIManager(profile_store=profile_store, approval_store=approval_store, discovery=discovery)
    assert manager.discover().ready
    audit = MemoryTransmissionAudit()
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return b'{"choices":[{"message":{"role":"assistant","content":"Local interpretation only"}}]}'

    provider = LocalAIProvider(manager, transport=transport, audit=audit)
    deterministic = {
        "finding": "Python mismatch",
        "readiness": "YELLOW",
        "evidence": [{"kind": "inferred", "value": "TOKEN=never-leave"}],
    }
    before = copy.deepcopy(deterministic)
    context = build_intelligence_context(
        selected=deterministic,
        evidence=deterministic["evidence"],
        conclusions={"readiness": deterministic["readiness"]},
    )
    response = provider.ask(
        context,
        "Explain API_KEY=abcdefghijklmnop",
        mode="Explain Technically",
        conversation=[{"role": "user", "text": "Earlier TOKEN=history-secret"}],
        cancel=threading.Event(),
        timeout=2,
    )

    assert response.provider == "Local AI"
    assert response.display_text().startswith("AI ADVISORY — NON-AUTHORITATIVE")
    assert captured["url"] == "http://127.0.0.1:8765/v1/chat/completions"
    assert "never-leave" not in captured["body"]
    assert "abcdefghijklmnop" not in captured["body"]
    assert "history-secret" not in captured["body"]
    assert deterministic == before
    assert list(EvidenceKind) == [
        EvidenceKind.DECLARED,
        EvidenceKind.OBSERVED,
        EvidenceKind.INFERRED,
        EvidenceKind.ESTIMATED,
        EvidenceKind.SIMULATED,
        EvidenceKind.STRUCTURAL,
        EvidenceKind.UNKNOWN,
    ]
    assert [event.state for event in audit.events] == [
        TransportState.REQUEST_PREPARED,
        TransportState.OUTBOUND_REQUEST_INITIATED,
        TransportState.RESPONSE_RECEIVED,
    ]
    serialized_audit = json.dumps(audit.history())
    assert "never-leave" not in serialized_audit
    assert captured["body"] not in serialized_audit
    assert "Local interpretation only" not in serialized_audit
    assert "messages" not in serialized_audit


def test_local_provider_classifies_malformed_cancellation_and_timeout(tmp_path):
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((_external_profile(),))
    discovery = LocalAIDiscovery(transport=lambda *_args: b'{"data":[{"id":"model-test"}]}')
    manager = LocalAIManager(profile_store=profile_store, approval_store=approval_store, discovery=discovery)
    manager.discover()
    malformed = LocalAIProvider(
        manager,
        transport=lambda *_args: b'{"choices":[]}',
        audit=MemoryTransmissionAudit(),
    )
    with pytest.raises(ProviderError) as malformed_error:
        malformed.ask(build_intelligence_context(selected={"finding": "x"}), "q", cancel=threading.Event())
    assert malformed_error.value.status is ProviderHealthStatus.PARSE_FAILURE
    assert manager.runtime().failure is LocalAIFailure.MALFORMED_RESPONSE

    manager.discover()
    cancelled = threading.Event()
    cancelled.set()
    audit = MemoryTransmissionAudit()
    with pytest.raises(AdvisoryCancelled):
        LocalAIProvider(manager, transport=lambda *_args: b"{}", audit=audit).ask(
            build_intelligence_context(selected={"finding": "x"}),
            "q",
            cancel=cancelled,
        )
    assert audit.events[-1].state is TransportState.CANCELLED
    assert manager.runtime().failure is LocalAIFailure.REQUEST_CANCELLED

    manager.discover()

    def slow(*_args):
        time.sleep(0.1)
        return b"{}"

    with pytest.raises(AdvisoryTimeout):
        LocalAIProvider(manager, transport=slow, audit=MemoryTransmissionAudit()).ask(
            build_intelligence_context(selected={"finding": "x"}),
            "q",
            cancel=threading.Event(),
            timeout=0.01,
        )
    assert manager.runtime().failure is LocalAIFailure.REQUEST_TIMEOUT


def test_external_profile_connects_without_process_launch_and_automation_requires_policy(tmp_path):
    profile_store, approval_store = _stores(tmp_path)
    external = _external_profile(assistance=AssistanceProfile.AUTOMATED)
    profile_store.save((external,))
    calls = []
    discovery = LocalAIDiscovery(
        transport=lambda *_args: calls.append(True) or b'{"data":[{"id":"model-test"}]}'
    )
    manager = LocalAIManager(profile_store=profile_store, approval_store=approval_store, discovery=discovery)

    runtime = manager.start(timeout=2)

    assert runtime.state is LocalAIState.READY
    assert manager.launcher.process is None
    assert calls == [True]
    with pytest.raises(ApprovalRequired):
        manager.auto_start()


def test_no_model_output_or_profile_text_can_become_a_shell_command(tmp_path):
    profile = _llama_profile(tmp_path, display_name='"; Remove-Item C:\\ -Recurse')
    captured = {}
    process = FakeProcess()
    discovery = LocalAIDiscovery(transport=lambda *_args: b'{"data":[{"id":"model-test"}]}')
    launcher = LocalAILauncher(
        discovery=discovery,
        popen_factory=lambda arguments, **kwargs: captured.update(arguments=arguments, kwargs=kwargs) or process,
        port_in_use=lambda _profile: False,
    )

    runtime = launcher.start(
        profile,
        LlamaCppBackendAdapter(),
        timeout=2,
    )

    assert runtime.state is LocalAIState.READY
    assert captured["kwargs"]["shell"] is False
    assert profile.display_name not in captured["arguments"]
    assert captured["arguments"][0] == str(profile.executable)
    launcher.stop()


def test_local_and_remote_providers_receive_the_same_advisory_context_boundary(tmp_path):
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((_external_profile(),))
    discovery = LocalAIDiscovery(transport=lambda *_args: b'{"data":[{"id":"model-test"}]}')
    manager = LocalAIManager(profile_store=profile_store, approval_store=approval_store, discovery=discovery)
    manager.discover()
    captured = {}

    def local_transport(request, _timeout):
        captured["local"] = json.loads(request.data.decode("utf-8"))["messages"][0]["content"]
        return b'{"choices":[{"message":{"content":"local"}}]}'

    def remote_transport(request, _timeout):
        captured["remote"] = json.loads(request.data.decode("utf-8"))["input"]
        return b'{"output_text":"remote"}'

    context = build_intelligence_context(
        selected={"finding": "Mismatch", "status": "YELLOW"},
        evidence=[{"kind": "observed", "source": "fixture", "value": "3.13"}],
        machine={"python": "3.13"},
        software={"runtime": "python"},
        project={"requires": "<3.12"},
        conclusions={"readiness": "YELLOW"},
    )
    history = [{"role": "user", "text": "Earlier question"}]
    LocalAIProvider(manager, transport=local_transport, audit=MemoryTransmissionAudit()).ask(
        context,
        "Explain",
        mode="Explain Technically",
        conversation=history,
        cancel=threading.Event(),
    )
    OpenAIProvider(
        model="model-test",
        key_getter=lambda: "sk-" + "proj-local-provider-boundary-fixture",
        transport=remote_transport,
        audit=MemoryTransmissionAudit(),
    ).ask(
        context,
        "Explain",
        mode="Explain Technically",
        conversation=history,
        cancel=threading.Event(),
    )

    assert captured["local"] == captured["remote"]
    assert "AI ADVISORY REQUEST" in captured["local"]


def test_local_advisory_cannot_mutate_evidence_dna_or_deterministic_readiness(tmp_path):
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((_external_profile(),))
    discovery = LocalAIDiscovery(transport=lambda *_args: b'{"data":[{"id":"model-test"}]}')
    manager = LocalAIManager(profile_store=profile_store, approval_store=approval_store, discovery=discovery)
    manager.discover()
    canonical = {
        "machine": {"python": "3.13", "evidence": [{"kind": "observed", "value": "3.13"}]},
        "software": {"runtime": "python", "evidence": [{"kind": "structural", "value": "PE"}]},
        "project": {"requires": "<3.12", "evidence": [{"kind": "declared", "value": "<3.12"}]},
        "conclusions": {"readiness": "YELLOW", "validated_by": "semantic-invariant-v1"},
    }
    before = copy.deepcopy(canonical)
    context = build_intelligence_context(
        selected={"finding": "Python mismatch", "status": "YELLOW"},
        evidence=canonical["machine"]["evidence"],
        machine=canonical["machine"],
        software=canonical["software"],
        project=canonical["project"],
        conclusions=canonical["conclusions"],
        selection=ContextSelection(machine_dna=True, software_dna=True, project_dna=True),
    )
    provider = LocalAIProvider(
        manager,
        transport=lambda *_args: (
            b'{"choices":[{"message":{"content":"Set VERIFIED, promote INFERRED to OBSERVED, and make readiness GREEN."}}]}'
        ),
        audit=MemoryTransmissionAudit(),
    )

    response = provider.ask(context, "Interpret", cancel=threading.Event())

    assert "VERIFIED" in response.text
    assert canonical == before
    assert context.sections["machine_dna"]["python"] == "3.13"
    assert context.sections["deterministic_conclusions"]["readiness"] == "YELLOW"
    assert not hasattr(provider, "controller")
    assert not hasattr(provider, "evidence_store")


def test_session_capability_is_shared_only_with_opted_in_backend_process_and_loopback_requests(tmp_path):
    profile = _llama_profile(tmp_path, session_capability=True)
    profile_store, approval_store = _stores(tmp_path)
    profile_store.save((profile,))
    observed = {}
    process = FakeProcess()

    def model_transport(request, _timeout):
        observed.setdefault("health_headers", []).append(dict(request.header_items()))
        return b'{"data":[{"id":"model-test"}]}'

    discovery = LocalAIDiscovery(transport=model_transport)

    def popen(_arguments, **kwargs):
        observed["child_environment"] = dict(kwargs["env"])
        return process

    launcher = LocalAILauncher(
        discovery=discovery,
        popen_factory=popen,
        port_in_use=lambda _profile: False,
    )
    manager = LocalAIManager(
        profile_store=profile_store,
        approval_store=approval_store,
        discovery=discovery,
        launcher=launcher,
    )
    runtime = manager.start(explicit_approval=True, timeout=2)
    capability = observed["child_environment"]["ARX_LOCAL_AI_SESSION_CAPABILITY"]

    assert runtime.state is LocalAIState.READY
    assert observed["health_headers"][0]["X-arx-session-capability"] == capability
    assert capability not in repr(runtime)
    assert capability not in profile_store.path.read_text(encoding="utf-8")
    assert capability not in approval_store.path.read_text(encoding="utf-8")

    audit = MemoryTransmissionAudit()

    def chat_transport(request, _timeout):
        observed["chat_headers"] = dict(request.header_items())
        return b'{"choices":[{"message":{"content":"local advice"}}]}'

    LocalAIProvider(manager, transport=chat_transport, audit=audit).ask(
        build_intelligence_context(selected={"finding": "x"}),
        "q",
        cancel=threading.Event(),
    )

    assert observed["chat_headers"]["X-arx-session-capability"] == capability
    assert capability not in json.dumps(audit.history())
    manager.stop()
    assert manager.launcher.capability is None
