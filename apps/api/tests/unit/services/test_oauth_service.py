"""
Comprehensive OAuth Service Test Suite
Tests OAuth provider configuration, authorization URL generation,
token exchange, user info normalization, and user creation flows.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class TestProviderConfiguration:
    """Test OAuth provider configuration retrieval"""

    def test_get_google_provider_config(self):
        """Should return Google provider configuration"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "google_client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "google_secret"

            config = OAuthService.get_provider_config(OAuthProvider.GOOGLE)

            assert config is not None
            assert config["client_id"] == "google_client_id"
            assert config["client_secret"] == "google_secret"
            assert "accounts.google.com" in config["auth_url"]

    def test_get_github_provider_config(self):
        """Should return GitHub provider configuration"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GITHUB_CLIENT_ID = "github_client_id"
            mock_settings.OAUTH_GITHUB_CLIENT_SECRET = "github_secret"

            config = OAuthService.get_provider_config(OAuthProvider.GITHUB)

            assert config is not None
            assert config["client_id"] == "github_client_id"
            assert "github.com" in config["auth_url"]

    def test_get_microsoft_provider_config(self):
        """Should return Microsoft provider configuration"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_MICROSOFT_CLIENT_ID = "ms_client_id"
            mock_settings.OAUTH_MICROSOFT_CLIENT_SECRET = "ms_secret"

            config = OAuthService.get_provider_config(OAuthProvider.MICROSOFT)

            assert config is not None
            assert "microsoftonline.com" in config["auth_url"]

    def test_get_unconfigured_provider(self):
        """Should return None for unconfigured provider"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = None
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = None

            config = OAuthService.get_provider_config(OAuthProvider.GOOGLE)

            assert config is None

    def test_get_discord_provider_config(self):
        """Should return Discord provider configuration"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_DISCORD_CLIENT_ID = "discord_id"
            mock_settings.OAUTH_DISCORD_CLIENT_SECRET = "discord_secret"

            config = OAuthService.get_provider_config(OAuthProvider.DISCORD)

            assert config is not None
            assert urlparse(config["auth_url"]).netloc.endswith("discord.com")

    def test_get_linkedin_provider_config(self):
        """Should return LinkedIn provider configuration"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_LINKEDIN_CLIENT_ID = "linkedin_id"
            mock_settings.OAUTH_LINKEDIN_CLIENT_SECRET = "linkedin_secret"

            config = OAuthService.get_provider_config(OAuthProvider.LINKEDIN)

            assert config is not None
            assert urlparse(config["auth_url"]).netloc.endswith("linkedin.com")


class TestStateTokenGeneration:
    """Test OAuth state token generation"""

    def test_generate_state_token_length(self):
        """State token should be sufficiently long"""
        from app.services.oauth import OAuthService

        token = OAuthService.generate_state_token()

        assert len(token) >= 32

    def test_generate_state_token_uniqueness(self):
        """Each state token should be unique"""
        from app.services.oauth import OAuthService

        tokens = {OAuthService.generate_state_token() for _ in range(100)}

        assert len(tokens) == 100

    def test_generate_state_token_url_safe(self):
        """State token should be URL-safe"""
        from app.services.oauth import OAuthService

        token = OAuthService.generate_state_token()

        # URL-safe characters
        assert all(c.isalnum() or c in "-_" for c in token)


class TestAuthorizationUrlGeneration:
    """Test OAuth authorization URL generation"""

    def test_google_auth_url(self):
        """Should generate valid Google authorization URL"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "google_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "google_secret"

            url = OAuthService.get_authorization_url(
                OAuthProvider.GOOGLE,
                redirect_uri="https://app.example.com/callback",
                state="test_state",
            )

            assert url is not None
            assert urlparse(url).netloc == "accounts.google.com"
            assert "client_id=google_id" in url
            assert "state=test_state" in url
            assert "redirect_uri=" in url
            assert "access_type=offline" in url  # Google-specific

    def test_github_auth_url(self):
        """Should generate valid GitHub authorization URL"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GITHUB_CLIENT_ID = "github_id"
            mock_settings.OAUTH_GITHUB_CLIENT_SECRET = "github_secret"

            url = OAuthService.get_authorization_url(
                OAuthProvider.GITHUB,
                redirect_uri="https://app.example.com/callback",
                state="test_state",
            )

            assert url is not None
            assert urlparse(url).netloc == "github.com"
            # GitHub scope may be URL-encoded
            assert "user" in url and "email" in url

    def test_auth_url_with_additional_scopes(self):
        """Should include additional scopes"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "google_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "google_secret"

            url = OAuthService.get_authorization_url(
                OAuthProvider.GOOGLE,
                redirect_uri="https://app.example.com/callback",
                state="test_state",
                additional_scopes=["calendar.readonly"],
            )

            assert "calendar.readonly" in url

    def test_auth_url_unconfigured_provider(self):
        """Should return None for unconfigured provider"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = None
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = None

            url = OAuthService.get_authorization_url(
                OAuthProvider.GOOGLE,
                redirect_uri="https://app.example.com/callback",
                state="test_state",
            )

            assert url is None

    def test_microsoft_auth_url_response_mode(self):
        """Microsoft should include response_mode parameter"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_MICROSOFT_CLIENT_ID = "ms_id"
            mock_settings.OAUTH_MICROSOFT_CLIENT_SECRET = "ms_secret"

            url = OAuthService.get_authorization_url(
                OAuthProvider.MICROSOFT,
                redirect_uri="https://app.example.com/callback",
                state="test_state",
            )

            assert "response_mode=query" in url


class TestTokenExchange:
    """Test OAuth token exchange"""

    async def test_successful_token_exchange(self):
        """Should exchange code for tokens successfully"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "access_token": "access_123",
                "refresh_token": "refresh_123",
                "expires_in": 3600,
            }
        )

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                tokens = await OAuthService.exchange_code_for_tokens(
                    OAuthProvider.GOOGLE, "auth_code", "https://app.example.com/callback"
                )

                assert tokens is not None
                assert tokens["access_token"] == "access_123"
                assert tokens["refresh_token"] == "refresh_123"

    async def test_failed_token_exchange(self):
        """Should return None on failed exchange"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid code"

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                tokens = await OAuthService.exchange_code_for_tokens(
                    OAuthProvider.GOOGLE, "invalid_code", "https://app.example.com/callback"
                )

                assert tokens is None

    async def test_token_exchange_network_error(self):
        """Should handle network errors gracefully"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("Network error")
                )

                tokens = await OAuthService.exchange_code_for_tokens(
                    OAuthProvider.GOOGLE, "code", "https://app.example.com/callback"
                )

                assert tokens is None


class TestUserInfoRetrieval:
    """Test OAuth user info retrieval"""

    async def test_get_google_user_info(self):
        """Should retrieve and normalize Google user info"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "id": "google_123",
                "email": "user@gmail.com",
                "verified_email": True,
                "given_name": "John",
                "family_name": "Doe",
                "name": "John Doe",
                "picture": "https://lh3.googleusercontent.com/photo.jpg",
            }
        )

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                user_info = await OAuthService.get_user_info(
                    OAuthProvider.GOOGLE, "access_token"
                )

                assert user_info is not None
                assert user_info["provider"] == "google"
                assert user_info["email"] == "user@gmail.com"
                assert user_info["email_verified"] is True
                assert user_info["first_name"] == "John"
                assert user_info["last_name"] == "Doe"

    async def test_get_github_user_info_with_email(self):
        """Should retrieve GitHub user info including email"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json = MagicMock(
            return_value={
                "id": 12345,
                "login": "johndoe",
                "name": "John Doe",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "email": None,  # GitHub often doesn't include email here
            }
        )

        email_response = MagicMock()
        email_response.status_code = 200
        email_response.json = MagicMock(
            return_value=[
                {"email": "john@example.com", "primary": True, "verified": True},
                {"email": "john@work.com", "primary": False, "verified": True},
            ]
        )

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GITHUB_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GITHUB_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    side_effect=[user_response, email_response]
                )

                user_info = await OAuthService.get_user_info(
                    OAuthProvider.GITHUB, "access_token"
                )

                assert user_info is not None
                assert user_info["provider"] == "github"
                assert user_info["provider_user_id"] == "12345"
                assert user_info["email"] == "john@example.com"

    async def test_get_user_info_failure(self):
        """Should return None on failure"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            with patch("app.services.oauth.httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                user_info = await OAuthService.get_user_info(
                    OAuthProvider.GOOGLE, "invalid_token"
                )

                assert user_info is None


class TestNormalizeUserInfo:
    """Test user info normalization across providers"""

    def test_normalize_google_user_info(self):
        """Should normalize Google user info"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        raw_info = {
            "id": "google_123",
            "email": "user@gmail.com",
            "verified_email": True,
            "given_name": "John",
            "family_name": "Doe",
            "name": "John Doe",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
        }

        normalized = OAuthService.normalize_user_info(OAuthProvider.GOOGLE, raw_info)

        assert normalized["provider"] == "google"
        assert normalized["provider_user_id"] == "google_123"
        assert normalized["email"] == "user@gmail.com"
        assert normalized["email_verified"] is True
        assert normalized["first_name"] == "John"
        assert normalized["last_name"] == "Doe"
        assert normalized["profile_image_url"] == "https://lh3.googleusercontent.com/photo.jpg"

    def test_normalize_github_user_info(self):
        """Should normalize GitHub user info"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        raw_info = {
            "id": 12345,
            "email": "user@example.com",
            "name": "John Doe",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }

        normalized = OAuthService.normalize_user_info(OAuthProvider.GITHUB, raw_info)

        assert normalized["provider"] == "github"
        assert normalized["provider_user_id"] == "12345"
        assert normalized["email_verified"] is True  # GitHub only returns verified
        assert normalized["first_name"] == "John"
        assert normalized["last_name"] == "Doe"

    def test_normalize_microsoft_user_info(self):
        """Should normalize Microsoft user info"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        raw_info = {
            "id": "ms_123",
            "mail": "user@outlook.com",
            "givenName": "John",
            "surname": "Doe",
            "displayName": "John Doe",
        }

        normalized = OAuthService.normalize_user_info(OAuthProvider.MICROSOFT, raw_info)

        assert normalized["provider"] == "microsoft"
        assert normalized["email"] == "user@outlook.com"
        assert normalized["first_name"] == "John"
        assert normalized["last_name"] == "Doe"

    def test_normalize_discord_user_info(self):
        """Should normalize Discord user info with avatar URL"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        raw_info = {
            "id": "123456789",
            "email": "user@discord.com",
            "verified": True,
            "global_name": "JohnD",
            "username": "johndoe",
            "avatar": "abc123",
        }

        normalized = OAuthService.normalize_user_info(OAuthProvider.DISCORD, raw_info)

        assert normalized["provider"] == "discord"
        assert normalized["email_verified"] is True
        assert urlparse(normalized["profile_image_url"]).netloc == "cdn.discordapp.com"

    def test_normalize_linkedin_user_info(self):
        """Should normalize LinkedIn user info"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        raw_info = {
            "sub": "linkedin_123",
            "email": "user@linkedin.com",
            "email_verified": True,
            "given_name": "John",
            "family_name": "Doe",
            "name": "John Doe",
            "picture": "https://media.licdn.com/photo.jpg",
        }

        normalized = OAuthService.normalize_user_info(OAuthProvider.LINKEDIN, raw_info)

        assert normalized["provider"] == "linkedin"
        assert normalized["provider_user_id"] == "linkedin_123"


class TestParseScopes:
    """Test scope parsing from token responses"""

    def test_parse_comma_separated_scopes(self):
        """Should parse GitHub-style comma-separated scopes"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        tokens = {"scope": "user:email,repo,read:user"}

        scopes = OAuthService._parse_scopes_from_tokens(tokens, OAuthProvider.GITHUB)

        assert "user:email" in scopes
        assert "repo" in scopes
        assert "read:user" in scopes

    def test_parse_space_separated_scopes(self):
        """Should parse standard space-separated scopes"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        tokens = {"scope": "openid email profile"}

        scopes = OAuthService._parse_scopes_from_tokens(tokens, OAuthProvider.GOOGLE)

        assert "openid" in scopes
        assert "email" in scopes
        assert "profile" in scopes

    def test_parse_empty_scopes_falls_back_to_config(self):
        """Should fall back to configured scopes when not in response"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        tokens = {}

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_GOOGLE_CLIENT_ID = "client_id"
            mock_settings.OAUTH_GOOGLE_CLIENT_SECRET = "client_secret"

            scopes = OAuthService._parse_scopes_from_tokens(tokens, OAuthProvider.GOOGLE)

            assert len(scopes) > 0  # Should have default scopes


class TestFindOrCreateUser:
    """Test user finding/creation from OAuth info"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()
        return db

    def test_find_existing_oauth_account(self, mock_db):
        """Should find existing user via OAuth account"""
        from app.models import OAuthProvider, User
        from app.services.oauth import OAuthService

        existing_user = MagicMock(spec=User)
        existing_oauth = MagicMock()
        existing_oauth.user = existing_user
        existing_oauth.access_token = "old_token"

        mock_db.query.return_value.filter.return_value.first.return_value = (
            existing_oauth
        )

        user_info = {
            "provider_user_id": "oauth_123",
            "email": "user@example.com",
            "raw_data": {},
        }
        tokens = {"access_token": "new_token", "expires_in": 3600}

        user, is_new = OAuthService.find_or_create_user(
            mock_db, OAuthProvider.GOOGLE, user_info, tokens
        )

        assert user == existing_user
        assert is_new is False
        assert existing_oauth.access_token == "new_token"

    def test_link_oauth_to_existing_user(self, mock_db):
        """Should link OAuth to existing user with same email"""
        from app.models import OAuthProvider, User
        from app.services.oauth import OAuthService

        existing_user = MagicMock(spec=User)
        existing_user.id = uuid4()
        existing_user.first_name = None
        existing_user.last_name = None
        existing_user.profile_image_url = None
        existing_user.email_verified = False

        # No existing OAuth account
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,  # No OAuth account
            existing_user,  # Existing user with email
        ]

        user_info = {
            "provider_user_id": "oauth_123",
            "email": "user@example.com",
            "email_verified": True,
            "first_name": "John",
            "last_name": "Doe",
            "profile_image_url": "https://photo.jpg",
            "raw_data": {},
        }
        tokens = {"access_token": "token", "expires_in": 3600}

        user, is_new = OAuthService.find_or_create_user(
            mock_db, OAuthProvider.GOOGLE, user_info, tokens
        )

        assert user == existing_user
        assert is_new is False
        assert existing_user.first_name == "John"


class TestHandleOAuthCallback:
    """Test full OAuth callback handling"""

    async def test_successful_callback(self):
        """Should handle successful OAuth callback with all mocks"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        # Mock AuthService with the method the OAuth service expects
        mock_auth_service = MagicMock()
        mock_auth_service.create_user_session = MagicMock(
            return_value=("access", "refresh", MagicMock())
        )

        # Use a comprehensive patch approach
        with patch.multiple(
            OAuthService,
            exchange_code_for_tokens=AsyncMock(
                return_value={"access_token": "token", "expires_in": 3600}
            ),
            get_user_info=AsyncMock(
                return_value={
                    "provider_user_id": "123",
                    "email": "user@example.com",
                    "raw_data": {},
                }
            ),
            find_or_create_user=MagicMock(return_value=(mock_user, False)),
        ):
            with patch(
                "app.services.oauth.AuthService",
                mock_auth_service,
            ):
                result = await OAuthService.handle_oauth_callback(
                    mock_db,
                    OAuthProvider.GOOGLE,
                    "auth_code",
                    "state",
                    "https://redirect.url",
                )

                assert result is not None
                user, auth_data = result
                assert user == mock_user
                assert "access_token" in auth_data

    async def test_callback_token_exchange_failure(self):
        """Should return None if token exchange fails"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch.object(
            OAuthService,
            "exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await OAuthService.handle_oauth_callback(
                MagicMock(),
                OAuthProvider.GOOGLE,
                "invalid_code",
                "state",
                "https://redirect.url",
            )

            assert result is None

    async def test_callback_user_info_failure(self):
        """Should return None if user info retrieval fails"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch.object(
            OAuthService,
            "exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value={"access_token": "token"},
        ):
            with patch.object(
                OAuthService,
                "get_user_info",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await OAuthService.handle_oauth_callback(
                    MagicMock(),
                    OAuthProvider.GOOGLE,
                    "code",
                    "state",
                    "https://redirect.url",
                )

                assert result is None


class TestAppleOAuth:
    """Test Apple-specific OAuth functionality"""

    def test_apple_provider_requires_special_config(self):
        """Apple OAuth should require team_id, key_id, and private_key"""
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        with patch("app.services.oauth.settings") as mock_settings:
            mock_settings.OAUTH_APPLE_CLIENT_ID = "com.example.app"
            mock_settings.OAUTH_APPLE_TEAM_ID = None  # Missing
            mock_settings.OAUTH_APPLE_KEY_ID = None
            mock_settings.OAUTH_APPLE_PRIVATE_KEY = None

            config = OAuthService.get_provider_config(OAuthProvider.APPLE)

            assert config is None

    def test_apple_client_secret_generation(self):
        """Should generate Apple client secret JWT"""
        from app.services.oauth import OAuthService

        # Mock JWT generation - the import is inside the method
        with patch("jwt.encode", return_value="mock_jwt"):
            secret = OAuthService._generate_apple_client_secret(
                client_id="com.example.app",
                team_id="TEAM123",
                key_id="KEY123",
                private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            )

            assert secret == "mock_jwt"
