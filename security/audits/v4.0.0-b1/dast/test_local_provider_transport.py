"""Bounded localhost-only checks for the Beta 1 OpenAI transport boundary."""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from arx.advisory.health import ProviderHealthStatus
from arx.advisory.providers import (
    MAX_PROVIDER_RESPONSE_BYTES,
    OpenAIProvider,
    ProviderError,
)


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


class _RedirectHandler(_QuietHandler):
    def do_GET(self) -> None:
        if self.path == "/start":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"redirect-followed")


class _OversizedHandler(_QuietHandler):
    def do_GET(self) -> None:
        payload = b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1)
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def _local_server(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_default_transport_rejects_local_redirect() -> None:
    with _local_server(_RedirectHandler) as base:
        request = urllib.request.Request(f"{base}/start", method="GET")
        with pytest.raises(urllib.error.HTTPError) as error:
            OpenAIProvider._default_transport(request, timeout=2)

    assert error.value.code == 302


def test_default_transport_rejects_oversized_local_response() -> None:
    with _local_server(_OversizedHandler) as base:
        request = urllib.request.Request(base, method="GET")
        with pytest.raises(ProviderError) as error:
            OpenAIProvider._default_transport(request, timeout=2)

    assert error.value.status is ProviderHealthStatus.PARSE_FAILURE
    assert "oversized" in str(error.value).lower()
