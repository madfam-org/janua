import pytest
pytestmark = pytest.mark.asyncio


"""
Unit tests for BillingService - simplified to match actual implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx

from app.services.billing_service import BillingService, PRICING_TIERS


class TestBillingServiceInitialization:
    """Test billing service initialization."""

    def test_billing_service_init(self):
        """Test billing service initialization."""
        service = BillingService()
        assert hasattr(service, 'conekta_api_key')
        assert hasattr(service, 'conekta_api_url')
        assert hasattr(service, 'fungies_api_key')
        assert hasattr(service, 'fungies_api_url')
        assert service.conekta_api_url == "https://api.conekta.io"
        assert service.fungies_api_url == "https://api.fungies.io/v1"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_mexico(self):
        """Test provider determination for Mexico."""
        service = BillingService()
        provider = await service.determine_payment_provider("MX")
        assert provider == "conekta"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_international(self):
        """Test provider determination for international countries."""
        service = BillingService()

        # Test various countries
        for country in ["US", "CA", "GB", "DE", "FR"]:
            provider = await service.determine_payment_provider(country)
            assert provider == "fungies"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_case_insensitive(self):
        """Test provider determination is case insensitive."""
        service = BillingService()

        provider_upper = await service.determine_payment_provider("MX")
        provider_lower = await service.determine_payment_provider("mx")

        assert provider_upper == provider_lower == "conekta"


class TestConektaIntegration:
    """Test Conekta payment provider integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BillingService()

    @pytest.mark.asyncio
    async def test_create_conekta_customer_success(self):
        """Test creating Conekta customer successfully."""
        mock_response = {
            "id": "cus_test123",
            "email": "test@example.com",
            "name": "Test User",
            "phone": "+52555123456"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status = Mock()

            result = await self.service.create_conekta_customer(
                email="test@example.com",
                name="Test User",
                phone="+52555123456",
                metadata={"user_id": "123"}
            )

            assert result["id"] == "cus_test123"
            assert result["email"] == "test@example.com"
            assert result["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_create_conekta_customer_http_error(self):
        """Test creating Conekta customer with HTTP error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status.side_effect = httpx.HTTPError("API Error")

            with pytest.raises(httpx.HTTPError):
                await self.service.create_conekta_customer(
                    email="test@example.com",
                    name="Test User"
                )

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_success(self):
        """Test creating Conekta subscription successfully."""
        mock_subscription = {
            "id": "sub_test123",
            "customer_id": "cus_test123",
            "plan_id": "pro_monthly",
            "status": "active"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_subscription)
            mock_response.raise_for_status = Mock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await self.service.create_conekta_subscription(
                customer_id="cus_test123",
                plan_id="pro_monthly"
            )

            assert result["id"] == "sub_test123"
            assert result["customer_id"] == "cus_test123"
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_with_card_token(self):
        """Test creating Conekta subscription with card token."""
        mock_payment_method = {
            "id": "pm_test123",
            "type": "card"
        }

        mock_subscription = {
            "id": "sub_test123",
            "customer_id": "cus_test123",
            "plan_id": "pro_monthly",
            "status": "active"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # First call for payment method, second for subscription
            mock_post.side_effect = [
                Mock(json=Mock(return_value=mock_payment_method), raise_for_status=Mock()),
                Mock(json=Mock(return_value=mock_subscription), raise_for_status=Mock())
            ]

            result = await self.service.create_conekta_subscription(
                customer_id="cus_test123",
                plan_id="pro_monthly",
                card_token="tok_test123"
            )

            assert result["id"] == "sub_test123"
            assert mock_post.call_count == 2  # Payment method + subscription

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_success(self):
        """Test canceling Conekta subscription successfully."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock()
            mock_client.return_value.__aenter__.return_value.delete.return_value.raise_for_status = Mock()

            result = await self.service.cancel_conekta_subscription("sub_test123")

            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_error(self):
        """Test canceling Conekta subscription with error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock()
            mock_client.return_value.__aenter__.return_value.delete.return_value.raise_for_status.side_effect = httpx.HTTPError("Subscription not found")

            result = await self.service.cancel_conekta_subscription("sub_invalid")

            assert result is False


class TestFungiesIntegration:
    """Test Fungies.io payment provider integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BillingService()

    @pytest.mark.asyncio
    async def test_create_fungies_customer_success(self):
        """Test creating Fungies customer successfully."""
        mock_response = {
            "id": "fung_cus_test123",
            "email": "test@example.com",
            "name": "Test User"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status = Mock()

            result = await self.service.create_fungies_customer(
                email="test@example.com",
                name="Test User",
                country="US"
            )

            assert result["id"] == "fung_cus_test123"
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_success(self):
        """Test creating Fungies subscription successfully."""
        mock_subscription = {
            "id": "fung_sub_test123",
            "customer_id": "fung_cus_test123",
            "plan": "pro",
            "status": "active"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_subscription)
            mock_response.raise_for_status = Mock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await self.service.create_fungies_subscription(
                customer_id="fung_cus_test123",
                tier="pro",
                payment_method_id="stripe_pm_123"
            )

            assert result["id"] == "fung_sub_test123"
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_update_fungies_subscription_success(self):
        """Test updating Fungies subscription successfully."""
        mock_response = {
            "id": "fung_sub_test123",
            "plan": "scale",
            "status": "active"
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.put = AsyncMock()
            mock_client.return_value.__aenter__.return_value.put.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.put.return_value.raise_for_status = Mock()

            result = await self.service.update_fungies_subscription(
                subscription_id="fung_sub_test123",
                tier="scale"
            )

            assert result["plan"] == "scale"

    @pytest.mark.asyncio
    async def test_cancel_fungies_subscription_success(self):
        """Test canceling Fungies subscription successfully."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock()
            mock_client.return_value.__aenter__.return_value.delete.return_value.raise_for_status = Mock()

            result = await self.service.cancel_fungies_subscription("fung_sub_test123")

            assert result is True


class TestUnifiedBillingInterface:
    """Test unified billing interface methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BillingService()

    @pytest.mark.asyncio
    async def test_create_subscription_mexico(self):
        """Test creating subscription for Mexico (Conekta)."""
        with patch.object(self.service, 'determine_payment_provider') as mock_provider, \
             patch.object(self.service, 'create_conekta_customer') as mock_customer, \
             patch.object(self.service, 'create_conekta_subscription') as mock_subscription:

            mock_provider.return_value = "conekta"
            mock_customer.return_value = {"id": "cus_test123"}
            mock_subscription.return_value = {"id": "sub_test123", "status": "active"}

            result = await self.service.create_subscription(
                email="test@example.com",
                name="Test User",
                country="MX",
                tier="pro"
            )

            assert result["id"] == "sub_test123"
            mock_customer.assert_called_once()
            mock_subscription.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_international(self):
        """Test creating subscription for international (Fungies)."""
        with patch.object(self.service, 'determine_payment_provider') as mock_provider, \
             patch.object(self.service, 'create_fungies_customer') as mock_customer, \
             patch.object(self.service, 'create_fungies_subscription') as mock_subscription:

            mock_provider.return_value = "fungies"
            mock_customer.return_value = {"id": "fung_cus_test123"}
            mock_subscription.return_value = {"id": "fung_sub_test123", "status": "active"}

            result = await self.service.create_subscription(
                email="test@example.com",
                name="Test User",
                country="US",
                tier="pro"
            )

            assert result["id"] == "fung_sub_test123"
            mock_customer.assert_called_once()
            mock_subscription.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pricing_for_country_mexico(self):
        """Test getting pricing for Mexico."""
        pricing = await self.service.get_pricing_for_country("MX")

        assert "community" in pricing
        assert "pro" in pricing
        assert pricing["pro"]["price"] == 1380  # MXN price
        assert pricing["pro"]["currency"] == "MXN"

    @pytest.mark.asyncio
    async def test_get_pricing_for_country_international(self):
        """Test getting pricing for international countries."""
        pricing = await self.service.get_pricing_for_country("US")

        assert "community" in pricing
        assert "pro" in pricing
        assert pricing["pro"]["price"] == 69  # USD price
        assert pricing["pro"]["currency"] == "USD"

    def test_validate_plan_valid(self):
        """Test validating valid plan."""
        result = self.service.validate_plan("pro")
        assert result is True

        result = self.service.validate_plan("community")
        assert result is True

        result = self.service.validate_plan("enterprise")
        assert result is True

    def test_validate_plan_invalid(self):
        """Test validating invalid plan."""
        result = self.service.validate_plan("invalid_plan")
        assert result is False

        result = self.service.validate_plan("")
        assert result is False

        result = self.service.validate_plan(None)
        assert result is False

    def test_get_plan_features(self):
        """Test getting plan features."""
        features = self.service.get_plan_features("pro")
        expected_features = ["everything_community", "advanced_rbac", "custom_domains", "webhooks", "sso"]

        assert features == expected_features

    def test_get_plan_features_invalid(self):
        """Test getting features for invalid plan."""
        features = self.service.get_plan_features("invalid_plan")
        assert features == []

    def test_get_plan_mau_limit(self):
        """Test getting MAU limit for plan."""
        limit = self.service.get_plan_mau_limit("pro")
        assert limit == 10000

        limit = self.service.get_plan_mau_limit("community")
        assert limit == 2000

        limit = self.service.get_plan_mau_limit("enterprise")
        assert limit is None  # Unlimited

    def test_calculate_overage_cost(self):
        """Test calculating overage cost."""
        # Community plan overage
        cost = self.service.calculate_overage_cost("community", 3000)
        assert cost > 0  # Should charge for going over 2000 MAU

        # Pro plan within limits
        cost = self.service.calculate_overage_cost("pro", 8000)
        assert cost == 0  # Within 10000 MAU limit

        # Pro plan overage
        cost = self.service.calculate_overage_cost("pro", 12000)
        assert cost > 0  # Should charge for going over 10000 MAU


class TestPricingConfiguration:
    """Test pricing configuration and constants."""

    def test_pricing_tiers_structure(self):
        """Test pricing tiers have correct structure."""
        for plan_name, plan_data in PRICING_TIERS.items():
            assert "price_mxn" in plan_data
            assert "price_usd" in plan_data
            assert "mau_limit" in plan_data
            assert "features" in plan_data
            assert isinstance(plan_data["features"], list)

    def test_community_plan_free(self):
        """Test community plan is free."""
        community = PRICING_TIERS["community"]
        assert community["price_mxn"] == 0
        assert community["price_usd"] == 0
        assert community["mau_limit"] == 2000

    def test_enterprise_plan_custom(self):
        """Test enterprise plan has custom pricing."""
        enterprise = PRICING_TIERS["enterprise"]
        assert enterprise["price_mxn"] is None
        assert enterprise["price_usd"] is None
        assert enterprise["mau_limit"] is None


class TestErrorHandling:
    """Test error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BillingService()

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self):
        """Test handling network timeout."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(httpx.TimeoutException):
                await self.service.create_conekta_customer(
                    email="test@example.com",
                    name="Test User"
                )

    @pytest.mark.asyncio
    async def test_handle_invalid_api_key(self):
        """Test handling invalid API key."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status.side_effect = httpx.HTTPError("Unauthorized")

            with pytest.raises(httpx.HTTPError):
                await self.service.create_conekta_customer(
                    email="test@example.com",
                    name="Test User"
                )

    @pytest.mark.asyncio
    async def test_handle_missing_customer(self):
        """Test handling missing customer error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status.side_effect = httpx.HTTPError("Customer not found")

            with pytest.raises(httpx.HTTPError):
                await self.service.create_conekta_subscription(
                    customer_id="invalid_customer",
                    plan_id="pro_monthly"
                )