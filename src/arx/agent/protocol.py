from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from arx.core.models import EvidenceKind

from .models import AgentOperationalState


CHALLENGE_PROTOCOL_VERSION = "agent-challenge/0.1"


class ExecutionProvenanceState(str, Enum):
    OBSERVED = "OBSERVED"
    RECEIPT_REPORTED = "RECEIPT_REPORTED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ChallengeScope:
    kind: str
    target: str
    qualifiers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChallengeFixture:
    relative_path: str
    size: int
    sha256: str
    role: str = "input"


@dataclass(frozen=True)
class ArtifactExpectation:
    relative_path: str
    required: bool = True
    expected_size: int | None = None
    expected_sha256: str | None = None
    expected_text: str | None = None
    executable: bool = False


@dataclass
class AgentCapabilityChallenge:
    protocol_version: str
    challenge_id: str
    capability_id: str
    family: str
    purpose: str
    scope: ChallengeScope
    workspace_id: str
    workspace: str
    allowed_operations: list[str]
    forbidden_operations: list[str]
    timeout_seconds: int
    expected_evidence: list[str]
    artifact_expectations: list[ArtifactExpectation]
    validator: dict[str, str]
    fixture_version: str
    fixtures: list[ChallengeFixture] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    machine_reference: str | None = None
    execution_context_requirements: dict[str, str] = field(default_factory=dict)
    safety_profile: str = "bounded-disposable-workspace"
    producer: dict[str, str] = field(default_factory=lambda: {"name": "ARX"})
    generated_at: str | None = None


@dataclass(frozen=True)
class ReceiptArtifact:
    relative_path: str
    size: int
    sha256: str


@dataclass
class AgentCapabilityReceipt:
    protocol_version: str
    challenge_id: str
    agent_reference: str
    execution_context_reference: str
    execution_context: dict[str, str]
    claimed_state: AgentOperationalState
    started_at: str | None
    finished_at: str | None
    duration_ms: int | float | None
    exit_code: int | None
    stdout_summary: str
    stderr_summary: str
    evidence_refs: list[str]
    artifacts: list[ReceiptArtifact]
    performed_operations: list[str] = field(default_factory=list)
    tool_observations: list[dict[str, str]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True)
class TrustedExecutionObservation:
    observation_id: str
    challenge_id: str
    provider_id: str
    resolved_executable_class: str
    command_fingerprint: str
    working_directory_fingerprint: str
    started_at: str
    finished_at: str
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    artifact_hashes: dict[str, str]
    execution_context_reference: str
    evidence_kind: EvidenceKind
    observer: dict[str, str]


@dataclass
class AgentChallengeValidation:
    protocol_version: str
    challenge_id: str
    capability_id: str
    scope: ChallengeScope
    agent_reference: str
    execution_context_reference: str
    generated_at: str
    validator: dict[str, str]
    receipt_structurally_valid: bool
    identity_match: bool
    policy_compliant: bool
    workspace_boundary_valid: bool
    required_evidence_valid: bool
    fixture_integrity_valid: bool
    artifacts_valid: bool
    artifact_hashes_valid: bool
    expected_output_valid: bool
    timeout_consistent: bool
    outcome_validated: bool
    execution_provenance: ExecutionProvenanceState
    claimed_state: AgentOperationalState
    validated_state: AgentOperationalState
    reason_codes: list[str]
    evidence: list[dict[str, Any]]
    limitations: list[str] = field(default_factory=list)
    remaining_uncertainty: list[str] = field(default_factory=list)


class AgentAdapter(Protocol):
    """Vendor-neutral transport seam; adapters may not validate their own claims."""

    def describe(self) -> dict[str, str]: ...

    def submit_challenge(self, challenge: AgentCapabilityChallenge) -> AgentCapabilityReceipt: ...


def validate_receipt(
    challenge: AgentCapabilityChallenge,
    receipt: AgentCapabilityReceipt,
    *,
    workspace: str | Path | None = None,
    trusted_execution_observation: TrustedExecutionObservation | None = None,
) -> AgentChallengeValidation:
    """Validate a receipt and workspace artifacts without executing receipt content."""
    from .challenges import validate_challenge_receipt

    return validate_challenge_receipt(
        challenge,
        receipt,
        workspace=workspace,
        trusted_execution_observation=trusted_execution_observation,
    )
