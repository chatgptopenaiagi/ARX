from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from arx.core.models import Evidence, utc_now


def stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def evidence_id(evidence: Evidence) -> str:
    return stable_id(
        "evidence",
        evidence.kind.value,
        evidence.source,
        evidence.value,
        evidence.method,
        getattr(evidence, "evidence_type", ""),
        getattr(evidence, "source_key", ""),
    )


class Relevance(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONALLY_REQUIRED = "conditionally_required"
    NOT_REQUIRED = "not_required"
    UNKNOWN_RELEVANCE = "unknown_relevance"


class Satisfaction(str, Enum):
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"
    OPTIONAL_UNAVAILABLE = "optional_unavailable"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ProviderKind(str, Enum):
    CPYTHON = "cpython"
    CONDA = "conda"
    UV_MANAGED = "uv_managed"
    VIRTUAL_ENVIRONMENT = "virtual_environment"
    WINDOWSAPPS_ALIAS = "windowsapps_alias"
    UNKNOWN = "unknown"


class ProviderHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ProviderScope(str, Enum):
    USER = "user"
    MACHINE = "machine"
    UNKNOWN = "unknown"


class RequirementEvidenceType(str, Enum):
    REQUIREMENT = "requirement"
    SELECTION = "selection"
    DEPENDENCY_ENVIRONMENT = "dependency_environment"
    DEPENDENCY_REQUIREMENT = "dependency_requirement"
    CI_TESTED = "ci_tested"
    INFERRED = "inferred"


class InterpretationState(str, Enum):
    INTERPRETED = "interpreted"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class Recoverability(str, Enum):
    READY = "ready"
    RECOVERABLE = "recoverable"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class RequirementEvidence(Evidence):
    """Typed project evidence whose purpose is independent from confidence."""

    capability: str = ""
    evidence_type: RequirementEvidenceType = RequirementEvidenceType.REQUIREMENT
    source_kind: str = "unknown"
    source_path: str = ""
    source_key: str = ""
    raw: str | None = None
    provenance: str = "static project inspection"


def _requirement_evidence_type(value: str) -> RequirementEvidenceType:
    aliases = {
        "dependency_resolution": RequirementEvidenceType.DEPENDENCY_ENVIRONMENT,
        "ci": RequirementEvidenceType.CI_TESTED,
        "inferred_environment": RequirementEvidenceType.INFERRED,
    }
    return aliases[value] if value in aliases else RequirementEvidenceType(value)


def _source_kind(source: str) -> str:
    lowered = source.lower()
    if lowered.endswith((".toml", ".lock")):
        return "toml"
    if lowered.endswith((".cfg", ".ini")):
        return "ini"
    if lowered.endswith(".py"):
        return "python_ast"
    return "plain_text"


def requirement_evidence(
    evidence: Evidence,
    *,
    capability: str,
    field_name: str,
    evidence_purpose: str,
) -> RequirementEvidence:
    if isinstance(evidence, RequirementEvidence):
        return evidence
    raw = str(evidence.value)
    return RequirementEvidence(
        kind=evidence.kind,
        source=evidence.source,
        value=evidence.value,
        method=evidence.method,
        confidence=evidence.confidence,
        note=evidence.note,
        capability=capability,
        evidence_type=_requirement_evidence_type(evidence_purpose),
        source_kind=_source_kind(evidence.source),
        source_path=evidence.source,
        source_key=field_name,
        raw=raw[:512],
        provenance=evidence.method,
    )


@dataclass
class ManifestRecord:
    path: str
    kind: str
    size: int
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Requirement:
    id: str
    capability: str
    constraint: str | None
    source: str
    field: str
    relevance: Relevance
    relation: str = "requires"
    evidence_purpose: str = "requirement"
    confidence: float = 1.0
    evidence: list[RequirementEvidence] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)
    effective_specifier: str | None = None
    is_effective: bool = False
    interpretation_state: InterpretationState = InterpretationState.INTERPRETED
    conflict_ids: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        capability: str,
        constraint: str | None,
        source: str,
        field: str,
        relevance: Relevance,
        relation: str = "requires",
        evidence_purpose: str = "requirement",
        confidence: float = 1.0,
        evidence: list[Evidence] | None = None,
        parent_ids: list[str] | None = None,
    ) -> Requirement:
        return cls(
            id=stable_id(
                "requirement", capability, constraint, source, field, relation, evidence_purpose
            ),
            capability=capability,
            constraint=constraint,
            source=source,
            field=field,
            relevance=relevance,
            relation=relation,
            evidence_purpose=evidence_purpose,
            confidence=confidence,
            evidence=[
                requirement_evidence(
                    item,
                    capability=capability,
                    field_name=field,
                    evidence_purpose=evidence_purpose,
                )
                for item in (evidence or [])
            ],
            parent_ids=list(parent_ids or []),
            effective_specifier=constraint,
            interpretation_state=(
                InterpretationState.INTERPRETED
                if constraint is not None
                else InterpretationState.UNKNOWN
            ),
            unknowns=([] if constraint is not None else ["Requirement value is unavailable or unsupported."]),
        )


@dataclass
class RequirementEdge:
    source_id: str
    target_id: str
    relation: str


@dataclass
class RequirementGraph:
    project_root: str = ""
    requirements_by_capability: dict[str, list[str]] = field(default_factory=dict)
    effective_requirement_ids: dict[str, str] = field(default_factory=dict)
    provenance_by_requirement: dict[str, list[str]] = field(default_factory=dict)
    conflict_ids: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        root: Path,
        requirements: list[Requirement],
        unknowns: list[str] | None = None,
    ) -> RequirementGraph:
        grouped: dict[str, list[str]] = {}
        effective: dict[str, str] = {}
        provenance: dict[str, list[str]] = {}
        for item in requirements:
            grouped.setdefault(item.capability, []).append(item.id)
            if item.is_effective:
                effective[item.capability] = item.id
            provenance[item.id] = [evidence_id(evidence) for evidence in item.evidence]
        conflict_ids = list(
            dict.fromkeys(
                identifier
                for item in requirements
                for identifier in item.conflict_ids
            )
        )
        interpretation_unknowns = [
            unknown for item in requirements for unknown in item.unknowns
        ]
        return cls(
            project_root=str(root),
            requirements_by_capability=grouped,
            effective_requirement_ids=effective,
            provenance_by_requirement=provenance,
            conflict_ids=conflict_ids,
            unknowns=list(dict.fromkeys([*(unknowns or []), *interpretation_unknowns])),
        )


@dataclass
class ProjectDNA:
    generated_at: str
    id: str
    identity: str
    root: Path
    languages: list[str] = field(default_factory=list)
    ecosystems: list[str] = field(default_factory=list)
    build_systems: list[str] = field(default_factory=list)
    manifests: list[ManifestRecord] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    optional_requirements: list[Requirement] = field(default_factory=list)
    requirement_edges: list[RequirementEdge] = field(default_factory=list)
    requirement_graph: RequirementGraph = field(default_factory=RequirementGraph)
    entrypoint_hints: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 1.0
    unknowns: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        root: str | Path,
        identity: str | None = None,
        requirements: list[Requirement] | None = None,
        optional_requirements: list[Requirement] | None = None,
        **kwargs: object,
    ) -> ProjectDNA:
        normalized_root = Path(root).expanduser().resolve()
        project_id = stable_id("project", os.path.normcase(str(normalized_root)))
        required = list(requirements or [])
        optional = list(optional_requirements or [])
        edges = [
            RequirementEdge(project_id, item.id, item.relation)
            for item in [*required, *optional]
        ]
        all_requirements = [*required, *optional]
        graph = RequirementGraph.create(
            normalized_root,
            all_requirements,
            list(kwargs.get("unknowns", []) or []),
        )
        return cls(
            generated_at=utc_now(),
            id=project_id,
            identity=identity or normalized_root.name,
            root=normalized_root,
            requirements=required,
            optional_requirements=optional,
            requirement_edges=edges,
            requirement_graph=graph,
            **kwargs,
        )

    @property
    def primary_python_requirement(self) -> Requirement | None:
        candidates = [
            item
            for item in self.requirements
            if item.capability == "python.runtime" and item.relation == "requires"
        ]
        if not candidates:
            return None
        effective = [item for item in candidates if item.is_effective]
        if effective:
            return effective[0]
        priorities = {
            ("pyproject.toml", "project.requires-python"): 0,
            ("uv.lock", "requires-python"): 1,
            ("setup.cfg", "options.python_requires"): 2,
            ("setup.py", "setup.python_requires"): 3,
        }
        return min(candidates, key=lambda item: priorities.get((item.source, item.field), 2))


@dataclass
class Provider:
    id: str
    capability: str
    path: str
    executable_identity: str
    version: str | None
    kind: ProviderKind
    discovery_method: str
    healthy: bool | None
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)
    exists: bool = True
    health_status: ProviderHealth = ProviderHealth.UNKNOWN
    health_reason: str | None = None
    architecture: str | None = None
    scope: ProviderScope = ProviderScope.UNKNOWN


@dataclass
class ProviderEdge:
    source_id: str
    target_id: str
    relation: str = "provides"


@dataclass
class ProviderGraph:
    capability_ids: list[str]
    providers: list[Provider]
    edges: list[ProviderEdge]

    @classmethod
    def create(cls, providers: list[Provider]) -> ProviderGraph:
        capabilities = sorted({item.capability for item in providers})
        return cls(
            capability_ids=capabilities,
            providers=list(providers),
            edges=[ProviderEdge(item.id, item.capability) for item in providers],
        )


@dataclass
class ProviderRoles:
    capability: str
    resolved_provider_id: str | None
    compatible_provider_ids: list[str] = field(default_factory=list)
    preferred_provider_id: str | None = None
    pinned_constraints: list[str] = field(default_factory=list)
    pinned_provider_ids: list[str] = field(default_factory=list)


@dataclass
class ExecutionContext:
    id: str
    shell: str
    working_directory: str
    path_fingerprint: str
    process_environment_fingerprint: str
    account_fingerprint: str | None = None
    command: str = "python"
    virtual_environment: bool = False
    conda_environment: bool = False
    uv_indicators: list[str] = field(default_factory=list)

    @classmethod
    def capture(
        cls,
        working_directory: str | Path,
        *,
        environment: dict[str, str] | None = None,
        shell: str | None = None,
        command: str = "python",
    ) -> ExecutionContext:
        env = dict(os.environ if environment is None else environment)
        directory = str(Path(working_directory).expanduser().resolve())
        path_value = env.get("PATH", "")
        path_fingerprint = hashlib.sha256(path_value.encode("utf-8")).hexdigest()
        relevant = {
            key: env.get(key, "")
            for key in (
                "PATH",
                "PATHEXT",
                "VIRTUAL_ENV",
                "CONDA_PREFIX",
                "CONDA_DEFAULT_ENV",
                "UV_PROJECT_ENVIRONMENT",
            )
        }
        environment_fingerprint = hashlib.sha256(
            json.dumps(relevant, sort_keys=True).encode("utf-8")
        ).hexdigest()
        account_identity = "\\".join(
            item
            for item in (env.get("USERDOMAIN", ""), env.get("USERNAME", ""))
            if item
        )
        account_fingerprint = (
            hashlib.sha256(account_identity.encode("utf-8")).hexdigest()
            if account_identity
            else None
        )
        virtual_environment = bool(env.get("VIRTUAL_ENV"))
        conda_environment = bool(env.get("CONDA_PREFIX") or env.get("CONDA_DEFAULT_ENV"))
        uv_indicators = [
            key for key in ("UV_PROJECT_ENVIRONMENT",) if env.get(key)
        ]
        context_id = stable_id(
            "execution-context",
            shell or ("powershell" if os.name == "nt" else "process"),
            directory,
            path_fingerprint,
            environment_fingerprint,
            account_fingerprint,
            command,
        )
        return cls(
            id=context_id,
            shell=shell or ("powershell" if os.name == "nt" else "process"),
            working_directory=directory,
            path_fingerprint=path_fingerprint,
            process_environment_fingerprint=environment_fingerprint,
            account_fingerprint=account_fingerprint,
            command=command,
            virtual_environment=virtual_environment,
            conda_environment=conda_environment,
            uv_indicators=uv_indicators,
        )


@dataclass
class ExecutionResolution:
    id: str
    command: str
    context_id: str
    context: ExecutionContext
    resolved_path: str | None = None
    resolved_provider_id: str | None = None
    candidate_provider_ids: list[str] = field(default_factory=list)
    method: str = "unresolved"
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        command: str,
        context: ExecutionContext,
        resolved_path: str | None = None,
        resolved_provider_id: str | None = None,
        candidate_provider_ids: list[str] | None = None,
        method: str = "unresolved",
        confidence: float = 0.0,
        evidence: list[Evidence] | None = None,
    ) -> ExecutionResolution:
        return cls(
            id=stable_id(
                "resolution", context.id, command, resolved_path, resolved_provider_id
            ),
            command=command,
            context_id=context.id,
            context=context,
            resolved_path=resolved_path,
            resolved_provider_id=resolved_provider_id,
            candidate_provider_ids=list(candidate_provider_ids or []),
            method=method,
            confidence=confidence,
            evidence=list(evidence or []),
        )


@dataclass
class RequirementEvaluation:
    requirement_id: str
    relevance: Relevance
    satisfaction: Satisfaction
    resolved_provider_id: str | None
    compatible_provider_ids: list[str]
    unverified_provider_ids: list[str]
    preferred_provider_id: str | None
    reason: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class Conflict:
    id: str
    participant_ids: list[str]
    evidence_refs: list[str]
    consequence: str
    confidence: float
    blocks: bool = False


@dataclass
class Finding:
    id: str
    message: str
    evidence_refs: list[str] = field(default_factory=list)
    matters: bool = True


@dataclass
class SeverityDecision:
    severity: Severity
    reason: str
    current_context_satisfaction: Satisfaction = Satisfaction.UNKNOWN
    recoverability: Recoverability = Recoverability.UNKNOWN
    blocker_ids: list[str] = field(default_factory=list)
    warning_ids: list[str] = field(default_factory=list)
    satisfied_count: int = 0
    warning_count: int = 0
    blocker_count: int = 0


@dataclass
class Policy:
    host_mutation: str = "forbidden"
    prefer_existing_providers: bool = True
    prefer_project_local: bool = True
    global_path_changes: str = "forbidden"
    global_runtime_upgrade: str = "forbidden"
    uninstall_alternative_providers: str = "forbidden"
    windows_security_changes: str = "forbidden"
    prefer_reversible_recommendations: bool = True


@dataclass
class ResolutionStep:
    id: str
    action: str
    reason: str
    provider_id: str | None = None
    automatic: bool = False
    reversible: bool = True


@dataclass
class ResolutionPlan:
    goal: str
    steps: list[ResolutionStep]
    policy_constraints: list[str]
    automatic_execution: bool = False


@dataclass
class ExplanationNode:
    id: str
    type: str
    label: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class ExplanationEdge:
    source_id: str
    target_id: str
    relation: str


@dataclass
class ExplanationGraph:
    nodes: list[ExplanationNode] = field(default_factory=list)
    edges: list[ExplanationEdge] = field(default_factory=list)


@dataclass
class ProjectPreflight:
    generated_at: str
    provider_inventory_generated_at: str | None
    project: ProjectDNA
    providers: list[Provider]
    context: ExecutionContext
    resolution: ExecutionResolution
    provider_roles: ProviderRoles
    evaluations: list[RequirementEvaluation]
    conflicts: list[Conflict]
    findings: list[Finding]
    severity: SeverityDecision
    policy: Policy
    plan: ResolutionPlan
    explanation: ExplanationGraph

    @property
    def evaluation(self) -> RequirementEvaluation:
        primary = self.project.primary_python_requirement
        if primary:
            for item in self.evaluations:
                if item.requirement_id == primary.id:
                    return item
        if not self.evaluations:
            raise LookupError("preflight contains no requirement evaluations")
        return self.evaluations[0]


# Domain-language aliases document the one canonical model; they are not
# parallel serialization types.
ProviderRecord = Provider
ProviderSelection = ProviderRoles
Decision = SeverityDecision
ProjectReadinessResult = ProjectPreflight
