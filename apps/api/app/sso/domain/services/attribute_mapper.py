"""
Attribute mapping service for SSO protocols
"""

from typing import Dict, Any, Optional
from ..protocols.base import UserProvisioningData


class AttributeMapper:
    """Service for mapping SSO attributes to user data"""

    def __init__(self):
        # Default attribute mappings for common providers
        self.default_saml_mappings = {
            "email": [
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "email",
                "mail",
            ],
            "first_name": [
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
                "firstName",
                "givenName",
            ],
            "last_name": [
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
                "lastName",
                "surname",
            ],
            "display_name": [
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
                "displayName",
                "name",
            ],
        }

        self.default_oidc_mappings = {
            "email": ["email"],
            "first_name": ["given_name", "first_name"],
            "last_name": ["family_name", "last_name"],
            "display_name": ["name", "preferred_username"],
        }

    def map_saml_attributes(
        self, attributes: Dict[str, Any], custom_mapping: Optional[Dict[str, str]] = None
    ) -> UserProvisioningData:
        """Map SAML attributes to user provisioning data"""

        mapping = {**self.default_saml_mappings, **(custom_mapping or {})}
        mapped_data = {}

        for field, possible_attrs in mapping.items():
            value = self._find_attribute_value(attributes, possible_attrs)
            if value:
                mapped_data[field] = value

        # Ensure email is present
        if not mapped_data.get("email"):
            raise ValueError("Email attribute is required but not found in SAML response")

        return UserProvisioningData(
            email=mapped_data["email"],
            first_name=mapped_data.get("first_name"),
            last_name=mapped_data.get("last_name"),
            display_name=mapped_data.get("display_name"),
            attributes=attributes,
        )

    def map_oidc_claims(
        self, claims: Dict[str, Any], custom_mapping: Optional[Dict[str, str]] = None
    ) -> UserProvisioningData:
        """Map OIDC claims to user provisioning data"""

        mapping = {**self.default_oidc_mappings, **(custom_mapping or {})}
        mapped_data = {}

        for field, possible_claims in mapping.items():
            value = self._find_claim_value(claims, possible_claims)
            if value:
                mapped_data[field] = value

        # Ensure email is present
        if not mapped_data.get("email"):
            raise ValueError("Email claim is required but not found in OIDC response")

        return UserProvisioningData(
            email=mapped_data["email"],
            first_name=mapped_data.get("first_name"),
            last_name=mapped_data.get("last_name"),
            display_name=mapped_data.get("display_name"),
            attributes=claims,
        )

    def _find_attribute_value(
        self, attributes: Dict[str, Any], possible_keys: list
    ) -> Optional[str]:
        """Find attribute value from possible keys"""

        for key in possible_keys:
            value = attributes.get(key)
            if value:
                # SAML attributes are often arrays
                if isinstance(value, list) and value:
                    return str(value[0])
                return str(value)

        return None

    def _find_claim_value(self, claims: Dict[str, Any], possible_keys: list) -> Optional[str]:
        """Find claim value from possible keys"""

        for key in possible_keys:
            value = claims.get(key)
            if value:
                return str(value)

        return None

    def get_provider_specific_mapping(self, provider: str) -> Dict[str, list]:
        """Get provider-specific attribute mappings"""

        provider_mappings = {
            "okta": {
                "email": ["email"],
                "first_name": ["firstName"],
                "last_name": ["lastName"],
                "display_name": ["displayName"],
            },
            "azure_ad": {
                "email": ["http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"],
                "first_name": ["http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"],
                "last_name": ["http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"],
                "display_name": [
                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/displayname"
                ],
            },
            "google_workspace": {
                "email": ["email"],
                "first_name": ["given_name"],
                "last_name": ["family_name"],
                "display_name": ["name"],
            },
        }

        return provider_mappings.get(provider, {})
