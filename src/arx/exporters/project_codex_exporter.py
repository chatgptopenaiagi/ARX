from __future__ import annotations

from arx.core.evidence import redact
from arx.core.models import Evidence, serialize
from arx.project.models import (
    ProjectPreflight,
    Provider,
    Satisfaction,
    evidence_id,
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
    return result


def project_codex_report(report: ProjectPreflight, version: str) -> dict[str, object]:
    """Create redacted semantic compression without mixing observations and advice."""
    provider_by_id = {item.id: item for item in report.providers}
    primary = report.project.primary_python_requirement
    primary_evaluation = None
    if primary:
        primary_evaluation = next(
            (item for item in report.evaluations if item.requirement_id == primary.id), None
        )
    resolved = provider_by_id.get(report.resolution.resolved_provider_id or "")
    compatible = (
        [provider_by_id[item] for item in primary_evaluation.compatible_provider_ids]
        if primary_evaluation
        else []
    )
    preferred = (
        provider_by_id.get(primary_evaluation.preferred_provider_id or "")
        if primary_evaluation
        else None
    )
    conflicts = {item.id: item for item in report.conflicts}
    findings = {item.id: item for item in report.findings}

    def finding(identifier: str) -> dict[str, object]:
        if identifier in conflicts:
            item = conflicts[identifier]
            return {
                "id": item.id,
                "message": item.consequence,
                "evidence_refs": item.evidence_refs,
                "confidence": item.confidence,
            }
        item = findings.get(identifier)
        return {
            "id": identifier,
            "message": item.message if item else identifier,
            "evidence_refs": item.evidence_refs if item else [],
        }

    unknowns = list(report.project.unknowns)
    unknowns.extend(
        item.reason
        for item in report.evaluations
        if item.satisfaction in {Satisfaction.UNKNOWN, Satisfaction.AMBIGUOUS}
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
            "python_resolution": {
                "command": report.resolution.command,
                "context_id": report.context.id,
                "method": report.resolution.method,
                "provider_id": report.resolution.resolved_provider_id,
            },
            "provider_count": len(report.providers),
        },
        "decisions": {
            "relevance": primary_evaluation.relevance.value.upper() if primary_evaluation else "UNKNOWN_RELEVANCE",
            "satisfaction": primary_evaluation.satisfaction.value.upper() if primary_evaluation else "UNKNOWN",
            "satisfaction_reason": primary_evaluation.reason if primary_evaluation else "No Python runtime requirement was evaluated.",
            "severity": report.severity.severity.value.upper(),
            "severity_reason": report.severity.reason,
        },
        "selected_providers": {
            "resolved": _provider(resolved),
            "compatible": [_provider(item) for item in compatible],
            "preferred": _provider(preferred),
        },
        "blockers": [finding(item) for item in report.severity.blocker_ids],
        "warnings": [finding(item) for item in report.severity.warning_ids],
        "recommendations": [serialize(item) for item in report.plan.steps],
        "constraints": list(report.plan.policy_constraints),
        "unknowns": list(dict.fromkeys(unknowns)),
        "evidence_references": _evidence(report),
    }
    return redact(contract, private_roots=[report.project.root])
