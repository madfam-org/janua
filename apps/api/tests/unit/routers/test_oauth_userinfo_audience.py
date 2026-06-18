"""OAuth userinfo + per-client audience verification tests."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.v1.oauth_provider import (
    UserInfoResponse,
    _accepted_audiences_for_client,
    _audiences_from_claims,
    _merge_audiences,
    _verify_oauth_token,
    userinfo,
)


class TestAudienceHelpers:
    def test_audiences_from_string_claim(self):
        assert _audiences_from_claims({"aud": "karafiel-api"}) == ["karafiel-api"]

    def test_audiences_from_list_claim(self):
        assert _audiences_from_claims({"aud": ["karafiel-api", "janua.dev"]}) == [
            "karafiel-api",
            "janua.dev",
        ]

    def test_merge_audiences_deduplicates(self):
        assert _merge_audiences(
            ["karafiel-api", "janua.dev"],
            ["karafiel-api", "enclii-api"],
        ) == ["karafiel-api", "janua.dev", "enclii-api"]

    def test_accepted_audiences_for_karafiel_client(self):
        client = MagicMock()
        client.audience = "karafiel-api"
        with patch("app.routers.v1.oauth_provider.settings") as mock_settings:
            mock_settings.JWT_AUDIENCE = "janua.dev"
            assert _accepted_audiences_for_client(client) == [
                "karafiel-api",
                "janua.dev",
            ]


class TestVerifyOAuthToken:
    @pytest.mark.asyncio
    async def test_accepts_per_client_audience_from_token_claim(self):
        token = "signed.jwt.token"
        claims = {
            "sub": str(uuid4()),
            "client_id": "jnc_karafiel_admin_prod",
            "aud": "karafiel-api",
            "type": "access",
        }
        client = MagicMock()
        client.client_id = "jnc_karafiel_admin_prod"
        client.audience = "karafiel-api"
        client.is_active = True
        db = AsyncMock()

        with (
            patch(
                "app.routers.v1.oauth_provider.jwt_manager.get_unverified_claims",
                return_value=claims,
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "app.routers.v1.oauth_provider.jwt_manager.verify_token",
                return_value=claims,
            ) as mock_verify,
        ):
            payload = await _verify_oauth_token(token, "access", db)

        assert payload == claims
        mock_verify.assert_called_once()
        audiences = mock_verify.call_args.kwargs["audience"]
        assert "karafiel-api" in audiences
        assert "janua.dev" in audiences

    @pytest.mark.asyncio
    async def test_falls_back_to_token_aud_when_client_missing(self):
        token = "signed.jwt.token"
        claims = {
            "sub": str(uuid4()),
            "aud": "karafiel-api",
            "type": "access",
        }
        db = AsyncMock()

        with (
            patch(
                "app.routers.v1.oauth_provider.jwt_manager.get_unverified_claims",
                return_value=claims,
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.routers.v1.oauth_provider.jwt_manager.verify_token",
                return_value=claims,
            ) as mock_verify,
            patch("app.routers.v1.oauth_provider.settings") as mock_settings,
        ):
            mock_settings.JWT_AUDIENCE = "janua.dev"
            payload = await _verify_oauth_token(token, "access", db)

        assert payload == claims
        audiences = mock_verify.call_args.kwargs["audience"]
        assert audiences == ["janua.dev", "karafiel-api"]


class TestUserinfoEndpoint:
    @pytest.mark.asyncio
    async def test_userinfo_returns_email_for_karafiel_audience_token(self):
        user_id = uuid4()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer access-token"}

        user = MagicMock()
        user.id = user_id
        user.email = "admin@madfam.io"
        user.email_verified = True
        user.first_name = "MADFAM"
        user.last_name = "Admin"
        user.avatar_url = None
        user.profile_image_url = None
        user.updated_at = None

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        )

        payload = {
            "sub": str(user_id),
            "scope": "openid profile email",
            "aud": "karafiel-api",
        }

        with patch(
            "app.routers.v1.oauth_provider._verify_oauth_token",
            new=AsyncMock(return_value=payload),
        ):
            response = await userinfo(request, db)

        assert isinstance(response, UserInfoResponse)
        assert response.sub == str(user_id)
        assert response.email == "admin@madfam.io"
        assert response.given_name == "MADFAM"
        assert response.family_name == "Admin"

    @pytest.mark.asyncio
    async def test_userinfo_invalid_token_returns_401_not_500(self):
        request = MagicMock()
        request.headers = {"Authorization": "Bearer bad-token"}
        db = AsyncMock()

        with patch(
            "app.routers.v1.oauth_provider._verify_oauth_token",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc:
                await userinfo(request, db)

        assert exc.value.status_code == 401
