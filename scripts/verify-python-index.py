"""Compare an existing PyPI/TestPyPI release with reviewed local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote


INDEXES = {
    "pypi": "https://pypi.org/pypi",
    "testpypi": "https://test.pypi.org/pypi",
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def remote_sha256(url: str) -> str:
    value = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "ARX-release-verifier/4"})
    with urllib.request.urlopen(request, timeout=30) as response:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_release(index: str, version: str, retries: int) -> dict[str, object]:
    endpoint = f"{INDEXES[index]}/arx-prescanner/{quote(version, safe='')}/json"
    request = urllib.request.Request(endpoint, headers={"User-Agent": "ARX-release-verifier/4"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.load(response)
            if isinstance(value, dict):
                return value
        except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError):
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
    expected = {path.name: sha256(path) for path in (wheel, sdist) if path.is_file()}
    if len(expected) != 2:
        raise SystemExit("The reviewed wheel and source distribution are both required.")

    try:
        release = load_release(arguments.index, arguments.version, arguments.retries)
        info = release.get("info", {})
        if not isinstance(info, dict) or info.get("name") != "arx-prescanner" or info.get("version") != arguments.version:
            raise RuntimeError("Published package identity does not match the reviewed release.")
        urls = release.get("urls", [])
        if not isinstance(urls, list):
            raise RuntimeError("Published release file metadata is malformed.")
        published = {item.get("filename"): item for item in urls if isinstance(item, dict)}
        if set(published) != set(expected):
            raise RuntimeError("Published release does not contain exactly the reviewed wheel and source distribution.")
        for filename, expected_hash in expected.items():
            item = published[filename]
            digests = item.get("digests", {})
            url = item.get("url")
            if not isinstance(digests, dict) or digests.get("sha256") != expected_hash or not isinstance(url, str):
                raise RuntimeError(f"Published digest metadata does not match {filename}.")
            if remote_sha256(url) != expected_hash:
                raise RuntimeError(f"Downloaded published bytes do not match {filename}.")
    except (OSError, RuntimeError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise SystemExit(str(exc)) from None

    print(f"{arguments.index}: PASS (arx-prescanner {arguments.version}; exact wheel and sdist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
