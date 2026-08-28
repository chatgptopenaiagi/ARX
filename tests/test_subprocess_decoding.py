from __future__ import annotations

import pytest

from arx.core.subprocess import decode_output, run_bounded


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"ASCII 123", "ASCII 123"),
        ("Flutter \u2022 stable".encode("utf-8"), "Flutter \u2022 stable"),
        (b"\xef\xbb\xbfUTF-8 BOM", "UTF-8 BOM"),
        ("WSL 2.6.1".encode("utf-16"), "WSL 2.6.1"),
        ("WSL 2.6.1".encode("utf-16-le"), "WSL 2.6.1"),
        ("WSL 2.6.1".encode("utf-16-be"), "WSL 2.6.1"),
        (b"legacy \x96 dash", "legacy \u2013 dash"),
    ],
)
def test_decode_output_normalizes_supported_windows_encodings(raw, expected, monkeypatch):
    monkeypatch.setattr("arx.core.subprocess.os.name", "nt")
    monkeypatch.setattr("arx.core.subprocess.locale.getpreferredencoding", lambda _do_setlocale=False: "utf-8")
    value = decode_output(raw, 100)
    assert value == expected
    assert "\x00" not in value
    assert not value.startswith("\ufeff")


def test_decode_output_handles_invalid_bytes_without_unbounded_failure(monkeypatch):
    monkeypatch.setattr("arx.core.subprocess.os.name", "posix")
    monkeypatch.setattr("arx.core.subprocess.locale.getpreferredencoding", lambda _do_setlocale=False: "utf-8")
    value = decode_output(b"valid\xff\xfeinvalid", 8)
    assert len(value) <= 8
    assert value.startswith("valid")


def test_utf16_truncation_ends_on_complete_code_unit():
    raw = "abcdefghij".encode("utf-16-le") + b"\xff"
    value = decode_output(raw, 10)
    assert value == "abcdefghij"
    assert "\x00" not in value


def test_run_bounded_uses_bytes_shell_false_and_character_limit():
    captured = {}
    def runner(args, **kwargs):
        captured.update(kwargs)
        return type("Completed", (), {"returncode": 0, "stdout": ("\u2022" * 20).encode(), "stderr": b""})()
    result = run_bounded(["fixed.exe", "--version"], timeout=2, limit=7, runner=runner)
    assert result["stdout"] == "\u2022" * 7
    assert captured["text"] is False
    assert captured["shell"] is False
    assert captured["timeout"] == 2
    assert "â" not in result["stdout"]
    assert "\x00" not in result["stdout"]
    assert not result["stdout"].startswith("\ufeff")
    assert len(result["stdout"]) <= 7


def test_invalid_middle_utf8_is_not_trimmed_as_boundary_truncation(monkeypatch):
    monkeypatch.setattr("arx.core.subprocess.os.name", "posix")
    monkeypatch.setattr("arx.core.subprocess.locale.getpreferredencoding", lambda _do_setlocale=False: "utf-8")
    value = decode_output(b"ok\xffmiddle" + "•".encode("utf-8"), 20)
    assert value.startswith("ok�middle")
