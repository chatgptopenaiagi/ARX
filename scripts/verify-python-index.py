"""Compare an existing PyPI/TestPyPI release with reviewed local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import quote

INDEXES = {
    "pypi": "https://pypi.org/pypi",
    "testpypi": "https://test.pypi.org/pypi",
}
INDEX_HOSTS = {
    "pypi": frozenset({"pypi.org"}),
    "testpypi": frozenset({"test.pypi.org"}),
}
ARTIFACT_HOSTS = {
    "pypi": frozenset({"files.pythonhosted.org"}),
    "testpypi": frozenset({"test-files.pythonhosted.org"}),
}
MAX_INDEX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_DISTRIBUTION_BYTES = 50 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 30
READ_BLOCK_BYTES = 1024 * 1024


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Reject redirects so every authenticated trust decision uses the validated URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_https_url(
    url: str,
    *,
    expected_hosts: frozenset[str],
    required_path_prefix: str,
) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Remote URL failed validation.") from exc
    hostname = parsed.hostname.casefold() if parsed.hostname else ""
    if (
        parsed.scheme.casefold() != "https"
        or hostname not in expected_hosts
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith(required_path_prefix)
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Remote URL failed the HTTPS host allowlist.")


def _open_request(request: urllib.request.Request, timeout: int):
    opener = urllib.request.build_opener(_RejectRedirects())
    return opener.open(request, timeout=timeout)


def _content_length(response) -> int | None:
    raw = response.headers.get("Content-Length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Remote response supplied an invalid Content-Length.") from exc
    if value < 0:
        raise RuntimeError("Remote response supplied an invalid Content-Length.")
    return value


def _read_bounded(response, *, maximum_bytes: int, expected_bytes: int | None = None) -> bytes:
    declared = _content_length(response)
    if declared is not None and declared > maximum_bytes:
        raise RuntimeError("Remote response exceeds the permitted size.")
    if expected_bytes is not None and declared is not None and declared != expected_bytes:
        raise RuntimeError("Remote response size does not match reviewed metadata.")
    chunks: list[bytes] = []
    total = 0
    while True:
        block = response.read(min(READ_BLOCK_BYTES, maximum_bytes - total + 1))
        if not block:
            break
        total += len(block)
        if total > maximum_bytes or (expected_bytes is not None and total > expected_bytes):
            raise RuntimeError("Remote response exceeds the permitted size.")
        chunks.append(block)
    if expected_bytes is not None and total != expected_bytes:
        raise RuntimeError("Downloaded size does not match reviewed metadata.")
    return b"".join(chunks)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def remote_sha256(url: str, *, index: str, expected_size: int) -> str:
    if not 0 < expected_size <= MAX_DISTRIBUTION_BYTES:
        raise RuntimeError("Reviewed distribution size is outside the permitted bounds.")
    _validate_https_url(
        url,
        expected_hosts=ARTIFACT_HOSTS[index],
        required_path_prefix="/packages/",
    )
    request = urllib.request.Request(url, headers={"User-Agent": "ARX-release-verifier/4"})
    with _open_request(request, REQUEST_TIMEOUT_SECONDS) as response:
        _validate_https_url(
            response.geturl(),
            expected_hosts=ARTIFACT_HOSTS[index],
            required_path_prefix="/packages/",
        )
        if getattr(response, "status", 200) != 200:
            raise RuntimeError("Artifact download returned an unexpected HTTP status.")
        payload = _read_bounded(
            response,
            maximum_bytes=MAX_DISTRIBUTION_BYTES,
            expected_bytes=expected_size,
        )
    return hashlib.sha256(payload).hexdigest()


def load_release(index: str, version: str, retries: int) -> dict[str, object]:
    endpoint = f"{INDEXES[index]}/arx-prescanner/{quote(version, safe='')}/json"
    _validate_https_url(
        endpoint,
        expected_hosts=INDEX_HOSTS[index],
        required_path_prefix="/pypi/arx-prescanner/",
    )
    request = urllib.request.Request(endpoint, headers={"User-Agent": "ARX-release-verifier/4"})
    for attempt in range(1, retries + 1):
        try:
            with _open_request(request, REQUEST_TIMEOUT_SECONDS) as response:
                _validate_https_url(
                    response.geturl(),
                    expected_hosts=INDEX_HOSTS[index],
                    required_path_prefix="/pypi/arx-prescanner/",
                )
                if getattr(response, "status", 200) != 200:
                    raise RuntimeError("Package index returned an unexpected HTTP status.")
                raw = _read_bounded(response, maximum_bytes=MAX_INDEX_RESPONSE_BYTES)
                value = json.loads(raw.decode("utf-8"))
            if isinstance(value, dict):
                return value
        except (
            OSError,
            RuntimeError,
            UnicodeError,
            ValueError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ):
            if attempt == retries:
                break
            time.sleep(10)
    raise RuntimeError(f"{index} did not expose the requested release within the bounded retry window.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", choices=sorted(INDEXES), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--retries", type=int, default=1)
    arguments = parser.parse_args()
    if not 1 <= arguments.retries <= 30:
        raise SystemExit("--retries must be between 1 and 30.")

    wheel = arguments.dist_dir / f"arx_prescanner-{arguments.version}-py3-none-any.whl"
    sdist = arguments.dist_dir / f"arx_prescanner-{arguments.version}.tar.gz"
    expected = {
        path.name: {"sha256": sha256(path), "size": path.stat().st_size}
        for path in (wheel, sdist)
        if path.is_file()
    }
    if len(expected) != 2:
        raise SystemExit("The reviewed wheel and source distribution are both required.")

    try:
        release = load_release(arguments.index, arguments.version, arguments.retries)
        info = release.get("info", {})
        if not isinstance(info, dict) or info.get("name") != "arx-prescanner" or info.get("version") != arguments.version:
            raise RuntimeError("Published package identity does not match the reviewed release.")
        urls = release.get("urls", [])
        if not isinstance(urls, list):
            raise TypeError("Published release file metadata is malformed.")
        published = {item.get("filename"): item for item in urls if isinstance(item, dict)}
        if set(published) != set(expected):
            raise RuntimeError("Published release does not contain exactly the reviewed wheel and source distribution.")
        for filename, expected_identity in expected.items():
            item = published[filename]
            digests = item.get("digests", {})
            url = item.get("url")
            size = item.get("size")
            expected_hash = expected_identity["sha256"]
            expected_size = expected_identity["size"]
            if (
                not isinstance(digests, dict)
                or digests.get("sha256") != expected_hash
                or not isinstance(url, str)
                or type(size) is not int
                or size != expected_size
            ):
                raise RuntimeError(f"Published digest metadata does not match {filename}.")
            if remote_sha256(url, index=arguments.index, expected_size=expected_size) != expected_hash:
                raise RuntimeError(f"Downloaded published bytes do not match {filename}.")
    except (OSError, RuntimeError, TypeError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(str(exc)) from None

    print(f"{arguments.index}: PASS (arx-prescanner {arguments.version}; exact wheel and sdist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
