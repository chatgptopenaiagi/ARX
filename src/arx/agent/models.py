from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import Any

from arx.core.models import EvidenceKind


class AgentOperationalState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


class CalibrationOutcome(str, Enum):
    CORRECT_AVAILABLE = "CORRECT_AVAILABLE"
    CORRECT_UNAVAILABLE = "CORRECT_UNAVAILABLE"
    CORRECT_RESTRICTED = "CORRECT_RESTRICTED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    UNKNOWN_RESOLVED_AVAILABLE = "UNKNOWN_RESOLVED_AVAILABLE"
    UNKNOWN_RESOLVED_UNAVAILABLE = "UNKNOWN_RESOLVED_UNAVAILABLE"
    UNKNOWN_RESOLVED_BLOCKED = "UNKNOWN_RESOLVED_BLOCKED"
    UNKNOWN_REMAINS_UNRESOLVED = "UNKNOWN_REMAINS_UNRESOLVED"


@dataclass
class AgentIdentity:
    name: str
    implementation: str | None = None
    version: str | None = None
    model_identifier: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentExecutionContext:
    working_directory: str | None = None
    process_architecture: str | None = None
    interactive: bool | None = None
    privilege_class: str | None = None
    sandbox_profile: str | None = None
    approval_profile: str | None = None
    agent_reported_host: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentPolicy:
    profile: str
    mutation_boundary: str = "safe-bounded"
    remote_mutation: str = "not-authorized-unless-explicit"
    dangerous_probes: str = "not-tested"
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapabilityScope:
    kind: str
    target: str
    qualifiers: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentCapabilityEvidence:
    id: str
    kind: EvidenceKind
    source: str
    method: str
    summary: str | None = None
    exit_code: int | None = None
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | float | None = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapabilityDimensions:
    declared: str = "UNKNOWN"
    availability: str = "UNKNOWN"
    resolution: str = "UNKNOWN"
    permission: str = "UNKNOWN"
    authorization: str = "UNKNOWN"
    attempt: str = "NOT_TESTED"
    execution: str = "NOT_EXECUTED"
    success: str = "UNKNOWN"


@dataclass
class AgentCapability:
    id: str
    family: str
    name: str
    state: AgentOperationalState
    scope: AgentCapabilityScope
    dimensions: AgentCapabilityDimensions
    result: str | None = None
    reason_code: str | None = None
    limitations: list[str] = field(default_factory=list)
    dependency_ids: list[str] = field(default_factory=list)
    source_dependency_ids: list[str] = field(default_factory=list)
    canonical_dependency_ids: list[str] = field(default_factory=list)
    evidence: list[AgentCapabilityEvidence] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | float | None = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapabilityEdge:
    source_id: str
    target_id: str
    relation: str = "requires"


@dataclass
class AgentCapabilityGraph:
    node_ids: list[str]
    edges: list[AgentCapabilityEdge] = field(default_factory=list)
    unresolved_dependency_ids: list[str] = field(default_factory=list)


@dataclass
class AgentContradiction:
    id: str
    code: str
    subject_capability_id: str | None
    capability_refs: list[str]
    evidence_refs: list[str]
    scope: str
    severity: str
    impact: str
    resolved_interpretation: str | None = None
    remaining_uncertainty: list[str] = field(default_factory=list)
    source_record: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContextDescriptor:
    id: str
    label: str
    activation: str
    environment_markers: list[str] = field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.OBSERVED


@dataclass
class AgentCapabilityStateTransition:
    capability_id: str
    before_context_id: str
    before_state: AgentOperationalState
    after_context_id: str
    after_state: AgentOperationalState
    interpretation: str
    evidence_refs: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class AgentIntervention:
    id: str
    timestamp: str | None
    reason: str
    actor: str
    before: dict[str, Any]
    action: str
    after: dict[str, Any]
    effect_on_agent_capability: str
    scope: str
    before_context: AgentContextDescriptor | None = None
    after_context: AgentContextDescriptor | None = None
    capability_transitions: list[AgentCapabilityStateTransition] = field(default_factory=list)
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    agent_reference_id: str | None = None
    machine_reference_id: str | None = None
    ordering: str = "before_then_after"
    software_install_performed: bool | None = None


def stable_context_transition_id(
    before_snapshot_id: str,
    after_snapshot_id: str,
    agent_reference_id: str,
    machine_reference_id: str,
    capability_ids: list[str],
) -> str:
    """Return a deterministic identity without environment values or other secrets."""
    payload = "\x1f".join(
        [before_snapshot_id, after_snapshot_id, agent_reference_id, machine_reference_id, *sorted(capability_ids)]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"agent-context-transition:{digest}"


@dataclass
class AgentCalibrationEntry:
    capability: str
    declared_state: str
    observed_state: AgentOperationalState
    outcome: CalibrationOutcome


@dataclass
class AgentCalibration:
    entries: list[AgentCalibrationEntry] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    note: str = "Categorical comparison only; not a probability or intelligence score."


@dataclass
class MachineReference:
    machine_dna_id: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "UNRESOLVED"


@dataclass
class AgentDNASnapshot:
    schema_version: str
    snapshot_id: str
    producer: dict[str, str]
    generated_at: str
    agent: AgentIdentity
    machine_reference: MachineReference
    execution_context: AgentExecutionContext
    policy: AgentPolicy
    capabilities: list[AgentCapability]
    capability_graph: AgentCapabilityGraph
    contradictions: list[AgentContradiction]
    interventions: list[AgentIntervention]
    calibration: AgentCalibration
    unknowns: list[str]
    summary: dict[str, Any]
    extensions: dict[str, Any] = field(default_factory=dict)
