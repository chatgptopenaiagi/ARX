"""Bounded local metadata audit for advisory provider transport boundaries."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from .context import redact_external


class TransportState(str, Enum):
    REQUEST_PREPARED = "REQUEST_PREPARED"
    OUTBOUND_REQUEST_INITIATED = "OUTBOUND_REQUEST_INITIATED"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    REQUEST_FAILED = "REQUEST_FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class TransmissionEvent:
    timestamp: str
    attempt_id: str
    provider_id: str
    operation: str
    state: TransportState
    model: str | None = None
    request_bytes: int | None = None
    response_bytes: int | None = None
    latency_ms: int | None = None
    error_category: str | None = None

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["state"] = self.state.value
        return result


class AuditError(RuntimeError):
    pass


def _default_audit_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "ARX" / "audit" / "external-transmissions.jsonl"


class TransmissionAudit:
    """Sensitive behavioral metadata retained locally with count, age, and file bounds."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        retention_days: int = 30,
        max_events_per_file: int = 200,
        max_files: int = 3,
        max_file_bytes: int = 128_000,
    ):
        if retention_days < 1 or max_events_per_file < 1 or max_files < 1 or max_file_bytes < 1_024:
            raise ValueError("Transmission audit bounds must be positive.")
        self.path = Path(path) if path is not None else _default_audit_path()
        self.retention_days = retention_days
        self.max_events_per_file = max_events_per_file
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self._lock = threading.RLock()

    @contextlib.contextmanager
    def _process_lock(self):
        """Serialize rotation across multiple local ARX processes."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\x00")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _paths(self) -> list[Path]:
        return [self.path, *(Path(f"{self.path}.{index}") for index in range(1, self.max_files))]

    @staticmethod
    def _safe_record(event: TransmissionEvent) -> dict[str, object]:
        record = redact_external(event.as_dict())
        if not isinstance(record, dict):
            raise AuditError("Transmission audit metadata could not be sanitized.")
        forbidden = {"prompt", "response", "body", "authorization", "credential", "api_key", "path", "url", "sent"}
        if forbidden.intersection(key.casefold() for key in record):
            raise AuditError("Transmission audit metadata contains a forbidden field.")
        bounded_tokens = {
            "attempt_id": (r"[A-Za-z0-9._-]{1,64}", 64),
            "provider_id": (r"[a-z0-9._-]{1,64}", 64),
            "operation": (r"[a-z0-9_]{1,32}", 32),
            "state": (r"[A-Z_]{1,40}", 40),
            "model": (r"[A-Za-z0-9._:-]{1,128}", 128),
            "error_category": (r"[A-Z_]{1,40}", 40),
        }
        for key, (pattern, limit) in bounded_tokens.items():
            value = record.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > limit or re.fullmatch(pattern, value) is None:
                raise AuditError(f"Transmission audit {key} metadata is invalid.")
        for key in ("request_bytes", "response_bytes", "latency_ms"):
            value = record.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1_000_000_000):
                raise AuditError(f"Transmission audit {key} metadata is invalid.")
        timestamp = record.get("timestamp")
        try:
            parsed_timestamp = datetime.fromisoformat(str(timestamp))
        except (TypeError, ValueError) as exc:
            raise AuditError("Transmission audit timestamp metadata is invalid.") from exc
        if parsed_timestamp.tzinfo is None or len(str(timestamp)) > 64:
            raise AuditError("Transmission audit timestamp metadata is invalid.")
        if len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > 4_096:
            raise AuditError("Transmission audit metadata exceeds its record bound.")
        return record

    def _read_records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for path in reversed(self._paths()):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if len(line) > 4_096:
                            continue
                        value = json.loads(line)
                        if isinstance(value, dict):
                            records.append(value)
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
        return records

    def _retained(self, records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        retained = []
        for record in records:
            try:
                timestamp = datetime.fromisoformat(str(record["timestamp"]))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if timestamp >= cutoff:
                retained.append(record)
        return retained[-self.max_events_per_file * self.max_files :]

    def _atomic_write(self, path: Path, records: list[dict[str, object]]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                for record in records:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, path)
        except Exception:
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise

    def _rewrite(self, records: list[dict[str, object]]) -> None:
        paths = self._paths()
        for path in paths:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
        remaining = list(records)
        for path in paths:
            if not remaining:
                break
            chunk: list[dict[str, object]] = []
            encoded_bytes = 0
            while remaining and len(chunk) < self.max_events_per_file:
                candidate = remaining[-1]
                encoded = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                size = len(encoded.encode("utf-8"))
                if chunk and encoded_bytes + size > self.max_file_bytes:
                    break
                remaining.pop()
                chunk.append(candidate)
                encoded_bytes += size
            self._atomic_write(path, list(reversed(chunk)))

    def record(self, event: TransmissionEvent) -> None:
        record = self._safe_record(event)
        with self._lock:
            try:
                with self._process_lock():
                    records = self._retained([*self._read_records(), record])
                    self._rewrite(records)
            except AuditError:
                raise
            except OSError as exc:
                raise AuditError("The local transmission audit could not be written.") from exc

    def history(self) -> list[dict[str, object]]:
        with self._lock, self._process_lock():
            records = self._read_records()
            retained = self._retained(records)
            if retained != records:
                self._rewrite(retained)
            return retained

    def clear_history(self) -> None:
        """Explicit user action; callers must not invoke this during normal application cleanup."""

        with self._lock, self._process_lock():
            for path in self._paths():
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()

    def export_redacted(self, target: Path) -> None:
        """Explicit metadata-only export with another external-boundary redaction pass."""

        destination = Path(target)
        content = json.dumps(redact_external(self.history()), indent=2, ensure_ascii=False, sort_keys=True)
        destination.write_text(content + "\n", encoding="utf-8")


class MemoryTransmissionAudit:
    """Non-persistent audit sink for deterministic tests."""

    def __init__(self):
        self.events: list[TransmissionEvent] = []

    def record(self, event: TransmissionEvent) -> None:
        TransmissionAudit._safe_record(event)
        self.events.append(event)

    def history(self) -> list[dict[str, object]]:
        return [event.as_dict() for event in self.events]

    def clear_history(self) -> None:
        self.events.clear()


_DEFAULT_AUDIT: TransmissionAudit | None = None
_DEFAULT_AUDIT_LOCK = threading.Lock()


def default_transmission_audit() -> TransmissionAudit:
    """Share one process-local writer/lock for the default audit path."""

    global _DEFAULT_AUDIT
    with _DEFAULT_AUDIT_LOCK:
        if _DEFAULT_AUDIT is None:
            _DEFAULT_AUDIT = TransmissionAudit()
        return _DEFAULT_AUDIT
