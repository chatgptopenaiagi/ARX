from __future__ import annotations

from .models import (
    ProjectPreflight,
    ProviderHealth,
    Recoverability,
    Relevance,
    Satisfaction,
    Severity,
)


NO_COMPATIBLE_PROVIDER = "ARX-PYTHON-NO-COMPATIBLE-PROVIDER"


class SemanticInvariantError(ValueError):
    """Raised when a readiness result collapses distinct semantic truths."""


def validate_readiness_result(report: ProjectPreflight) -> None:
    """Reject contradictory canonical results before any surface consumes them."""
    roles = report.provider_roles
    providers = {item.id: item for item in report.providers}
    compatible_ids = set(roles.compatible_provider_ids)
    preferred_id = roles.preferred_provider_id

    if roles.resolved_provider_id != report.resolution.resolved_provider_id:
        raise SemanticInvariantError(
            "Provider roles and execution resolution disagree about the resolved provider."
        )
    if preferred_id is not None and preferred_id not in compatible_ids:
        raise SemanticInvariantError(
            "A preferred provider must be a usable compatible provider."
        )
    for identifier in compatible_ids:
        provider = providers.get(identifier)
        if (
            provider is None
            or not provider.exists
            or provider.health_status is not ProviderHealth.HEALTHY
            or provider.healthy is not True
        ):
            raise SemanticInvariantError(
                "Usable compatible providers must exist and have confirmed healthy status."
            )

    no_compatible_claimed = NO_COMPATIBLE_PROVIDER in {
        *report.severity.blocker_ids,
        *(item.id for item in report.findings),
    }
    if no_compatible_claimed and (compatible_ids or preferred_id is not None):
        raise SemanticInvariantError(
            "NO-COMPATIBLE-PROVIDER is impossible when a usable compatible provider exists."
        )

    primary = report.project.primary_python_requirement
    primary_evaluation = next(
        (
            item
            for item in report.evaluations
            if primary is not None and item.requirement_id == primary.id
        ),
        None,
    )
    if primary_evaluation is not None:
        if set(primary_evaluation.compatible_provider_ids) != compatible_ids:
            raise SemanticInvariantError(
                "Canonical provider roles must reflect the effective requirement evaluation."
            )
        if (
            report.severity.current_context_satisfaction
            is not primary_evaluation.satisfaction
        ):
            raise SemanticInvariantError(
                "Decision current-context satisfaction must match the effective evaluation."
            )

    requirement_by_id = {
        item.id: item
        for item in [
            *report.project.requirements,
            *report.project.optional_requirements,
        ]
    }
    if report.severity.severity is Severity.GREEN:
        unsatisfied_required = [
            item.requirement_id
            for item in report.evaluations
            if requirement_by_id[item.requirement_id].relevance
            in {Relevance.REQUIRED, Relevance.CONDITIONALLY_REQUIRED}
            and item.satisfaction is not Satisfaction.SATISFIED
        ]
        if unsatisfied_required or report.severity.blocker_ids or report.severity.warning_ids:
            raise SemanticInvariantError(
                "GREEN requires every evaluated required capability to be satisfied without findings."
            )

    expected_recoverability = Recoverability.BLOCKED
    if not report.severity.blocker_ids:
        current = report.severity.current_context_satisfaction
        if current is Satisfaction.SATISFIED or (
            current is Satisfaction.NOT_APPLICABLE
            and report.severity.severity is Severity.GREEN
        ):
            expected_recoverability = Recoverability.READY
        elif compatible_ids:
            expected_recoverability = Recoverability.RECOVERABLE
        else:
            expected_recoverability = Recoverability.UNKNOWN
    if report.severity.recoverability is not expected_recoverability:
        raise SemanticInvariantError(
            "Decision recoverability contradicts blockers, context satisfaction, or compatible providers."
        )
