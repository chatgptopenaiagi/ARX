"""Optional advisory bridges kept separate from deterministic ARX evidence."""

from .audit import (
    AuditError,
    MemoryTransmissionAudit,
    TransmissionAudit,
    TransmissionEvent,
    TransportState,
    default_transmission_audit,
)
from .context import (
    ANALYSIS_MODES,
    AdvisoryContext,
    build_advisory_context,
    build_advisory_prompt,
    redact_external,
)
from .credentials import (
    CredentialError,
    CredentialSource,
    CredentialState,
    CredentialStatus,
    CredentialUnreadable,
    ProviderCredentialResolver,
    WindowsDPAPICredentialStore,
    default_openai_credential_resolver,
    default_openai_credential_store,
    import_openai_credential_file,
)
from .health import ProviderHealth, ProviderHealthStatus, validate_provider_health
from .providers import (
    AdvisoryCancelled,
    AdvisoryResponse,
    AdvisoryTimeout,
    CodexCLIProvider,
    OpenAIProvider,
    ProviderAvailability,
    ProviderError,
)

__all__ = [
    "ANALYSIS_MODES",
    "AuditError",
    "AdvisoryCancelled",
    "AdvisoryContext",
    "AdvisoryResponse",
    "AdvisoryTimeout",
    "CodexCLIProvider",
    "CredentialError",
    "CredentialSource",
    "CredentialState",
    "CredentialStatus",
    "CredentialUnreadable",
    "MemoryTransmissionAudit",
    "OpenAIProvider",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ProviderCredentialResolver",
    "ProviderAvailability",
    "ProviderError",
    "build_advisory_context",
    "build_advisory_prompt",
    "default_openai_credential_resolver",
    "default_openai_credential_store",
    "default_transmission_audit",
    "import_openai_credential_file",
    "redact_external",
    "TransmissionAudit",
    "TransmissionEvent",
    "TransportState",
    "validate_provider_health",
    "WindowsDPAPICredentialStore",
]
