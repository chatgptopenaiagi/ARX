"""Optional OpenAI and Codex providers for advisory-only ARX interpretation."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from .context import AdvisoryContext, build_advisory_prompt, redact_external


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.4"
MAX_ADVISORY_RESPONSE_CHARS = 64_000


class ProviderError(RuntimeError):
    """An understandable provider failure safe to show in ARX Desktop."""


class AdvisoryCancelled(ProviderError):
    pass


class AdvisoryTimeout(ProviderError):
    pass


@dataclass(frozen=True)
class ProviderAvailability:
    available: bool
    reason: str
    version: str | None = None


@dataclass(frozen=True)
class AdvisoryResponse:
    provider: str
    text: str
    trust_label: str = "AI ADVISORY — UNVERIFIED AI ANALYSIS"

    def display_text(self) -> str:
        body = self.text.strip()
        if body.upper().startswith("AI ADVISORY"):
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


def _bounded(value: str) -> str:
    if len(value) <= MAX_ADVISORY_RESPONSE_CHARS:
        return value
    omitted = len(value) - MAX_ADVISORY_RESPONSE_CHARS
    return f"{value[:MAX_ADVISORY_RESPONSE_CHARS]}\n\n… <{omitted} response characters omitted by ARX>"


def _run_cancellable(call: Callable[[], bytes], cancel: threading.Event, timeout: float) -> bytes:
    results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", call()))
        except Exception as exc:
            results.put(("error", exc))

    threading.Thread(target=worker, daemon=True, name="arx-provider-transport").start()
    deadline = time.monotonic() + timeout
    while True:
        if cancel.is_set():
            raise AdvisoryCancelled("The advisory request was cancelled.")
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


def parse_openai_response(payload: object) -> str:
    """Extract supported Responses API output while rejecting malformed data."""

    if not isinstance(payload, Mapping):
        raise ProviderError("OpenAI returned a malformed response.")
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    fragments = []
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
    if not text:
        error = payload.get("error")
        if isinstance(error, Mapping) and error.get("message"):
            raise ProviderError(f"OpenAI could not complete the request: {redact_external(str(error['message']))}")
        raise ProviderError("OpenAI returned no advisory text.")
    return text


class OpenAIProvider:
    """Direct optional adapter for the supported OpenAI Responses API."""

    name = "OpenAI"

    def __init__(
        self,
        *,
        model: str | None = None,
        key_getter: Callable[[], str | None] | None = None,
        transport: Callable[[urllib.request.Request, float], bytes] | None = None,
    ):
        self.model = model or os.environ.get("ARX_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        self._key_getter = key_getter or (lambda: os.environ.get("OPENAI_API_KEY"))
        self._transport = transport or self._default_transport

    @staticmethod
    def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(MAX_ADVISORY_RESPONSE_CHARS * 2)

    def availability(self) -> ProviderAvailability:
        key = self._key_getter()
        if not key or len(key.strip()) < 20 or any(character.isspace() for character in key.strip()):
            return ProviderAvailability(False, "OPENAI_API_KEY is not configured or is invalid.")
        if not self.model.strip():
            return ProviderAvailability(False, "The OpenAI model configuration is empty.")
        return ProviderAvailability(True, f"OpenAI Responses API using {self.model}")

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
            raise ProviderError(availability.reason)
        prompt = build_advisory_prompt(context, question, mode=mode, conversation=conversation)
        body = json.dumps(
            {"model": self.model, "input": prompt, "store": False, "max_output_tokens": 1_500},
            ensure_ascii=False,
        ).encode("utf-8")
        key = self._key_getter() or ""
        request = urllib.request.Request(
            OPENAI_RESPONSES_URL,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            raw = _run_cancellable(lambda: self._transport(request, timeout), cancellation, timeout)
            parsed = json.loads(raw.decode("utf-8"))
            return AdvisoryResponse(self.name, _bounded(parse_openai_response(parsed)))
        except (AdvisoryCancelled, AdvisoryTimeout, ProviderError):
            raise
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"OpenAI request failed with HTTP {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = redact_external(str(getattr(exc, "reason", exc)))
            raise ProviderError(f"OpenAI is currently unavailable: {reason}") from None
        except (UnicodeError, json.JSONDecodeError):
            raise ProviderError("OpenAI returned a malformed response.") from None


class CodexCLIProvider:
    """Read-only, ephemeral, non-interactive Codex CLI adapter."""

    name = "Codex CLI"

    def __init__(
        self,
        *,
        executable: str | None = None,
        finder: Callable[[str], str | None] = shutil.which,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        version_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        self.executable = executable or finder("codex")
        self._popen_factory = popen_factory
        self._version_runner = version_runner

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
            raise ProviderError("Codex CLI is not currently available.")
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
            raise ProviderError(availability.reason)
        prompt = build_advisory_prompt(context, question, mode=mode, conversation=conversation)
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
            except OSError as exc:
                raise ProviderError(f"Codex CLI could not be started: {redact_external(str(exc))}") from None
            deadline = time.monotonic() + timeout
            first = True
            while True:
                if cancellation.is_set():
                    self._stop(process)
                    raise AdvisoryCancelled("Codex analysis was cancelled.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop(process)
                    raise AdvisoryTimeout(f"Codex analysis timed out after {timeout:g} seconds.")
                try:
                    stdout, stderr = process.communicate(input=prompt if first else None, timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    continue
            if process.returncode != 0:
                safe_error = _bounded(str(redact_external((stderr or "Codex CLI failed.").strip())))
                raise ProviderError(f"Codex CLI could not complete the advisory request: {safe_error}")
            if not (stdout or "").strip():
                raise ProviderError("Codex CLI returned no advisory text.")
            return AdvisoryResponse(self.name, _bounded(stdout.strip()))
