"""Provider-neutral credential resolution with Windows per-user DPAPI storage."""

from __future__ import annotations

import contextlib
import ctypes
import os
import re
import tempfile
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator


MAX_CREDENTIAL_BYTES = 4_096
MAX_PROTECTED_BLOB_BYTES = 65_536
_BLOB_MAGIC = b"ARX4-DPAPI-CREDENTIAL\x00\x01"
_OPENAI_KEY = re.compile(rb"sk-[A-Za-z0-9_.-]{16,511}\Z")
_PROVIDER_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class CredentialState(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    CREDENTIAL_UNREADABLE = "CREDENTIAL_UNREADABLE"


class CredentialSource(str, Enum):
    NONE = "NONE"
    PROCESS_ENVIRONMENT = "PROCESS_ENVIRONMENT"
    SECURE_WINDOWS_STORE = "SECURE_WINDOWS_STORE"


@dataclass(frozen=True)
class CredentialStatus:
    provider_id: str
    state: CredentialState
    source: CredentialSource
    message: str


class CredentialError(RuntimeError):
    """A credential-boundary failure whose message contains no secret."""


class CredentialNotConfigured(CredentialError):
    pass


class CredentialUnreadable(CredentialError):
    pass


class CredentialStorageUnavailable(CredentialError):
    pass


class SecretBuffer:
    """A short-lived mutable secret buffer that is zeroed on close."""

    def __init__(self, value: bytearray, source: CredentialSource):
        self._value = value
        self.source = source
        self._closed = False

    def text(self) -> str:
        if self._closed:
            raise CredentialError("The credential lease is closed.")
        return self._value.decode("ascii")

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._value)):
                self._value[index] = 0
            self._closed = True

    def __enter__(self) -> "SecretBuffer":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "<SecretBuffer redacted>"


class _DataBlob(ctypes.Structure):
    _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte)))


def _input_blob(value: bytearray) -> tuple[_DataBlob, object]:
    if value:
        buffer = (ctypes.c_ubyte * len(value)).from_buffer(value)
        return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer
    return _DataBlob(0, None), None


def _dpapi_protect(value: bytearray) -> bytes:
    if os.name != "nt":
        raise CredentialStorageUnavailable("Windows DPAPI is available only on Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL
    source, keepalive = _input_blob(value)
    protected = _DataBlob()
    result = crypt32.CryptProtectData(
        ctypes.byref(source),
        "ARX 4 provider credential",
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(protected),
    )
    del keepalive
    if not result:
        raise CredentialStorageUnavailable(f"Windows DPAPI protection failed with error {ctypes.get_last_error()}.")
    try:
        return ctypes.string_at(protected.pbData, protected.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(protected.pbData, wintypes.HLOCAL))


def _dpapi_unprotect(value: bytes) -> bytearray:
    if os.name != "nt":
        raise CredentialStorageUnavailable("Windows DPAPI is available only on Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL
    protected_buffer = bytearray(value)
    source, keepalive = _input_blob(protected_buffer)
    plaintext = _DataBlob()
    description = wintypes.LPWSTR()
    try:
        result = crypt32.CryptUnprotectData(
            ctypes.byref(source),
            ctypes.byref(description),
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(plaintext),
        )
        del keepalive
        if not result:
            raise CredentialUnreadable(
                "A saved credential exists but Windows DPAPI could not decrypt it in the current user context."
            )
        return bytearray(ctypes.string_at(plaintext.pbData, plaintext.cbData))
    finally:
        for index in range(len(protected_buffer)):
            protected_buffer[index] = 0
        if plaintext.pbData:
            kernel32.LocalFree(ctypes.cast(plaintext.pbData, wintypes.HLOCAL))
        if description:
            kernel32.LocalFree(ctypes.cast(description, wintypes.HLOCAL))


def _valid_secret(value: bytearray) -> bool:
    return 20 <= len(value) <= MAX_CREDENTIAL_BYTES and not any(chr(item).isspace() for item in value)


def _default_store_path(provider_id: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    filename = provider_id.replace("_", "-") + ".dpapi"
    return Path(base) / "ARX" / "credentials" / filename


class WindowsDPAPICredentialStore:
    """Binary DPAPI blob scoped to the current Windows user."""

    def __init__(
        self,
        provider_id: str,
        *,
        path: Path | None = None,
        protector: Callable[[bytearray], bytes] = _dpapi_protect,
        unprotector: Callable[[bytes], bytearray] = _dpapi_unprotect,
    ):
        normalized = provider_id.casefold()
        if not _PROVIDER_ID.fullmatch(normalized):
            raise ValueError("Credential provider id is invalid.")
        self.provider_id = normalized
        self.path = Path(path) if path is not None else _default_store_path(normalized)
        self._protector = protector
        self._unprotector = unprotector

    def exists(self) -> bool:
        return self.path.is_file()

    def save(self, secret: bytearray) -> CredentialStatus:
        if not _valid_secret(secret):
            raise CredentialError("The credential format is invalid.")
        protected = self._protector(secret)
        if not protected or len(protected) > MAX_PROTECTED_BLOB_BYTES:
            raise CredentialStorageUnavailable("Windows DPAPI returned an invalid protected credential blob.")
        envelope = _BLOB_MAGIC + protected
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(envelope)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
        except Exception:
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise CredentialStorageUnavailable("The protected credential could not be stored safely.") from None
        return CredentialStatus(
            self.provider_id,
            CredentialState.CONFIGURED,
            CredentialSource.SECURE_WINDOWS_STORE,
            "A protected per-user Windows credential is configured.",
        )

    @contextlib.contextmanager
    def lease(self) -> Iterator[SecretBuffer]:
        if not self.path.is_file():
            raise CredentialNotConfigured("No saved provider credential is configured.")
        if self.path.is_symlink():
            raise CredentialUnreadable("The saved credential path is not a regular local file.")
        try:
            if self.path.stat().st_size > MAX_PROTECTED_BLOB_BYTES + len(_BLOB_MAGIC):
                raise CredentialUnreadable("The saved credential blob is invalid or oversized.")
            envelope = self.path.read_bytes()
        except CredentialUnreadable:
            raise
        except OSError as exc:
            raise CredentialUnreadable("The saved credential blob could not be read.") from exc
        if not envelope.startswith(_BLOB_MAGIC):
            raise CredentialUnreadable("The saved credential blob has an unsupported format.")
        try:
            plaintext = self._unprotector(envelope[len(_BLOB_MAGIC) :])
        except CredentialUnreadable:
            raise
        except Exception as exc:
            raise CredentialUnreadable(
                "A saved credential exists but cannot be decrypted in the current Windows context."
            ) from exc
        if not _valid_secret(plaintext):
            for index in range(len(plaintext)):
                plaintext[index] = 0
            raise CredentialUnreadable("The decrypted credential has an invalid format.")
        lease = SecretBuffer(plaintext, CredentialSource.SECURE_WINDOWS_STORE)
        try:
            yield lease
        finally:
            lease.close()

    def status(self) -> CredentialStatus:
        if not self.exists():
            return CredentialStatus(
                self.provider_id,
                CredentialState.NOT_CONFIGURED,
                CredentialSource.NONE,
                "No saved provider credential is configured.",
            )
        try:
            with self.lease():
                pass
        except CredentialError:
            return CredentialStatus(
                self.provider_id,
                CredentialState.CREDENTIAL_UNREADABLE,
                CredentialSource.SECURE_WINDOWS_STORE,
                "A saved OpenAI credential exists but cannot be decrypted in the current Windows context. "
                "Reconfigure or remove the stored credential.",
            )
        return CredentialStatus(
            self.provider_id,
            CredentialState.CONFIGURED,
            CredentialSource.SECURE_WINDOWS_STORE,
            "A protected per-user Windows credential is configured.",
        )

    def remove(self) -> CredentialStatus:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CredentialStorageUnavailable("The protected credential could not be removed.") from exc
        return CredentialStatus(
            self.provider_id,
            CredentialState.NOT_CONFIGURED,
            CredentialSource.NONE,
            "No saved provider credential is configured.",
        )


class ProviderCredentialResolver:
    """Resolve developer environment credentials before a provider-specific secure store."""

    def __init__(
        self,
        provider_id: str,
        environment_name: str,
        secure_store: WindowsDPAPICredentialStore | None,
        *,
        environment_getter: Callable[[str], str | None] | None = None,
    ):
        self.provider_id = provider_id
        self.environment_name = environment_name
        self.secure_store = secure_store
        self._environment_getter = environment_getter or os.environ.get

    def _environment_value(self) -> str | None:
        value = self._environment_getter(self.environment_name)
        return value if value and value.strip() else None

    def status(self) -> CredentialStatus:
        value = self._environment_value()
        if value is not None:
            encoded = bytearray(value.encode("utf-8", errors="ignore"))
            valid = _valid_secret(encoded)
            for index in range(len(encoded)):
                encoded[index] = 0
            if valid:
                return CredentialStatus(
                    self.provider_id,
                    CredentialState.CONFIGURED,
                    CredentialSource.PROCESS_ENVIRONMENT,
                    f"A credential is configured through {self.environment_name}.",
                )
            return CredentialStatus(
                self.provider_id,
                CredentialState.NOT_CONFIGURED,
                CredentialSource.PROCESS_ENVIRONMENT,
                f"{self.environment_name} is present but has an invalid format.",
            )
        if self.secure_store is not None:
            return self.secure_store.status()
        return CredentialStatus(
            self.provider_id,
            CredentialState.NOT_CONFIGURED,
            CredentialSource.NONE,
            f"{self.environment_name} is not configured.",
        )

    @contextlib.contextmanager
    def lease(self) -> Iterator[SecretBuffer]:
        value = self._environment_value()
        if value is not None:
            encoded = bytearray(value.encode("utf-8", errors="ignore"))
            if not _valid_secret(encoded):
                for index in range(len(encoded)):
                    encoded[index] = 0
                raise CredentialNotConfigured(f"{self.environment_name} is not configured with a valid credential.")
            lease = SecretBuffer(encoded, CredentialSource.PROCESS_ENVIRONMENT)
            try:
                yield lease
            finally:
                lease.close()
            return
        if self.secure_store is None:
            raise CredentialNotConfigured(f"{self.environment_name} is not configured.")
        with self.secure_store.lease() as lease:
            yield lease


def default_openai_credential_store(*, path: Path | None = None) -> WindowsDPAPICredentialStore:
    return WindowsDPAPICredentialStore("openai-api", path=path)


def default_openai_credential_resolver(*, path: Path | None = None) -> ProviderCredentialResolver:
    return ProviderCredentialResolver("openai-api", "OPENAI_API_KEY", default_openai_credential_store(path=path))


def _extract_openai_key(buffer: bytearray) -> bytearray:
    start = 0
    end = len(buffer)
    while start < end and chr(buffer[start]).isspace():
        start += 1
    while end > start and chr(buffer[end - 1]).isspace():
        end -= 1
    prefix = b"OPENAI_API_KEY="
    if buffer[start:end].startswith(prefix):
        start += len(prefix)
        while start < end and chr(buffer[start]).isspace():
            start += 1
        while end > start and chr(buffer[end - 1]).isspace():
            end -= 1
    if end - start >= 2 and buffer[start] == buffer[end - 1] and buffer[start] in (ord("'"), ord('"')):
        start += 1
        end -= 1
    candidate = bytearray(buffer[start:end])
    if not _OPENAI_KEY.fullmatch(candidate):
        for index in range(len(candidate)):
            candidate[index] = 0
        raise CredentialError("The selected file does not contain one valid OpenAI API credential.")
    return candidate


def import_openai_credential_file(source: Path, store: WindowsDPAPICredentialStore) -> CredentialStatus:
    """Read one bounded plaintext file only inside this import boundary, then DPAPI-protect it."""

    path = Path(source)
    try:
        if path.is_symlink() or not path.is_file():
            raise CredentialError("The selected credential source is not a regular file.")
        size = path.stat().st_size
    except CredentialError:
        raise
    except OSError as exc:
        raise CredentialError("The selected credential file could not be inspected safely.") from exc
    if size <= 0 or size > MAX_CREDENTIAL_BYTES:
        raise CredentialError("The selected credential file is empty or oversized.")
    raw = bytearray(size)
    secret: bytearray | None = None
    try:
        try:
            with path.open("rb", buffering=0) as handle:
                count = handle.readinto(raw)
        except OSError as exc:
            raise CredentialError("The selected credential file could not be read safely.") from exc
        if count != size:
            raise CredentialError("The selected credential file could not be read completely.")
        secret = _extract_openai_key(raw)
        status = store.save(secret)
        verified = store.status()
        if verified.state is not CredentialState.CONFIGURED:
            raise CredentialStorageUnavailable("The protected credential could not be verified after import.")
        return status
    finally:
        if secret is not None:
            for index in range(len(secret)):
                secret[index] = 0
        for index in range(len(raw)):
            raw[index] = 0
