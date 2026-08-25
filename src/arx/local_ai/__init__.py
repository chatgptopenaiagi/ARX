"""Optional localhost-only AI bridge kept outside deterministic ARX layers."""

from .bridge import LocalAIProvider, parse_local_chat_response
from .discovery import (
    DiscoveryResult,
    LocalAIDiscovery,
    LocalModel,
    parse_models_response,
)
from .health import provider_availability
from .launcher import LocalAILauncher, LocalAILaunchError
from .manager import (
    ApprovalRequired,
    LocalAIApprovalStore,
    LocalAIConfigurationError,
    LocalAIManager,
    LocalAIProfileStore,
)
from .models import (
    AssistanceProfile,
    BackendKind,
    BackendProfile,
    LocalAIFailure,
    LocalAIRuntime,
    LocalAIState,
    LocalEndpoint,
)
from .session import CapabilityExpired, SessionCapability

__all__ = [
    "ApprovalRequired",
    "AssistanceProfile",
    "BackendKind",
    "BackendProfile",
    "CapabilityExpired",
    "DiscoveryResult",
    "LocalAIApprovalStore",
    "LocalAIConfigurationError",
    "LocalAIDiscovery",
    "LocalAIFailure",
    "LocalAILaunchError",
    "LocalAILauncher",
    "LocalAIManager",
    "LocalAIProfileStore",
    "LocalAIProvider",
    "LocalAIRuntime",
    "LocalAIState",
    "LocalEndpoint",
    "LocalModel",
    "SessionCapability",
    "parse_local_chat_response",
    "parse_models_response",
    "provider_availability",
]
