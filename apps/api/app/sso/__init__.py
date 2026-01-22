"""
SSO module for protocol-specific authentication
"""

from .application.services.sso_orchestrator import SSOOrchestrator
from .domain.protocols.base import SSOProtocol, SSOConfiguration, SSOSession
from .domain.protocols.saml import SAMLProtocol
from .domain.protocols.oidc import OIDCProtocol
from .interfaces.rest.sso_controller import sso_router

__all__ = [
    "SSOOrchestrator",
    "SSOProtocol",
    "SSOConfiguration",
    "SSOSession",
    "SAMLProtocol",
    "OIDCProtocol",
    "sso_router",
]
