"""
Base protocol abstraction for SSO implementations
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class SSOProtocol(ABC):
    """Abstract base class for SSO protocol implementations"""

    @abstractmethod
    async def initiate_authentication(
        self,
        organization_id: str,
        return_url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Initiate authentication flow for the protocol
        
        Returns:
            Dict containing auth_url, protocol-specific params, and request metadata
        """

    @abstractmethod
    async def handle_callback(
        self,
        callback_data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle callback from identity provider
        
        Returns:
            Dict containing user data, session info, and tokens
        """

    @abstractmethod
    async def validate_configuration(
        self,
        config: Dict[str, Any]
    ) -> bool:
        """
        Validate protocol-specific configuration
        
        Returns:
            True if configuration is valid
        """

    @abstractmethod
    def get_protocol_name(self) -> str:
        """Return the protocol name (e.g., 'saml2', 'oidc')"""

    @abstractmethod
    def get_required_config_fields(self) -> list[str]:
        """Return list of required configuration fields for this protocol"""


class SSOConfiguration:
    """Value object for SSO configuration data"""
    
    def __init__(
        self,
        organization_id: str,
        protocol: str,
        provider_name: str,
        config: Dict[str, Any],
        attribute_mapping: Optional[Dict[str, str]] = None,
        jit_provisioning: bool = True,
        default_role: str = "member"
    ):
        self.organization_id = organization_id
        self.protocol = protocol
        self.provider_name = provider_name
        self.config = config
        self.attribute_mapping = attribute_mapping or {}
        self.jit_provisioning = jit_provisioning
        self.default_role = default_role
        self.created_at = datetime.utcnow()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        return self.config.get(key, default)
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration values"""
        self.config.update(updates)


class SSOSession:
    """Value object for SSO session data"""
    
    def __init__(
        self,
        user_id: str,
        session_id: str,
        protocol: str,
        provider_name: str,
        attributes: Dict[str, Any],
        expires_at: datetime,
        session_index: Optional[str] = None,
        name_id: Optional[str] = None
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.protocol = protocol
        self.provider_name = provider_name
        self.attributes = attributes
        self.expires_at = expires_at
        self.session_index = session_index
        self.name_id = name_id
        self.created_at = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.utcnow() > self.expires_at
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get session attribute with optional default"""
        return self.attributes.get(key, default)


class UserProvisioningData:
    """Value object for user provisioning data"""
    
    def __init__(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        display_name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.display_name = display_name
        self.attributes = attributes or {}
    
    def get_full_name(self) -> str:
        """Get full name from first and last name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.email