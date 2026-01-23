"""
Comprehensive Attribute Mapper Test Suite
Tests SAML and OIDC attribute mapping to user provisioning data.
"""

import pytest

pytestmark = pytest.mark.asyncio


class TestSAMLAttributeMapping:
    """Test SAML attribute mapping"""

    @pytest.fixture
    def attribute_mapper(self):
        """Create attribute mapper instance"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    def test_map_saml_email_standard_claim(self, attribute_mapper):
        """Should map standard email claim"""
        attributes = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": [
                "user@example.com"
            ]
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "user@example.com"

    def test_map_saml_email_simple_attribute(self, attribute_mapper):
        """Should map simple email attribute"""
        attributes = {"email": ["user@example.com"]}

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "user@example.com"

    def test_map_saml_email_mail_attribute(self, attribute_mapper):
        """Should map mail attribute"""
        attributes = {"mail": ["user@example.com"]}

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "user@example.com"

    def test_map_saml_first_name_standard_claim(self, attribute_mapper):
        """Should map standard first name claim"""
        attributes = {
            "email": ["user@example.com"],
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname": ["John"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.first_name == "John"

    def test_map_saml_first_name_simple_attribute(self, attribute_mapper):
        """Should map simple firstName attribute"""
        attributes = {
            "email": ["user@example.com"],
            "firstName": ["Jane"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.first_name == "Jane"

    def test_map_saml_last_name_standard_claim(self, attribute_mapper):
        """Should map standard last name claim"""
        attributes = {
            "email": ["user@example.com"],
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname": ["Doe"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.last_name == "Doe"

    def test_map_saml_display_name(self, attribute_mapper):
        """Should map display name"""
        attributes = {
            "email": ["user@example.com"],
            "displayName": ["John Doe"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.display_name == "John Doe"

    def test_map_saml_all_attributes(self, attribute_mapper):
        """Should map all attributes correctly"""
        attributes = {
            "email": ["john@example.com"],
            "firstName": ["John"],
            "lastName": ["Doe"],
            "displayName": ["John Doe"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "john@example.com"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.display_name == "John Doe"
        assert result.attributes == attributes

    def test_map_saml_missing_email_raises_error(self, attribute_mapper):
        """Should raise error when email is missing"""
        attributes = {
            "firstName": ["John"],
            "lastName": ["Doe"],
        }

        with pytest.raises(ValueError) as exc_info:
            attribute_mapper.map_saml_attributes(attributes)

        assert "Email attribute is required" in str(exc_info.value)

    def test_map_saml_with_custom_mapping(self, attribute_mapper):
        """Should use custom attribute mapping"""
        attributes = {
            "custom_email": ["custom@example.com"],
            "custom_name": ["Custom User"],
        }

        custom_mapping = {
            "email": ["custom_email"],
            "display_name": ["custom_name"],
        }

        result = attribute_mapper.map_saml_attributes(attributes, custom_mapping)

        assert result.email == "custom@example.com"
        assert result.display_name == "Custom User"

    def test_map_saml_array_attribute_uses_first_value(self, attribute_mapper):
        """Should use first value from array attributes"""
        attributes = {
            "email": ["first@example.com", "second@example.com"],
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "first@example.com"

    def test_map_saml_non_array_attribute(self, attribute_mapper):
        """Should handle non-array attribute values"""
        attributes = {
            "email": "single@example.com",  # Not an array
        }

        result = attribute_mapper.map_saml_attributes(attributes)

        assert result.email == "single@example.com"


class TestOIDCClaimMapping:
    """Test OIDC claim mapping"""

    @pytest.fixture
    def attribute_mapper(self):
        """Create attribute mapper instance"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    def test_map_oidc_email_claim(self, attribute_mapper):
        """Should map email claim"""
        claims = {"email": "user@example.com"}

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.email == "user@example.com"

    def test_map_oidc_given_name(self, attribute_mapper):
        """Should map given_name claim"""
        claims = {
            "email": "user@example.com",
            "given_name": "John",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.first_name == "John"

    def test_map_oidc_family_name(self, attribute_mapper):
        """Should map family_name claim"""
        claims = {
            "email": "user@example.com",
            "family_name": "Doe",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.last_name == "Doe"

    def test_map_oidc_name(self, attribute_mapper):
        """Should map name claim to display_name"""
        claims = {
            "email": "user@example.com",
            "name": "John Doe",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.display_name == "John Doe"

    def test_map_oidc_preferred_username_fallback(self, attribute_mapper):
        """Should use preferred_username as fallback for display_name"""
        claims = {
            "email": "user@example.com",
            "preferred_username": "johndoe",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.display_name == "johndoe"

    def test_map_oidc_all_claims(self, attribute_mapper):
        """Should map all standard OIDC claims"""
        claims = {
            "email": "john@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "name": "John Doe",
            "sub": "user_123",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.email == "john@example.com"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.display_name == "John Doe"
        assert result.attributes == claims

    def test_map_oidc_missing_email_raises_error(self, attribute_mapper):
        """Should raise error when email is missing"""
        claims = {
            "given_name": "John",
            "family_name": "Doe",
        }

        with pytest.raises(ValueError) as exc_info:
            attribute_mapper.map_oidc_claims(claims)

        assert "Email claim is required" in str(exc_info.value)

    def test_map_oidc_with_custom_mapping(self, attribute_mapper):
        """Should use custom claim mapping"""
        claims = {
            "user_email": "custom@example.com",
            "full_name": "Custom User",
        }

        custom_mapping = {
            "email": ["user_email"],
            "display_name": ["full_name"],
        }

        result = attribute_mapper.map_oidc_claims(claims, custom_mapping)

        assert result.email == "custom@example.com"
        assert result.display_name == "Custom User"

    def test_map_oidc_first_name_fallback(self, attribute_mapper):
        """Should use first_name as fallback for given_name"""
        claims = {
            "email": "user@example.com",
            "first_name": "John",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.first_name == "John"

    def test_map_oidc_last_name_fallback(self, attribute_mapper):
        """Should use last_name as fallback for family_name"""
        claims = {
            "email": "user@example.com",
            "last_name": "Doe",
        }

        result = attribute_mapper.map_oidc_claims(claims)

        assert result.last_name == "Doe"


class TestProviderSpecificMappings:
    """Test provider-specific attribute mappings"""

    @pytest.fixture
    def attribute_mapper(self):
        """Create attribute mapper instance"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    def test_get_okta_mapping(self, attribute_mapper):
        """Should return Okta-specific mappings"""
        mapping = attribute_mapper.get_provider_specific_mapping("okta")

        assert "email" in mapping
        assert "firstName" in mapping["first_name"]
        assert "lastName" in mapping["last_name"]
        assert "displayName" in mapping["display_name"]

    def test_get_azure_ad_mapping(self, attribute_mapper):
        """Should return Azure AD-specific mappings"""
        mapping = attribute_mapper.get_provider_specific_mapping("azure_ad")

        assert "email" in mapping
        assert (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
            in mapping["first_name"]
        )
        assert (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
            in mapping["last_name"]
        )

    def test_get_google_workspace_mapping(self, attribute_mapper):
        """Should return Google Workspace-specific mappings"""
        mapping = attribute_mapper.get_provider_specific_mapping("google_workspace")

        assert "email" in mapping["email"]
        assert "given_name" in mapping["first_name"]
        assert "family_name" in mapping["last_name"]
        assert "name" in mapping["display_name"]

    def test_get_unknown_provider_returns_empty(self, attribute_mapper):
        """Should return empty mapping for unknown provider"""
        mapping = attribute_mapper.get_provider_specific_mapping("unknown_provider")

        assert mapping == {}


class TestAttributeValueFinding:
    """Test attribute value finding helpers"""

    @pytest.fixture
    def attribute_mapper(self):
        """Create attribute mapper instance"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    def test_find_attribute_value_first_key(self, attribute_mapper):
        """Should find value from first matching key"""
        attributes = {
            "key1": ["value1"],
            "key2": ["value2"],
        }

        result = attribute_mapper._find_attribute_value(attributes, ["key1", "key2"])

        assert result == "value1"

    def test_find_attribute_value_second_key(self, attribute_mapper):
        """Should find value from second key when first is missing"""
        attributes = {
            "key2": ["value2"],
        }

        result = attribute_mapper._find_attribute_value(
            attributes, ["missing_key", "key2"]
        )

        assert result == "value2"

    def test_find_attribute_value_not_found(self, attribute_mapper):
        """Should return None when no key found"""
        attributes = {"other_key": ["value"]}

        result = attribute_mapper._find_attribute_value(
            attributes, ["key1", "key2"]
        )

        assert result is None

    def test_find_attribute_value_empty_array(self, attribute_mapper):
        """Should return None for empty array"""
        attributes = {"key1": []}

        result = attribute_mapper._find_attribute_value(attributes, ["key1"])

        assert result is None

    def test_find_claim_value_first_key(self, attribute_mapper):
        """Should find claim value from first matching key"""
        claims = {
            "key1": "value1",
            "key2": "value2",
        }

        result = attribute_mapper._find_claim_value(claims, ["key1", "key2"])

        assert result == "value1"

    def test_find_claim_value_second_key(self, attribute_mapper):
        """Should find claim value from second key when first is missing"""
        claims = {
            "key2": "value2",
        }

        result = attribute_mapper._find_claim_value(claims, ["missing_key", "key2"])

        assert result == "value2"

    def test_find_claim_value_not_found(self, attribute_mapper):
        """Should return None when no key found"""
        claims = {"other_key": "value"}

        result = attribute_mapper._find_claim_value(claims, ["key1", "key2"])

        assert result is None


class TestDefaultMappings:
    """Test default attribute mappings"""

    @pytest.fixture
    def attribute_mapper(self):
        """Create attribute mapper instance"""
        from app.sso.domain.services.attribute_mapper import AttributeMapper

        return AttributeMapper()

    def test_default_saml_email_mappings(self, attribute_mapper):
        """Should have standard SAML email attribute mappings"""
        mappings = attribute_mapper.default_saml_mappings["email"]

        assert (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
            in mappings
        )
        assert "email" in mappings
        assert "mail" in mappings

    def test_default_saml_name_mappings(self, attribute_mapper):
        """Should have standard SAML name attribute mappings"""
        first_name = attribute_mapper.default_saml_mappings["first_name"]
        last_name = attribute_mapper.default_saml_mappings["last_name"]

        assert (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
            in first_name
        )
        assert (
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
            in last_name
        )

    def test_default_oidc_email_mappings(self, attribute_mapper):
        """Should have standard OIDC email claim mappings"""
        mappings = attribute_mapper.default_oidc_mappings["email"]

        assert "email" in mappings

    def test_default_oidc_name_mappings(self, attribute_mapper):
        """Should have standard OIDC name claim mappings"""
        first_name = attribute_mapper.default_oidc_mappings["first_name"]
        last_name = attribute_mapper.default_oidc_mappings["last_name"]
        display_name = attribute_mapper.default_oidc_mappings["display_name"]

        assert "given_name" in first_name
        assert "family_name" in last_name
        assert "name" in display_name
        assert "preferred_username" in display_name


class TestUserProvisioningDataHelpers:
    """Test UserProvisioningData helper methods"""

    def test_get_full_name_with_both_names(self):
        """Should combine first and last name"""
        from app.sso.domain.protocols.base import UserProvisioningData

        data = UserProvisioningData(
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            attributes={},
        )

        assert data.get_full_name() == "John Doe"

    def test_get_full_name_with_first_name_only(self):
        """Should return display_name or email when only first name provided"""
        from app.sso.domain.protocols.base import UserProvisioningData

        # Without display_name, falls back to email
        data = UserProvisioningData(
            email="user@example.com",
            first_name="John",
            attributes={},
        )
        assert data.get_full_name() == "user@example.com"

        # With display_name, uses display_name
        data_with_display = UserProvisioningData(
            email="user@example.com",
            first_name="John",
            display_name="Johnny",
            attributes={},
        )
        assert data_with_display.get_full_name() == "Johnny"

    def test_get_full_name_with_last_name_only(self):
        """Should return display_name or email when only last name provided"""
        from app.sso.domain.protocols.base import UserProvisioningData

        # Without display_name, falls back to email
        data = UserProvisioningData(
            email="user@example.com",
            last_name="Doe",
            attributes={},
        )
        assert data.get_full_name() == "user@example.com"

        # With display_name, uses display_name
        data_with_display = UserProvisioningData(
            email="user@example.com",
            last_name="Doe",
            display_name="Mr. Doe",
            attributes={},
        )
        assert data_with_display.get_full_name() == "Mr. Doe"

    def test_get_full_name_with_no_names(self):
        """Should return email when no names available"""
        from app.sso.domain.protocols.base import UserProvisioningData

        data = UserProvisioningData(
            email="user@example.com",
            attributes={},
        )

        assert data.get_full_name() == "user@example.com"
