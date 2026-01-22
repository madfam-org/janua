import pytest

pytestmark = pytest.mark.asyncio


"""
Working unit tests for BillingService - matches actual implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
import httpx

from app.services.billing_service import BillingService, PRICING_TIERS


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for billing service tests."""
    with patch("app.services.billing_service.settings") as mock_settings:
        mock_settings.CONEKTA_API_KEY = "test_conekta_key"
        mock_settings.FUNGIES_API_KEY = "test_fungies_key"
        yield mock_settings


class TestBillingService:
    """Test billing service functionality."""

    def test_billing_service_initialization(self):
        """Test billing service initializes correctly."""
        billing = BillingService()

        assert hasattr(billing, "conekta_api_key")
        assert hasattr(billing, "conekta_api_url")
        assert hasattr(billing, "fungies_api_key")
        assert hasattr(billing, "fungies_api_url")
        assert billing.conekta_api_url == "https://api.conekta.io"
        assert billing.fungies_api_url == "https://api.fungies.io/v1"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_mexico(self):
        """Test payment provider determination for Mexico."""
        billing = BillingService()

        provider = await billing.determine_payment_provider("MX")
        assert provider == "conekta"

        provider = await billing.determine_payment_provider("mx")
        assert provider == "conekta"

    @pytest.mark.asyncio
    async def test_determine_payment_provider_international(self):
        """Test payment provider determination for international."""
        billing = BillingService()

        provider = await billing.determine_payment_provider("US")
        assert provider == "fungies"

        provider = await billing.determine_payment_provider("BR")
        assert provider == "fungies"

        provider = await billing.determine_payment_provider("DE")
        assert provider == "fungies"

    def test_pricing_tiers_structure(self):
        """Test pricing tiers are properly structured."""
        assert "community" in PRICING_TIERS
        assert "pro" in PRICING_TIERS
        assert "scale" in PRICING_TIERS
        assert "enterprise" in PRICING_TIERS

        # Check community tier is free
        assert PRICING_TIERS["community"]["price_mxn"] == 0
        assert PRICING_TIERS["community"]["price_usd"] == 0

        # Check pro tier has pricing
        assert PRICING_TIERS["pro"]["price_mxn"] == 1380
        assert PRICING_TIERS["pro"]["price_usd"] == 69
        assert PRICING_TIERS["pro"]["mau_limit"] == 10000


class TestConektaIntegration:
    """Test Conekta payment provider integration."""

    @pytest.mark.asyncio
    async def test_create_conekta_customer_success(self):
        """Test successful Conekta customer creation."""
        billing = BillingService()

        mock_response = {"id": "cus_test_123", "email": "test@example.com", "name": "Test User"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_conekta_customer(
                email="test@example.com",
                name="Test User",
                phone="+525551234567",
                metadata={"org_id": "123"},
            )

            assert result["id"] == "cus_test_123"
            assert result["email"] == "test@example.com"
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conekta_customer_failure(self):
        """Test Conekta customer creation failure."""
        billing = BillingService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPError("API Error")

            with pytest.raises(Exception):
                await billing.create_conekta_customer(email="test@example.com", name="Test User")

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_success(self):
        """Test successful Conekta subscription creation."""
        billing = BillingService()

        mock_subscription = {
            "id": "sub_test_123",
            "customer_id": "cus_test_123",
            "status": "active",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_subscription
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_conekta_subscription(
                customer_id="cus_test_123", plan_id="plan_pro"
            )

            assert result["id"] == "sub_test_123"
            assert result["customer_id"] == "cus_test_123"

    @pytest.mark.asyncio
    async def test_create_conekta_subscription_with_card_token(self):
        """Test Conekta subscription creation with card token."""
        billing = BillingService()

        mock_payment_method = {"id": "pm_test_123"}
        mock_subscription = {
            "id": "sub_test_123",
            "customer_id": "cus_test_123",
            "status": "active",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value

            # Mock payment method response
            mock_payment_response = AsyncMock()
            mock_payment_response.json = AsyncMock(return_value=mock_payment_method)
            mock_payment_response.raise_for_status = AsyncMock(return_value=None)

            # Mock subscription response
            mock_subscription_response = AsyncMock()
            mock_subscription_response.json = AsyncMock(return_value=mock_subscription)
            mock_subscription_response.raise_for_status = AsyncMock(return_value=None)

            mock_client_instance.post.side_effect = [
                mock_payment_response,  # First call for payment method
                mock_subscription_response,  # Second call for subscription
            ]

            result = await billing.create_conekta_subscription(
                customer_id="cus_test_123", plan_id="plan_pro", card_token="tok_test_card"
            )

            assert result["id"] == "sub_test_123"
            assert mock_client_instance.post.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_success(self):
        """Test successful Conekta subscription cancellation."""
        billing = BillingService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.cancel_conekta_subscription("sub_test_123")

            assert result is True
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_conekta_subscription_failure(self):
        """Test Conekta subscription cancellation failure."""
        billing = BillingService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPError("API Error")

            result = await billing.cancel_conekta_subscription("sub_test_123")

            assert result is False

    @pytest.mark.asyncio
    async def test_create_conekta_checkout_session_success(self):
        """Test successful Conekta checkout session creation."""
        billing = BillingService()

        mock_session = {
            "id": "checkout_test_123",
            "url": "https://checkout.conekta.com/session_123",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_session
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_conekta_checkout_session(
                customer_email="test@example.com",
                tier="pro",
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )

            assert result["id"] == "checkout_test_123"
            assert "url" in result

    @pytest.mark.asyncio
    async def test_create_conekta_checkout_session_invalid_tier(self):
        """Test Conekta checkout session with invalid tier."""
        billing = BillingService()

        with pytest.raises(ValueError, match="Invalid tier for payment"):
            await billing.create_conekta_checkout_session(
                customer_email="test@example.com",
                tier="community",  # Free tier
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )


class TestFungiesIntegration:
    """Test Fungies.io payment provider integration."""

    @pytest.mark.asyncio
    async def test_create_fungies_customer_success(self):
        """Test successful Fungies customer creation."""
        billing = BillingService()

        mock_response = {
            "id": "cus_fungies_123",
            "email": "test@example.com",
            "name": "Test User",
            "country": "US",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_fungies_customer(
                email="test@example.com", name="Test User", country="US", metadata={"org_id": "123"}
            )

            assert result["id"] == "cus_fungies_123"
            assert result["country"] == "US"

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_success(self):
        """Test successful Fungies subscription creation."""
        billing = BillingService()

        mock_subscription = {
            "id": "sub_fungies_123",
            "customer_id": "cus_fungies_123",
            "status": "active",
            "plan": {"amount": 6900, "currency": "USD"},  # $69 in cents
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_subscription
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_fungies_subscription(
                customer_id="cus_fungies_123", tier="pro", payment_method_id="pm_test_123"
            )

            assert result["id"] == "sub_fungies_123"
            assert result["plan"]["amount"] == 6900

    @pytest.mark.asyncio
    async def test_create_fungies_subscription_invalid_tier(self):
        """Test Fungies subscription with invalid tier."""
        billing = BillingService()

        with pytest.raises(ValueError, match="Invalid tier for payment"):
            await billing.create_fungies_subscription(
                customer_id="cus_fungies_123", tier="community"  # Free tier
            )

    @pytest.mark.asyncio
    async def test_create_fungies_checkout_session_success(self):
        """Test successful Fungies checkout session creation."""
        billing = BillingService()

        mock_session = {"id": "cs_fungies_123", "url": "https://checkout.fungies.io/session_123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_session
            mock_response_obj.raise_for_status = AsyncMock(return_value=None)
            mock_client_instance.post.return_value = mock_response_obj

            result = await billing.create_fungies_checkout_session(
                customer_email="test@example.com",
                tier="scale",
                country="US",
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )

            assert result["id"] == "cs_fungies_123"
            assert "url" in result


class TestUnifiedBillingInterface:
    """Test unified billing interface methods."""

    @pytest.mark.asyncio
    async def test_create_checkout_session_conekta(self):
        """Test creating checkout session for Mexico (Conekta)."""
        billing = BillingService()

        mock_session = {
            "id": "checkout_test_123",
            "url": "https://checkout.conekta.com/session_123",
        }

        with patch.object(billing, "create_conekta_checkout_session") as mock_conekta, patch(
            "app.models.CheckoutSession"
        ) as mock_checkout_model:
            mock_conekta.return_value = mock_session

            # Mock database session
            mock_db = AsyncMock()

            result = await billing.create_checkout_session(
                db=mock_db,
                tenant_id=uuid4(),
                email="test@example.com",
                tier="pro",
                country="MX",
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )

            assert result["provider"] == "conekta"
            assert result["id"] == "checkout_test_123"
            mock_conekta.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_checkout_session_fungies(self):
        """Test creating checkout session for international (Fungies)."""
        billing = BillingService()

        mock_session = {"id": "cs_fungies_123", "url": "https://checkout.fungies.io/session_123"}

        with patch.object(billing, "create_fungies_checkout_session") as mock_fungies, patch(
            "app.models.CheckoutSession"
        ) as mock_checkout_model:
            mock_fungies.return_value = mock_session

            # Mock database session
            mock_db = AsyncMock()

            result = await billing.create_checkout_session(
                db=mock_db,
                tenant_id=uuid4(),
                email="test@example.com",
                tier="pro",
                country="US",
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )

            assert result["provider"] == "fungies"
            assert result["id"] == "cs_fungies_123"
            mock_fungies.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_webhook_conekta(self):
        """Test handling Conekta webhook."""
        billing = BillingService()

        mock_db = AsyncMock()

        with patch.object(billing, "_handle_conekta_webhook") as mock_handler:
            mock_handler.return_value = True

            result = await billing.handle_webhook(
                db=mock_db,
                provider="conekta",
                event_type="order.paid",
                event_data={"customer_id": "cus_test_123"},
            )

            assert result is True
            mock_handler.assert_called_once_with(
                mock_db, "order.paid", {"customer_id": "cus_test_123"}
            )

    @pytest.mark.asyncio
    async def test_handle_webhook_fungies(self):
        """Test handling Fungies webhook."""
        billing = BillingService()

        mock_db = AsyncMock()

        with patch.object(billing, "_handle_fungies_webhook") as mock_handler:
            mock_handler.return_value = True

            result = await billing.handle_webhook(
                db=mock_db,
                provider="fungies",
                event_type="checkout.session.completed",
                event_data={"id": "cs_test_123"},
            )

            assert result is True
            mock_handler.assert_called_once_with(
                mock_db, "checkout.session.completed", {"id": "cs_test_123"}
            )

    @pytest.mark.asyncio
    async def test_handle_webhook_unknown_provider(self):
        """Test handling webhook with unknown provider."""
        billing = BillingService()

        mock_db = AsyncMock()

        result = await billing.handle_webhook(
            db=mock_db, provider="unknown", event_type="test.event", event_data={}
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_usage_limits_within_limits(self):
        """Test usage limits check when within limits."""
        billing = BillingService()

        # Mock tenant
        mock_tenant = AsyncMock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 5000  # Within pro limit of 10,000

        mock_db = AsyncMock()
        # Mock database execute result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db.execute.return_value = mock_result

        is_within_limits, message = await billing.check_usage_limits(db=mock_db, tenant_id=uuid4())

        assert is_within_limits is True
        assert message is None

    @pytest.mark.asyncio
    async def test_check_usage_limits_exceeded(self):
        """Test usage limits check when exceeded."""
        billing = BillingService()

        # Mock tenant
        mock_tenant = AsyncMock()
        mock_tenant.subscription_tier = "pro"
        mock_tenant.current_mau = 15000  # Exceeds pro limit of 10,000

        mock_db = AsyncMock()
        # Mock database execute result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db.execute.return_value = mock_result

        is_within_limits, message = await billing.check_usage_limits(db=mock_db, tenant_id=uuid4())

        assert is_within_limits is False
        assert "MAU limit reached" in message
        assert "10,000" in message

    @pytest.mark.asyncio
    async def test_check_usage_limits_tenant_not_found(self):
        """Test usage limits check when tenant not found."""
        billing = BillingService()

        mock_db = AsyncMock()
        # Mock database execute result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        is_within_limits, message = await billing.check_usage_limits(db=mock_db, tenant_id=uuid4())

        assert is_within_limits is False
        assert message == "Tenant not found"


class TestWebhookHandlers:
    """Test webhook handling for both providers."""

    @pytest.mark.asyncio
    async def test_handle_conekta_webhook_order_paid(self):
        """Test handling Conekta order.paid webhook."""
        billing = BillingService()

        mock_db = AsyncMock()
        mock_org = AsyncMock()
        mock_org.id = uuid4()

        # Mock database query - db.query() should return a sync object, but .first() should be async
        mock_query_result = AsyncMock()
        mock_query_result.filter.return_value.first = AsyncMock(return_value=mock_org)
        mock_db.query = Mock(return_value=mock_query_result)

        event_data = {"customer_id": "cus_test_123"}

        result = await billing._handle_conekta_webhook(
            db=mock_db, event_type="order.paid", event_data=event_data
        )

        assert result is True
        assert mock_org.subscription_status == "active"

    @pytest.mark.asyncio
    async def test_handle_fungies_webhook_checkout_completed(self):
        """Test handling Fungies checkout.session.completed webhook."""
        billing = BillingService()

        mock_db = AsyncMock()
        mock_user = AsyncMock()
        mock_user.organization_id = uuid4()
        mock_org = AsyncMock()
        mock_org.id = mock_user.organization_id

        # Mock database query results for two separate queries
        # Set up mock for User query: db.query(User).filter(...).first()
        mock_user_query = AsyncMock()
        mock_user_query.filter.return_value.first = AsyncMock(return_value=mock_user)

        # Set up mock for Organization query: db.query(Organization).filter(...).first()
        mock_org_query = AsyncMock()
        mock_org_query.filter.return_value.first = AsyncMock(return_value=mock_org)

        # db.query() itself should be sync, returning different mock objects
        mock_db.query = Mock(side_effect=[mock_user_query, mock_org_query])

        event_data = {"id": "cs_test_123", "customer_email": "test@example.com"}

        result = await billing._handle_fungies_webhook(
            db=mock_db, event_type="checkout.session.completed", event_data=event_data
        )

        assert result is True
        assert mock_org.subscription_status == "active"


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_conekta_api_error_handling(self):
        """Test handling Conekta API errors gracefully."""
        billing = BillingService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                await billing.create_conekta_customer(email="test@example.com", name="Test User")

    @pytest.mark.asyncio
    async def test_fungies_api_error_handling(self):
        """Test handling Fungies API errors gracefully."""
        billing = BillingService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.post.side_effect = Exception("API error")

            with pytest.raises(Exception):
                await billing.create_fungies_customer(
                    email="test@example.com", name="Test User", country="US"
                )

    @pytest.mark.asyncio
    async def test_database_error_in_checkout_session(self):
        """Test database error handling in checkout session creation."""
        billing = BillingService()

        mock_session = {
            "id": "checkout_test_123",
            "url": "https://checkout.conekta.com/session_123",
        }

        with patch.object(billing, "create_conekta_checkout_session") as mock_conekta, patch(
            "app.models.CheckoutSession", side_effect=Exception("DB error")
        ):
            mock_conekta.return_value = mock_session
            mock_db = AsyncMock()

            # Should continue execution despite DB error
            result = await billing.create_checkout_session(
                db=mock_db,
                tenant_id=uuid4(),
                email="test@example.com",
                tier="pro",
                country="MX",
                success_url="https://app.com/success",
                cancel_url="https://app.com/cancel",
            )

            # Session creation should still succeed
            assert result["provider"] == "conekta"
            assert result["id"] == "checkout_test_123"
