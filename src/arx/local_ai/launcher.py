"""Supervise one approved local backend process without shell execution."""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from .backends.openai_compatible import LaunchSpec
from .discovery import LocalAIDiscovery
from .models import (
    BackendProfile,
    LocalAIFailure,
    LocalAIRuntime,
    LocalAIState,
    utc_now,
)
from .session import SessionCapability

_SAFE_CHILD_ENVIRONMENT = (
    "SYSTEMROOT",
    "WINDIR",
    "SYSTEMDRIVE",
    "TEMP",
    "TMP",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
)


class BackendAdapter(Protocol):
    def launch_spec(self, profile: BackendProfile, capability: SessionCapability) -> LaunchSpec | None: ...


class LocalAILaunchError(RuntimeError):
    def __init__(self, failure: LocalAIFailure, message: str):
        super().__init__(message)
        self.failure = failure


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_child_environment(extra: Mapping[str, str]) -> dict[str, str]:
    result = {key: os.environ[key] for key in _SAFE_CHILD_ENVIRONMENT if key in os.environ}
    for key, value in extra.items():
        if key != "ARX_LOCAL_AI_SESSION_CAPABILITY" or not value or len(value) > 256:
            raise ValueError("The typed local AI backend supplied an unsupported child environment value.")
        result[key] = value
    return result


def _port_in_use(profile: BackendProfile) -> bool:
    try:
        with socket.create_connection((profile.endpoint.host, profile.endpoint.port), timeout=0.2):
            return True
    except OSError:
        return False


class LocalAILauncher:
    """Own process lifecycle for a single typed, approved backend profile."""

    def __init__(
        self,
        *,
        discovery: LocalAIDiscovery | None = None,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        port_in_use: Callable[[BackendProfile], bool] = _port_in_use,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.discovery = discovery or LocalAIDiscovery()
        self._popen_factory = popen_factory
        self._port_in_use = port_in_use
        self._monotonic = monotonic
        self._sleep = sleeper
        self._process: subprocess.Popen | None = None
        self._capability: SessionCapability | None = None
        self._runtime: LocalAIRuntime | None = None

    @property
    def runtime(self) -> LocalAIRuntime | None:
        return self._runtime

    @property
    def capability(self) -> SessionCapability | None:
        return self._capability

    @property
    def process(self) -> subprocess.Popen | None:
        return self._process

    def _failed(self, profile: BackendProfile, failure: LocalAIFailure, message: str) -> LocalAIRuntime:
        self._runtime = LocalAIRuntime(
            profile.profile_id,
            LocalAIState.FAILED,
            profile.endpoint.base_url,
            model_identity=profile.model_id,
            failure=failure,
            message=message,
            exit_code=self._process.poll() if self._process is not None else None,
        )
        return self._runtime

    def start(
        self,
        profile: BackendProfile,
        adapter: BackendAdapter,
        *,
        timeout: float = 60,
        cancel: threading.Event | None = None,
    ) -> LocalAIRuntime:
        if not profile.launchable:
            raise LocalAILaunchError(LocalAIFailure.API_INCOMPATIBLE, "This profile describes an external local endpoint.")
        if timeout <= 0 or timeout > 600:
            raise ValueError("Local AI startup timeout must be between 0 and 600 seconds.")
        if self._process is not None and self._process.poll() is None:
            raise LocalAILaunchError(LocalAIFailure.PORT_CONFLICT, "ARX already supervises a local AI process.")
        if profile.executable is None or profile.model_path is None:
            return self._failed(profile, LocalAIFailure.EXECUTABLE_MISSING, "The typed launch profile is incomplete.")
        if not profile.executable.is_file():
            return self._failed(profile, LocalAIFailure.EXECUTABLE_MISSING, "The configured backend executable is missing.")
        if not profile.model_path.is_file():
            return self._failed(profile, LocalAIFailure.MODEL_MISSING, "The configured local model file is missing.")
        if self._port_in_use(profile):
            return self._failed(profile, LocalAIFailure.PORT_CONFLICT, "The configured loopback port is already in use.")
        cancellation = cancel or threading.Event()
        capability = SessionCapability()
        try:
            spec = adapter.launch_spec(profile, capability)
            if spec is None or not spec.arguments or spec.arguments[0] != str(profile.executable):
                raise ValueError("The typed backend adapter did not produce the expected executable identity.")
            if any(not isinstance(item, str) or "\x00" in item or len(item) > 2_048 for item in spec.arguments):
                raise ValueError("The typed backend adapter produced an invalid argument.")
            environment = _safe_child_environment(spec.environment)
            executable_hash = _file_sha256(profile.executable)
            self._runtime = LocalAIRuntime(
                profile.profile_id,
                LocalAIState.STARTING,
                profile.endpoint.base_url,
                model_identity=profile.model_id or profile.model_path.name,
                executable_identity=spec.executable_identity,
                executable_sha256=executable_hash,
                started_at=utc_now(),
                message="Starting an explicitly approved local AI backend.",
            )
            process = self._popen_factory(
                list(spec.arguments),
                cwd=str(profile.executable.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            capability.close()
            return self._failed(profile, LocalAIFailure.EXECUTABLE_MISSING, "The approved local backend could not be started safely.")
        except ValueError:
            capability.close()
            return self._failed(profile, LocalAIFailure.API_INCOMPATIBLE, "The typed local backend profile could not be launched safely.")
        self._process = process
        self._capability = capability
        self._runtime = LocalAIRuntime(
            **{
                **self._runtime.as_dict(),
                "state": LocalAIState.HEALTH_CHECK,
                "pid": process.pid,
                "failure": None,
                "message": "Waiting for the local model API to report ready.",
            }
        )
        deadline = self._monotonic() + timeout
        while self._monotonic() < deadline:
            if cancellation.is_set():
                self.stop()
                return LocalAIRuntime(
                    profile.profile_id,
                    LocalAIState.STOPPED,
                    profile.endpoint.base_url,
                    model_identity=profile.model_id or profile.model_path.name,
                    executable_identity=spec.executable_identity,
                    executable_sha256=executable_hash,
                    pid=process.pid,
                    started_at=self._runtime.started_at,
                    message="Local AI startup was cancelled.",
                    exit_code=process.poll(),
                )
            exit_code = process.poll()
            if exit_code is not None:
                capability.close()
                self._capability = None
                return self._failed(profile, LocalAIFailure.PROCESS_CRASHED, "The local backend exited before becoming ready.")
            result = self.discovery.probe(profile, timeout=min(1, max(0.1, deadline - self._monotonic())), capability=capability)
            if result.ready:
                model = profile.model_id or result.models[0].model_id
                self._runtime = LocalAIRuntime(
                    profile.profile_id,
                    LocalAIState.READY,
                    profile.endpoint.base_url,
                    model_identity=model,
                    executable_identity=spec.executable_identity,
                    executable_sha256=executable_hash,
                    pid=process.pid,
                    started_at=self._runtime.started_at,
                    backend_version=result.backend_version,
                    message=result.message,
                )
                return self._runtime
            if result.failure in {LocalAIFailure.AUTH_FAILURE, LocalAIFailure.MODEL_MISSING}:
                self.stop()
                return self._failed(profile, result.failure, result.message)
            self._sleep(0.1)
        self.stop()
        return self._failed(profile, LocalAIFailure.STARTUP_TIMEOUT, "The local backend did not become ready before the timeout.")

    def stop(self, *, timeout: float = 5) -> LocalAIRuntime | None:
        runtime = self._runtime
        process = self._process
        if runtime is None:
            return None
        self._runtime = LocalAIRuntime(
            runtime.profile_id,
            LocalAIState.STOPPING,
            runtime.endpoint,
            model_identity=runtime.model_identity,
            executable_identity=runtime.executable_identity,
            executable_sha256=runtime.executable_sha256,
            pid=runtime.pid,
            started_at=runtime.started_at,
            backend_version=runtime.backend_version,
            message="Stopping the ARX-supervised local AI backend.",
            exit_code=runtime.exit_code,
        )
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=min(timeout, 2))
        if self._capability is not None:
            self._capability.close()
        exit_code = process.poll() if process is not None else runtime.exit_code
        self._capability = None
        self._process = None
        self._runtime = LocalAIRuntime(
            runtime.profile_id,
            LocalAIState.STOPPED,
            runtime.endpoint,
            model_identity=runtime.model_identity,
            executable_identity=runtime.executable_identity,
            executable_sha256=runtime.executable_sha256,
            pid=runtime.pid,
            started_at=runtime.started_at,
            backend_version=runtime.backend_version,
            message="The ARX-supervised local AI backend is stopped.",
            exit_code=exit_code,
        )
        return self._runtime
