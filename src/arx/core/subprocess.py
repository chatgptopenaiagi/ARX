"""Bounded subprocess byte decoding shared by deterministic machine probes."""

from __future__ import annotations

import locale
import os
import subprocess
from collections.abc import Callable


def decode_output(value: bytes | str | None, limit: int) -> str:
    """Decode bytes and bound the retained/report text to ``limit`` characters."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:limit]
    # Four bytes covers one bounded Unicode scalar. subprocess.run has already
    # captured the stream; this bounds only the bytes retained for decoding/reporting.
    raw = value[: limit * 4]
    if raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    else:
        even_nuls = raw[0::2].count(0)
        odd_nuls = raw[1::2].count(0)
        pairs = max(len(raw) // 2, 1)
        encoding = "utf-16-le" if odd_nuls / pairs > 0.3 else "utf-16-be" if even_nuls / pairs > 0.3 else "utf-8"
    if encoding.startswith("utf-16") and len(raw) % 2:
        raw = raw[:-1]
    try:
        return raw.decode(encoding)[:limit]
    except UnicodeDecodeError as initial_error:
        if encoding in {"utf-8", "utf-8-sig"} and initial_error.reason == "unexpected end of data" and initial_error.end == len(raw):
            # ARX's own byte bound cut only the final code point. Preserve every
            # complete preceding character; never trim an invalid middle byte.
            return raw[:initial_error.start].decode(encoding)[:limit]
        fallbacks = []
        preferred = locale.getpreferredencoding(False)
        if preferred and preferred.casefold().replace("-", "") not in {"utf8", encoding.casefold().replace("-", "")}:
            fallbacks.append(preferred)
        if os.name == "nt" and all(item.casefold() != "cp1252" for item in fallbacks):
            fallbacks.append("cp1252")
        for fallback in fallbacks:
            try:
                return raw.decode(fallback)[:limit]
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")[:limit]


def run_bounded(
    args: list[str],
    *,
    timeout: int,
    limit: int,
    runner: Callable[..., object] = subprocess.run,
) -> dict:
    """Run a fixed caller-supplied command and bound retained output after completion."""
    completed = runner(
        args,
        capture_output=True,
        text=False,
        timeout=timeout,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stdout = decode_output(getattr(completed, "stdout", b""), limit)
    stderr = decode_output(getattr(completed, "stderr", b""), limit)
    return {"returncode": int(getattr(completed, "returncode", 1)), "stdout": stdout, "stderr": stderr}
