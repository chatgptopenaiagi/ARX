import urllib.parse

import pytest

from arx.advisory.context import build_advisory_context
from arx.advisory.web import build_search_query, build_search_url, official_domain, open_search


def _context(reason=r"C:\Users\Alice\project\build.log: CMake could not find CUDA compiler"):
    return build_advisory_context(
        "Compatibility finding",
        ("check", "status", "observed", "reason"),
        ("CUDA", "RED", "13.0", reason),
    )


def test_web_query_contains_useful_finding_terms_not_just_status():
    query = build_search_query(_context())

    assert "CUDA" in query
    assert "CMake" in query
    assert query != "RED"
    assert len(query) <= 240


def test_exact_error_search_removes_local_path_and_random_identifier():
    context = _context(r"C:\Private\repo\build.log deadbeefdeadbeefdeadbeef: CMake could not find CUDA compiler")
    query = build_search_query(context, "exact_error")

    assert r"C:\Private" not in query
    assert "deadbeefdeadbeefdeadbeef" not in query
    assert "CMake could not find CUDA compiler" in query


def test_search_url_is_https_and_safely_url_encoded():
    url = build_search_url("Python & CUDA <3.12", "google")
    parsed = urllib.parse.urlparse(url)

    assert parsed.scheme == "https"
    assert parsed.hostname == "www.google.com"
    assert urllib.parse.parse_qs(parsed.query)["q"] == ["Python & CUDA <3.12"]
    assert " & " not in url


def test_official_documentation_search_uses_recognized_domain_and_falls_back():
    cuda = _context()
    unknown = build_advisory_context("Finding", ("component", "status"), ("UnfamiliarTool", "YELLOW"))

    assert official_domain(cuda) == "docs.nvidia.com"
    assert build_search_query(cuda, "official").startswith("site:docs.nvidia.com")
    assert build_search_query(unknown, "official").startswith("official documentation")


def test_browser_bridge_accepts_only_known_https_search_hosts():
    opened = []
    safe = build_search_url("Python compatibility")
    open_search(safe, opener=lambda *args, **kwargs: opened.append((args, kwargs)))

    assert opened == [((safe,), {"new": 2})]
    with pytest.raises(ValueError):
        open_search("file:///C:/private/report.json", opener=lambda *_args, **_kwargs: None)
    with pytest.raises(ValueError):
        open_search("https://evil.example/?q=test", opener=lambda *_args, **_kwargs: None)
