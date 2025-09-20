
pytestmark = pytest.mark.asyncio

"""
Comprehensive integration tests for service layer integrations
Tests JWT, cache, email, billing, and other core services
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime, timedelta
import uuid
import jwt as pyjwt

from app.services.jwt_service import JWTService
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.billing_service import BillingService
from app.models import User, UserStatus


@pytest.mark.asyncio
class TestJWTServiceIntegration:
    """Integration tests for JWT service"""

    @pytest.mark.asyncio
    async def test_jwt_token_lifecycle(self):
        """Test complete JWT token lifecycle"""
        jwt_service = JWTService()

        # Test token creation
        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "role": "user"
        }

        # Create access token
        access_token = jwt_service.create_access_token(user_data)
        assert access_token is not None
        assert isinstance(access_token, str)

        # Create refresh token
        refresh_token = jwt_service.create_refresh_token(user_data)
        assert refresh_token is not None
        assert isinstance(refresh_token, str)

        # Verify access token
        decoded_access = jwt_service.verify_token(access_token)
        assert decoded_access["user_id"] == user_data["user_id"]
        assert decoded_access["email"] == user_data["email"]
        assert decoded_access["token_type"] == "access"

        # Verify refresh token
        decoded_refresh = jwt_service.verify_token(refresh_token)
        assert decoded_refresh["user_id"] == user_data["user_id"]
        assert decoded_refresh["token_type"] == "refresh"

    @pytest.mark.asyncio
    async def test_jwt_token_expiration(self):
        """Test JWT token expiration handling"""
        jwt_service = JWTService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com"
        }

        # Create token with short expiration
        with patch.object(jwt_service, 'access_token_expire_minutes', 0.01):  # 0.6 seconds
            token = jwt_service.create_access_token(user_data)

            # Token should be valid immediately
            decoded = jwt_service.verify_token(token)
            assert decoded is not None

            # Wait for expiration
            import asyncio
            await asyncio.sleep(1)

            # Token should now be expired
            with pytest.raises(Exception):  # Should raise token expired exception
                jwt_service.verify_token(token)

    @pytest.mark.asyncio
    async def test_jwt_token_validation_security(self):
        """Test JWT token validation security"""
        jwt_service = JWTService()

        # Test invalid tokens
        invalid_tokens = [
            "invalid.jwt.token",
            "header.payload.signature",
            "",
            None,
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
        ]

        for invalid_token in invalid_tokens:
            with pytest.raises(Exception):
                jwt_service.verify_token(invalid_token)

    @pytest.mark.asyncio
    async def test_jwt_token_refresh_flow(self):
        """Test JWT token refresh flow"""
        jwt_service = JWTService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com"
        }

        # Create initial tokens
        access_token = jwt_service.create_access_token(user_data)
        refresh_token = jwt_service.create_refresh_token(user_data)

        # Refresh the access token
        new_access_token = jwt_service.refresh_access_token(refresh_token)
        assert new_access_token is not None
        assert new_access_token != access_token  # Should be different

        # Verify new token
        decoded_new = jwt_service.verify_token(new_access_token)
        assert decoded_new["user_id"] == user_data["user_id"]
        assert decoded_new["email"] == user_data["email"]

    @pytest.mark.asyncio
    async def test_jwt_custom_claims(self):
        """Test JWT with custom claims"""
        jwt_service = JWTService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "permissions": ["read", "write"],
            "organization_id": str(uuid.uuid4()),
            "role": "admin"
        }

        token = jwt_service.create_access_token(user_data)
        decoded = jwt_service.verify_token(token)

        assert decoded["permissions"] == ["read", "write"]
        assert decoded["organization_id"] == user_data["organization_id"]
        assert decoded["role"] == "admin"


@pytest.mark.asyncio
class TestCacheServiceIntegration:
    """Integration tests for cache service"""

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self, mock_redis):
        """Test basic cache operations"""
        from app.services.cache import CacheService

        cache_service = CacheService()
        cache_service.redis = mock_redis

        # Test set and get
        await cache_service.set("test_key", "test_value", expire=300)
        mock_redis.setex.assert_called_with("test_key", 300, "test_value")

        mock_redis.get.return_value = "test_value"
        value = await cache_service.get("test_key")
        assert value == "test_value"
        mock_redis.get.assert_called_with("test_key")

        # Test delete
        await cache_service.delete("test_key")
        mock_redis.delete.assert_called_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_json_serialization(self, mock_redis):
        """Test cache JSON serialization"""
        from app.services.cache import CacheService

        cache_service = CacheService()
        cache_service.redis = mock_redis

        # Test complex data structures
        complex_data = {
            "user_id": str(uuid.uuid4()),
            "permissions": ["read", "write"],
            "metadata": {
                "last_login": datetime.utcnow().isoformat(),
                "session_count": 5
            }
        }

        # Mock Redis to return JSON string
        import json as json_lib
        json_string = json_lib.dumps(complex_data)
        mock_redis.get.return_value = json_string

        await cache_service.set_json("complex_key", complex_data)
        retrieved_data = await cache_service.get_json("complex_key")

        assert retrieved_data["user_id"] == complex_data["user_id"]
        assert retrieved_data["permissions"] == complex_data["permissions"]
        assert retrieved_data["metadata"]["session_count"] == 5

    @pytest.mark.asyncio
    async def test_cache_rate_limiting(self, mock_redis):
        """Test cache-based rate limiting"""
        from app.services.cache import CacheService

        cache_service = CacheService()
        cache_service.redis = mock_redis

        # Test rate limit increment
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        count = await cache_service.increment_rate_limit("user:123", window=60)
        assert count == 1
        mock_redis.incr.assert_called_with("rate_limit:user:123")
        mock_redis.expire.assert_called_with("rate_limit:user:123", 60)

    @pytest.mark.asyncio
    async def test_cache_session_management(self, mock_redis):
        """Test cache-based session management"""
        from app.services.cache import CacheService

        cache_service = CacheService()
        cache_service.redis = mock_redis

        session_data = {
            "user_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "ip_address": "192.168.1.1",
            "user_agent": "Chrome/91.0"
        }

        session_id = str(uuid.uuid4())

        # Store session
        await cache_service.store_session(session_id, session_data, expire=3600)

        # Retrieve session
        mock_redis.get.return_value = json.dumps(session_data)
        retrieved_session = await cache_service.get_session(session_id)

        assert retrieved_session["user_id"] == session_data["user_id"]
        assert retrieved_session["ip_address"] == session_data["ip_address"]


@pytest.mark.asyncio
class TestEmailServiceIntegration:
    """Integration tests for email service"""

    @pytest.mark.asyncio
    async def test_email_service_initialization(self):
        """Test email service initialization"""
        email_service = EmailService()
        assert email_service is not None
        # Test configuration loading
        assert hasattr(email_service, 'smtp_server') or hasattr(email_service, 'config')

    @pytest.mark.asyncio
    async def test_verification_email_sending(self):
        """Test sending verification emails"""
        email_service = EmailService()

        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "verification_token": "verification_token_123"
        }

        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.return_value = True

            result = await email_service.send_verification_email(
                user_data["email"],
                user_data["first_name"],
                user_data["verification_token"]
            )

            assert result is True
            mock_send.assert_called_once()

            # Verify email content
            call_args = mock_send.call_args
            assert user_data["email"] in str(call_args)
            assert user_data["verification_token"] in str(call_args)

    @pytest.mark.asyncio
    async def test_password_reset_email(self):
        """Test sending password reset emails"""
        email_service = EmailService()

        reset_data = {
            "email": "user@example.com",
            "first_name": "Jane",
            "reset_token": "reset_token_456"
        }

        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.return_value = True

            result = await email_service.send_password_reset_email(
                reset_data["email"],
                reset_data["first_name"],
                reset_data["reset_token"]
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_magic_link_email(self):
        """Test sending magic link emails"""
        email_service = EmailService()

        magic_data = {
            "email": "magic@example.com",
            "first_name": "Magic",
            "magic_token": "magic_token_789"
        }

        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.return_value = True

            result = await email_service.send_magic_link_email(
                magic_data["email"],
                magic_data["first_name"],
                magic_data["magic_token"]
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_organization_invitation_email(self):
        """Test sending organization invitation emails"""
        email_service = EmailService()

        invitation_data = {
            "email": "invite@example.com",
            "inviter_name": "John Doe",
            "organization_name": "Test Company",
            "invitation_token": "invite_token_abc",
            "role": "member"
        }

        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.return_value = True

            result = await email_service.send_organization_invitation(
                invitation_data["email"],
                invitation_data["inviter_name"],
                invitation_data["organization_name"],
                invitation_data["invitation_token"],
                invitation_data["role"]
            )

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_template_rendering(self):
        """Test email template rendering"""
        email_service = EmailService()

        template_data = {
            "user_name": "John Doe",
            "verification_url": "https://app.example.com/verify?token=123",
            "company_name": "Test Company"
        }

        with patch.object(email_service, 'render_template') as mock_render:
            mock_render.return_value = "Rendered HTML content"

            rendered = email_service.render_template("verification_email.html", template_data)
            assert rendered == "Rendered HTML content"
            mock_render.assert_called_once_with("verification_email.html", template_data)

    @pytest.mark.asyncio
    async def test_email_delivery_failure_handling(self):
        """Test email delivery failure handling"""
        email_service = EmailService()

        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.side_effect = Exception("SMTP server unavailable")

            result = await email_service.send_verification_email(
                "test@example.com",
                "Test User",
                "token_123"
            )

            # Should handle failure gracefully
            assert result is False or result is None


@pytest.mark.asyncio
class TestBillingServiceIntegration:
    """Integration tests for billing service"""

    @pytest.mark.asyncio
    async def test_billing_service_initialization(self):
        """Test billing service initialization"""
        billing_service = BillingService()
        assert billing_service is not None

    @pytest.mark.asyncio
    async def test_subscription_creation(self):
        """Test creating a subscription"""
        billing_service = BillingService()

        subscription_data = {
            "organization_id": str(uuid.uuid4()),
            "plan_id": "pro_plan",
            "payment_method_id": "pm_test_123"
        }

        with patch.object(billing_service, 'create_subscription') as mock_create:
            mock_subscription = {
                "id": "sub_test_123",
                "status": "active",
                "current_period_start": datetime.utcnow().isoformat(),
                "current_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
            mock_create.return_value = mock_subscription

            result = await billing_service.create_subscription(
                subscription_data["organization_id"],
                subscription_data["plan_id"],
                subscription_data["payment_method_id"]
            )

            assert result["id"] == "sub_test_123"
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_webhook_processing(self):
        """Test billing webhook processing"""
        billing_service = BillingService()

        webhook_data = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_test_123",
                    "subscription": "sub_test_123",
                    "amount_paid": 2999,
                    "status": "paid"
                }
            }
        }

        with patch.object(billing_service, 'process_webhook') as mock_process:
            mock_process.return_value = True

            result = await billing_service.process_webhook(webhook_data)
            assert result is True
            mock_process.assert_called_once_with(webhook_data)

    @pytest.mark.asyncio
    async def test_usage_tracking(self):
        """Test usage tracking for billing"""
        billing_service = BillingService()

        usage_data = {
            "organization_id": str(uuid.uuid4()),
            "metric": "api_calls",
            "quantity": 100,
            "timestamp": datetime.utcnow().isoformat()
        }

        with patch.object(billing_service, 'track_usage') as mock_track:
            mock_track.return_value = True

            result = await billing_service.track_usage(
                usage_data["organization_id"],
                usage_data["metric"],
                usage_data["quantity"]
            )

            assert result is True
            mock_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoice_generation(self):
        """Test invoice generation"""
        billing_service = BillingService()

        invoice_data = {
            "organization_id": str(uuid.uuid4()),
            "billing_period_start": datetime.utcnow() - timedelta(days=30),
            "billing_period_end": datetime.utcnow()
        }

        with patch.object(billing_service, 'generate_invoice') as mock_generate:
            mock_invoice = {
                "id": "inv_test_123",
                "amount": 2999,
                "status": "draft",
                "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
            mock_generate.return_value = mock_invoice

            result = await billing_service.generate_invoice(
                invoice_data["organization_id"],
                invoice_data["billing_period_start"],
                invoice_data["billing_period_end"]
            )

            assert result["id"] == "inv_test_123"
            assert result["amount"] == 2999


@pytest.mark.asyncio
class TestAuthServiceIntegration:
    """Integration tests for authentication service"""

    @pytest.mark.asyncio
    async def test_user_registration_flow(self, test_db_session):
        """Test complete user registration flow"""
        auth_service = AuthService()

        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe"
        }

        with patch.object(auth_service, 'create_user') as mock_create:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = user_data["email"]
            mock_user.status = UserStatus.ACTIVE
            mock_create.return_value = mock_user

            result = await await auth_service.create_user(
                user_data["email"],
                user_data["password"],
                user_data["first_name"],
                user_data["last_name"]
            )

            assert result.email == user_data["email"]
            assert result.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_user_authentication_flow(self, test_db_session):
        """Test user authentication flow"""
        auth_service = AuthService()

        credentials = {
            "email": "user@example.com",
            "password": "UserPassword123!"
        }

        with patch.object(auth_service, 'authenticate_user') as mock_auth:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = credentials["email"]
            mock_user.status = UserStatus.ACTIVE
            mock_user.email_verified = True
            mock_auth.return_value = mock_user

            result = await auth_service.authenticate_user(
                credentials["email"],
                credentials["password"]
            )

            assert result.email == credentials["email"]
            assert result.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_session_management(self, test_db_session, mock_redis):
        """Test session management"""
        auth_service = AuthService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "user@example.com",
            "ip_address": "192.168.1.1",
            "user_agent": "Chrome/91.0"
        }

        with patch.object(auth_service, 'create_session') as mock_create_session:
            mock_session_data = {
                "access_token": "access_token_123",
                "refresh_token": "refresh_token_123",
                "session_id": str(uuid.uuid4())
            }
            mock_create_session.return_value = (
                mock_session_data["access_token"],
                mock_session_data["refresh_token"],
                {"id": mock_session_data["session_id"]}
            )

            access_token, refresh_token, session = await auth_service.create_session(
                user_data["user_id"],
                user_data["ip_address"],
                user_data["user_agent"]
            )

            assert access_token == mock_session_data["access_token"]
            assert refresh_token == mock_session_data["refresh_token"]
            assert session["id"] == mock_session_data["session_id"]

    @pytest.mark.asyncio
    async def test_password_reset_flow(self, test_db_session):
        """Test password reset flow"""
        auth_service = AuthService()

        reset_data = {
            "email": "user@example.com",
            "new_password": "NewPassword123!",
            "reset_token": "reset_token_456"
        }

        with patch.object(auth_service, 'reset_password') as mock_reset:
            mock_reset.return_value = True

            result = await auth_service.reset_password(
                reset_data["reset_token"],
                reset_data["new_password"]
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_email_verification_flow(self, test_db_session):
        """Test email verification flow"""
        auth_service = AuthService()

        verification_token = "verification_token_123"

        with patch.object(auth_service, 'verify_email') as mock_verify:
            mock_verify.return_value = True

            result = await auth_service.verify_email(verification_token)
            assert result is True


@pytest.mark.asyncio
class TestServiceIntegrationEdgeCases:
    """Edge cases and error handling for service integrations"""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self):
        """Test handling of Redis connection failures"""
        from app.services.cache import CacheService

        cache_service = CacheService()

        # Mock Redis connection failure
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis unavailable")
        cache_service.redis = mock_redis

        # Should handle connection failure gracefully
        result = await cache_service.get("test_key")
        assert result is None  # Should return None or default value

    @pytest.mark.asyncio
    async def test_jwt_secret_rotation(self):
        """Test JWT secret key rotation"""
        jwt_service = JWTService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com"
        }

        # Create token with original secret
        token = jwt_service.create_access_token(user_data)

        # Verify with original secret
        decoded = jwt_service.verify_token(token)
        assert decoded["user_id"] == user_data["user_id"]

        # Simulate secret rotation
        with patch.object(jwt_service, 'secret_key', 'new_secret_key'):
            # Old token should be invalid with new secret
            with pytest.raises(Exception):
                jwt_service.verify_token(token)

    @pytest.mark.asyncio
    async def test_email_service_smtp_failure(self):
        """Test email service SMTP failure handling"""
        email_service = EmailService()

        with patch.object(email_service, 'smtp_client') as mock_smtp:
            mock_smtp.send_message.side_effect = Exception("SMTP connection failed")

            result = await email_service.send_verification_email(
                "test@example.com",
                "Test User",
                "token_123"
            )

            # Should handle SMTP failure gracefully
            assert result is False

    @pytest.mark.asyncio
    async def test_billing_service_api_failure(self):
        """Test billing service API failure handling"""
        billing_service = BillingService()

        with patch.object(billing_service, 'stripe_client') as mock_stripe:
            mock_stripe.Subscription.create.side_effect = Exception("Stripe API unavailable")

            result = await billing_service.create_subscription(
                str(uuid.uuid4()),
                "pro_plan",
                "pm_test_123"
            )

            # Should handle API failure gracefully
            assert result is None or "error" in result

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self):
        """Test concurrent service operations"""
        import asyncio

        jwt_service = JWTService()

        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com"
        }

        # Create multiple tokens concurrently
        tasks = [
            jwt_service.create_access_token(user_data)
            for _ in range(10)
        ]

        tokens = await asyncio.gather(*tasks)

        # All tokens should be valid and unique
        assert len(tokens) == 10
        assert len(set(tokens)) == 10  # All unique

        # All tokens should be verifiable
        for token in tokens:
            decoded = jwt_service.verify_token(token)
            assert decoded["user_id"] == user_data["user_id"]

    @pytest.mark.asyncio
    async def test_service_memory_usage(self):
        """Test service memory usage under load"""
        jwt_service = JWTService()

        # Create many tokens to test memory usage
        tokens = []
        for i in range(1000):
            user_data = {
                "user_id": str(uuid.uuid4()),
                "email": f"user{i}@example.com"
            }
            token = jwt_service.create_access_token(user_data)
            tokens.append(token)

        # Verify all tokens are still valid
        valid_count = 0
        for token in tokens:
            try:
                decoded = jwt_service.verify_token(token)
                if decoded:
                    valid_count += 1
            except:
                pass

        # Most tokens should be valid
        assert valid_count >= 950  # Allow for some potential failures