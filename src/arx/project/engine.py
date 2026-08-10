from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Mapping

from arx.core.models import Evidence, EvidenceKind, utc_now

from .models import (
    Conflict,
    ExecutionContext,
    ExecutionResolution,
    ExplanationEdge,
    ExplanationGraph,
    ExplanationNode,
    Finding,
    Policy,
    ProjectDNA,
    ProjectPreflight,
    Provider,
    Relevance,
    Requirement,
    RequirementEvaluation,
    ResolutionPlan,
    ResolutionStep,
    Satisfaction,
    Severity,
    SeverityDecision,
    evidence_id,
    stable_id,
)
from .resolver import providers_from_machine, resolve_python
from .scanner import inspect_project
from .versions import exact_version_from_constraint, python_version_satisfies


DEFAULT_POLICY_CONSTRAINTS = [
    "do not mutate the host automatically",
    "do not modify global PATH",
    "do not upgrade global runtimes",
    "do not uninstall alternative providers",
    "do not change Windows security",
]


def _provider_map(providers: list[Provider]) -> dict[str, Provider]:
    return {item.id: item for item in providers}


def _project_local(provider: Provider, project: ProjectDNA) -> bool:
    try:
        provider_path = Path(provider.path).resolve(strict=False)
        return provider_path.is_relative_to(project.root)
    except (OSError, ValueError):
        return False


def _preferred_provider(
    compatible: list[Provider],
    resolved: Provider | None,
    project: ProjectDNA,
    policy: Policy,
) -> Provider | None:
    if not compatible:
        return None

    def rank(provider: Provider) -> tuple[int, int, str]:
        local = policy.prefer_project_local and _project_local(provider, project)
        current = resolved is not None and provider.id == resolved.id
        return (0 if local else 1, 0 if current else 1, os.path.normcase(provider.path))

    return min(compatible, key=rank)


def evaluate_requirement(
    requirement: Requirement,
    project: ProjectDNA,
    providers: list[Provider],
    resolution: ExecutionResolution,
    policy: Policy,
) -> RequirementEvaluation:
    provider_by_id = _provider_map(providers)
    resolved = provider_by_id.get(resolution.resolved_provider_id or "")
    relevant_providers = [item for item in providers if item.capability == requirement.capability]
    compatible: list[Provider] = []
    unknown_compatibility = False
    for item in relevant_providers:
        if item.healthy is not True:
            continue
        result = python_version_satisfies(item.version, requirement.constraint)
        if result is True:
            compatible.append(item)
        elif result is None:
            unknown_compatibility = True

    preferred = _preferred_provider(compatible, resolved, project, policy)
    refs = [evidence_id(item) for item in requirement.evidence]
    refs.extend(evidence_id(item) for item in resolution.evidence)

    if requirement.relevance is Relevance.NOT_REQUIRED:
        satisfaction = Satisfaction.NOT_APPLICABLE
        reason = "The capability is established as not required by this project."
    elif requirement.capability not in {"python.runtime", "python.optional-runtime"}:
        satisfaction = Satisfaction.UNKNOWN
        reason = "The Python package provider inventory is outside the initial runtime slice."
    elif requirement.constraint is None:
        satisfaction = Satisfaction.UNKNOWN
        reason = "The project requirement could not be determined from authoritative evidence."
    elif resolved is None or resolved.capability != requirement.capability:
        if requirement.relevance is Relevance.OPTIONAL and not compatible:
            satisfaction = Satisfaction.OPTIONAL_UNAVAILABLE
            reason = "The optional capability has no available compatible provider."
        elif compatible:
            satisfaction = Satisfaction.UNSATISFIED
            reason = "The command is unresolved, but an existing compatible provider is available."
        elif unknown_compatibility:
            satisfaction = Satisfaction.UNKNOWN
            reason = "Resolution is unavailable and provider compatibility cannot be verified."
        else:
            satisfaction = Satisfaction.UNSATISFIED
            reason = "The required command does not resolve to an available provider."
    elif resolved.healthy is not True:
        satisfaction = Satisfaction.CONFLICT
        reason = "The resolved provider exists as evidence but is not a healthy interpreter."
    else:
        result = python_version_satisfies(resolved.version, requirement.constraint)
        if result is True:
            satisfaction = Satisfaction.SATISFIED
            reason = "The resolved healthy provider satisfies the project requirement."
        elif result is False:
            satisfaction = Satisfaction.UNSATISFIED
            reason = "The resolved provider does not satisfy the project requirement."
        else:
            satisfaction = Satisfaction.UNKNOWN
            reason = "The provider version or project constraint is not safely comparable."

    return RequirementEvaluation(
        requirement_id=requirement.id,
        relevance=requirement.relevance,
        satisfaction=satisfaction,
        resolved_provider_id=resolved.id if resolved else None,
        compatible_provider_ids=[item.id for item in compatible],
        preferred_provider_id=preferred.id if preferred else None,
        reason=reason,
        evidence_refs=list(dict.fromkeys(refs)),
    )


def _source_conflicts(project: ProjectDNA) -> list[Conflict]:
    primary = project.primary_python_requirement
    if not primary or not primary.constraint:
        return []
    conflicts: list[Conflict] = []
    for selected in (
        item
        for item in project.requirements
        if item.capability == "python.runtime" and item.relation == "selects"
    ):
        version = exact_version_from_constraint(selected.constraint)
        result = python_version_satisfies(version, primary.constraint) if version else None
        if result is False:
            conflicts.append(
                Conflict(
                    id="ARX-PROJECT-REQUIREMENT-CONFLICT",
                    participant_ids=[primary.id, selected.id],
                    evidence_refs=[
                        *[evidence_id(item) for item in primary.evidence],
                        *[evidence_id(item) for item in selected.evidence],
                    ],
                    consequence=(
                        f"{selected.source} selects Python {version}, which contradicts "
                        f"{primary.source} constraint {primary.constraint}."
                    ),
                    confidence=min(primary.confidence, selected.confidence),
                    blocks=True,
                )
            )
    return conflicts


def _resolution_conflicts(
    project: ProjectDNA,
    providers: list[Provider],
    resolution: ExecutionResolution,
    evaluations: list[RequirementEvaluation],
) -> list[Conflict]:
    primary = project.primary_python_requirement
    if not primary:
        return []
    evaluation = next((item for item in evaluations if item.requirement_id == primary.id), None)
    if not evaluation or evaluation.satisfaction not in {Satisfaction.UNSATISFIED, Satisfaction.CONFLICT}:
        return []
    resolved = _provider_map(providers).get(resolution.resolved_provider_id or "")
    if not resolved:
        return []
    return [
        Conflict(
            id="ARX-PYTHON-DEFAULT-MISMATCH",
            participant_ids=[primary.id, resolved.id, resolution.id],
            evidence_refs=list(
                dict.fromkeys(
                    [
                        *[evidence_id(item) for item in primary.evidence],
                        *[evidence_id(item) for item in resolved.evidence],
                        *[evidence_id(item) for item in resolution.evidence],
                    ]
                )
            ),
            consequence=(
                f"The current python command resolves to {resolved.version or 'an unknown version'}, "
                f"which does not provide a healthy match for {primary.constraint or 'the project requirement'}."
            ),
            confidence=min(primary.confidence, resolution.confidence),
            blocks=not evaluation.compatible_provider_ids,
        )
    ]


def _findings(
    project: ProjectDNA,
    providers: list[Provider],
    resolution: ExecutionResolution,
    evaluations: list[RequirementEvaluation],
    conflicts: list[Conflict],
) -> list[Finding]:
    findings: list[Finding] = []
    versions: dict[str, list[Provider]] = defaultdict(list)
    for provider in providers:
        if provider.version:
            versions[provider.version].append(provider)
        if provider.kind.value == "windowsapps_alias":
            findings.append(
                Finding(
                    "ARX-PYTHON-WINDOWSAPPS-ALIAS",
                    "A WindowsApps Python execution alias was observed and is not treated as a healthy interpreter unless independently verified.",
                    [evidence_id(item) for item in provider.evidence],
                    provider.id == resolution.resolved_provider_id,
                )
            )
    if any(len(items) > 1 for items in versions.values()):
        findings.append(
            Finding(
                "ARX-PYTHON-MULTIPLE-PROVIDERS",
                "Multiple distinct Python providers report an identical version; path-based identities are preserved.",
                matters=False,
            )
        )
    if not evaluations:
        findings.append(
            Finding(
                "ARX-RESOLUTION-UNKNOWN",
                "No supported project requirement was available for semantic evaluation.",
                [evidence_id(item) for item in project.evidence],
            )
        )
    for evaluation in evaluations:
        if (
            evaluation.relevance in {Relevance.REQUIRED, Relevance.CONDITIONALLY_REQUIRED}
            and evaluation.satisfaction in {Satisfaction.UNSATISFIED, Satisfaction.CONFLICT}
            and not evaluation.compatible_provider_ids
        ):
            findings.append(
                Finding(
                    "ARX-PYTHON-NO-COMPATIBLE-PROVIDER",
                    "No healthy existing provider satisfies a required Python capability.",
                    evaluation.evidence_refs,
                )
            )
        elif evaluation.satisfaction in {Satisfaction.UNKNOWN, Satisfaction.AMBIGUOUS, Satisfaction.PARTIAL}:
            findings.append(
                Finding(
                    "ARX-RESOLUTION-UNKNOWN",
                    evaluation.reason,
                    evaluation.evidence_refs,
                )
            )
    conflict_ids = {item.id for item in conflicts}
    unique: dict[str, Finding] = {item.id: item for item in findings if item.id not in conflict_ids}
    return list(unique.values())


def severity_for(
    evaluations: list[RequirementEvaluation],
    conflicts: list[Conflict],
    findings: list[Finding],
) -> SeverityDecision:
    blocker_ids = [item.id for item in conflicts if item.blocks]
    warning_ids = [item.id for item in conflicts if not item.blocks]
    finding_by_id = {item.id: item for item in findings}
    for evaluation in evaluations:
        required = evaluation.relevance in {Relevance.REQUIRED, Relevance.CONDITIONALLY_REQUIRED}
        if required and evaluation.satisfaction in {Satisfaction.UNSATISFIED, Satisfaction.CONFLICT}:
            if not evaluation.compatible_provider_ids:
                blocker_ids.append("ARX-PYTHON-NO-COMPATIBLE-PROVIDER")
            else:
                warning_ids.append("ARX-PYTHON-DEFAULT-MISMATCH")
        elif evaluation.satisfaction in {
            Satisfaction.UNKNOWN,
            Satisfaction.AMBIGUOUS,
            Satisfaction.PARTIAL,
        }:
            warning_ids.append("ARX-RESOLUTION-UNKNOWN")
    warning_ids.extend(
        item.id
        for item in findings
        if item.matters and item.id != "ARX-PYTHON-NO-COMPATIBLE-PROVIDER"
    )
    blocker_ids = list(dict.fromkeys(blocker_ids))
    warning_ids = [item for item in dict.fromkeys(warning_ids) if item not in blocker_ids]
    severity = Severity.RED if blocker_ids else Severity.YELLOW if warning_ids else Severity.GREEN
    if severity is Severity.RED:
        reason = "One or more required project capabilities are blocked."
    elif severity is Severity.YELLOW:
        reason = "The project can progress after resolving warnings or uncertainty."
    else:
        reason = "All evaluated required project capabilities are satisfied."
    satisfied_count = sum(item.satisfaction is Satisfaction.SATISFIED for item in evaluations)
    return SeverityDecision(
        severity=severity,
        reason=reason,
        blocker_ids=blocker_ids,
        warning_ids=warning_ids,
        satisfied_count=satisfied_count,
        warning_count=len(warning_ids),
        blocker_count=len(blocker_ids),
    )


def plan_resolution(
    project: ProjectDNA,
    providers: list[Provider],
    evaluations: list[RequirementEvaluation],
    conflicts: list[Conflict],
    severity: SeverityDecision,
    policy: Policy,
) -> ResolutionPlan:
    steps: list[ResolutionStep] = []
    provider_by_id = _provider_map(providers)
    source_conflict = any(item.id == "ARX-PROJECT-REQUIREMENT-CONFLICT" for item in conflicts)
    if source_conflict:
        steps.append(
            ResolutionStep(
                "ARX-PLAN-ALIGN-PYTHON-CONSTRAINTS",
                "Review and align .python-version with the authoritative project Python constraint.",
                "Contradictory project requirements cannot produce a trustworthy selection.",
            )
        )
    primary = project.primary_python_requirement
    primary_evaluation = (
        next((item for item in evaluations if primary and item.requirement_id == primary.id), None)
        if primary
        else None
    )
    if source_conflict:
        pass
    elif primary_evaluation and primary_evaluation.satisfaction is Satisfaction.SATISFIED and not steps:
        steps.append(
            ResolutionStep(
                "ARX-PLAN-NO-ACTION",
                "Keep using the resolved project-compatible Python provider.",
                "The current resolution already satisfies the project requirement.",
            )
        )
    elif primary_evaluation and primary_evaluation.preferred_provider_id:
        preferred = provider_by_id[primary_evaluation.preferred_provider_id]
        steps.append(
            ResolutionStep(
                "ARX-PLAN-USE-EXISTING-PYTHON",
                f"Use the existing Python {preferred.version or 'provider'} at {preferred.path} for this project.",
                "An existing healthy provider satisfies the requirement, so another installation is unnecessary.",
                provider_id=preferred.id,
            )
        )
    elif primary_evaluation and primary_evaluation.satisfaction in {
        Satisfaction.UNSATISFIED,
        Satisfaction.CONFLICT,
    }:
        steps.append(
            ResolutionStep(
                "ARX-PLAN-PROVISION-PROJECT-PYTHON",
                f"Provision a project-local Python satisfying {primary.constraint if primary else 'the project requirement'} through a human-controlled workflow.",
                "No healthy existing provider is compatible; ARX will not mutate the host automatically.",
            )
        )
    elif primary_evaluation and primary_evaluation.satisfaction is Satisfaction.UNKNOWN:
        steps.append(
            ResolutionStep(
                "ARX-PLAN-VERIFY-PYTHON-REQUIREMENT",
                "Correct or clarify the project Python requirement, then run preflight again.",
                "ARX does not invent an unreadable, missing, or unsupported constraint.",
            )
        )
    if severity.severity is not Severity.GREEN and steps:
        steps.append(
            ResolutionStep(
                "ARX-PLAN-REEVALUATE-CONTEXT",
                "Re-run ARX project preflight in the intended execution context.",
                "Resolution is context-scoped and must be verified after a selection change.",
            )
        )
    return ResolutionPlan(
        goal="GREEN project readiness",
        steps=steps,
        policy_constraints=list(DEFAULT_POLICY_CONSTRAINTS),
        automatic_execution=False,
    )


def build_explanation(
    project: ProjectDNA,
    providers: list[Provider],
    resolution: ExecutionResolution,
    evaluations: list[RequirementEvaluation],
    conflicts: list[Conflict],
    severity: SeverityDecision,
    plan: ResolutionPlan,
) -> ExplanationGraph:
    nodes: dict[str, ExplanationNode] = {}
    edges: list[ExplanationEdge] = []

    all_evidence: list[Evidence] = list(project.evidence)
    for provider in providers:
        all_evidence.extend(provider.evidence)
    all_evidence.extend(resolution.evidence)
    for item in all_evidence:
        identifier = evidence_id(item)
        nodes.setdefault(
            identifier,
            ExplanationNode(identifier, "evidence", f"{item.source}: {item.value}"),
        )
    for requirement in [*project.requirements, *project.optional_requirements]:
        refs = [evidence_id(item) for item in requirement.evidence]
        nodes[requirement.id] = ExplanationNode(
            requirement.id,
            "requirement",
            f"{requirement.capability} {requirement.constraint or 'unknown'}",
            refs,
        )
        edges.extend(ExplanationEdge(ref, requirement.id, "supports") for ref in refs)
    for provider in providers:
        refs = [evidence_id(item) for item in provider.evidence]
        nodes[provider.id] = ExplanationNode(
            provider.id,
            "provider",
            f"{provider.kind.value} {provider.version or 'unknown'} at {provider.path}",
            refs,
        )
        edges.extend(ExplanationEdge(ref, provider.id, "supports") for ref in refs)
    resolution_refs = [evidence_id(item) for item in resolution.evidence]
    nodes[resolution.id] = ExplanationNode(
        resolution.id,
        "resolution",
        f"{resolution.command} -> {resolution.resolved_provider_id or 'unknown'}",
        resolution_refs,
    )
    edges.extend(ExplanationEdge(ref, resolution.id, "supports") for ref in resolution_refs)
    if resolution.resolved_provider_id:
        edges.append(ExplanationEdge(resolution.resolved_provider_id, resolution.id, "resolves_as"))
    for evaluation in evaluations:
        identifier = stable_id("satisfaction", evaluation.requirement_id, evaluation.satisfaction.value)
        nodes[identifier] = ExplanationNode(
            identifier,
            "satisfaction",
            f"{evaluation.satisfaction.value}: {evaluation.reason}",
            evaluation.evidence_refs,
        )
        edges.append(ExplanationEdge(evaluation.requirement_id, identifier, "evaluates"))
        edges.append(ExplanationEdge(resolution.id, identifier, "evaluates"))
    for conflict in conflicts:
        nodes[conflict.id] = ExplanationNode(
            conflict.id, "conflict", conflict.consequence, conflict.evidence_refs
        )
        edges.extend(ExplanationEdge(participant, conflict.id, "contradicts") for participant in conflict.participant_ids)
    severity_id = stable_id("severity", severity.severity.value, *severity.blocker_ids, *severity.warning_ids)
    nodes[severity_id] = ExplanationNode(
        severity_id, "severity", f"{severity.severity.value}: {severity.reason}"
    )
    for node in list(nodes.values()):
        if node.type in {"satisfaction", "conflict"}:
            edges.append(ExplanationEdge(node.id, severity_id, "causes"))
    for step in plan.steps:
        nodes[step.id] = ExplanationNode(step.id, "recommendation", step.action)
        edges.append(ExplanationEdge(severity_id, step.id, "recommends"))
    return ExplanationGraph(list(nodes.values()), edges)


def preflight(
    project: ProjectDNA,
    providers: list[Provider],
    resolution: ExecutionResolution,
    policy: Policy | None = None,
) -> ProjectPreflight:
    active_policy = policy or Policy()
    requirements = [*project.requirements, *project.optional_requirements]
    evaluations = [
        evaluate_requirement(item, project, providers, resolution, active_policy)
        for item in requirements
    ]
    conflicts = [
        *_source_conflicts(project),
        *_resolution_conflicts(project, providers, resolution, evaluations),
    ]
    findings = _findings(project, providers, resolution, evaluations, conflicts)
    severity = severity_for(evaluations, conflicts, findings)
    plan = plan_resolution(project, providers, evaluations, conflicts, severity, active_policy)
    explanation = build_explanation(
        project, providers, resolution, evaluations, conflicts, severity, plan
    )
    return ProjectPreflight(
        generated_at=utc_now(),
        project=project,
        providers=list(providers),
        context=resolution.context,
        resolution=resolution,
        evaluations=evaluations,
        conflicts=conflicts,
        findings=findings,
        severity=severity,
        policy=active_policy,
        plan=plan,
        explanation=explanation,
    )


def project_preflight(
    target: str | Path,
    *,
    machine: Mapping[str, object] | None = None,
    context: ExecutionContext | None = None,
    environment: Mapping[str, str] | None = None,
    providers: list[Provider] | None = None,
    resolution: ExecutionResolution | None = None,
    policy: Policy | None = None,
) -> ProjectPreflight:
    project = inspect_project(target)
    if providers is None:
        if machine is None:
            from arx.machine import scan_machine

            machine = scan_machine(True)
        providers = providers_from_machine(machine)
    active_context = context or ExecutionContext.capture(
        project.root,
        environment=dict(environment) if environment is not None else None,
    )
    active_resolution = resolution or resolve_python(
        providers,
        active_context,
        environment=environment,
    )
    return preflight(project, providers, active_resolution, policy)
