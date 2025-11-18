"""
Billing Service Tests - Updated for Multi-Provider Strategy

Provider Strategy:
- Mexico: Conekta (primary) → Stripe (fallback)
- International: Polar.sh (primary) → Stripe (fallback)
- Detection: Geolocation + billing address validation

Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest

from app.services.billing_service import PRICING_TIERS, BillingService

pytestmark = pytest.mark.asyncio


class TestBillingServiceInitialization:
    """Test billing service initialization"""

    def test_billing_service_init(self):
        """Test billing service initializes with all providers"""
        service = BillingService()
        assert service.conekta_api_key is not None
        assert service.polar_api_key is not None
        assert service.stripe_api_key is not None
        assert service.conekta_api_url == "https://api.conekta.io"
        assert service.polar_api_url == "https://api.polar.sh/v1"
        assert service.stripe_api_url == "https://api.stripe.com/v1"

    def test_pricing_tiers_configuration(self):
        """Test pricing tiers are properly configured"""
        assert "community" in PRICING_TIERS
        assert "pro" in PRICING_TIERS
        assert "scale" in PRICING_TIERS
        assert "enterprise" in PRICING_TIERS

        # Validate pricing structure
        pro = PRICING_TIERS["pro"]
        assert pro["price_mxn"] == 1380
        assert pro["price_usd"] == 69
        assert pro["mau_limit"] == 10000


class TestPaymentProviderSelection:
    """Test payment provider determination logic"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    async def test_determine_provider_mexico_uses_conekta(self, billing_service):
        """Test Mexico uses Conekta as primary provider"""
        provider = await billing_service.determine_payment_provider("MX")
        assert provider == "conekta"

    async def test_determine_provider_international_uses_polar(self, billing_service):
        """Test international countries use Polar.sh"""
        assert await billing_service.determine_payment_provider("US") == "polar"
        assert await billing_service.determine_payment_provider("CA") == "polar"
        assert await billing_service.determine_payment_provider("GB") == "polar"
        assert await billing_service.determine_payment_provider("DE") == "polar"
        assert await billing_service.determine_payment_provider("JP") == "polar"

    async def test_determine_provider_fallback_uses_stripe(self, billing_service):
        """Test fallback mode always returns Stripe"""
        assert await billing_service.determine_payment_provider("MX", fallback=True) == "stripe"
        assert await billing_service.determine_payment_provider("US", fallback=True) == "stripe"
        assert await billing_service.determine_payment_provider("DE", fallback=True) == "stripe"


class TestConektaIntegration:
    """Test Conekta integration (Mexico)"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    async def test_create_conekta_customer_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta customer creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "id": "cust_conekta_123",
            "email": "test@example.com",
            "name": "Test User",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_customer(
            email="test@example.com", name="Test User", phone="+52123456789"
        )

        assert result["id"] == "cust_conekta_123"
        assert result["email"] == "test@example.com"

    async def test_create_conekta_subscription_with_card_token(
        self, billing_service, mock_httpx_client
    ):
        """Test Conekta subscription with card token (adds payment method first)"""
        payment_response = AsyncMock()
        payment_response.json.return_value = {"id": "pm_123", "type": "card"}
        payment_response.raise_for_status = AsyncMock()

        subscription_response = AsyncMock()
        subscription_response.json.return_value = {"id": "sub_conekta_123", "status": "active"}
        subscription_response.raise_for_status = AsyncMock()

        mock_httpx_client.post.side_effect = [payment_response, subscription_response]

        result = await billing_service.create_conekta_subscription(
            customer_id="cust_123", plan_id="pro", card_token="tok_visa_4242"
        )

        assert result["id"] == "sub_conekta_123"
        assert mock_httpx_client.post.call_count == 2

    async def test_create_conekta_checkout_session_success(
        self, billing_service, mock_httpx_client
    ):
        """Test Conekta checkout session creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "id": "checkout_conekta_123",
            "url": "https://checkout.conekta.io/123",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_checkout_session(
            customer_email="test@example.com",
            tier="pro",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["id"] == "checkout_conekta_123"
        assert "url" in result

    async def test_cancel_conekta_subscription_success(self, billing_service, mock_httpx_client):
        """Test Conekta subscription cancellation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "canceled"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.cancel_conekta_subscription("sub_123")
        assert result is True


class TestPolarIntegration:
    """Test Polar.sh integration (International)"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    async def test_create_polar_customer_success(self, billing_service, mock_httpx_client):
        """Test Polar customer creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"id": "polar_cust_123", "email": "test@example.com"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_polar_customer(
            email="test@example.com", name="Test User", country="US"
        )

        assert result["id"] == "polar_cust_123"

    async def test_create_polar_subscription_success(self, billing_service, mock_httpx_client):
        """Test Polar subscription creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"id": "polar_sub_123", "status": "active"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_polar_subscription(
            customer_id="polar_cust_123", tier="pro"
        )

        assert result["id"] == "polar_sub_123"

    async def test_create_polar_checkout_session_success(self, billing_service, mock_httpx_client):
        """Test Polar checkout session creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "id": "polar_checkout_123",
            "url": "https://checkout.polar.sh/123",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_polar_checkout_session(
            customer_email="test@example.com",
            tier="pro",
            country="US",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["id"] == "polar_checkout_123"

    async def test_update_polar_subscription_success(self, billing_service, mock_httpx_client):
        """Test Polar subscription update"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"id": "polar_sub_123", "tier": "scale"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.put.return_value = mock_response

        result = await billing_service.update_polar_subscription("polar_sub_123", "scale")
        assert result["tier"] == "scale"

    async def test_cancel_polar_subscription_success(self, billing_service, mock_httpx_client):
        """Test Polar subscription cancellation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "canceled"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.delete.return_value = mock_response

        result = await billing_service.cancel_polar_subscription("polar_sub_123")
        assert result is True


class TestStripeIntegration:
    """Test Stripe integration (Universal fallback)"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    async def test_create_stripe_customer_success(self, billing_service, mock_httpx_client):
        """Test Stripe customer creation"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"id": "cus_stripe_123", "email": "test@example.com"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_stripe_customer(
            email="test@example.com", name="Test User"
        )

        assert result["id"] == "cus_stripe_123"

    async def test_create_stripe_checkout_session_mexico(self, billing_service, mock_httpx_client):
        """Test Stripe checkout for Mexico uses MXN"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "id": "cs_stripe_123",
            "url": "https://checkout.stripe.com/123",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_stripe_checkout_session(
            customer_email="test@example.com",
            tier="pro",
            country="MX",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["id"] == "cs_stripe_123"

    async def test_create_stripe_checkout_session_international(
        self, billing_service, mock_httpx_client
    ):
        """Test Stripe checkout for international uses USD"""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "id": "cs_stripe_456",
            "url": "https://checkout.stripe.com/456",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_stripe_checkout_session(
            customer_email="test@example.com",
            tier="pro",
            country="US",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["id"] == "cs_stripe_456"


class TestUnifiedBillingInterface:
    """Test unified billing interface routing"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    async def test_create_subscription_mexico_uses_conekta(self, billing_service):
        """Test unified interface routes Mexico to Conekta"""
        with patch.object(
            billing_service, "create_conekta_subscription", new_callable=AsyncMock
        ) as mock_conekta:
            mock_conekta.return_value = {"id": "sub_conekta_123"}

            result = await billing_service.create_subscription(
                customer_id="cust_123", tier="pro", country="MX", payment_method_id="pm_123"
            )

            assert result["id"] == "sub_conekta_123"
            mock_conekta.assert_called_once()

    async def test_create_subscription_international_uses_polar(self, billing_service):
        """Test unified interface routes international to Polar"""
        with patch.object(
            billing_service, "create_polar_subscription", new_callable=AsyncMock
        ) as mock_polar:
            mock_polar.return_value = {"id": "polar_sub_123"}

            result = await billing_service.create_subscription(
                customer_id="polar_cust_123", tier="pro", country="US", payment_method_id="pm_123"
            )

            assert result["id"] == "polar_sub_123"
            mock_polar.assert_called_once()


class TestPricingAndValidation:
    """Test pricing logic and validation"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    def test_get_pricing_for_country_mexico(self, billing_service):
        """Test pricing for Mexico returns MXN prices"""
        pricing = billing_service.get_pricing_for_country("MX")

        assert pricing["provider"] == "conekta"
        assert pricing["currency"] == "MXN"
        assert pricing["tiers"]["pro"]["price"] == 1380
        assert pricing["tiers"]["scale"]["price"] == 5980

    def test_get_pricing_for_country_international(self, billing_service):
        """Test pricing for international returns USD prices"""
        pricing = billing_service.get_pricing_for_country("US")

        assert pricing["provider"] == "polar"
        assert pricing["currency"] == "USD"
        assert pricing["tiers"]["pro"]["price"] == 69
        assert pricing["tiers"]["scale"]["price"] == 299

    def test_validate_plan_valid_tiers(self, billing_service):
        """Test plan validation"""
        assert billing_service.validate_plan("community") is True
        assert billing_service.validate_plan("pro") is True
        assert billing_service.validate_plan("scale") is True
        assert billing_service.validate_plan("enterprise") is True

    def test_validate_plan_invalid_tier(self, billing_service):
        """Test invalid tier validation"""
        assert billing_service.validate_plan("invalid") is False
        assert billing_service.validate_plan("") is False

    def test_get_plan_features(self, billing_service):
        """Test feature retrieval"""
        pro_features = billing_service.get_plan_features("pro")
        assert "advanced_rbac" in pro_features
        assert "sso" in pro_features

    def test_get_plan_mau_limit(self, billing_service):
        """Test MAU limit retrieval"""
        assert billing_service.get_plan_mau_limit("community") == 2000
        assert billing_service.get_plan_mau_limit("pro") == 10000
        assert billing_service.get_plan_mau_limit("enterprise") is None

    def test_calculate_overage_cost(self, billing_service):
        """Test overage cost calculation"""
        # No overage
        assert billing_service.calculate_overage_cost("pro", 9000) == 0.0

        # With overage
        assert billing_service.calculate_overage_cost("pro", 11000) == 10.0  # 1000 * $0.01


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    async def test_invalid_tier_checkout_raises_error(self, billing_service):
        """Test invalid tier raises ValueError"""
        with pytest.raises(ValueError):
            await billing_service.create_conekta_checkout_session(
                customer_email="test@example.com",
                tier="community",  # Free tier
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    async def test_polar_invalid_tier_raises_error(self, billing_service):
        """Test Polar invalid tier raises ValueError"""
        with pytest.raises(ValueError):
            await billing_service.create_polar_subscription(
                customer_id="polar_cust_123", tier="invalid_tier"
            )

    async def test_http_error_handling(self, billing_service):
        """Test HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError("Error", request=Mock(), response=mock_response)
            )
            client_instance.post.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.create_conekta_customer(email="test@example.com", name="Test")


class TestUsageLimits:
    """Test usage limit checking"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    async def test_check_usage_limits_tenant_not_found(self, billing_service, mock_db):
        """Test usage check when tenant not found"""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        within_limits, message = await billing_service.check_usage_limits(mock_db, uuid4())

        assert within_limits is False
        assert "not found" in message

    async def test_check_usage_limits_within_limit(self, billing_service, mock_db):
        """Test usage check within limits"""
        mock_tenant = Mock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 5000

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
        mock_db.execute = AsyncMock(return_value=mock_result)

        within_limits, message = await billing_service.check_usage_limits(mock_db, uuid4())

        assert within_limits is True
        assert message is None

    async def test_check_usage_limits_exceeded(self, billing_service, mock_db):
        """Test usage check when limit exceeded"""
        mock_tenant = Mock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 10000

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=mock_tenant)
        mock_db.execute = AsyncMock(return_value=mock_result)

        within_limits, message = await billing_service.check_usage_limits(mock_db, uuid4())

        assert within_limits is False
        assert "MAU limit reached" in message
