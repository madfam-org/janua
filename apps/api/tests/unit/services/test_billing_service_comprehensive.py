import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive test coverage for Billing Service
Critical for revenue protection and enterprise billing operations

Target: 23% → 80%+ coverage
Covers: Conekta (Mexico), Fungies.io (International), pricing, subscriptions
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import httpx
import json

from app.services.billing_service import BillingService, PRICING_TIERS
from app.models.user import Tenant


class TestBillingServiceInitialization:
    """Test billing service initialization and configuration"""

    def test_billing_service_init(self):
        """Test billing service initializes correctly"""
        service = BillingService()
        assert service is not None
        assert hasattr(service, 'determine_payment_provider')

    def test_pricing_tiers_configuration(self):
        """Test pricing tiers are properly configured"""
        assert "community" in PRICING_TIERS
        assert "pro" in PRICING_TIERS
        assert "scale" in PRICING_TIERS
        assert "enterprise" in PRICING_TIERS

        # Validate community tier
        community = PRICING_TIERS["community"]
        assert community["price_mxn"] == 0
        assert community["price_usd"] == 0
        assert community["mau_limit"] == 2000
        assert "basic_auth" in community["features"]

        # Validate pro tier
        pro = PRICING_TIERS["pro"]
        assert pro["price_mxn"] == 1380
        assert pro["price_usd"] == 69
        assert pro["mau_limit"] == 10000


class TestPaymentProviderDetermination:
    """Test payment provider selection logic"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.mark.asyncio
    async def test_determine_payment_provider_mexico(self, billing_service):
        """Test Conekta is selected for Mexico"""
        provider = await billing_service.determine_payment_provider("MX")
        assert provider == "conekta"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_international(self, billing_service):
        """Test Fungies.io is selected for international"""
        provider = await billing_service.determine_payment_provider("US")
        assert provider == "fungies"

        provider = await billing_service.determine_payment_provider("CA")
        assert provider == "fungies"

        provider = await billing_service.determine_payment_provider("DE")
        assert provider == "fungies"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_unknown_country(self, billing_service):
        """Test fallback for unknown countries"""
        provider = await billing_service.determine_payment_provider("XX")
        assert provider == "fungies"  # Should default to international


class TestConektaIntegration:
    """Test Conekta payment processing (Mexico)"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch('httpx.AsyncClient') as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_conekta_customer_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta customer creation"""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cust_conekta_123",
            "email": "test@example.com",
            "name": "Test User"
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_customer(
            email="test@example.com",
            name="Test User",
            phone="+52123456789"
        )

        assert result["id"] == "cust_conekta_123"
        assert result["email"] == "test@example.com"
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conekta_customer_failure(self, billing_service, mock_httpx_client):
        """Test Conekta customer creation failure"""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "Invalid email format"
        }
        mock_response.raise_for_status = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Invalid email format", request=Mock(), response=mock_response
        ))
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await billing_service.create_conekta_customer(
                email="invalid-email",
                name="Test User"
            )

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta subscription creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "sub_conekta_123",
            "status": "active",
            "customer": "cust_conekta_123",
            "plan": "pro_plan_mx"
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_subscription(
            customer_id="cust_conekta_123",
            plan_id="pro_plan_mx"
        )

        assert result["id"] == "sub_conekta_123"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta subscription cancellation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "sub_conekta_123",
            "status": "canceled"
        }
        mock_httpx_client.delete.return_value = mock_response

        result = await billing_service.cancel_conekta_subscription("sub_conekta_123")
        assert result is True


class TestFungiesIntegration:
    """Test Fungies.io payment processing (International)"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch('httpx.AsyncClient') as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_fungies_customer_success(self, billing_service, mock_httpx_client):
        """Test successful Fungies.io customer creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "fung_cust_123",
            "email": "test@example.com",
            "status": "active"
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_fungies_customer(
            email="test@example.com",
            name="Test User",
            country="US"
        )

        assert result["id"] == "fung_cust_123"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Fungies.io subscription creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "fung_sub_123",
            "status": "active",
            "customer_id": "fung_cust_123",
            "plan": "pro_plan_usd"
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_fungies_subscription(
            customer_id="fung_cust_123",
            tier="pro"
        )

        assert result["id"] == "fung_sub_123"
        assert result["status"] == "active"


class TestPricingAndValidation:
    """Test pricing logic and plan validation"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    def test_get_pricing_for_country_mexico(self, billing_service):
        """Test pricing retrieval for Mexico (MXN)"""
        pricing = billing_service.get_pricing_for_country("MX")

        assert "tiers" in pricing
        assert "community" in pricing["tiers"]
        assert "pro" in pricing["tiers"]
        assert "scale" in pricing["tiers"]
        assert "enterprise" in pricing["tiers"]
        assert pricing["tiers"]["community"]["price"] == 0
        assert pricing["tiers"]["pro"]["price"] == 1380
        assert pricing["tiers"]["scale"]["price"] == 5980
        assert pricing["currency"] == "MXN"
        assert pricing["provider"] == "conekta"

    def test_get_pricing_for_country_international(self, billing_service):
        """Test pricing retrieval for international (USD)"""
        pricing = billing_service.get_pricing_for_country("US")

        assert "tiers" in pricing
        assert "community" in pricing["tiers"]
        assert "pro" in pricing["tiers"]
        assert "scale" in pricing["tiers"]
        assert "enterprise" in pricing["tiers"]
        assert pricing["tiers"]["community"]["price"] == 0
        assert pricing["tiers"]["pro"]["price"] == 69
        assert pricing["tiers"]["scale"]["price"] == 299
        assert pricing["currency"] == "USD"
        assert pricing["provider"] == "fungies"

    def test_validate_plan_valid_tiers(self, billing_service):
        """Test plan validation for valid tiers"""
        assert billing_service.validate_plan("community") is True
        assert billing_service.validate_plan("pro") is True
        assert billing_service.validate_plan("scale") is True
        assert billing_service.validate_plan("enterprise") is True

    def test_validate_plan_invalid_tier(self, billing_service):
        """Test plan validation for invalid tier"""
        assert billing_service.validate_plan("invalid") is False
        assert billing_service.validate_plan("premium") is False
        assert billing_service.validate_plan("") is False
        assert billing_service.validate_plan(None) is False


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client_error(self):
        with patch('httpx.AsyncClient') as mock:
            client_instance = AsyncMock()
            client_instance.post.side_effect = httpx.RequestError("Network error")
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_network_error_handling(self, billing_service, mock_httpx_client_error):
        """Test handling of network errors"""
        with pytest.raises(Exception) as exc_info:
            await billing_service.create_conekta_customer(
                email="test@example.com",
                name="Test User"
            )

        assert "Network error" in str(exc_info.value)