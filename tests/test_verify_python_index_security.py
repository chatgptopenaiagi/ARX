from __future__ import annotations

import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-python-index.py"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("arx_verify_python_index", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse(BytesIO):
    def __init__(
        self,
        payload: bytes,
        *,
        url: str,
        content_length: str | None = None,
        status: int = 200,
    ):
        super().__init__(payload)
        self._url = url
        self.status = status
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def geturl(self) -> str:
        return self._url


@pytest.mark.parametrize(
    "url",
    (
        "http://files.pythonhosted.org/packages/a.whl",
        "file:///packages/a.whl",
        "https://example.invalid/packages/a.whl",
        "https://user@files.pythonhosted.org/packages/a.whl",
        "https://files.pythonhosted.org:444/packages/a.whl",
        "https://files.pythonhosted.org/not-packages/a.whl",
        "https://files.pythonhosted.org/packages/a.whl?download=1",
        "https://files.pythonhosted.org/packages/a.whl#fragment",
    ),
)
def test_artifact_url_validation_fails_closed(url):
    verifier = _load_verifier()

    with pytest.raises(RuntimeError, match="allowlist|validation"):
        verifier._validate_https_url(
            url,
            expected_hosts=verifier.ARTIFACT_HOSTS["pypi"],
            required_path_prefix="/packages/",
        )


def test_artifact_url_validation_accepts_exact_origin_and_default_port():
    verifier = _load_verifier()

    for url in (
        "https://files.pythonhosted.org/packages/a.whl",
        "https://files.pythonhosted.org:443/packages/a.whl",
    ):
        verifier._validate_https_url(
            url,
            expected_hosts=verifier.ARTIFACT_HOSTS["pypi"],
            required_path_prefix="/packages/",
        )


def test_testpypi_artifact_host_is_independent_from_production():
    verifier = _load_verifier()

    with pytest.raises(RuntimeError, match="allowlist"):
        verifier._validate_https_url(
            "https://files.pythonhosted.org/packages/a.whl",
            expected_hosts=verifier.ARTIFACT_HOSTS["testpypi"],
            required_path_prefix="/packages/",
        )


def test_redirect_handler_rejects_every_redirect():
    verifier = _load_verifier()
    handler = verifier._RejectRedirects()

    assert handler.redirect_request(None, None, 302, "Found", {}, "https://example.invalid") is None


def test_remote_hash_enforces_final_origin_size_and_hash(monkeypatch):
    verifier = _load_verifier()
    payload = b"reviewed distribution"
    url = "https://files.pythonhosted.org/packages/reviewed.whl"
    observed_request = {}
    response = FakeResponse(
        payload,
        url=url,
        content_length=str(len(payload)),
    )

    def open_request(request, timeout):
        observed_request["url"] = request.full_url
        observed_request["timeout"] = timeout
        return response

    monkeypatch.setattr(verifier, "_open_request", open_request)

    observed = verifier.remote_sha256(url, index="pypi", expected_size=len(payload))

    assert observed == hashlib.sha256(payload).hexdigest()
    assert observed_request == {"url": url, "timeout": 30}


@pytest.mark.parametrize(
    ("payload", "content_length", "expected_size", "message"),
    (
        (b"longer", "6", 5, "size does not match"),
        (b"short", None, 6, "Downloaded size does not match"),
        (b"longer", None, 5, "exceeds"),
        (b"data", "not-a-number", 4, "invalid Content-Length"),
    ),
)
def test_remote_hash_rejects_size_mismatches(
    monkeypatch, payload, content_length, expected_size, message
):
    verifier = _load_verifier()
    url = "https://files.pythonhosted.org/packages/reviewed.whl"
    response = FakeResponse(
        payload,
        url=url,
        content_length=content_length,
    )
    monkeypatch.setattr(verifier, "_open_request", lambda request, timeout: response)

    with pytest.raises(RuntimeError, match=message):
        verifier.remote_sha256(url, index="pypi", expected_size=expected_size)


def test_remote_hash_revalidates_effective_url_after_open(monkeypatch):
    verifier = _load_verifier()
    source = "https://files.pythonhosted.org/packages/reviewed.whl"
    response = FakeResponse(
        b"data",
        url="https://example.invalid/packages/reviewed.whl",
        content_length="4",
    )
    monkeypatch.setattr(verifier, "_open_request", lambda request, timeout: response)

    with pytest.raises(RuntimeError, match="allowlist"):
        verifier.remote_sha256(source, index="pypi", expected_size=4)


def test_index_metadata_read_is_bounded(monkeypatch):
    verifier = _load_verifier()
    endpoint = "https://pypi.org/pypi/arx-prescanner/4.0.0b2/json"
    response = FakeResponse(
        b"{}",
        url=endpoint,
        content_length=str(verifier.MAX_INDEX_RESPONSE_BYTES + 1),
    )
    monkeypatch.setattr(verifier, "_open_request", lambda request, timeout: response)
    monkeypatch.setattr(verifier.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="bounded retry window"):
        verifier.load_release("pypi", "4.0.0b2", retries=1)
