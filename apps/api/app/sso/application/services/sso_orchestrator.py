"""
Main SSO orchestration service
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ...domain.protocols.base import SSOProtocol, SSOConfiguration, SSOSession
from ...domain.protocols.saml import SAMLProtocol
from ...domain.protocols.oidc import OIDCProtocol
from ...domain.services.attribute_mapper import AttributeMapper
from ...domain.services.user_provisioning import UserProvisioningService
from ...infrastructure.configuration.config_repository import SSOConfigurationRepository
from ...infrastructure.session.session_repository import SSOSessionRepository
from ...exceptions import ValidationError, AuthenticationError


class SSOOrchestrator:
    """
    Main orchestration service for SSO operations

    Coordinates between different protocols, user provisioning, and session management
    """

    def __init__(
        self,
        config_repository: SSOConfigurationRepository,
        session_repository: SSOSessionRepository,
        user_provisioning: UserProvisioningService,
        cache_service,
        jwt_service,
        audit_logger=None,
    ):
        self.config_repository = config_repository
        self.session_repository = session_repository
        self.user_provisioning = user_provisioning
        self.cache_service = cache_service
        self.jwt_service = jwt_service
        self.audit_logger = audit_logger

        # Initialize attribute mapper
        self.attribute_mapper = AttributeMapper()

        # Initialize protocol handlers
        self.protocols: Dict[str, SSOProtocol] = {
            "saml2": SAMLProtocol(cache_service, self.attribute_mapper),
            "oidc": OIDCProtocol(cache_service, self.attribute_mapper),
        }

    async def initiate_authentication(
        self,
        organization_id: str,
        protocol: str,
        return_url: Optional[str] = None,
        provider_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate SSO authentication flow

        Args:
            organization_id: Organization identifier
            protocol: SSO protocol (saml2, oidc)
            return_url: URL to redirect after authentication
            provider_config: Optional provider configuration (for testing)

        Returns:
            Authentication initiation data (auth URL, state, etc.)
        """

        # Validate protocol
        if protocol not in self.protocols:
            raise ValidationError(f"Unsupported SSO protocol: {protocol}")

        # Get SSO configuration
        if provider_config:
            # Use provided config (for testing)
            sso_config = SSOConfiguration(
                organization_id=organization_id,
                protocol=protocol,
                provider_name="test",
                config=provider_config,
            )
        else:
            # Get from repository
            sso_config = await self.config_repository.get_by_organization(organization_id, protocol)

            if not sso_config:
                raise ValidationError(
                    f"SSO not configured for organization {organization_id} with protocol {protocol}"
                )

        # Get protocol handler
        protocol_handler = self.protocols[protocol]

        # Initiate authentication
        auth_data = await protocol_handler.initiate_authentication(
            organization_id=organization_id, return_url=return_url, config=sso_config.config
        )

        # Log initiation
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="sso_authentication_initiated",
                organization_id=organization_id,
                details={
                    "protocol": protocol,
                    "provider": sso_config.provider_name,
                    "return_url": return_url,
                },
            )

        return auth_data

    async def handle_authentication_callback(
        self, protocol: str, callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle SSO authentication callback

        Args:
            protocol: SSO protocol (saml2, oidc)
            callback_data: Data from the callback request

        Returns:
            Authentication result with user and tokens
        """

        # Validate protocol
        if protocol not in self.protocols:
            raise ValidationError(f"Unsupported SSO protocol: {protocol}")

        # Get protocol handler
        protocol_handler = self.protocols[protocol]

        # Handle callback
        callback_result = await protocol_handler.handle_callback(callback_data)

        organization_id = callback_result["organization_id"]
        user_data = callback_result["user_data"]
        session_data = callback_result["session_data"]

        # Get SSO configuration
        sso_config = await self.config_repository.get_by_organization(organization_id, protocol)

        if not sso_config:
            raise AuthenticationError("SSO configuration not found")

        # Provision user
        user = await self.user_provisioning.provision_user(
            user_data=user_data,
            organization_id=organization_id,
            sso_config=sso_config,
            session_data=session_data,
        )

        # Validate user access
        if not await self.user_provisioning.validate_user_access(user, sso_config):
            raise AuthenticationError("User access denied by SSO configuration")

        # Create SSO session
        sso_session = SSOSession(
            user_id=user.id,
            session_id=f"sso_{user.id}_{datetime.utcnow().timestamp()}",
            protocol=protocol,
            provider_name=sso_config.provider_name,
            attributes=session_data,
            expires_at=datetime.utcnow() + timedelta(hours=8),
            session_index=session_data.get("session_index"),
            name_id=session_data.get("name_id"),
        )

        # Store session
        await self.session_repository.create(sso_session)

        # Generate JWT token
        jwt_payload = {
            "user_id": user.id,
            "organization_id": organization_id,
            "email": user.email,
            "role": user.role,
            "sso_session_id": sso_session.session_id,
        }

        tokens = self.jwt_service.create_token_pair(jwt_payload)

        # Log successful authentication
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="sso_authentication_success",
                user_id=user.id,
                organization_id=organization_id,
                details={
                    "protocol": protocol,
                    "provider": sso_config.provider_name,
                    "user_email": user.email,
                    "session_id": sso_session.session_id,
                },
            )

        return {
            "user": user,
            "tokens": tokens,
            "session": sso_session,
            "return_url": callback_result.get("return_url"),
        }

    async def initiate_logout(
        self, user_id: str, session_id: str, return_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Initiate SSO logout (Single Logout)

        Args:
            user_id: User identifier
            session_id: SSO session identifier
            return_url: URL to redirect after logout

        Returns:
            Logout initiation data if SLO is supported, None otherwise
        """

        # Get SSO session
        sso_session = await self.session_repository.get_by_session_id(session_id)

        if not sso_session or sso_session.user_id != user_id:
            raise ValidationError("Invalid SSO session")

        # Get SSO configuration
        sso_config = await self.config_repository.get_by_organization(
            sso_session.user_id, sso_session.protocol  # This should be organization_id
        )

        if not sso_config:
            # Just invalidate local session
            await self.session_repository.invalidate(session_id)
            return None

        # Check if protocol supports logout
        protocol_handler = self.protocols.get(sso_session.protocol)
        if not protocol_handler or not hasattr(protocol_handler, "initiate_logout"):
            # Just invalidate local session
            await self.session_repository.invalidate(session_id)
            return None

        # Initiate protocol-specific logout
        logout_data = await protocol_handler.initiate_logout(
            session_data=sso_session.attributes, config=sso_config.config, return_url=return_url
        )

        # Invalidate local session
        await self.session_repository.invalidate(session_id)

        # Log logout
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type="sso_logout_initiated",
                user_id=user_id,
                details={
                    "protocol": sso_session.protocol,
                    "provider": sso_config.provider_name,
                    "session_id": session_id,
                },
            )

        return logout_data

    async def get_supported_protocols(self) -> list[str]:
        """Get list of supported SSO protocols"""
        return list(self.protocols.keys())

    async def validate_protocol_configuration(self, protocol: str, config: Dict[str, Any]) -> bool:
        """Validate SSO protocol configuration"""

        if protocol not in self.protocols:
            raise ValidationError(f"Unsupported SSO protocol: {protocol}")

        protocol_handler = self.protocols[protocol]
        return await protocol_handler.validate_configuration(config)
