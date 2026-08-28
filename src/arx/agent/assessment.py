from __future__ import annotations

from collections import Counter

from .models import (
    AgentCalibration,
    AgentCalibrationEntry,
    AgentOperationalState,
    CalibrationOutcome,
    AgentCapabilityStateTransition,
    AgentContextDescriptor,
)
from arx.core.models import EvidenceKind


def calibration_outcome(declared: str, observed: AgentOperationalState) -> CalibrationOutcome:
    if declared == "UNKNOWN":
        if observed is AgentOperationalState.PASS:
            return CalibrationOutcome.UNKNOWN_RESOLVED_AVAILABLE
        if observed is AgentOperationalState.FAIL:
            return CalibrationOutcome.UNKNOWN_RESOLVED_UNAVAILABLE
        if observed is AgentOperationalState.BLOCKED:
            return CalibrationOutcome.UNKNOWN_RESOLVED_BLOCKED
        return CalibrationOutcome.UNKNOWN_REMAINS_UNRESOLVED
    if declared == "EXPECTED_AVAILABLE":
        if observed is AgentOperationalState.PASS:
            return CalibrationOutcome.CORRECT_AVAILABLE
        if observed in {AgentOperationalState.NOT_TESTED, AgentOperationalState.UNKNOWN}:
            return CalibrationOutcome.UNKNOWN_REMAINS_UNRESOLVED
        return CalibrationOutcome.FALSE_POSITIVE
    if declared == "EXPECTED_UNAVAILABLE":
        return (
            CalibrationOutcome.FALSE_NEGATIVE
            if observed is AgentOperationalState.PASS
            else CalibrationOutcome.CORRECT_UNAVAILABLE
        )
    if declared == "EXPECTED_RESTRICTED":
        return (
            CalibrationOutcome.CORRECT_RESTRICTED
            if observed in {AgentOperationalState.NOT_TESTED, AgentOperationalState.BLOCKED}
            else CalibrationOutcome.FALSE_NEGATIVE
            if observed is AgentOperationalState.PASS
            else CalibrationOutcome.UNKNOWN_REMAINS_UNRESOLVED
        )
    return CalibrationOutcome.UNKNOWN_REMAINS_UNRESOLVED


def build_calibration(entries: list[AgentCalibrationEntry]) -> AgentCalibration:
    counts = Counter(item.outcome.value for item in entries)
    return AgentCalibration(entries=entries, counts=dict(sorted(counts.items())))


def validate_context_transition(
    before_context: AgentContextDescriptor,
    after_context: AgentContextDescriptor,
    transitions: list[AgentCapabilityStateTransition],
    *,
    capability_ids: set[str] | None = None,
) -> None:
    if before_context.id == after_context.id:
        raise ValueError("before and after execution contexts must differ")
    if not isinstance(before_context.evidence_kind, EvidenceKind) or not isinstance(after_context.evidence_kind, EvidenceKind):
        raise ValueError("context descriptors require a canonical EvidenceKind")
    seen: set[tuple[str, str, str]] = set()
    for item in transitions:
        if not isinstance(item.before_state, AgentOperationalState) or not isinstance(item.after_state, AgentOperationalState):
            raise ValueError(f"transition {item.capability_id} requires canonical operational states")
        if item.before_context_id != before_context.id or item.after_context_id != after_context.id:
            raise ValueError(f"transition {item.capability_id} references the wrong context pair")
        if capability_ids is not None and item.capability_id not in capability_ids:
            raise ValueError(f"transition capability does not exist in snapshot: {item.capability_id}")
        if any(not ref.startswith("agent-evidence:") for ref in item.evidence_refs):
            raise ValueError(f"transition {item.capability_id} contains a non-evidence reference")
        key = (item.capability_id, item.before_context_id, item.after_context_id)
        if key in seen:
            raise ValueError(f"duplicate capability transition: {item.capability_id}")
        seen.add(key)
        if item.before_state is AgentOperationalState.BLOCKED and not item.blocked_by:
            raise ValueError(f"blocked transition {item.capability_id} requires blocked_by")
