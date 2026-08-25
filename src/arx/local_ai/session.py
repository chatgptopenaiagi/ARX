"""Memory-only capability material for one supervised local-AI session."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable


class CapabilityExpired(RuntimeError):
    pass


class SessionCapability:
    """A short-lived secret that has no serializable or printable representation."""

    __slots__ = ("_bytes", "_closed", "_expires_at", "_now")

    def __init__(
        self,
        *,
        ttl_seconds: float = 900,
        now: Callable[[], float] = time.monotonic,
        token_factory: Callable[[int], str] = secrets.token_urlsafe,
    ):
        if not 1 <= ttl_seconds <= 3_600:
            raise ValueError("Local AI session capability lifetime must be between 1 and 3600 seconds.")
        value = token_factory(32)
        if not isinstance(value, str) or len(value) < 32:
            raise ValueError("The session capability generator returned insufficient material.")
        self._bytes = bytearray(value.encode("ascii"))
        self._closed = False
        self._now = now
        self._expires_at = now() + ttl_seconds

    @property
    def expired(self) -> bool:
        return self._closed or self._now() >= self._expires_at

    def header_value(self) -> str:
        """Expose the value only at the in-memory local transport boundary."""

        if self.expired:
            raise CapabilityExpired("The local AI session capability has expired.")
        return self._bytes.decode("ascii")

    def close(self) -> None:
        for index in range(len(self._bytes)):
            self._bytes[index] = 0
        self._closed = True

    def __enter__(self) -> SessionCapability:  # noqa: PYI034 - Python 3.10 has no typing.Self
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "SessionCapability(<memory-only redacted>)"

    __str__ = __repr__
