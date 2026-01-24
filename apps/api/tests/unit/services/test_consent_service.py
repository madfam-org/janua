"""
Tests for app/services/consent_service.py - OAuth Consent Service

Tests consent management for OAuth clients.
Target: 34% → 90% coverage.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.consent_service import ConsentService

pytestmark = pytest.mark.asyncio


class TestParseScopes:
    """Test scope parsing functionality."""

    def test_parse_standard_scopes(self):
        """Test parsing standard OAuth scopes."""
        scopes = ConsentService.parse_scopes("openid profile email")
        assert scopes == {"openid", "profile", "email"}

    def test_parse_empty_string(self):
        """Test parsing empty string returns empty set."""
        scopes = ConsentService.parse_scopes("")
        assert scopes == set()

    def test_parse_none_returns_empty_set(self):
        """Test parsing None returns empty set."""
        scopes = ConsentService.parse_scopes(None)
        assert scopes == set()

    def test_parse_single_scope(self):
        """Test parsing single scope."""
        scopes = ConsentService.parse_scopes("openid")
        assert scopes == {"openid"}

    def test_parse_with_extra_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        scopes = ConsentService.parse_scopes("  openid   profile  ")
        assert scopes == {"openid", "profile"}

    def test_parse_custom_scopes(self):
        """Test parsing custom application scopes."""
        scopes = ConsentService.parse_scopes("read:user write:user read:org")
        assert scopes == {"read:user", "write:user", "read:org"}

    def test_parse_duplicate_scopes(self):
        """Test parsing duplicate scopes returns unique set."""
        scopes = ConsentService.parse_scopes("openid openid profile openid")
        assert scopes == {"openid", "profile"}


class TestHasConsent:
    """Test has_consent method for checking existing consents."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    @pytest.fixture
    def client_id(self):
        """Test OAuth client ID."""
        return "test-client-id"

    async def test_has_consent_returns_true_when_all_scopes_covered(self, mock_db, user_id, client_id):
        """Test returns True when user has consented to all requested scopes."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile", "email"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.has_consent(
            mock_db,
            user_id,
            client_id,
            {"openid", "profile"},
        )

        assert result is True

    async def test_has_consent_returns_false_when_no_consent_exists(self, mock_db, user_id, client_id):
        """Test returns False when no consent record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await ConsentService.has_consent(
            mock_db,
            user_id,
            client_id,
            {"openid"},
        )

        assert result is False

    async def test_has_consent_returns_false_when_consent_expired(self, mock_db, user_id, client_id):
        """Test returns False when consent has expired."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = datetime.utcnow() - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.has_consent(
            mock_db,
            user_id,
            client_id,
            {"openid"},
        )

        assert result is False

    async def test_has_consent_returns_false_when_scope_missing(self, mock_db, user_id, client_id):
        """Test returns False when requested scope not in consent."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.has_consent(
            mock_db,
            user_id,
            client_id,
            {"openid", "email"},  # email not in consent
        )

        assert result is False

    async def test_has_consent_with_none_scopes_in_consent(self, mock_db, user_id, client_id):
        """Test handles consent record with None scopes."""
        mock_consent = MagicMock()
        mock_consent.scopes = None
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.has_consent(
            mock_db,
            user_id,
            client_id,
            {"openid"},
        )

        assert result is False


class TestGetMissingScopes:
    """Test get_missing_scopes method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    @pytest.fixture
    def client_id(self):
        """Test OAuth client ID."""
        return "test-client-id"

    async def test_returns_all_scopes_when_no_consent(self, mock_db, user_id, client_id):
        """Test returns all requested scopes when no consent exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await ConsentService.get_missing_scopes(
            mock_db,
            user_id,
            client_id,
            {"openid", "profile", "email"},
        )

        assert result == {"openid", "profile", "email"}

    async def test_returns_empty_when_all_consented(self, mock_db, user_id, client_id):
        """Test returns empty set when all scopes already consented."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile", "email"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.get_missing_scopes(
            mock_db,
            user_id,
            client_id,
            {"openid", "profile"},
        )

        assert result == set()

    async def test_returns_only_missing_scopes(self, mock_db, user_id, client_id):
        """Test returns only the scopes not yet consented."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.get_missing_scopes(
            mock_db,
            user_id,
            client_id,
            {"openid", "profile", "email", "offline_access"},
        )

        assert result == {"email", "offline_access"}

    async def test_returns_all_when_consent_expired(self, mock_db, user_id, client_id):
        """Test returns all scopes when consent has expired."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid", "profile"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = datetime.utcnow() - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.get_missing_scopes(
            mock_db,
            user_id,
            client_id,
            {"openid", "profile"},
        )

        assert result == {"openid", "profile"}


class TestGrantConsent:
    """Test grant_consent method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    @pytest.fixture
    def client_id(self):
        """Test OAuth client ID."""
        return "test-client-id"

    async def test_creates_new_consent_when_none_exists(self, mock_db, user_id, client_id):
        """Test creates new consent when no previous consent."""
        # First query returns None (no existing consent)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Patch at module level to avoid SQLAlchemy issues
        with patch("app.services.consent_service.select"):
            with patch("app.services.consent_service.UserConsent") as MockConsent:
                mock_consent_instance = MagicMock()
                mock_consent_instance.scopes = ["openid", "profile"]
                MockConsent.return_value = mock_consent_instance

                result = await ConsentService.grant_consent(
                    mock_db,
                    user_id,
                    client_id,
                    {"openid", "profile"},
                )

                MockConsent.assert_called_once()
                mock_db.add.assert_called_once_with(mock_consent_instance)
                mock_db.commit.assert_called_once()

    async def test_updates_existing_consent(self, mock_db, user_id, client_id):
        """Test updates existing consent with new scopes."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid"]
        mock_consent.revoked_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.grant_consent(
            mock_db,
            user_id,
            client_id,
            {"profile", "email"},
        )

        # Should merge scopes
        assert set(mock_consent.scopes) == {"openid", "profile", "email"}
        mock_db.commit.assert_called_once()

    async def test_unrevokes_previously_revoked_consent(self, mock_db, user_id, client_id):
        """Test clears revoked_at when granting new consent."""
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid"]
        mock_consent.revoked_at = datetime.utcnow() - timedelta(days=1)
        mock_consent.expires_at = datetime.utcnow() + timedelta(days=30)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        await ConsentService.grant_consent(
            mock_db,
            user_id,
            client_id,
            {"profile"},
        )

        assert mock_consent.revoked_at is None
        assert mock_consent.expires_at is None

    async def test_returns_consent_record(self, mock_db, user_id, client_id):
        """Test returns the consent record after granting."""
        mock_consent = MagicMock()
        mock_consent.scopes = []
        mock_consent.revoked_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.grant_consent(
            mock_db,
            user_id,
            client_id,
            {"openid"},
        )

        assert result == mock_consent


class TestRevokeConsent:
    """Test revoke_consent method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    @pytest.fixture
    def client_id(self):
        """Test OAuth client ID."""
        return "test-client-id"

    async def test_revokes_existing_consent(self, mock_db, user_id, client_id):
        """Test successfully revokes existing consent."""
        mock_consent = MagicMock()
        mock_consent.revoked_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        result = await ConsentService.revoke_consent(mock_db, user_id, client_id)

        assert result is True
        assert mock_consent.revoked_at is not None
        mock_db.commit.assert_called_once()

    async def test_returns_false_when_no_consent_exists(self, mock_db, user_id, client_id):
        """Test returns False when no consent to revoke."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await ConsentService.revoke_consent(mock_db, user_id, client_id)

        assert result is False


class TestListConsents:
    """Test list_consents method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    async def test_returns_all_active_consents(self, mock_db, user_id):
        """Test returns list of all active consents for user."""
        mock_consent1 = MagicMock()
        mock_consent1.client_id = "client1"
        mock_consent2 = MagicMock()
        mock_consent2.client_id = "client2"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_consent1, mock_consent2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await ConsentService.list_consents(mock_db, user_id)

        assert len(result) == 2
        assert result[0].client_id == "client1"
        assert result[1].client_id == "client2"

    async def test_returns_empty_list_when_no_consents(self, mock_db, user_id):
        """Test returns empty list when user has no consents."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await ConsentService.list_consents(mock_db, user_id)

        assert result == []


class TestGetScopeDescriptions:
    """Test get_scope_descriptions method."""

    def test_returns_scope_descriptions_dict(self):
        """Test returns dictionary of scope descriptions."""
        descriptions = ConsentService.get_scope_descriptions()

        assert isinstance(descriptions, dict)
        assert len(descriptions) > 0

    def test_includes_standard_oidc_scopes(self):
        """Test includes standard OIDC scopes."""
        descriptions = ConsentService.get_scope_descriptions()

        assert "openid" in descriptions
        assert "profile" in descriptions
        assert "email" in descriptions

    def test_includes_offline_access_scope(self):
        """Test includes offline_access scope."""
        descriptions = ConsentService.get_scope_descriptions()

        assert "offline_access" in descriptions

    def test_includes_custom_scopes(self):
        """Test includes custom application scopes."""
        descriptions = ConsentService.get_scope_descriptions()

        assert "read:user" in descriptions
        assert "write:user" in descriptions
        assert "read:org" in descriptions
        assert "write:org" in descriptions

    def test_descriptions_are_tuples(self):
        """Test each description is a tuple with name and description."""
        descriptions = ConsentService.get_scope_descriptions()

        for scope, desc in descriptions.items():
            assert isinstance(desc, tuple)
            assert len(desc) == 2
            assert isinstance(desc[0], str)  # Name
            assert isinstance(desc[1], str)  # Description

    def test_openid_scope_description(self):
        """Test openid scope has correct description."""
        descriptions = ConsentService.get_scope_descriptions()

        openid = descriptions["openid"]
        assert "OpenID" in openid[0]
        assert "identity" in openid[1].lower()

    def test_email_scope_description(self):
        """Test email scope has correct description."""
        descriptions = ConsentService.get_scope_descriptions()

        email = descriptions["email"]
        assert "Email" in email[0]
        assert "email" in email[1].lower()


class TestConsentServiceIntegration:
    """Integration tests for consent service workflows."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session with full capabilities."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def user_id(self):
        """Generate test user ID."""
        return uuid4()

    async def test_grant_then_check_consent_workflow(self, mock_db, user_id):
        """Test granting consent then checking it."""
        client_id = "workflow-test-client"

        # Setup consent that will be created and then checked
        new_consent = MagicMock()
        new_consent.scopes = ["openid", "profile"]
        new_consent.revoked_at = None
        new_consent.expires_at = None

        mock_result = MagicMock()
        # Initially no consent
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Patch select to avoid SQLAlchemy issues
        with patch("app.services.consent_service.select"):
            with patch("app.services.consent_service.UserConsent") as MockConsent:
                MockConsent.return_value = new_consent

                await ConsentService.grant_consent(
                    mock_db,
                    user_id,
                    client_id,
                    {"openid", "profile"},
                )

        # After grant, consent exists
        mock_result.scalar_one_or_none.return_value = new_consent

        with patch("app.services.consent_service.select"):
            has_consent = await ConsentService.has_consent(
                mock_db,
                user_id,
                client_id,
                {"openid"},
            )

        assert has_consent is True

    async def test_incremental_consent_workflow(self, mock_db, user_id):
        """Test adding scopes incrementally to existing consent."""
        client_id = "incremental-test-client"

        # Initial consent with basic scopes
        mock_consent = MagicMock()
        mock_consent.scopes = ["openid"]
        mock_consent.revoked_at = None
        mock_consent.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_result

        # Grant additional scopes
        await ConsentService.grant_consent(
            mock_db,
            user_id,
            client_id,
            {"profile", "email"},
        )

        # Verify scopes were merged
        assert "openid" in mock_consent.scopes
        assert "profile" in mock_consent.scopes
        assert "email" in mock_consent.scopes
