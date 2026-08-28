from __future__ import annotations

from collections import Counter

from .models import (
    AgentCalibration,
    AgentCalibrationEntry,
    AgentOperationalState,
    CalibrationOutcome,
)


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
