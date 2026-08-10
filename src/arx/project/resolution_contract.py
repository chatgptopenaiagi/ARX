from __future__ import annotations

from collections.abc import Callable

from .models import Provider, ProviderRoles


def assign_provider_roles(
    *,
    capability: str,
    providers: list[Provider],
    resolved_provider_id: str | None,
    is_compatible: Callable[[Provider], bool],
    preferred_key: Callable[[Provider], tuple[object, ...]],
    pinned_constraints: list[str] | None = None,
    is_pinned: Callable[[Provider], bool] | None = None,
) -> ProviderRoles:
    """Assign factual and policy roles without conflating them.

    Compatibility and pin interpretation remain ecosystem-specific predicates;
    resolution, role separation, and deterministic preference are generic.
    """
    relevant = [item for item in providers if item.capability == capability]
    compatible = [item for item in relevant if is_compatible(item)]
    preferred = min(compatible, key=preferred_key) if compatible else None
    pinned = [item for item in relevant if is_pinned and is_pinned(item)]
    return ProviderRoles(
        capability=capability,
        resolved_provider_id=resolved_provider_id,
        compatible_provider_ids=[item.id for item in compatible],
        preferred_provider_id=preferred.id if preferred else None,
        pinned_constraints=list(pinned_constraints or []),
        pinned_provider_ids=[item.id for item in pinned],
    )
