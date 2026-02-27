"""
Main SSO orchestration service
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select

from ...domain.protocols.base import SSOConfiguration, SSOProtocol, SSOSession
from ...domain.protocols.oidc import OIDCProtocol
from ...domain.protocols.saml import SAMLProtocol
from ...domain.services.attribute_mapper import AttributeMapper
from ...domain.services.user_provisioning import UserProvisioningService
from ...exceptions import AuthenticationError, ValidationError
from ...infrastructure.configuration.config_repository import SSOConfigurationRepository
from ...infrastructure.session.session_repository import SSOSessionRepository


KNOWN_PRODUCTS = {"enclii", "tezca", "yantra4d", "dhanam"}

# Legacy Janua subscription_tier -> foundry_tier mapping (backwards compat)
LEGACY_TIER_MAP = {
    "community": "community",
    "free": "community",
    "pro": "sovereign",
    "sovereign": "sovereign",
    "scale": "ecosystem",
    "enterprise": "ecosystem",
    "ecosystem": "ecosystem",
}


def map_subscription_to_foundry_tier(subscription_tier: str | None) -> str:
    """Map Janua subscription_tier to Foundry tier for JWT claims.

    Legacy mapping kept for backwards compatibility during transition:
    - community/free -> community
    - pro/sovereign -> sovereign
    - scale/enterprise/ecosystem -> ecosystem
    """
    if not subscription_tier:
        return "community"
    return LEGACY_TIER_MAP.get(subscription_tier.lower(), "community")


def resolve_product_tiers(product_tiers: dict | None, subscription_tier: str | None) -> dict:
    """Resolve per-product tier claims from organization data.

    Returns a dict of JWT claim keys to tier values. Products without a tier
    are omitted (absent claim = community/self-hosted, not billed).

    Args:
        product_tiers: JSONB dict from Organization.product_tiers
        subscription_tier: Legacy string from Organization.subscription_tier
    """
    tiers = product_tiers or {}

    # Build per-product claims
    claims = {}

    # foundry_tier: backwards-compatible Enclii claim
    enclii_tier = tiers.get("enclii")
    if enclii_tier:
        # Map new tier names to legacy foundry_tier values for Enclii compat
        foundry_map = {"essentials": "community", "pro": "sovereign", "madfam": "ecosystem"}
        claims["foundry_tier"] = foundry_map.get(enclii_tier, enclii_tier)
    else:
        # Fall back to legacy subscription_tier mapping
        claims["foundry_tier"] = map_subscription_to_foundry_tier(subscription_tier)

    # Per-product claims (None/absent = community, no claim emitted)
    for product in ("tezca", "yantra4d", "dhanam"):
        tier = tiers.get(product)
        if tier:
            claims[f"{product}_tier"] = tier

    return claims


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

        # Query organization to get per-product tier claims
        tier_claims = {"foundry_tier": "community"}  # Default if no organization
        if organization_id:
            from app.models import Organization

            result = await self.config_repository.db.execute(
                select(Organization.subscription_tier, Organization.product_tiers).where(
                    Organization.id == organization_id
                )
            )
            row = result.one_or_none()
            if row:
                tier_claims = resolve_product_tiers(row.product_tiers, row.subscription_tier)

        # Generate JWT token with per-product tier claims
        jwt_payload = {
            "user_id": user.id,
            "organization_id": organization_id,
            "email": user.email,
            "role": user.role,
            "sso_session_id": sso_session.session_id,
            **tier_claims,
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
