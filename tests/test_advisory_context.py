import json
import os

from arx.advisory.context import (
    MAX_CONTEXT_CHARS,
    build_advisory_context,
    build_advisory_prompt,
    redact_external,
)


def test_context_selects_one_finding_and_relevant_project_data_only(tmp_path, monkeypatch):
    profile = tmp_path / "Jörg"
    project = profile / "PrivateProject"
    monkeypatch.setenv("USERPROFILE", str(profile))
    context = build_advisory_context(
        "Project requirement",
        ("capability", "status", "path", "reason"),
        ("python.runtime", "RED", str(project / ".venv" / "python.exe"), "Resolved 3.13; requires <3.12"),
        project={"identity": "PrivateProject", "project_root": str(project), "constraint": ">=3.10,<3.12"},
        evidence=[{"kind": "observed", "source": str(project / "pyproject.toml"), "value": "requires-python"}],
        private_roots=[project],
    )

    packet = context.preview()

    assert context.status == "RED"
    assert context.title == "python.runtime"
    assert "%PROJECT_ROOT%" in packet or "%USERPROFILE%" in packet
    assert str(profile) not in packet
    assert "machine" not in packet.casefold()
    assert context.context_id == build_advisory_context(
        "Project requirement",
        ("capability", "status", "path", "reason"),
        ("python.runtime", "RED", str(project / ".venv" / "python.exe"), "Resolved 3.13; requires <3.12"),
        project={"identity": "PrivateProject", "project_root": str(project), "constraint": ">=3.10,<3.12"},
        evidence=[{"kind": "observed", "source": str(project / "pyproject.toml"), "value": "requires-python"}],
        private_roots=[project],
    ).context_id


def test_external_redaction_removes_credentials_from_keys_and_free_text(monkeypatch):
    monkeypatch.setenv("USERNAME", "PrivateUser")
    secret = "sk-" + "proj-abcdefghijklmnopqrstuvwxyz012345"
    value = {
        "OPENAI_API_KEY": secret,
        "diagnostic": f"Bearer abcdefghijklmnopqrstuvwxyz API_KEY={secret} user PrivateUser",
        "nested": {"password": "hunter2", "cookie": "session-value"},
    }

    redacted = json.dumps(redact_external(value), ensure_ascii=False)

    assert secret not in redacted
    assert "hunter2" not in redacted
    assert "session-value" not in redacted
    assert "PrivateUser" not in redacted
    assert redacted.count("<redacted") >= 3


def test_windows_path_fields_are_redacted_on_every_platform():
    result = redact_external({"resolved_path": r"C:\Users\Alice Smith\Python\python.exe"})

    assert result["resolved_path"] == "%LOCAL_PATH%/python.exe"
    assert "Alice" not in result["resolved_path"]


def test_unkeyed_free_text_redacts_arbitrary_local_paths():
    result = redact_external(
        {
            "diagnostic": r"Read C:\Private\repo\build.log and /home/alice/private/report.json before retrying",
        }
    )

    assert r"C:\Private" not in result["diagnostic"]
    assert "/home/alice" not in result["diagnostic"]
    assert result["diagnostic"].count("%LOCAL_PATH%") == 2


def test_large_diagnostics_are_bounded_and_record_truncation():
    context = build_advisory_context(
        "Error",
        tuple(f"field_{index}" for index in range(100)),
        tuple("x" * 10_000 for _index in range(100)),
        project={f"project_{index}": "y" * 10_000 for index in range(100)},
        evidence=[{"value": "z" * 10_000, "index": index} for index in range(100)],
    )

    assert len(context.preview()) <= MAX_CONTEXT_CHARS
    assert "omitted by ARX" in context.preview()
    assert len(context.evidence) <= 8


def test_prompt_preserves_advisory_identity_and_redacts_question(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\Alice")
    context = build_advisory_context("Finding", ("status", "reason"), ("RED", "Python mismatch"))
    prompt = build_advisory_prompt(
        context,
        r"Explain C:\Users\Alice\secret and TOKEN=abcdefghijklmnop",
        mode="Suggest Safe Fix",
        conversation=[{"role": "assistant", "text": "Previous TOKEN=should-not-leak"}],
    )

    assert "AI ADVISORY REQUEST" in prompt
    assert "advisory only" in prompt
    assert "Do not claim to have changed the machine" in prompt
    assert "Suggest Safe Fix" in prompt
    assert r"C:\Users\Alice" not in prompt
    assert "abcdefghijklmnop" not in prompt
    assert "should-not-leak" not in prompt
    assert prompt.endswith("Return advisory analysis only; ARX supplies the trust label in its UI.")
