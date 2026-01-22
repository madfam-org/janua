import pytest

pytestmark = pytest.mark.asyncio


"""
Comprehensive test coverage for Billing Service
Critical for revenue protection and enterprise billing operations

Target: 23% → 80%+ coverage
Covers: Conekta (Mexico), Fungies.io (International), pricing, subscriptions
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.services.billing_service import PRICING_TIERS, BillingService


class TestBillingServiceInitialization:
    """Test billing service initialization and configuration"""

    def test_billing_service_init(self):
        """Test billing service initializes correctly"""
        service = BillingService()
        assert service is not None
        assert hasattr(service, "determine_payment_provider")

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
        with patch("httpx.AsyncClient") as mock:
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
            "name": "Test User",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_customer(
            email="test@example.com", name="Test User", phone="+52123456789"
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
        mock_response.json.return_value = {"error": "Invalid email format"}
        mock_response.raise_for_status = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Invalid email format", request=Mock(), response=mock_response
            )
        )
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await billing_service.create_conekta_customer(email="invalid-email", name="Test User")

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta subscription creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "sub_conekta_123",
            "status": "active",
            "customer": "cust_conekta_123",
            "plan": "pro_plan_mx",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_conekta_subscription(
            customer_id="cust_conekta_123", plan_id="pro_plan_mx"
        )

        assert result["id"] == "sub_conekta_123"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Conekta subscription cancellation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "sub_conekta_123", "status": "canceled"}
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
        with patch("httpx.AsyncClient") as mock:
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
            "status": "active",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_fungies_customer(
            email="test@example.com", name="Test User", country="US"
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
            "plan": "pro_plan_usd",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_fungies_subscription(
            customer_id="fung_cust_123", tier="pro"
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


class TestConektaSubscriptionWithCard:
    """Test Conekta subscription creation with card token"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_with_card_token(
        self, billing_service, mock_httpx_client
    ):
        """Test Conekta subscription creation with card token (adds payment method first)"""
        # Mock payment method creation response
        payment_method_response = AsyncMock()
        payment_method_response.status_code = 200
        payment_method_response.json.return_value = {
            "id": "pm_123",
            "type": "card",
            "last4": "4242",
        }
        payment_method_response.raise_for_status = AsyncMock()

        # Mock subscription creation response
        subscription_response = AsyncMock()
        subscription_response.status_code = 200
        subscription_response.json.return_value = {
            "id": "sub_conekta_123",
            "status": "active",
            "customer": "cust_conekta_123",
        }
        subscription_response.raise_for_status = AsyncMock()

        # Setup mock to return different responses for different calls
        mock_httpx_client.post.side_effect = [payment_method_response, subscription_response]

        result = await billing_service.create_conekta_subscription(
            customer_id="cust_conekta_123", plan_id="pro_plan_mx", card_token="tok_test_visa_4242"
        )

        assert result["id"] == "sub_conekta_123"
        assert result["status"] == "active"
        # Verify two POST calls were made (payment method + subscription)
        assert mock_httpx_client.post.call_count == 2


class TestConektaCheckoutSession:
    """Test Conekta checkout session creation"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_conekta_checkout_session_success(
        self, billing_service, mock_httpx_client
    ):
        """Test successful Conekta checkout session creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "checkout_conekta_123",
            "url": "https://checkout.conekta.io/session_123",
            "status": "open",
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

    @pytest.mark.asyncio
    async def test_create_conekta_checkout_session_invalid_tier(self, billing_service):
        """Test checkout session creation with invalid tier"""
        with pytest.raises(ValueError) as exc_info:
            await billing_service.create_conekta_checkout_session(
                customer_email="test@example.com",
                tier="community",  # Free tier, no payment needed
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )
        assert "Invalid tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_conekta_checkout_session_unknown_tier(self, billing_service):
        """Test checkout session creation with unknown tier"""
        with pytest.raises(ValueError):
            await billing_service.create_conekta_checkout_session(
                customer_email="test@example.com",
                tier="invalid_tier",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )


class TestFungiesCheckoutAndUpdate:
    """Test Fungies.io checkout and subscription updates"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_fungies_checkout_session_success(
        self, billing_service, mock_httpx_client
    ):
        """Test successful Fungies.io checkout session creation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "checkout_fung_123",
            "url": "https://checkout.fungies.io/session_123",
            "status": "open",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.create_fungies_checkout_session(
            customer_email="test@example.com",
            tier="pro",
            country="US",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["id"] == "checkout_fung_123"
        assert "url" in result

    @pytest.mark.asyncio
    async def test_create_fungies_checkout_session_invalid_tier(self, billing_service):
        """Test Fungies checkout with invalid tier"""
        with pytest.raises(ValueError):
            await billing_service.create_fungies_checkout_session(
                customer_email="test@example.com",
                tier="community",
                country="US",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @pytest.mark.asyncio
    async def test_update_fungies_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Fungies subscription update"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "fung_sub_123",
            "status": "active",
            "tier": "scale",
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.put.return_value = mock_response

        result = await billing_service.update_fungies_subscription(
            subscription_id="fung_sub_123", tier="scale"
        )

        assert result["id"] == "fung_sub_123"
        assert result["tier"] == "scale"

    @pytest.mark.asyncio
    async def test_update_fungies_subscription_invalid_tier(self, billing_service):
        """Test Fungies subscription update with invalid tier"""
        with pytest.raises(ValueError):
            await billing_service.update_fungies_subscription(
                subscription_id="fung_sub_123", tier="invalid_tier"
            )

    @pytest.mark.asyncio
    async def test_cancel_fungies_subscription_success(self, billing_service, mock_httpx_client):
        """Test successful Fungies subscription cancellation"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "canceled"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.delete.return_value = mock_response

        result = await billing_service.cancel_fungies_subscription("fung_sub_123")

        assert result is True
        mock_httpx_client.delete.assert_called_once()


class TestUnifiedBillingInterface:
    """Test unified billing interface that routes to correct provider"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.mark.asyncio
    async def test_create_subscription_mexico_uses_conekta(self, billing_service):
        """Test unified create_subscription uses Conekta for Mexico"""
        with patch.object(
            billing_service, "create_conekta_subscription", new_callable=AsyncMock
        ) as mock_conekta:
            mock_conekta.return_value = {"id": "sub_conekta_123", "provider": "conekta"}

            result = await billing_service.create_subscription(
                customer_id="cust_123", tier="pro", country="MX", payment_method_id="pm_123"
            )

            assert result["id"] == "sub_conekta_123"
            mock_conekta.assert_called_once_with(
                customer_id="cust_123", tier="pro", card_token="pm_123"
            )

    @pytest.mark.asyncio
    async def test_create_subscription_international_uses_fungies(self, billing_service):
        """Test unified create_subscription uses Fungies for international"""
        with patch.object(
            billing_service, "create_fungies_subscription", new_callable=AsyncMock
        ) as mock_fungies:
            mock_fungies.return_value = {"id": "fung_sub_123", "provider": "fungies"}

            result = await billing_service.create_subscription(
                customer_id="fung_cust_123", tier="pro", country="US", payment_method_id="pm_123"
            )

            assert result["id"] == "fung_sub_123"
            mock_fungies.assert_called_once_with(
                customer_id="fung_cust_123", tier="pro", payment_method_id="pm_123"
            )


class TestPlanFeaturesAndLimits:
    """Test plan features and MAU limit retrieval"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    def test_get_plan_features_valid_tiers(self, billing_service):
        """Test retrieving features for valid tiers"""
        community_features = billing_service.get_plan_features("community")
        assert "basic_auth" in community_features
        assert "email_support" in community_features

        pro_features = billing_service.get_plan_features("pro")
        assert "everything_community" in pro_features
        assert "advanced_rbac" in pro_features
        assert "sso" in pro_features

        scale_features = billing_service.get_plan_features("scale")
        assert "everything_pro" in scale_features
        assert "priority_support" in scale_features

        enterprise_features = billing_service.get_plan_features("enterprise")
        assert "everything_scale" in enterprise_features
        assert "dedicated_support" in enterprise_features

    def test_get_plan_features_invalid_tier(self, billing_service):
        """Test retrieving features for invalid tier returns None"""
        assert billing_service.get_plan_features("invalid") is None
        assert billing_service.get_plan_features("") is None

    def test_get_plan_mau_limit_valid_tiers(self, billing_service):
        """Test retrieving MAU limits for valid tiers"""
        assert billing_service.get_plan_mau_limit("community") == 2000
        assert billing_service.get_plan_mau_limit("pro") == 10000
        assert billing_service.get_plan_mau_limit("scale") == 50000
        assert billing_service.get_plan_mau_limit("enterprise") is None  # Custom

    def test_get_plan_mau_limit_invalid_tier(self, billing_service):
        """Test retrieving MAU limit for invalid tier returns None"""
        assert billing_service.get_plan_mau_limit("invalid") is None


class TestOverageCostCalculation:
    """Test overage cost calculation for MAU limits"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    def test_calculate_overage_no_overage(self, billing_service):
        """Test overage calculation when within limits"""
        # Community tier with 1500 MAU (under 2000 limit)
        cost = billing_service.calculate_overage_cost("community", 1500)
        assert cost == 0.0

        # Pro tier with 9000 MAU (under 10000 limit)
        cost = billing_service.calculate_overage_cost("pro", 9000)
        assert cost == 0.0

    def test_calculate_overage_with_overage(self, billing_service):
        """Test overage calculation when over limits"""
        # Community tier with 2500 MAU (500 over 2000 limit)
        cost = billing_service.calculate_overage_cost("community", 2500)
        assert cost == 5.0  # 500 * $0.01

        # Pro tier with 11000 MAU (1000 over 10000 limit)
        cost = billing_service.calculate_overage_cost("pro", 11000)
        assert cost == 10.0  # 1000 * $0.01

        # Scale tier with 52000 MAU (2000 over 50000 limit)
        cost = billing_service.calculate_overage_cost("scale", 52000)
        assert cost == 20.0  # 2000 * $0.01

    def test_calculate_overage_invalid_tier(self, billing_service):
        """Test overage calculation for invalid tier"""
        cost = billing_service.calculate_overage_cost("invalid", 5000)
        assert cost == 0.0

    def test_calculate_overage_enterprise_tier(self, billing_service):
        """Test overage calculation for enterprise (no limit)"""
        cost = billing_service.calculate_overage_cost("enterprise", 100000)
        assert cost == 0.0  # No limit for enterprise


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client_error(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            client_instance.post.side_effect = httpx.RequestError("Network error")
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_network_error_handling(self, billing_service, mock_httpx_client_error):
        """Test handling of network errors"""
        with pytest.raises(Exception) as exc_info:
            await billing_service.create_conekta_customer(
                email="test@example.com", name="Test User"
            )

        assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fungies_customer_creation_http_error(self, billing_service):
        """Test Fungies customer creation HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad Request", request=Mock(), response=mock_response
                )
            )
            client_instance.post.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.create_fungies_customer(
                    email="invalid@email", name="Test", country="US"
                )

    @pytest.mark.asyncio
    async def test_fungies_subscription_creation_http_error(self, billing_service):
        """Test Fungies subscription creation HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 402
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Payment Required", request=Mock(), response=mock_response
                )
            )
            client_instance.post.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.create_fungies_subscription(
                    customer_id="fung_cust_123", tier="pro"
                )

    @pytest.mark.asyncio
    async def test_conekta_checkout_session_http_error(self, billing_service):
        """Test Conekta checkout session HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal Server Error", request=Mock(), response=mock_response
                )
            )
            client_instance.post.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.create_conekta_checkout_session(
                    customer_email="test@example.com",
                    tier="pro",
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                )

    @pytest.mark.asyncio
    async def test_fungies_checkout_session_http_error(self, billing_service):
        """Test Fungies checkout session HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 503
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service Unavailable", request=Mock(), response=mock_response
                )
            )
            client_instance.post.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.create_fungies_checkout_session(
                    customer_email="test@example.com",
                    tier="scale",
                    country="DE",
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                )

    @pytest.mark.asyncio
    async def test_fungies_update_subscription_http_error(self, billing_service):
        """Test Fungies subscription update HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found", request=Mock(), response=mock_response
                )
            )
            client_instance.put.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.update_fungies_subscription(
                    subscription_id="nonexistent_sub", tier="scale"
                )

    @pytest.mark.asyncio
    async def test_fungies_cancel_subscription_http_error(self, billing_service):
        """Test Fungies subscription cancellation HTTP error handling"""
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.raise_for_status = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad Request", request=Mock(), response=mock_response
                )
            )
            client_instance.delete.return_value = mock_response
            mock.return_value.__aenter__.return_value = client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await billing_service.cancel_fungies_subscription("invalid_sub")


class TestConektaCancellation:
    """Test Conekta subscription cancellation"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_http_request(
        self, billing_service, mock_httpx_client
    ):
        """Test Conekta subscription cancellation makes correct HTTP request"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "sub_123", "status": "canceled"}
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.cancel_conekta_subscription("sub_123")

        assert result is True
        # Verify POST request was made to correct endpoint
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert "subscriptions/sub_123/cancel" in str(call_args)

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_http_error(self, billing_service, mock_httpx_client):
        """Test Conekta cancellation HTTP error returns False"""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.raise_for_status = AsyncMock(
            side_effect=httpx.HTTPStatusError("Bad Request", request=Mock(), response=mock_response)
        )
        mock_httpx_client.post.return_value = mock_response

        result = await billing_service.cancel_conekta_subscription("invalid_sub")

        assert result is False


class TestFungiesInvalidTierValidation:
    """Test Fungies subscription validation for invalid tiers"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_invalid_tier(self, billing_service):
        """Test Fungies subscription creation validates tier"""
        with pytest.raises(ValueError) as exc_info:
            await billing_service.create_fungies_subscription(
                customer_id="fung_cust_123", tier="community"  # Free tier
            )
        assert "Invalid tier" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_unknown_tier(self, billing_service):
        """Test Fungies subscription creation with unknown tier"""
        with pytest.raises(ValueError):
            await billing_service.create_fungies_subscription(
                customer_id="fung_cust_123", tier="unknown_tier"
            )


class TestCheckoutSessionDatabaseIntegration:
    """Test checkout session database storage"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_db_session(self):
        db = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("httpx.AsyncClient") as mock:
            client_instance = AsyncMock()
            mock.return_value.__aenter__.return_value = client_instance
            yield client_instance

    @pytest.mark.asyncio
    async def test_create_checkout_session_database_storage_error(
        self, billing_service, mock_db_session, mock_httpx_client
    ):
        """Test checkout session continues when database storage fails"""
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "checkout_123",
            "url": "https://checkout.example.com/123",
            "metadata": {"tier": "pro"},
        }
        mock_response.raise_for_status = AsyncMock()
        mock_httpx_client.post.return_value = mock_response

        # Mock database error
        mock_db_session.add.side_effect = Exception("Database connection error")

        # Patch uuid import for CheckoutSession
        with patch("uuid.uuid4", return_value="test-uuid"):
            # Should not raise exception - database storage is optional
            result = await billing_service.create_checkout_session(
                db=mock_db_session,
                tenant_id=uuid4(),
                email="test@example.com",
                tier="pro",
                country="MX",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        # Checkout session should still be created
        assert result["id"] == "checkout_123"
        assert result["provider"] == "conekta"


class TestWebhookHandling:
    """Test webhook event processing"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_db_session(self):
        db = AsyncMock()
        db.query = Mock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_handle_webhook_unknown_provider(self, billing_service, mock_db_session):
        """Test webhook handling for unknown provider"""
        result = await billing_service.handle_webhook(
            db=mock_db_session, provider="unknown_provider", event_type="test.event", event_data={}
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_webhook_conekta_order_paid(self, billing_service, mock_db_session):
        """Test Conekta order.paid webhook event"""
        # Mock organization query
        mock_org = Mock()
        mock_org.id = uuid4()
        mock_org.subscription_status = "pending"

        query_mock = Mock()
        query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db_session.query.return_value = query_mock

        event_data = {"customer_id": "cust_conekta_123", "order_id": "order_123"}

        result = await billing_service.handle_webhook(
            db=mock_db_session, provider="conekta", event_type="order.paid", event_data=event_data
        )

        assert result is True
        assert mock_org.subscription_status == "active"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_webhook_conekta_subscription_created(
        self, billing_service, mock_db_session
    ):
        """Test Conekta subscription.created webhook event"""
        mock_org = Mock()
        mock_org.id = uuid4()
        mock_org.subscription_id = None
        mock_org.subscription_status = "pending"

        query_mock = Mock()
        query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db_session.query.return_value = query_mock

        event_data = {"id": "sub_conekta_123", "customer_id": "cust_conekta_123"}

        result = await billing_service.handle_webhook(
            db=mock_db_session,
            provider="conekta",
            event_type="subscription.created",
            event_data=event_data,
        )

        assert result is True
        assert mock_org.subscription_id == "sub_conekta_123"
        assert mock_org.subscription_status == "active"

    @pytest.mark.asyncio
    async def test_handle_webhook_conekta_subscription_canceled(
        self, billing_service, mock_db_session
    ):
        """Test Conekta subscription.canceled webhook event"""
        mock_org = Mock()
        mock_org.id = uuid4()
        mock_org.subscription_status = "active"

        query_mock = Mock()
        query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db_session.query.return_value = query_mock

        event_data = {"id": "sub_conekta_123"}

        result = await billing_service.handle_webhook(
            db=mock_db_session,
            provider="conekta",
            event_type="subscription.canceled",
            event_data=event_data,
        )

        assert result is True
        assert mock_org.subscription_status == "canceled"

    @pytest.mark.asyncio
    async def test_handle_webhook_fungies_checkout_completed(
        self, billing_service, mock_db_session
    ):
        """Test Fungies checkout.session.completed webhook event"""
        mock_user = Mock()
        mock_user.organization_id = uuid4()

        mock_org = Mock()
        mock_org.id = mock_user.organization_id
        mock_org.subscription_status = "pending"

        # Mock query chain for user
        user_query_mock = Mock()
        user_query_mock.filter.return_value.first = AsyncMock(return_value=mock_user)

        # Mock query chain for org
        org_query_mock = Mock()
        org_query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)

        # Setup query to return different mocks based on model
        def query_side_effect(model):
            if "User" in str(model):
                return user_query_mock
            else:
                return org_query_mock

        mock_db_session.query.side_effect = query_side_effect

        event_data = {"id": "checkout_fung_123", "customer_email": "test@example.com"}

        result = await billing_service.handle_webhook(
            db=mock_db_session,
            provider="fungies",
            event_type="checkout.session.completed",
            event_data=event_data,
        )

        assert result is True
        assert mock_org.subscription_status == "active"

    @pytest.mark.asyncio
    async def test_handle_webhook_fungies_invoice_paid(self, billing_service, mock_db_session):
        """Test Fungies invoice.payment_succeeded webhook event"""
        mock_org = Mock()
        mock_org.id = uuid4()
        mock_org.subscription_status = "active"
        mock_org.last_payment_date = None

        query_mock = Mock()
        query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db_session.query.return_value = query_mock

        event_data = {"subscription": "fung_sub_123"}

        result = await billing_service.handle_webhook(
            db=mock_db_session,
            provider="fungies",
            event_type="invoice.payment_succeeded",
            event_data=event_data,
        )

        assert result is True
        assert mock_org.subscription_status == "active"
        assert mock_org.last_payment_date is not None

    @pytest.mark.asyncio
    async def test_handle_webhook_fungies_subscription_deleted(
        self, billing_service, mock_db_session
    ):
        """Test Fungies customer.subscription.deleted webhook event"""
        mock_org = Mock()
        mock_org.id = uuid4()
        mock_org.subscription_status = "active"

        query_mock = Mock()
        query_mock.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db_session.query.return_value = query_mock

        event_data = {"id": "fung_sub_123"}

        result = await billing_service.handle_webhook(
            db=mock_db_session,
            provider="fungies",
            event_type="customer.subscription.deleted",
            event_data=event_data,
        )

        assert result is True
        assert mock_org.subscription_status == "canceled"


class TestUsageLimitChecking:
    """Test usage limit validation"""

    @pytest.fixture
    def billing_service(self):
        return BillingService()

    @pytest.fixture
    def mock_db_session(self):
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_check_usage_limits_tenant_not_found(self, billing_service, mock_db_session):
        """Test usage limit check when tenant not found"""
        # Mock empty result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        within_limits, message = await billing_service.check_usage_limits(
            db=mock_db_session, tenant_id=uuid4()
        )

        assert within_limits is False
        assert "Tenant not found" in message

    @pytest.mark.asyncio
    async def test_check_usage_limits_within_limit(self, billing_service, mock_db_session):
        """Test usage limit check when within limits"""
        # Mock tenant with usage below limit
        mock_tenant = Mock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 5000  # Below 10,000 limit

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db_session.execute.return_value = mock_result

        within_limits, message = await billing_service.check_usage_limits(
            db=mock_db_session, tenant_id=uuid4()
        )

        assert within_limits is True
        assert message is None

    @pytest.mark.asyncio
    async def test_check_usage_limits_exceeded(self, billing_service, mock_db_session):
        """Test usage limit check when limit exceeded"""
        # Mock tenant with usage at limit
        mock_tenant = Mock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 10000  # At 10,000 limit

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db_session.execute.return_value = mock_result

        within_limits, message = await billing_service.check_usage_limits(
            db=mock_db_session, tenant_id=uuid4()
        )

        assert within_limits is False
        assert "MAU limit reached" in message
        assert "10,000" in message
