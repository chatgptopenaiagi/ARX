import json
from datetime import datetime, timedelta, timezone

import pytest

from arx.advisory.audit import AuditError, TransmissionAudit, TransmissionEvent, TransportState


def _event(index, *, timestamp=None, model="gpt-test"):
    return TransmissionEvent(
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        attempt_id=f"attempt-{index}",
        provider_id="openai-api",
        operation="advisory",
        state=TransportState.RESPONSE_RECEIVED,
        model=model,
        request_bytes=100 + index,
        response_bytes=200 + index,
        latency_ms=10 + index,
    )


def test_transmission_audit_is_metadata_only_bounded_and_rotated(tmp_path):
    audit = TransmissionAudit(
        tmp_path / "external-transmissions.jsonl",
        max_events_per_file=2,
        max_files=2,
        max_file_bytes=2_048,
    )

    for index in range(6):
        audit.record(_event(index))

    history = audit.history()
    serialized = json.dumps(history)
    assert [item["attempt_id"] for item in history] == ["attempt-2", "attempt-3", "attempt-4", "attempt-5"]
    assert len(list(tmp_path.glob("external-transmissions.jsonl*"))) <= 2
    assert "prompt" not in serialized.casefold()
    assert "response_body" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()
    assert '"sent"' not in serialized.casefold()


def test_transmission_audit_rejects_secret_shaped_metadata_and_excludes_expired_records(tmp_path):
    key = "sk-proj-this-is-a-test-key-not-a-real-secret"
    audit = TransmissionAudit(tmp_path / "audit.jsonl", retention_days=2)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    audit.record(_event(1, timestamp=old))
    with pytest.raises(AuditError):
        audit.record(_event(2, model=key))
    audit.record(_event(3))

    serialized = json.dumps(audit.history())
    assert "attempt-1" not in serialized
    assert key not in serialized
    assert "attempt-3" in serialized


def test_transmission_audit_clear_and_explicit_redacted_export(tmp_path):
    audit = TransmissionAudit(tmp_path / "audit.jsonl")
    audit.record(_event(1))
    exported = tmp_path / "chosen-export.json"

    audit.export_redacted(exported)

    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert payload[0]["state"] == "RESPONSE_RECEIVED"
    assert audit.history()
    audit.clear_history()
    assert audit.history() == []
    assert exported.exists()
