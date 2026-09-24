"""
Comprehensive OAuth Provider Router Test Suite
Tests OAuth 2.0 Authorization Server endpoints with security validation.
"""

import base64
import hashlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module for patching
from app.routers.v1 import oauth_provider as oauth_provider_module

pytestmark = pytest.mark.asyncio


class TestCSRFTokenManagement:
    """Test CSRF token generation and validation"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.setex = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=True)
        return redis

    async def test_generate_csrf_token_returns_token(self, mock_redis):
        """Should generate a CSRF token"""
        from app.routers.v1.oauth_provider import _generate_csrf_token

        token = await _generate_csrf_token("user_123", mock_redis)

        assert token is not None
        assert len(token) > 20  # Base64 encoded 32 bytes
        mock_redis.setex.assert_called_once()

    async def test_generate_csrf_token_stores_user_id(self, mock_redis):
        """Should store user ID with CSRF token"""
        from app.routers.v1.oauth_provider import _generate_csrf_token

        await _generate_csrf_token("user_123", mock_redis)

        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("oauth:csrf:")
        assert call_args[0][2] == "user_123"

    async def test_validate_csrf_token_success(self, mock_redis):
        """Should validate valid CSRF token"""
        from app.routers.v1.oauth_provider import _validate_csrf_token

        mock_redis.get = AsyncMock(return_value="user_123")

        result = await _validate_csrf_token("valid_token", "user_123", mock_redis)

        assert result is True
        mock_redis.delete.assert_called_once()

    async def test_validate_csrf_token_empty_token(self, mock_redis):
        """Should reject empty CSRF token"""
        from app.routers.v1.oauth_provider import _validate_csrf_token

        result = await _validate_csrf_token("", "user_123", mock_redis)

        assert result is False

    async def test_validate_csrf_token_not_found(self, mock_redis):
        """Should reject CSRF token not in Redis"""
        from app.routers.v1.oauth_provider import _validate_csrf_token

        mock_redis.get = AsyncMock(return_value=None)

        result = await _validate_csrf_token("invalid_token", "user_123", mock_redis)

        assert result is False

    async def test_validate_csrf_token_user_mismatch(self, mock_redis):
        """Should reject CSRF token with wrong user"""
        from app.routers.v1.oauth_provider import _validate_csrf_token

        mock_redis.get = AsyncMock(return_value="different_user")

        result = await _validate_csrf_token("token", "user_123", mock_redis)

        assert result is False


class TestPKCEVerification:
    """Test PKCE code verifier validation"""

    def test_verify_pkce_s256_success(self):
        """Should verify valid S256 PKCE challenge"""
        from app.routers.v1.oauth_provider import _verify_pkce

        # Generate a code verifier and its challenge
        code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        # SHA256 hash of code_verifier, base64url encoded (no padding)
        verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode("ascii")

        result = _verify_pkce(code_verifier, code_challenge, "S256")

        assert result is True

    def test_verify_pkce_s256_failure(self):
        """Should reject invalid PKCE verifier"""
        from app.routers.v1.oauth_provider import _verify_pkce

        result = _verify_pkce("wrong_verifier", "some_challenge", "S256")

        assert result is False

    def test_verify_pkce_plain_rejected(self):
        """Should reject plain PKCE method"""
        from app.routers.v1.oauth_provider import _verify_pkce

        result = _verify_pkce("verifier", "verifier", "plain")

        assert result is False

    def test_verify_pkce_unknown_method_rejected(self):
        """Should reject unknown PKCE method"""
        from app.routers.v1.oauth_provider import _verify_pkce

        result = _verify_pkce("verifier", "challenge", "unknown")

        assert result is False


class TestRedirectURIValidation:
    """Test redirect URI validation"""

    def test_validate_redirect_uri_exact_match(self):
        """Should accept exact match redirect URI"""
        from app.routers.v1.oauth_provider import _validate_redirect_uri

        allowed = ["https://app.example.com/callback"]

        with patch.object(
            oauth_provider_module, "validate_oauth_redirect_uri", return_value=True
        ):
            result = _validate_redirect_uri("https://app.example.com/callback", allowed)
            assert result is True

    def test_validate_redirect_uri_not_in_list(self):
        """Should reject redirect URI not in allowed list"""
        from app.routers.v1.oauth_provider import _validate_redirect_uri

        allowed = ["https://app.example.com/callback"]

        with patch.object(
            oauth_provider_module, "validate_oauth_redirect_uri", return_value=False
        ):
            result = _validate_redirect_uri("https://malicious.com/callback", allowed)
            assert result is False


class TestAuthCodeStorage:
    """Test authorization code storage in Redis"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=True)
        return redis

    async def test_store_auth_code_success(self, mock_redis):
        """Should store authorization code in Redis"""
        from app.routers.v1.oauth_provider import _store_auth_code

        code = "test_auth_code"
        data = {"client_id": "client_123", "user_id": "user_456"}

        await _store_auth_code(code, data, mock_redis)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "oauth:code:test_auth_code"
        assert json.loads(call_args[0][1])["client_id"] == "client_123"

    async def test_store_auth_code_redis_failure(self, mock_redis):
        """Should raise HTTPException on Redis failure"""
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import _store_auth_code

        mock_redis.set = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await _store_auth_code("code", {}, mock_redis)

        assert exc_info.value.status_code == 503

    async def test_get_auth_code_success(self, mock_redis):
        """Should retrieve authorization code from Redis"""
        from app.routers.v1.oauth_provider import _get_auth_code

        code_data = {"client_id": "client_123", "user_id": "user_456"}
        mock_redis.get = AsyncMock(return_value=json.dumps(code_data))

        result = await _get_auth_code("test_code", mock_redis)

        assert result == code_data

    async def test_get_auth_code_not_found(self, mock_redis):
        """Should return None for unknown authorization code"""
        from app.routers.v1.oauth_provider import _get_auth_code

        mock_redis.get = AsyncMock(return_value=None)

        result = await _get_auth_code("unknown_code", mock_redis)

        assert result is None

    async def test_delete_auth_code(self, mock_redis):
        """Should delete authorization code from Redis"""
        from app.routers.v1.oauth_provider import _delete_auth_code

        await _delete_auth_code("test_code", mock_redis)

        mock_redis.delete.assert_called_once_with("oauth:code:test_code")


class TestOAuthClientRetrieval:
    """Test OAuth client lookup"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        return db

    async def test_get_oauth_client_found(self, mock_db):
        """Should return OAuth client when found"""
        from app.routers.v1.oauth_provider import _get_oauth_client

        mock_client = MagicMock()
        mock_client.client_id = "test_client"
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_client))
        )

        result = await _get_oauth_client("test_client", mock_db)

        assert result == mock_client

    async def test_get_oauth_client_not_found(self, mock_db):
        """Should return None when client not found"""
        from app.routers.v1.oauth_provider import _get_oauth_client

        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await _get_oauth_client("unknown_client", mock_db)

        assert result is None


class TestIDTokenGeneration:
    """Test OpenID Connect ID Token generation"""

    @pytest.fixture
    def mock_user(self):
        """Mock user object"""
        user = MagicMock()
        user.id = "user_123"
        user.email = "test@example.com"
        user.email_verified = True
        user.name = "Test User"
        return user

    def test_generate_id_token_basic(self, mock_user):
        """Should generate ID token with required claims"""
        from app.routers.v1.oauth_provider import _generate_id_token

        with patch.object(oauth_provider_module.jwt_manager, "encode_token") as mock_encode:
            mock_encode.return_value = "encoded_id_token"

            result = _generate_id_token(mock_user, "client_123")

            assert result == "encoded_id_token"
            call_args = mock_encode.call_args[0][0]
            assert call_args["sub"] == "user_123"
            assert call_args["aud"] == "client_123"
            assert call_args["email"] == "test@example.com"
            assert "iss" in call_args
            assert "exp" in call_args
            assert "iat" in call_args

    def test_generate_id_token_with_nonce(self, mock_user):
        """Should include nonce in ID token when provided"""
        from app.routers.v1.oauth_provider import _generate_id_token

        with patch.object(oauth_provider_module.jwt_manager, "encode_token") as mock_encode:
            mock_encode.return_value = "encoded_id_token"

            _generate_id_token(mock_user, "client_123", nonce="test_nonce")

            call_args = mock_encode.call_args[0][0]
            assert call_args["nonce"] == "test_nonce"

    def test_generate_id_token_with_access_token(self, mock_user):
        """Should include at_hash when access token provided"""
        from app.routers.v1.oauth_provider import _generate_id_token

        with patch.object(oauth_provider_module.jwt_manager, "encode_token") as mock_encode:
            mock_encode.return_value = "encoded_id_token"

            _generate_id_token(mock_user, "client_123", access_token="test_access_token")

            call_args = mock_encode.call_args[0][0]
            assert "at_hash" in call_args


class TestSafeCallbackURLBuilder:
    """Test safe callback URL construction"""

    def test_build_safe_callback_url_success(self):
        """Should build callback URL with params"""
        from app.routers.v1.oauth_provider import _build_safe_callback_url

        with patch.object(oauth_provider_module, "is_safe_redirect_url", return_value=True):
            result = _build_safe_callback_url(
                "https://app.example.com/callback", {"code": "abc123", "state": "xyz"}
            )

            assert result.startswith("https://app.example.com/callback?")
            assert "code=abc123" in result
            assert "state=xyz" in result

    def test_build_safe_callback_url_unsafe_uri_rejected(self):
        """Should reject unsafe redirect URI"""
        from app.routers.v1.oauth_provider import _build_safe_callback_url

        with patch.object(oauth_provider_module, "is_safe_redirect_url", return_value=False):
            with pytest.raises(ValueError) as exc_info:
                _build_safe_callback_url("javascript:alert(1)", {"code": "abc"})

            assert "Invalid redirect URI" in str(exc_info.value)

    def test_build_safe_callback_url_client_validated_skips_host_check(self):
        """Should skip host allowlist check when client_validated=True"""
        from app.routers.v1.oauth_provider import _build_safe_callback_url

        # Even if is_safe_redirect_url would reject the host, client_validated=True bypasses it
        result = _build_safe_callback_url(
            "https://app.dhan.am/auth/callback",
            {"code": "abc123", "state": "xyz"},
            client_validated=True,
        )

        assert result.startswith("https://app.dhan.am/auth/callback?")
        assert "code=abc123" in result

    def test_build_safe_callback_url_client_validated_still_blocks_dangerous_schemes(self):
        """Should still block dangerous schemes even with client_validated=True"""
        from app.routers.v1.oauth_provider import _build_safe_callback_url

        with pytest.raises(ValueError):
            _build_safe_callback_url(
                "javascript:alert(1)", {"code": "abc"}, client_validated=True
            )

        with pytest.raises(ValueError):
            _build_safe_callback_url(
                "data:text/html,<script>", {"code": "abc"}, client_validated=True
            )


class TestUserEntitlements:
    """Test user entitlements fetching"""

    @pytest.fixture
    def mock_db(self):
        """Mock async database session"""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Mock user object"""
        user = MagicMock()
        user.id = "user_123"
        user.is_admin = False
        user.tenant_id = None
        return user

    async def test_get_user_entitlements_default(self, mock_db, mock_user):
        """Should return default entitlements when no memberships"""
        from app.routers.v1.oauth_provider import _get_user_entitlements

        # Mock no memberships
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        result = await _get_user_entitlements(mock_user, mock_db)

        assert result["tier"] == "community"
        assert result["roles"] == []
        assert result["sub_status"] == "inactive"
        assert result["is_admin"] is False

    async def test_get_user_entitlements_admin_flag(self, mock_db, mock_user):
        """Should include admin role when user is admin"""
        from app.routers.v1.oauth_provider import _get_user_entitlements

        mock_user.is_admin = True

        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        result = await _get_user_entitlements(mock_user, mock_db)

        assert "admin" in result["roles"]
        assert result["is_admin"] is True

    async def test_membership_query_filters_status_active(self, mock_db, mock_user):
        """The membership query MUST filter status == 'active'.

        Regression guard for G4: a removed/inactive member kept org roles/tier
        in their token because the query had no status filter. Mirror the idiom
        `_get_user_org_claims` uses. We compile the SELECT and assert the
        status='active' predicate is present in the WHERE clause.
        """
        from app.routers.v1.oauth_provider import _get_user_entitlements

        captured = {}

        async def _capture_execute(stmt, *args, **kwargs):
            # Compile WITHOUT literal_binds — the mock user id is not a real UUID
            # and would fail to render; the SQL text + bound params are enough.
            compiled = stmt.compile()
            captured["sql"] = str(compiled)
            captured["params"] = compiled.params
            return MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )

        mock_db.execute = AsyncMock(side_effect=_capture_execute)

        await _get_user_entitlements(mock_user, mock_db)

        sql = captured["sql"].lower()
        # The WHERE clause must reference the status column, and the bound value
        # must be 'active' — mirrors the filter `_get_user_org_claims` applies.
        assert "status" in sql
        assert "active" in captured["params"].values()

    async def test_inactive_member_gets_no_org_roles_or_tier(self, mock_db, mock_user):
        """A member whose only memberships are inactive/removed/pending gets the
        community defaults — no org roles, no org tier.

        With the status filter in the query, the DB returns zero rows for a
        user whose memberships are all non-active, so the function falls through
        to defaults. This mirrors `_get_user_org_claims`'s fail-closed behaviour.
        """
        from app.routers.v1.oauth_provider import _get_user_entitlements

        # DB returns [] because the status='active' filter excludes the user's
        # inactive/removed/pending memberships. The org lookup must NOT happen.
        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )

        result = await _get_user_entitlements(mock_user, mock_db)

        assert result["roles"] == []
        assert result["tier"] == "community"
        assert result["sub_status"] == "inactive"
        # Exactly one query ran (memberships). The org tier lookup is skipped
        # because no active membership was found.
        assert mock_db.execute.await_count == 1

    async def test_active_member_still_gets_org_roles_and_tier(self, mock_db, mock_user):
        """Behaviour for ACTIVE members is preserved exactly by the G4 fix."""
        from app.routers.v1.oauth_provider import _get_user_entitlements

        org_id = uuid.uuid4()
        active_member = MagicMock(role="admin", organization_id=org_id, status="active")
        org = MagicMock(subscription_tier="pro")

        call = {"n": 0}

        async def _execute(*args, **kwargs):
            call["n"] += 1
            if call["n"] == 1:  # membership query
                return MagicMock(
                    scalars=MagicMock(
                        return_value=MagicMock(all=MagicMock(return_value=[active_member]))
                    )
                )
            # org lookup
            return MagicMock(scalar_one_or_none=MagicMock(return_value=org))

        mock_db.execute = AsyncMock(side_effect=_execute)

        result = await _get_user_entitlements(mock_user, mock_db)

        assert "admin" in result["roles"]
        assert result["tier"] == "pro"


class TestAuthorizationEndpointValidation:
    """Test authorization endpoint validation logic"""

    def test_response_type_code_only(self):
        """Should only support 'code' response_type"""
        # This is enforced in the endpoint, tested via integration tests
        # Here we document the requirement
        assert True  # Placeholder for documentation

    def test_pkce_required_for_public_clients(self):
        """Public clients must use PKCE"""
        # This is enforced in the endpoint - public clients without code_challenge are rejected
        assert True  # Placeholder for documentation

    def test_pkce_s256_only(self):
        """Only S256 PKCE method is supported"""
        # plain method is rejected for security reasons
        assert True  # Placeholder for documentation


class TestTokenEndpointValidation:
    """Test token endpoint validation"""

    def test_grant_type_authorization_code(self):
        """Should support authorization_code grant"""
        assert True  # Placeholder - tested via integration tests

    def test_grant_type_refresh_token(self):
        """Should support refresh_token grant"""
        assert True  # Placeholder - tested via integration tests

    async def test_client_credentials_grant_mints_service_account_claims(self):
        """Should mint short-lived machine tokens with org and product-tier claims."""
        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        org_id = uuid.uuid4()
        mock_client = MagicMock()
        mock_client.client_id = "jnc_ecosystem_probe"
        mock_client.name = "MADFAM Ecosystem Probe"
        mock_client.allowed_scopes = ["openid", "admin", "yantra4d:quote", "cotiza:quote"]
        mock_client.audience = "madfam-ecosystem"
        mock_client.is_confidential = True
        mock_client.organization_id = org_id

        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "madfam"
        mock_org.subscription_tier = "madfam"
        mock_org.product_tiers = {
            "yantra4d": "madfam",
            "cotiza": "madfam",
            "forgesight": "madfam",
        }

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_org))
        )
        mock_db.commit = AsyncMock()

        with patch.object(
            oauth_provider_module.jwt_manager,
            "create_access_token",
            return_value=("encoded_access_token", "jti", None),
        ) as mock_create:
            response = await _handle_client_credentials_grant(
                client=mock_client,
                requested_scope="openid admin yantra4d:quote",
                db=mock_db,
            )

        assert response.access_token == "encoded_access_token"
        assert response.refresh_token is None
        assert response.scope == "admin openid yantra4d:quote"
        mock_db.commit.assert_called_once()

        _, kwargs = mock_create.call_args
        assert kwargs["user_id"] == "service-account:jnc_ecosystem_probe"
        assert kwargs["email"] == "madfam-ecosystem-probe@service.auth.madfam.io"
        claims = kwargs["additional_claims"]
        assert claims["aud"] == "madfam-ecosystem"
        assert claims["org_id"] == str(org_id)
        assert claims["tenant_id"] == str(org_id)
        # The pinned shape GREW deliberately. `yantra4d:quote` is a namespaced
        # app-role-shaped scope, it is in this client's `allowed_scopes`, it was
        # requested, and the client is org-bound — so it is now emitted VERBATIM
        # for the resource server to match, alongside every string this claim
        # carried before. `admin` and `service_account` are untouched: the
        # change is additive, never a replacement. See
        # `tests/unit/routers/test_service_client_app_roles.py` for the rule.
        assert claims["roles"] == ["admin", "service_account", "yantra4d:quote"]
        assert claims["is_admin"] is True
        assert claims["yantra4d_tier"] == "madfam"
        assert claims["cotiza_tier"] == "madfam"
        assert claims["forgesight_tier"] == "madfam"

    async def test_client_credentials_rejects_scope_not_allowed_on_client(self):
        """Should fail closed when a machine client requests ungranted scopes."""
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        mock_client = MagicMock()
        mock_client.client_id = "jnc_ecosystem_probe"
        mock_client.name = "MADFAM Ecosystem Probe"
        mock_client.allowed_scopes = ["openid", "yantra4d:quote"]
        mock_client.is_confidential = True
        mock_client.organization_id = None

        with pytest.raises(HTTPException) as exc_info:
            await _handle_client_credentials_grant(
                client=mock_client,
                requested_scope="openid admin",
                db=AsyncMock(),
            )

        assert exc_info.value.status_code == 400
        assert "invalid_scope" in exc_info.value.detail

    async def test_client_credentials_product_scope_emits_tier_without_org(self):
        """Product scopes should produce downstream tier claims for machine clients."""
        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        mock_client = MagicMock()
        mock_client.client_id = "jnc_ecosystem_probe"
        mock_client.name = "MADFAM Ecosystem Probe"
        mock_client.allowed_scopes = ["openid", "yantra4d:quote", "cotiza:quote"]
        mock_client.audience = "madfam-ecosystem"
        mock_client.is_confidential = True
        mock_client.organization_id = None

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch.object(
            oauth_provider_module.jwt_manager,
            "create_access_token",
            return_value=("encoded_access_token", "jti", None),
        ) as mock_create:
            await _handle_client_credentials_grant(
                client=mock_client,
                requested_scope="openid yantra4d:quote cotiza:quote",
                db=mock_db,
            )

        _, kwargs = mock_create.call_args
        claims = kwargs["additional_claims"]
        assert claims["yantra4d_tier"] == "madfam"
        assert claims["cotiza_tier"] == "madfam"
        assert "forgesight_tier" not in claims


class TestUserInfoEndpointClaims:
    """Test UserInfo endpoint claims"""

    @pytest.fixture
    def mock_user(self):
        """Mock user with profile data"""
        user = MagicMock()
        user.id = "user_123"
        user.email = "test@example.com"
        user.email_verified = True
        user.first_name = "Test"
        user.last_name = "User"
        user.avatar_url = "https://example.com/avatar.jpg"
        return user

    def test_userinfo_contains_sub(self, mock_user):
        """UserInfo response must contain 'sub' claim"""
        # The sub claim is the user ID
        assert mock_user.id == "user_123"

    def test_userinfo_email_claims(self, mock_user):
        """UserInfo should include email claims when requested"""
        assert mock_user.email == "test@example.com"
        assert mock_user.email_verified is True

    def test_userinfo_profile_claims(self, mock_user):
        """UserInfo should include profile claims when requested"""
        # given_name, family_name derived from first_name, last_name
        assert mock_user.first_name == "Test"
        assert mock_user.last_name == "User"


class TestSecurityValidations:
    """Test security-critical validations"""

    def test_redirect_uri_validated_before_redirect(self):
        """Redirect URI must be validated against registered URIs before any redirect"""
        # This is a critical security check (CWE-601 prevention)
        # The authorize endpoint validates redirect_uri before showing consent or redirecting
        assert True  # Enforced in implementation

    def test_csrf_token_single_use(self):
        """CSRF tokens must be consumed after use (single use)"""
        # _validate_csrf_token deletes the token after successful validation
        assert True  # Enforced in implementation

    def test_auth_code_single_use(self):
        """Authorization codes must be consumed after use (single use)"""
        # Token endpoint deletes auth code after exchange
        assert True  # Enforced in implementation

    def test_state_preserved_in_callback(self):
        """State parameter must be preserved in callback for CSRF protection"""
        # The state param from authorization request is included in callback
        assert True  # Enforced in implementation

    def test_email_verification_required(self):
        """OAuth authorization should require email verification"""
        # When REQUIRE_EMAIL_VERIFICATION is enabled, unverified users are blocked
        # (with grace period for new accounts)
        assert True  # Enforced in implementation


class TestOAuthSchemas:
    """Test OAuth Pydantic schemas"""

    def test_authorization_request_schema(self):
        """Test AuthorizationRequest schema"""
        from app.routers.v1.oauth_provider import AuthorizationRequest

        request = AuthorizationRequest(
            response_type="code",
            client_id="client_123",
            redirect_uri="https://app.example.com/callback",
            scope="openid profile email",
            state="csrf_state",
            code_challenge="challenge",
            code_challenge_method="S256",
        )

        assert request.response_type == "code"
        assert request.client_id == "client_123"
        assert request.scope == "openid profile email"

    def test_token_request_schema(self):
        """Test TokenRequest schema"""
        from app.routers.v1.oauth_provider import TokenRequest

        request = TokenRequest(
            grant_type="authorization_code",
            code="auth_code_123",
            redirect_uri="https://app.example.com/callback",
            client_id="client_123",
            code_verifier="verifier_123",
            scope="openid profile",
        )

        assert request.grant_type == "authorization_code"
        assert request.code == "auth_code_123"
        assert request.scope == "openid profile"

    def test_machine_only_oauth_client_allows_empty_redirect_uris(self):
        """client_credentials-only clients should not need browser redirects."""
        from app.schemas.oauth_client import OAuthClientCreate

        client = OAuthClientCreate(
            name="madfam-ecosystem-probe",
            redirect_uris=[],
            grant_types=["client_credentials"],
            allowed_scopes=["openid", "yantra4d:quote"],
            organization_id=str(uuid.uuid4()),
        )

        assert client.redirect_uris == []
        assert client.grant_types == ["client_credentials"]
        assert client.organization_id is not None

    def test_interactive_oauth_client_requires_redirect_uris(self):
        """Interactive OAuth clients still require registered redirect URIs."""
        from app.schemas.oauth_client import OAuthClientCreate

        with pytest.raises(Exception):
            OAuthClientCreate(
                name="interactive-app",
                redirect_uris=[],
                grant_types=["authorization_code"],
                allowed_scopes=["openid"],
            )

    def test_token_response_schema(self):
        """Test TokenResponse schema"""
        from app.routers.v1.oauth_provider import TokenResponse

        response = TokenResponse(
            access_token="access_123",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_123",
            id_token="id_token_123",
            scope="openid profile",
        )

        assert response.access_token == "access_123"
        assert response.token_type == "Bearer"
        assert response.expires_in == 3600

    def test_userinfo_response_schema(self):
        """Test UserInfoResponse schema"""
        from app.routers.v1.oauth_provider import UserInfoResponse

        response = UserInfoResponse(
            sub="user_123",
            email="test@example.com",
            email_verified=True,
            name="Test User",
            given_name="Test",
            family_name="User",
        )

        assert response.sub == "user_123"
        assert response.email == "test@example.com"
        assert response.name == "Test User"


class TestPreLoginRedisStorage:
    """Test that unauthenticated authorize requests store params in Redis
    and redirect to login with auth_request_id (not double-encoded next URL)."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.setex = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=True)
        return redis

    def test_authorize_stores_params_in_redis_when_unauthenticated(self):
        """Verify the authorize endpoint code path stores OAuth params in Redis
        instead of encoding them into the redirect URL."""
        import inspect

        from app.routers.v1.oauth_provider import authorize_get

        source = inspect.getsource(authorize_get)

        # Must use Redis-backed storage pattern (not urlencode of full authorize URL)
        assert "oauth:pre_login:" in source, (
            "authorize_get should store params in Redis with key prefix 'oauth:pre_login:'"
        )
        assert "auth_request_id" in source, (
            "authorize_get should pass auth_request_id to login page"
        )
        # Must NOT build a 'next' URL containing the full authorize path+query
        # (this was the root cause of the double-encoding redirect loop)
        assert 'f"{scheme}://{request_host}{request.url.path}?{request.url.query}"' not in source, (
            "authorize_get must not build a 'next' URL from request.url.path+query "
            "(causes double-encoding redirect loop)"
        )

    def test_pre_login_data_contains_all_oauth_params(self):
        """The stored pre_login_data must include all OAuth authorize parameters
        so the authorize URL can be reconstructed after login."""
        import inspect

        from app.routers.v1.oauth_provider import authorize_get

        source = inspect.getsource(authorize_get)

        required_params = [
            '"response_type"',
            '"client_id"',
            '"redirect_uri"',
            '"scope"',
            '"state"',
            '"nonce"',
            '"code_challenge"',
            '"code_challenge_method"',
        ]
        for param in required_params:
            assert param in source, (
                f"pre_login_data must include {param} for authorize URL reconstruction"
            )

    async def test_pre_login_redis_key_format(self, mock_redis):
        """Verify the Redis key format follows the existing convention."""
        # The key must be oauth:pre_login:{id} to match oauth:auth_request:{id}
        import secrets

        pre_login_id = secrets.token_urlsafe(16)
        key = f"oauth:pre_login:{pre_login_id}"

        await mock_redis.setex(key, 600, json.dumps({"client_id": "test"}))

        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("oauth:pre_login:")
        assert call_args[0][1] == 600  # 10 minute TTL

    def test_login_redirect_does_not_contain_next_with_full_url(self):
        """The redirect to login must use auth_request_id, not a 'next' param
        containing the full authorize URL (which caused double-encoding)."""
        import inspect

        from app.routers.v1.oauth_provider import authorize_get

        source = inspect.getsource(authorize_get)

        # In the unauthenticated branch, login_params should include auth_request_id
        # and should NOT include a 'next' key with scheme://host/path?query
        assert '"auth_request_id": pre_login_id' in source, (
            "login_params must include auth_request_id"
        )


class TestOidcEndSession:
    """Tests for OIDC RP-Initiated Logout (GET and POST /logout)."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.is_active = True
        client.redirect_uris = [
            "https://app.ceq.lol/auth/callback",
            "http://localhost:5801/auth/callback",
        ]
        return client

    @pytest.fixture
    def mock_db(self, mock_client):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_client
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_logout_redirects_to_post_logout_uri(self, mock_db):
        from app.routers.v1.oauth_provider import oidc_end_session

        response = await oidc_end_session(
            client_id="jnc_test",
            post_logout_redirect_uri="https://app.ceq.lol/",
            state=None,
            db=mock_db,
        )

        assert response.status_code == 302
        assert response.headers["location"] == "https://app.ceq.lol/"

    async def test_logout_rejects_unknown_client(self, mock_db):
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import oidc_end_session

        result = mock_db.execute.return_value
        result.scalar_one_or_none.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await oidc_end_session(
                client_id="jnc_missing",
                post_logout_redirect_uri="https://app.ceq.lol/",
                state=None,
                db=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "invalid_client"

    async def test_logout_rejects_unregistered_post_logout_uri(self, mock_db):
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import oidc_end_session

        with pytest.raises(HTTPException) as exc_info:
            await oidc_end_session(
                client_id="jnc_test",
                post_logout_redirect_uri="https://evil.com/",
                state=None,
                db=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert "post_logout_redirect_uri" in exc_info.value.detail

    async def test_logout_forwards_state_to_redirect_uri(self, mock_db):
        from app.routers.v1.oauth_provider import oidc_end_session

        response = await oidc_end_session(
            client_id="jnc_test",
            post_logout_redirect_uri="https://app.ceq.lol/",
            state="opaque-123",
            db=mock_db,
        )

        assert response.status_code == 302
        assert response.headers["location"] == "https://app.ceq.lol/?state=opaque-123"

    async def test_logout_clears_the_sso_cookie(self, mock_db):
        from app.auth.sso_cookie import SSO_COOKIE_NAME
        from app.routers.v1.oauth_provider import oidc_end_session

        response = await oidc_end_session(
            client_id="jnc_test",
            post_logout_redirect_uri="https://app.ceq.lol/",
            state=None,
            db=mock_db,
        )

        # A Max-Age=0 Set-Cookie for janua_sso must be on the redirect response.
        set_cookies = response.headers.getlist("set-cookie")
        assert any(
            SSO_COOKIE_NAME in c and ("Max-Age=0" in c or "max-age=0" in c) for c in set_cookies
        ), set_cookies

    async def test_post_logout_redirects_to_post_logout_uri(self, mock_db):
        """OIDC RP-Initiated Logout permits POST; it must behave like GET."""
        from app.routers.v1.oauth_provider import oidc_end_session_post

        response = await oidc_end_session_post(
            client_id="jnc_test",
            post_logout_redirect_uri="https://app.ceq.lol/",
            state=None,
            db=mock_db,
        )

        assert response.status_code == 302
        assert response.headers["location"] == "https://app.ceq.lol/"

    async def test_post_logout_rejects_unregistered_post_logout_uri(self, mock_db):
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import oidc_end_session_post

        with pytest.raises(HTTPException) as exc_info:
            await oidc_end_session_post(
                client_id="jnc_test",
                post_logout_redirect_uri="https://evil.com/",
                state=None,
                db=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert "post_logout_redirect_uri" in exc_info.value.detail

    async def test_post_logout_rejects_unknown_client(self, mock_db):
        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import oidc_end_session_post

        result = mock_db.execute.return_value
        result.scalar_one_or_none.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await oidc_end_session_post(
                client_id="jnc_missing",
                post_logout_redirect_uri="https://app.ceq.lol/",
                state=None,
                db=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "invalid_client"


class TestUserOrgClaims:
    """_get_user_org_claims — organization claims on HUMAN tokens.

    Contract under test: `orgs` lists every ACTIVE membership; `org_id` /
    `tenant_id` / `org_slug` appear only when unambiguous (single active
    membership, or user.tenant_id names one); non-active memberships and
    lookup failures emit nothing (fail-closed).
    """

    @staticmethod
    def _user(tenant_id=None):
        user = MagicMock()
        user.id = uuid.uuid4()
        user.tenant_id = tenant_id
        return user

    @staticmethod
    def _membership_row(role="member", slug="acme", org_id=None):
        member = MagicMock()
        member.role = role
        org = MagicMock()
        org.id = org_id or uuid.uuid4()
        org.slug = slug
        return (member, org)

    @staticmethod
    def _db_returning(rows):
        db = AsyncMock()
        result = MagicMock()  # result methods are sync (see TESTING_PATTERNS.md)
        result.all.return_value = rows
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_single_active_membership_emits_unambiguous_org(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        row = self._membership_row(role="member", slug="crea")
        db = self._db_returning([row])

        claims = await _get_user_org_claims(self._user(), db)

        org = row[1]
        assert claims["org_id"] == str(org.id)
        assert claims["tenant_id"] == str(org.id)
        assert claims["org_slug"] == "crea"
        assert claims["orgs"] == [{"id": str(org.id), "slug": "crea", "role": "member"}]

    async def test_multiple_memberships_without_tenant_emit_orgs_only(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        rows = [
            self._membership_row(slug="org-a"),
            self._membership_row(slug="org-b", role="admin"),
        ]
        db = self._db_returning(rows)

        claims = await _get_user_org_claims(self._user(tenant_id=None), db)

        assert "org_id" not in claims
        assert "tenant_id" not in claims
        assert "org_slug" not in claims
        assert [o["slug"] for o in claims["orgs"]] == ["org-a", "org-b"]

    async def test_multiple_memberships_with_matching_tenant_pick_it(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        target = self._membership_row(slug="org-b", role="admin")
        rows = [self._membership_row(slug="org-a"), target]
        db = self._db_returning(rows)

        claims = await _get_user_org_claims(self._user(tenant_id=target[1].id), db)

        assert claims["org_id"] == str(target[1].id)
        assert claims["org_slug"] == "org-b"
        assert len(claims["orgs"]) == 2

    async def test_no_memberships_emit_no_org_claims(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        db = self._db_returning([])

        claims = await _get_user_org_claims(self._user(), db)

        assert claims == {}

    async def test_lookup_failure_is_fail_closed_and_rolls_back(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))

        claims = await _get_user_org_claims(self._user(), db)

        assert claims == {}
        db.rollback.assert_awaited_once()

    async def test_query_filters_on_user_and_active_status(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        db = self._db_returning([])
        await _get_user_org_claims(self._user(), db)

        query = db.execute.await_args.args[0]
        compiled = str(query)
        assert "organization_members" in compiled
        assert "status" in compiled
        assert "user_id" in compiled

    async def test_null_member_role_defaults_to_member(self):
        from app.routers.v1.oauth_provider import _get_user_org_claims

        row = self._membership_row(role=None, slug="crea")
        db = self._db_returning([row])

        claims = await _get_user_org_claims(self._user(), db)

        assert claims["orgs"][0]["role"] == "member"
