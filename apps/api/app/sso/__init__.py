"""SSO module for protocol-specific authentication."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "SSOOrchestrator": ".application.services.sso_orchestrator",
    "SSOProtocol": ".domain.protocols.base",
    "SSOConfiguration": ".domain.protocols.base",
    "SSOSession": ".domain.protocols.base",
    "SAMLProtocol": ".domain.protocols.saml",
    "OIDCProtocol": ".domain.protocols.oidc",
    "sso_router": ".interfaces.rest.sso_controller",
}

__all__ = [
    "SSOOrchestrator",
    "SSOProtocol",
    "SSOConfiguration",
    "SSOSession",
    "SAMLProtocol",
    "OIDCProtocol",
    "sso_router",
]


def __getattr__(name: str) -> Any:
    """Load SSO exports lazily to keep package imports side-effect light."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name], __name__)
    return getattr(module, name)
