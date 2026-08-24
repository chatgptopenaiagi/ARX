import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts" / "collect-windows-lifecycle-evidence.ps1"
GUIDE = ROOT / "docs" / "WINDOWS_STANDARD_USER_LIFECYCLE.md"
EVIDENCE = ROOT / "security" / "beta2" / "evidence" / "standard-user-lifecycle.json"


def test_lifecycle_collector_is_observational_and_does_not_self_elevate():
    script = COLLECTOR.read_text(encoding="utf-8")
    lowered = script.casefold()

    assert "get-filehash" in lowered
    assert "get-acl" in lowered
    assert "start-process" not in lowered
    assert "-verb runas" not in lowered
    assert "remove-item" not in lowered
    assert "set-acl" not in lowered
    assert "cert:" not in lowered
    assert "set-mppreference" not in lowered


def test_lifecycle_guide_requires_both_windows_generations_and_direct_observation():
    guide = GUIDE.read_text(encoding="utf-8").casefold()

    for required in (
        "windows 10 22h2",
        "windows 11",
        "standard user",
        "program files",
        "upgrade",
        "uninstall",
        "asInvoker".casefold(),
        "blocked_not_executed",
    ):
        assert required in guide
    assert "static `asinvoker` manifest is necessary but not sufficient" in guide


def test_current_lifecycle_evidence_is_explicitly_blocked_not_executed():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["result"] == "BLOCKED_NOT_EXECUTED"
    assert not evidence["infrastructure_observation"]["development_host_used_as_disposable_guest"]
    assert all(value == "NOT_EXECUTED" for value in evidence["execution"].values())
    assert not any(evidence["safety"].values())
