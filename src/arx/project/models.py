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
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)

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
        confidence: float = 1.0,
        evidence: list[Evidence] | None = None,
        parent_ids: list[str] | None = None,
    ) -> Requirement:
        return cls(
            id=stable_id("requirement", capability, constraint, source, field, relation),
            capability=capability,
            constraint=constraint,
            source=source,
            field=field,
            relevance=relevance,
            relation=relation,
            confidence=confidence,
            evidence=list(evidence or []),
            parent_ids=list(parent_ids or []),
        )


@dataclass
class RequirementEdge:
    source_id: str
    target_id: str
    relation: str


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
        return cls(
            generated_at=utc_now(),
            id=project_id,
            identity=identity or normalized_root.name,
            root=normalized_root,
            requirements=required,
            optional_requirements=optional,
            requirement_edges=edges,
            **kwargs,
        )

    @property
    def primary_python_requirement(self) -> Requirement | None:
        candidates = [
            item for item in self.requirements if item.capability == "python.runtime"
        ]
        if not candidates:
            return None
        priorities = {
            ("pyproject.toml", "project.requires-python"): 0,
            ("uv.lock", "requires-python"): 1,
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
class ExecutionContext:
    id: str
    shell: str
    working_directory: str
    path_fingerprint: str
    process_environment_fingerprint: str
    command: str = "python"
    virtual_environment: str | None = None
    conda_environment: str | None = None
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
        virtual_environment = env.get("VIRTUAL_ENV")
        conda_environment = env.get("CONDA_PREFIX") or env.get("CONDA_DEFAULT_ENV")
        uv_indicators = [
            key for key in ("UV_PROJECT_ENVIRONMENT",) if env.get(key)
        ]
        context_id = stable_id(
            "execution-context",
            shell or ("powershell" if os.name == "nt" else "process"),
            directory,
            path_fingerprint,
            environment_fingerprint,
            command,
        )
        return cls(
            id=context_id,
            shell=shell or ("powershell" if os.name == "nt" else "process"),
            working_directory=directory,
            path_fingerprint=path_fingerprint,
            process_environment_fingerprint=environment_fingerprint,
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
        resolved_provider_id: str | None = None,
        candidate_provider_ids: list[str] | None = None,
        method: str = "unresolved",
        confidence: float = 0.0,
        evidence: list[Evidence] | None = None,
    ) -> ExecutionResolution:
        return cls(
            id=stable_id("resolution", context.id, command, resolved_provider_id),
            command=command,
            context_id=context.id,
            context=context,
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


@dataclass
class SeverityDecision:
    severity: Severity
    reason: str
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
    project: ProjectDNA
    providers: list[Provider]
    context: ExecutionContext
    resolution: ExecutionResolution
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
