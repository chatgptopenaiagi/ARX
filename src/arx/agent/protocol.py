from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AgentCapabilityChallenge:
    challenge_id: str
    capability_id: str
    scope: str
    allowed_operations: list[str]
    forbidden_operations: list[str]
    timeout_seconds: int
    expected_evidence: list[str]
    artifact_expectations: list[str] = field(default_factory=list)


@dataclass
class AgentCapabilityReceipt:
    challenge_id: str
    claimed_state: str
    evidence_refs: list[str]
    artifact_hashes: dict[str, str] = field(default_factory=dict)


class AgentAdapter(Protocol):
    """Future vendor-neutral transport seam; adapters may not validate their own claims."""

    def describe(self) -> dict[str, str]: ...

    def submit_challenge(self, challenge: AgentCapabilityChallenge) -> AgentCapabilityReceipt: ...


def validate_receipt(challenge: AgentCapabilityChallenge, receipt: AgentCapabilityReceipt) -> bool:
    """Structural validation only; executing arbitrary receipt content is intentionally excluded."""
    return challenge.challenge_id == receipt.challenge_id and bool(receipt.evidence_refs)
