"""Configuration, approval, discovery, and lifecycle orchestration for local AI."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from .backends import (
    GenericBackendAdapter,
    LlamaCppBackendAdapter,
    OpenAICompatibleBackendAdapter,
)
from .discovery import DiscoveryResult, LocalAIDiscovery
from .launcher import BackendAdapter, LocalAILauncher
from .models import (
    MAX_CONFIGURED_PROFILES,
    AssistanceProfile,
    BackendKind,
    BackendProfile,
    LocalAIFailure,
    LocalAIRuntime,
    LocalAIState,
    LocalEndpoint,
    utc_now,
)

MAX_LOCAL_CONFIG_BYTES = 64_000


class ApprovalRequired(RuntimeError):
    pass


class LocalAIConfigurationError(RuntimeError):
    pass


def _default_local_ai_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "ARX" / "local-ai"


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > MAX_LOCAL_CONFIG_BYTES:
        raise LocalAIConfigurationError("The bounded local AI configuration is too large.")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        with contextlib.suppress(OSError):
            temporary.chmod(0o600)
        os.replace(temporary, path)
    except Exception:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


class LocalAIProfileStore:
    """Local-only bounded profile storage; it has no export or cloud-sync path."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else _default_local_ai_directory() / "profiles.json"

    def load(self) -> tuple[BackendProfile, ...]:
        if not self.path.exists():
            return ()
        if not self.path.is_file() or self.path.is_symlink() or self.path.stat().st_size > MAX_LOCAL_CONFIG_BYTES:
            raise LocalAIConfigurationError("The local AI profile store is not a bounded regular file.")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema") != 1 or not isinstance(raw.get("profiles"), list):
                raise ValueError
            if len(raw["profiles"]) > MAX_CONFIGURED_PROFILES:
                raise ValueError
            profiles = tuple(BackendProfile.from_dict(item) for item in raw["profiles"] if isinstance(item, dict))
            if len(profiles) != len(raw["profiles"]) or len({item.profile_id for item in profiles}) != len(profiles):
                raise ValueError
            return profiles
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise LocalAIConfigurationError("The local AI profile store is malformed or unreadable.") from exc

    def save(self, profiles: tuple[BackendProfile, ...]) -> None:
        if len(profiles) > MAX_CONFIGURED_PROFILES or len({item.profile_id for item in profiles}) != len(profiles):
            raise LocalAIConfigurationError("The local AI profile set is invalid or exceeds its bound.")
        _atomic_json(self.path, {"schema": 1, "profiles": [item.as_dict() for item in profiles]})


@dataclass(frozen=True)
class ApprovalRecord:
    profile_id: str
    fingerprint: str
    automatic_start: bool
    approved_at: str


class LocalAIApprovalStore:
    """Persist only a profile fingerprint and explicit startup policy, never tokens."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else _default_local_ai_directory() / "approvals.json"

    def _load(self) -> dict[str, ApprovalRecord]:
        if not self.path.exists():
            return {}
        if not self.path.is_file() or self.path.is_symlink() or self.path.stat().st_size > MAX_LOCAL_CONFIG_BYTES:
            raise LocalAIConfigurationError("The local AI approval store is not a bounded regular file.")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            records = raw.get("approvals") if isinstance(raw, dict) and raw.get("schema") == 1 else None
            if not isinstance(records, list) or len(records) > MAX_CONFIGURED_PROFILES:
                raise ValueError
            result: dict[str, ApprovalRecord] = {}
            for item in records:
                if not isinstance(item, dict) or set(item) != {"profile_id", "fingerprint", "automatic_start", "approved_at"}:
                    raise ValueError
                record = ApprovalRecord(
                    str(item["profile_id"]),
                    str(item["fingerprint"]),
                    item["automatic_start"] is True,
                    str(item["approved_at"]),
                )
                if len(record.fingerprint) != 64:
                    raise ValueError
                result[record.profile_id] = record
            return result
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LocalAIConfigurationError("The local AI approval store is malformed or unreadable.") from exc

    def approved(self, profile: BackendProfile, *, automatic: bool = False) -> bool:
        record = self._load().get(profile.profile_id)
        return bool(
            record
            and record.fingerprint == profile.fingerprint()
            and (not automatic or record.automatic_start)
        )

    def approve(self, profile: BackendProfile) -> None:
        records = self._load()
        records[profile.profile_id] = ApprovalRecord(
            profile.profile_id,
            profile.fingerprint(),
            profile.assistance is AssistanceProfile.AUTOMATED,
            utc_now(),
        )
        _atomic_json(
            self.path,
            {
                "schema": 1,
                "approvals": [record.__dict__ for record in sorted(records.values(), key=lambda item: item.profile_id)],
            },
        )

    def revoke(self, profile_id: str) -> None:
        records = self._load()
        records.pop(profile_id, None)
        _atomic_json(
            self.path,
            {
                "schema": 1,
                "approvals": [record.__dict__ for record in sorted(records.values(), key=lambda item: item.profile_id)],
            },
        )


class LocalAIManager:
    """Coordinate explicit local endpoints and one supervised process."""

    def __init__(
        self,
        *,
        profile_store: LocalAIProfileStore | None = None,
        approval_store: LocalAIApprovalStore | None = None,
        discovery: LocalAIDiscovery | None = None,
        launcher: LocalAILauncher | None = None,
    ):
        self.profile_store = profile_store or LocalAIProfileStore()
        self.approval_store = approval_store or LocalAIApprovalStore()
        self.discovery = discovery or LocalAIDiscovery()
        self.launcher = launcher or LocalAILauncher(discovery=self.discovery)
        try:
            loaded = self.profile_store.load()
        except LocalAIConfigurationError:
            loaded = ()
        if not loaded:
            loaded = (
                BackendProfile(
                    "local-default",
                    "Local OpenAI-compatible API",
                    BackendKind.OPENAI_COMPATIBLE,
                    LocalEndpoint(),
                ),
            )
        self._profiles = {item.profile_id: item for item in loaded}
        self._runtime = {
            item.profile_id: LocalAIRuntime(
                item.profile_id,
                LocalAIState.NOT_FOUND,
                item.endpoint.base_url,
                model_identity=item.model_id,
                message="Not contacted. Use Discover or Start in Local AI Settings.",
            )
            for item in loaded
        }
        self._active_profile_id = loaded[0].profile_id
        self._lock = threading.RLock()
        self._adapters: dict[BackendKind, BackendAdapter] = {
            BackendKind.OPENAI_COMPATIBLE: OpenAICompatibleBackendAdapter(),
            BackendKind.GENERIC: GenericBackendAdapter(),
            BackendKind.LLAMA_CPP: LlamaCppBackendAdapter(),
        }

    @property
    def active_profile_id(self) -> str:
        return self._active_profile_id

    def profiles(self) -> tuple[BackendProfile, ...]:
        return tuple(self._profiles.values())

    def profile(self, profile_id: str | None = None) -> BackendProfile:
        key = profile_id or self._active_profile_id
        try:
            return self._profiles[key]
        except KeyError as exc:
            raise LocalAIConfigurationError("The selected local AI profile does not exist.") from exc

    def select(self, profile_id: str) -> None:
        self.profile(profile_id)
        self._active_profile_id = profile_id

    def save_profile(self, profile: BackendProfile) -> None:
        with self._lock:
            existing = self._profiles.get(profile.profile_id)
            replacing_active_process = (
                profile.profile_id == self._active_profile_id
                and self.launcher.process is not None
                and self.launcher.process.poll() is None
            )
            if replacing_active_process:
                if existing is not None and existing.fingerprint() == profile.fingerprint():
                    return
                raise LocalAIConfigurationError("Stop the active local backend before replacing its profile.")
            self._profiles[profile.profile_id] = profile
            if len(self._profiles) > MAX_CONFIGURED_PROFILES:
                self._profiles.pop(profile.profile_id, None)
                raise LocalAIConfigurationError("No more than eight local AI profiles may be configured.")
            self.profile_store.save(tuple(self._profiles.values()))
            self._runtime[profile.profile_id] = LocalAIRuntime(
                profile.profile_id,
                LocalAIState.DISCOVERED,
                profile.endpoint.base_url,
                model_identity=profile.model_id,
                message="Profile saved locally. No provider contact occurred.",
            )
            self._active_profile_id = profile.profile_id

    def runtime(self, profile_id: str | None = None) -> LocalAIRuntime:
        profile = self.profile(profile_id)
        runtime = self._runtime[profile.profile_id]
        process = self.launcher.process
        if runtime.pid is not None and process is not None:
            exit_code = process.poll()
            if exit_code is not None and runtime.state in {LocalAIState.READY, LocalAIState.BUSY}:
                runtime = LocalAIRuntime(
                    profile.profile_id,
                    LocalAIState.FAILED,
                    profile.endpoint.base_url,
                    model_identity=runtime.model_identity,
                    executable_identity=runtime.executable_identity,
                    executable_sha256=runtime.executable_sha256,
                    pid=runtime.pid,
                    started_at=runtime.started_at,
                    backend_version=runtime.backend_version,
                    failure=LocalAIFailure.PROCESS_CRASHED,
                    message="The supervised local AI process exited unexpectedly.",
                    exit_code=exit_code,
                )
                self._runtime[profile.profile_id] = runtime
        return runtime

    def discover(self, profile_id: str | None = None, *, timeout: float = 3) -> DiscoveryResult:
        profile = self.profile(profile_id)
        supervised = self.launcher.runtime if self.launcher.runtime and self.launcher.runtime.profile_id == profile.profile_id else None
        capability = self.launcher.capability if supervised is not None else None
        result = self.discovery.probe(profile, timeout=timeout, capability=capability)
        model = profile.model_id or (result.models[0].model_id if result.models else None)
        self._runtime[profile.profile_id] = LocalAIRuntime(
            profile.profile_id,
            result.state,
            profile.endpoint.base_url,
            model_identity=model,
            executable_identity=supervised.executable_identity if supervised is not None else None,
            executable_sha256=supervised.executable_sha256 if supervised is not None else None,
            pid=supervised.pid if supervised is not None else None,
            started_at=supervised.started_at if supervised is not None else None,
            backend_version=result.backend_version,
            failure=result.failure,
            message=result.message,
            exit_code=supervised.exit_code if supervised is not None else None,
        )
        return result

    def start(
        self,
        profile_id: str | None = None,
        *,
        explicit_approval: bool = False,
        timeout: float = 60,
        cancel: threading.Event | None = None,
    ) -> LocalAIRuntime:
        profile = self.profile(profile_id)
        if not profile.launchable:
            self.discover(profile.profile_id, timeout=min(timeout, 30))
            return self.runtime(profile.profile_id)
        if not self.approval_store.approved(profile):
            if not explicit_approval:
                raise ApprovalRequired("First-time local backend execution requires explicit human approval.")
            self.approval_store.approve(profile)
        runtime = self.launcher.start(
            profile,
            self._adapters[profile.backend],
            timeout=timeout,
            cancel=cancel,
        )
        self._runtime[profile.profile_id] = runtime
        return runtime

    def auto_start(self, profile_id: str | None = None, *, timeout: float = 60) -> LocalAIRuntime:
        profile = self.profile(profile_id)
        if profile.assistance is not AssistanceProfile.AUTOMATED or not self.approval_store.approved(profile, automatic=True):
            raise ApprovalRequired("Automatic startup is not enabled by an approved AUTOMATED profile policy.")
        return self.start(profile.profile_id, timeout=timeout)

    def stop(self, profile_id: str | None = None) -> LocalAIRuntime:
        profile = self.profile(profile_id)
        if self.launcher.runtime and self.launcher.runtime.profile_id == profile.profile_id:
            runtime = self.launcher.stop()
            if runtime is None:
                raise LocalAIConfigurationError("The supervised local AI runtime could not be stopped safely.")
        else:
            runtime = LocalAIRuntime(
                profile.profile_id,
                LocalAIState.STOPPED,
                profile.endpoint.base_url,
                model_identity=profile.model_id,
                message="The configured external local endpoint is disconnected from this ARX session.",
            )
        self._runtime[profile.profile_id] = runtime
        return runtime

    def mark_busy(self, profile_id: str) -> LocalAIRuntime:
        runtime = self.runtime(profile_id)
        if runtime.state is not LocalAIState.READY:
            return runtime
        updated = LocalAIRuntime(**{**runtime.as_dict(), "state": LocalAIState.BUSY, "failure": None})
        self._runtime[profile_id] = updated
        return updated

    def mark_ready(self, profile_id: str) -> LocalAIRuntime:
        runtime = self.runtime(profile_id)
        updated = LocalAIRuntime(
            **{
                **runtime.as_dict(),
                "state": LocalAIState.READY,
                "failure": None,
                "message": "The loopback-only local AI provider is ready.",
            }
        )
        self._runtime[profile_id] = updated
        return updated

    def mark_failed(self, profile_id: str, failure: LocalAIFailure, message: str) -> LocalAIRuntime:
        runtime = self.runtime(profile_id)
        updated = LocalAIRuntime(
            **{
                **runtime.as_dict(),
                "state": LocalAIState.FAILED,
                "failure": failure,
                "message": message,
            }
        )
        self._runtime[profile_id] = updated
        return updated

    def close(self) -> None:
        if self.launcher.runtime is not None:
            self.launcher.stop()
