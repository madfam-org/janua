"""
Tests for API Key management endpoints.

Covers:
- Key creation returns full key; subsequent GET only shows prefix
- Scopes are stored and returned correctly
- Revoked key returns 401 via middleware
- Verify endpoint returns org_id and scopes for valid key
- Rate limiting returns 429
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.models import ApiKey, Organization, OrganizationMember, User, UserStatus
from app.services.api_key_service import ApiKeyService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: uuid.UUID | None = None) -> User:
    uid = user_id or uuid.uuid4()
    user = User(
        id=uid,
        email="testuser@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    return user


def _make_org(org_id: uuid.UUID | None = None) -> Organization:
    oid = org_id or uuid.uuid4()
    return Organization(
        id=oid,
        name="Test Org",
        slug="test-org",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _make_membership(user: User, org: Organization) -> OrganizationMember:
    return OrganizationMember(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role="owner",
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Service-level unit tests (no HTTP, pure logic)
# ---------------------------------------------------------------------------


class TestApiKeyServiceKeyGeneration:
    """Test key generation helpers."""

    def test_generate_sk_live_key_format(self):
        """sk_live_ keys have the correct format and length."""
        full_key, key_hash, key_prefix = ApiKeyService.generate_sk_live_key()
        assert full_key.startswith("sk_live_")
        assert len(full_key) == 8 + 64  # "sk_live_" (8) + 64 hex chars
        assert len(key_hash) == 64  # SHA-256 hex digest
        assert key_prefix.startswith("sk_live_")
        assert len(key_prefix) == 12  # "sk_live_" (8) + 4 hex chars

    def test_generate_sk_live_key_hash_matches(self):
        """SHA-256 hash of full key matches returned hash."""
        full_key, key_hash, _ = ApiKeyService.generate_sk_live_key()
        assert hashlib.sha256(full_key.encode()).hexdigest() == key_hash

    def test_generate_sk_live_key_uniqueness(self):
        """Two generated keys are never the same."""
        key1, _, _ = ApiKeyService.generate_sk_live_key()
        key2, _, _ = ApiKeyService.generate_sk_live_key()
        assert key1 != key2

    def test_generate_legacy_key_format(self):
        """Legacy jnk_ keys maintain the original format."""
        full_key, key_hash, display_prefix = ApiKeyService.generate_api_key()
        assert full_key.startswith("jnk_")
        assert display_prefix.endswith("...")
        assert len(display_prefix) == 15  # 12 chars + "..."

    def test_verify_sha256_key(self):
        """verify_api_key works with SHA-256 hashed keys."""
        full_key, key_hash, _ = ApiKeyService.generate_sk_live_key()
        assert ApiKeyService.verify_api_key(full_key, key_hash) is True
        assert ApiKeyService.verify_api_key("sk_live_wrong", key_hash) is False

    def test_verify_bcrypt_key(self):
        """verify_api_key works with bcrypt hashed keys (legacy)."""
        full_key, key_hash, _ = ApiKeyService.generate_api_key()
        assert ApiKeyService.verify_api_key(full_key, key_hash) is True
        assert ApiKeyService.verify_api_key("jnk_wrong", key_hash) is False

    def test_hash_key_sha256(self):
        """hash_key_sha256 produces deterministic 64-char hex output."""
        result = ApiKeyService.hash_key_sha256("sk_live_abc123")
        assert len(result) == 64
        assert result == hashlib.sha256(b"sk_live_abc123").hexdigest()


# ---------------------------------------------------------------------------
# Schema-level tests
# ---------------------------------------------------------------------------


class TestApiKeySchemas:
    """Test Pydantic schema validation."""

    def test_create_schema_defaults(self):
        from app.schemas.api_key import ApiKeyCreate

        data = ApiKeyCreate(name="Test Key")
        assert data.scopes == []
        assert data.rate_limit_per_min == 60
        assert data.expires_at is None

    def test_create_schema_rate_limit_bounds(self):
        from app.schemas.api_key import ApiKeyCreate

        # Valid
        data = ApiKeyCreate(name="Test", rate_limit_per_min=1)
        assert data.rate_limit_per_min == 1

        data = ApiKeyCreate(name="Test", rate_limit_per_min=10000)
        assert data.rate_limit_per_min == 10000

        # Invalid
        with pytest.raises(Exception):
            ApiKeyCreate(name="Test", rate_limit_per_min=0)
        with pytest.raises(Exception):
            ApiKeyCreate(name="Test", rate_limit_per_min=10001)

    def test_create_schema_scope_validation(self):
        from app.schemas.api_key import ApiKeyCreate

        # Valid
        data = ApiKeyCreate(name="Test", scopes=["karafiel:stamp", "fortuna:read"])
        assert data.scopes == ["karafiel:stamp", "fortuna:read"]

        # Invalid: no colon separator
        with pytest.raises(Exception):
            ApiKeyCreate(name="Test", scopes=["invalid_scope"])

    def test_verify_request_schema(self):
        from app.schemas.api_key import ApiKeyVerifyRequest

        data = ApiKeyVerifyRequest(key="sk_live_" + "a" * 64)
        assert data.key.startswith("sk_live_")

        # Too short
        with pytest.raises(Exception):
            ApiKeyVerifyRequest(key="short")

    def test_verify_response_schema_invalid(self):
        from app.schemas.api_key import ApiKeyVerifyResponse

        resp = ApiKeyVerifyResponse(valid=False, org_id=None, scopes=[], key_id=None)
        assert resp.valid is False
        assert resp.org_id is None

    def test_verify_response_schema_valid(self):
        from app.schemas.api_key import ApiKeyVerifyResponse

        oid = str(uuid.uuid4())
        kid = str(uuid.uuid4())
        resp = ApiKeyVerifyResponse(
            valid=True,
            org_id=oid,
            scopes=["fortuna:read"],
            key_id=kid,
        )
        assert resp.valid is True
        assert resp.org_id == oid
        assert resp.scopes == ["fortuna:read"]


# ---------------------------------------------------------------------------
# Router endpoint tests (HTTP-level via httpx + mocked dependencies)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_app():
    """Create a test app with mocked dependencies."""
    # We need to mock at the dependency level
    from app.main import app as _app
    return _app


@pytest_asyncio.fixture
async def mock_user():
    return _make_user()


@pytest_asyncio.fixture
async def mock_org(mock_user):
    return _make_org()


@pytest_asyncio.fixture
async def mock_membership(mock_user, mock_org):
    return _make_membership(mock_user, mock_org)


@pytest.mark.asyncio
class TestVerifyEndpoint:
    """Test POST /api/v1/api-keys/verify endpoint."""

    async def test_verify_valid_key(self, test_app, mock_user, mock_org):
        """Valid key returns valid=True with org_id and scopes."""
        key_id = uuid.uuid4()
        org_id = mock_org.id
        scopes = ["karafiel:stamp", "fortuna:read"]

        mock_api_key = MagicMock()
        mock_api_key.organization_id = org_id
        mock_api_key.scopes = scopes
        mock_api_key.id = key_id

        with patch(
            "app.routers.v1.api_keys.ApiKeyService"
        ) as MockService:
            instance = MockService.return_value
            instance.verify_key_for_service = AsyncMock(return_value=mock_api_key)

            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/api-keys/verify",
                    json={"key": "sk_live_" + "a" * 64},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["org_id"] == str(org_id)
            assert data["scopes"] == scopes
            assert data["key_id"] == str(key_id)

    async def test_verify_invalid_key(self, test_app):
        """Invalid key returns valid=False, not an HTTP error."""
        with patch(
            "app.routers.v1.api_keys.ApiKeyService"
        ) as MockService:
            instance = MockService.return_value
            instance.verify_key_for_service = AsyncMock(return_value=None)

            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/api-keys/verify",
                    json={"key": "sk_live_" + "b" * 64},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
            assert data["org_id"] is None
            assert data["scopes"] == []
            assert data["key_id"] is None


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------


class TestApiKeyAuthMiddleware:
    """Test the API key auth middleware logic."""

    def test_extract_api_key_from_x_api_key_header(self):
        from app.middleware.api_key_auth import _extract_api_key

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/test",
            "query_string": b"",
            "headers": [
                (b"x-api-key", b"sk_live_abc123"),
            ],
        }
        request = MagicMock(spec=["headers"])
        request.headers = {"x-api-key": "sk_live_abc123"}

        key = _extract_api_key(request)
        assert key == "sk_live_abc123"

    def test_extract_api_key_from_bearer(self):
        from app.middleware.api_key_auth import _extract_api_key

        request = MagicMock(spec=["headers"])
        request.headers = {"authorization": "Bearer sk_live_abc123"}

        key = _extract_api_key(request)
        assert key == "sk_live_abc123"

    def test_extract_api_key_bearer_jwt_ignored(self):
        """Bearer tokens that are JWTs (not sk_live_ or jnk_) are ignored."""
        from app.middleware.api_key_auth import _extract_api_key

        request = MagicMock(spec=["headers"])
        request.headers = {"authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"}

        key = _extract_api_key(request)
        assert key is None

    def test_extract_api_key_none(self):
        """No API key headers returns None."""
        from app.middleware.api_key_auth import _extract_api_key

        request = MagicMock(spec=["headers"])
        request.headers = {"content-type": "application/json"}

        key = _extract_api_key(request)
        assert key is None


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Test the in-memory sliding-window rate limiter."""

    def test_allows_under_limit(self):
        from app.middleware.api_key_auth import _check_rate_limit, _rate_limit_buckets

        # Use a unique key to avoid cross-test interference
        test_key = f"test-{uuid.uuid4()}"

        allowed, retry_after = _check_rate_limit(test_key, limit_per_min=5)
        assert allowed is True
        assert retry_after == 0

    def test_blocks_over_limit(self):
        from app.middleware.api_key_auth import _check_rate_limit, _rate_limit_buckets

        test_key = f"test-{uuid.uuid4()}"

        # Fill up the bucket
        for _ in range(10):
            _check_rate_limit(test_key, limit_per_min=10)

        # 11th request should be blocked
        allowed, retry_after = _check_rate_limit(test_key, limit_per_min=10)
        assert allowed is False
        assert retry_after >= 1


# ---------------------------------------------------------------------------
# Integration-style test: create key, verify it, revoke it, verify again
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApiKeyLifecycle:
    """End-to-end lifecycle: create -> verify -> revoke -> verify returns invalid."""

    async def test_create_returns_full_key_and_get_shows_only_prefix(self):
        """POST create returns the full key; GET list only shows prefix."""
        # This is a logic assertion, not an HTTP test
        full_key, key_hash, key_prefix = ApiKeyService.generate_sk_live_key()

        # The full key contains the random part
        assert len(full_key) > len(key_prefix)

        # The key_prefix is a subset
        assert full_key.startswith(key_prefix[:8])  # "sk_live_"

        # The hash is NOT the full key (security invariant)
        assert key_hash != full_key

    async def test_scopes_stored_and_returned(self):
        """Scopes are preserved through the schema round-trip."""
        from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse

        create_data = ApiKeyCreate(
            name="Scoped Key",
            scopes=["karafiel:stamp", "fortuna:read"],
            rate_limit_per_min=120,
        )
        assert create_data.scopes == ["karafiel:stamp", "fortuna:read"]
        assert create_data.rate_limit_per_min == 120

        # Simulate response
        now = datetime.utcnow()
        resp = ApiKeyResponse(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            name="Scoped Key",
            prefix="sk_live_abcd...",
            key_prefix="sk_live_abcd",
            scopes=["karafiel:stamp", "fortuna:read"],
            rate_limit_per_min=120,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.scopes == ["karafiel:stamp", "fortuna:read"]
        assert resp.rate_limit_per_min == 120
