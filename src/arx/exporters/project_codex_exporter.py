from __future__ import annotations

from arx.core.evidence import redact
from arx.core.models import Evidence, serialize
from arx.project.models import (
    ProjectPreflight,
    Provider,
    Requirement,
    RequirementEvidence,
    Satisfaction,
    evidence_id,
    stable_id,
)
from arx.project.invariants import (
    NO_COMPATIBLE_PROVIDER,
    SemanticInvariantError,
    validate_readiness_result,
)


def _provider(provider: Provider | None) -> dict[str, object] | None:
    if provider is None:
        return None
    return {
        "id": provider.id,
        "path": provider.path,
        "version": provider.version,
        "kind": provider.kind.value,
        "healthy": provider.healthy,
        "health_status": provider.health_status.value,
        "health_reason": provider.health_reason,
        "architecture": provider.architecture,
        "scope": provider.scope.value,
        "exists": provider.exists,
        "confidence": provider.confidence,
        "discovery_method": provider.discovery_method,
    }


def _evidence(report: ProjectPreflight) -> dict[str, dict[str, object]]:
    items: list[Evidence] = list(report.project.evidence)
    for provider in report.providers:
        items.extend(provider.evidence)
    items.extend(report.resolution.evidence)
    result: dict[str, dict[str, object]] = {}
    for item in items:
        identifier = evidence_id(item)
        result[identifier] = {
            "classification": item.kind.value,
            "source": item.source,
            "value": item.value,
            "method": item.method,
            "confidence": item.confidence,
            "note": item.note,
        }
        if isinstance(item, RequirementEvidence):
            result[identifier].update(
                {
                    "capability": item.capability,
                    "evidence_type": item.evidence_type.value,
                    "source_kind": item.source_kind,
                    "source_path": item.source_path,
                    "source_key": item.source_key,
                    "raw": item.raw,
                    "provenance": item.provenance,
                }
            )
    return result


def _requirement(requirement: Requirement) -> dict[str, object]:
    return {
        "id": requirement.id,
        "capability": requirement.capability,
        "constraint": requirement.constraint,
        "effective_specifier": requirement.effective_specifier,
        "is_effective": requirement.is_effective,
        "source": requirement.source,
        "field": requirement.field,
        "relevance": requirement.relevance.value,
        "relation": requirement.relation,
        "evidence_purpose": requirement.evidence_purpose,
        "interpretation_state": requirement.interpretation_state.value,
        "conflict_ids": list(requirement.conflict_ids),
        "unknowns": list(requirement.unknowns),
        "evidence": [
            {
                "evidence_ref": evidence_id(item),
                "evidence_type": item.evidence_type.value,
                "source_kind": item.source_kind,
                "source_path": item.source_path,
                "source_key": item.source_key,
                "value": item.value,
                "confidence": item.confidence,
                "provenance": item.provenance,
            }
            for item in requirement.evidence
        ],
    }


def validate_project_codex_contract(contract: dict[str, object]) -> None:
    """Validate cross-field semantic invariants JSON Schema cannot express."""
    for name in ("blockers", "warnings", "unknowns"):
        if not isinstance(contract.get(name), list):
            raise SemanticInvariantError(f"AI Contract {name} must always be an array.")

    selected = contract.get("selected_providers")
    decisions = contract.get("decisions")
    if not isinstance(selected, dict) or not isinstance(decisions, dict):
        raise SemanticInvariantError("AI Contract provider roles and decisions are required.")
    compatible = selected.get("compatible")
    preferred = selected.get("preferred")
    if not isinstance(compatible, list):
        raise SemanticInvariantError("AI Contract compatible providers must be an array.")
    compatible_ids = {
        item.get("id") for item in compatible if isinstance(item, dict)
    }
    if preferred is not None:
        if not isinstance(preferred, dict) or preferred.get("id") not in compatible_ids:
            raise SemanticInvariantError(
                "AI Contract preferred provider must belong to the compatible set."
            )

    blocker_ids = {
        item.get("finding_id")
        for item in contract["blockers"]
        if isinstance(item, dict)
    }
    if NO_COMPATIBLE_PROVIDER in blocker_ids and (compatible or preferred is not None):
        raise SemanticInvariantError(
            "AI Contract cannot claim no compatible provider while exposing one."
        )
    if contract.get("decision") != decisions.get("severity"):
        raise SemanticInvariantError("AI Contract decision and severity disagree.")
    current = decisions.get("current_context")
    recoverability = decisions.get("recoverability")
    if not isinstance(current, dict) or not isinstance(recoverability, dict):
        raise SemanticInvariantError(
            "AI Contract must scope satisfaction and recoverability explicitly."
        )
    if decisions.get("satisfaction") != current.get("satisfaction"):
        raise SemanticInvariantError(
            "AI Contract flat and current-context satisfaction disagree."
        )
    if current.get("satisfied") is not (
        current.get("satisfaction") == "SATISFIED"
    ):
        raise SemanticInvariantError(
            "AI Contract current-context satisfaction boolean is contradictory."
        )
    if set(recoverability.get("compatible_provider_ids", [])) != compatible_ids:
        raise SemanticInvariantError(
            "AI Contract recoverability and compatible provider roles disagree."
        )
    preferred_identifier = preferred.get("id") if isinstance(preferred, dict) else None
    if recoverability.get("preferred_provider_id") != preferred_identifier:
        raise SemanticInvariantError(
            "AI Contract recoverability and preferred provider role disagree."
        )
    if (
        contract.get("decision") == "GREEN"
        and decisions.get("relevance") in {"REQUIRED", "CONDITIONALLY_REQUIRED"}
        and current.get("satisfaction") != "SATISFIED"
    ):
        raise SemanticInvariantError(
            "AI Contract cannot be GREEN with an unsatisfied required current context."
        )
    if contract.get("decision") == "GREEN" and (
        contract["blockers"] or contract["warnings"]
    ):
        raise SemanticInvariantError("AI Contract GREEN cannot contain findings.")
    if contract.get("decision") == "RED" and not contract["blockers"]:
        raise SemanticInvariantError("AI Contract RED requires an actual blocker.")
    if contract.get("decision") == "YELLOW" and (
        contract["blockers"] or not contract["warnings"]
    ):
        raise SemanticInvariantError(
            "AI Contract YELLOW requires warnings and cannot contain blockers."
        )
    if recoverability.get("status") == "RECOVERABLE" and (
        not compatible or contract["blockers"]
    ):
        raise SemanticInvariantError(
            "Recoverable requires an existing compatible provider and no blocker."
        )


def project_codex_report(report: ProjectPreflight, version: str) -> dict[str, object]:
    """Create redacted semantic compression without mixing observations and advice."""
    validate_readiness_result(report)
    provider_by_id = {item.id: item for item in report.providers}
    primary = report.project.primary_python_requirement
    primary_evaluation = None
    if primary:
        primary_evaluation = next(
            (item for item in report.evaluations if item.requirement_id == primary.id), None
        )
    resolved = provider_by_id.get(report.resolution.resolved_provider_id or "")
    compatible = [
        provider_by_id[item]
        for item in report.provider_roles.compatible_provider_ids
        if item in provider_by_id
    ]
    preferred = provider_by_id.get(report.provider_roles.preferred_provider_id or "")
    pinned = [
        provider_by_id[item]
        for item in report.provider_roles.pinned_provider_ids
        if item in provider_by_id
    ]
    conflicts = {item.id: item for item in report.conflicts}
    findings = {item.id: item for item in report.findings}

    def finding(identifier: str, severity: str) -> dict[str, object]:
        category = (
            "python.provider"
            if identifier.startswith("ARX-PYTHON-")
            else "project.requirement"
            if identifier.startswith("ARX-PROJECT-")
            else "project.resolution"
        )
        if identifier in conflicts:
            item = conflicts[identifier]
            return {
                "id": item.id,
                "finding_id": item.id,
                "severity": severity,
                "category": category,
                "message": item.consequence,
                "evidence_refs": item.evidence_refs,
                "confidence": item.confidence,
            }
        item = findings.get(identifier)
        return {
            "id": identifier,
            "finding_id": identifier,
            "severity": severity,
            "category": category,
            "message": item.message if item else identifier,
            "evidence_refs": item.evidence_refs if item else [],
        }

    unknowns = list(report.project.unknowns)
    unknowns.extend(
        item.reason
        for item in report.evaluations
        if item.satisfaction in {Satisfaction.UNKNOWN, Satisfaction.AMBIGUOUS}
    )
    project_evidence_fingerprint = stable_id(
        "project-evidence",
        report.project.id,
        *sorted(item.id for item in [*report.project.requirements, *report.project.optional_requirements]),
        *sorted(evidence_id(item) for item in report.project.evidence),
    )
    provider_inventory_fingerprint = stable_id(
        "provider-inventory",
        *sorted(
            f"{item.id}:{item.exists}:{item.health_status.value}"
            for item in report.providers
        ),
    )
    contract = {
        "schema_version": "0.2",
        "producer": {"name": "ARX", "version": version},
        "generated_at": report.generated_at,
        "decision": report.severity.severity.value.upper(),
        "facts": {
            "project": {
                "id": report.project.id,
                "identity": report.project.identity,
                "root": str(report.project.root),
                "languages": report.project.languages,
                "ecosystems": report.project.ecosystems,
                "manifests": [item.path for item in report.project.manifests],
            },
            "project_python_constraint": primary.constraint if primary else None,
            "requirements": [
                _requirement(item)
                for item in [
                    *report.project.requirements,
                    *report.project.optional_requirements,
                ]
            ],
            "requirement_graph": serialize(report.project.requirement_graph),
            "evaluated_requirement": (
                {
                    "id": primary.id,
                    "capability": primary.capability,
                    "constraint": primary.constraint,
                    "source": primary.source,
                    "field": primary.field,
                    "evidence_purpose": primary.evidence_purpose,
                    "evidence_refs": [evidence_id(item) for item in primary.evidence],
                }
                if primary
                else None
            ),
            "python_resolution": {
                "command": report.resolution.command,
                "context_id": report.context.id,
                "method": report.resolution.method,
                "resolved_path": report.resolution.resolved_path,
                "provider_id": report.resolution.resolved_provider_id,
            },
            "freshness": {
                "report_generated_at": report.generated_at,
                "project_observed_at": report.project.generated_at,
                "project_evidence_fingerprint": project_evidence_fingerprint,
                "provider_inventory_fingerprint": provider_inventory_fingerprint,
                "provider_inventory_observed_at": report.provider_inventory_generated_at,
                "execution_context_id": report.context.id,
                "path_fingerprint": report.context.path_fingerprint,
                "process_environment_fingerprint": report.context.process_environment_fingerprint,
                "account_fingerprint": report.context.account_fingerprint,
            },
            "provider_count": len(report.providers),
        },
        "decisions": {
            "scope": "python_interpreter_and_toolchain_requirements",
            "relevance": primary_evaluation.relevance.value.upper() if primary_evaluation else "UNKNOWN_RELEVANCE",
            "satisfaction": report.severity.current_context_satisfaction.value.upper(),
            "satisfaction_reason": primary_evaluation.reason if primary_evaluation else "No Python runtime requirement was evaluated.",
            "current_context": {
                "requirement_id": primary.id if primary else None,
                "satisfaction": report.severity.current_context_satisfaction.value.upper(),
                "satisfied": (
                    report.severity.current_context_satisfaction
                    is Satisfaction.SATISFIED
                ),
                "reason": primary_evaluation.reason if primary_evaluation else "No Python runtime requirement was evaluated.",
            },
            "recoverability": {
                "status": report.severity.recoverability.value.upper(),
                "compatible_provider_ids": list(report.provider_roles.compatible_provider_ids),
                "preferred_provider_id": report.provider_roles.preferred_provider_id,
            },
            "severity": report.severity.severity.value.upper(),
            "severity_reason": report.severity.reason,
        },
        "selected_providers": {
            "resolved": _provider(resolved),
            "compatible": [_provider(item) for item in compatible],
            "preferred": _provider(preferred),
            "pinned": [_provider(item) for item in pinned],
            "pinned_constraints": list(report.provider_roles.pinned_constraints),
        },
        "blockers": [finding(item, "BLOCKER") for item in report.severity.blocker_ids],
        "warnings": [finding(item, "WARNING") for item in report.severity.warning_ids],
        "recommendations": [serialize(item) for item in report.plan.steps],
        "constraints": list(report.plan.policy_constraints),
        "unknowns": list(dict.fromkeys(unknowns)),
        "evidence_references": _evidence(report),
    }
    redacted = redact(contract, private_roots=[report.project.root])
    validate_project_codex_contract(redacted)
    return redacted
