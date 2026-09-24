"""OAuthService: incremental-authorization URL and provider refresh-token exchange."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import settings
from app.models import OAuthProvider
from app.services.oauth import (
    OAuthService,
    ProviderRefreshRejected,
    ProviderRefreshUnavailable,
)

pytestmark = pytest.mark.asyncio

YT = "https://www.googleapis.com/auth/youtube.readonly"


@pytest.fixture(autouse=True)
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "OAUTH_GOOGLE_CLIENT_ID", "google-client-placeholder")
    monkeypatch.setattr(settings, "OAUTH_GOOGLE_CLIENT_SECRET", "google-secret-placeholder")


def _query(url: str) -> dict:
    return parse_qs(urlparse(url).query)


class TestAuthorizationUrl:
    def test_include_granted_scopes_only_when_asked(self):
        plain = _query(
            OAuthService.get_authorization_url(OAuthProvider.GOOGLE, "https://cb", "st", [YT])
        )
        assert "include_granted_scopes" not in plain
        incremental = _query(
            OAuthService.get_authorization_url(
                OAuthProvider.GOOGLE, "https://cb", "st", [YT], include_granted_scopes=True
            )
        )
        assert incremental["include_granted_scopes"] == ["true"]
        assert YT in incremental["scope"][0].split()

    def test_additional_scopes_are_not_duplicated(self):
        q = _query(
            OAuthService.get_authorization_url(
                OAuthProvider.GOOGLE, "https://cb", "st", ["openid", YT, YT]
            )
        )
        scopes = q["scope"][0].split()
        assert scopes.count("openid") == 1
        assert scopes.count(YT) == 1


def _client_returning(response=None, exc=None):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(side_effect=exc) if exc else AsyncMock(return_value=response)
    return client


def _response(status: int, body=None):
    request = httpx.Request("POST", "https://oauth2.googleapis.com/token")
    if body is None:
        return httpx.Response(status, content=b"not json", request=request)
    return httpx.Response(status, json=body, request=request)


class TestRefreshAccessToken:
    async def test_success_returns_tokens(self):
        body = {"access_token": "fresh-placeholder", "expires_in": 3599, "scope": f"openid {YT}"}
        client = _client_returning(_response(200, body))
        with patch("app.services.oauth.httpx.AsyncClient", return_value=client):
            tokens = await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")
        assert tokens["access_token"] == "fresh-placeholder"
        sent = client.post.await_args.kwargs["data"]
        assert sent["grant_type"] == "refresh_token"
        assert sent["refresh_token"] == "rt"

    async def test_invalid_grant_is_rejected(self):
        client = _client_returning(_response(400, {"error": "invalid_grant"}))
        with patch("app.services.oauth.httpx.AsyncClient", return_value=client):
            with pytest.raises(ProviderRefreshRejected, match="invalid_grant"):
                await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")

    async def test_provider_5xx_is_unavailable(self):
        client = _client_returning(_response(503, {"error": "backend"}))
        with patch("app.services.oauth.httpx.AsyncClient", return_value=client):
            with pytest.raises(ProviderRefreshUnavailable):
                await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")

    async def test_network_error_is_unavailable(self):
        client = _client_returning(exc=httpx.ConnectError("boom"))
        with patch("app.services.oauth.httpx.AsyncClient", return_value=client):
            with pytest.raises(ProviderRefreshUnavailable):
                await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")

    async def test_body_without_access_token_is_unavailable(self):
        client = _client_returning(_response(200, {"expires_in": 10}))
        with patch("app.services.oauth.httpx.AsyncClient", return_value=client):
            with pytest.raises(ProviderRefreshUnavailable):
                await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")

    async def test_missing_refresh_token_is_rejected_without_a_call(self):
        with patch("app.services.oauth.httpx.AsyncClient") as ctor:
            with pytest.raises(ProviderRefreshRejected):
                await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "")
        ctor.assert_not_called()

    async def test_unconfigured_provider_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(settings, "OAUTH_GOOGLE_CLIENT_SECRET", None)
        with pytest.raises(ProviderRefreshUnavailable):
            await OAuthService.refresh_access_token(OAuthProvider.GOOGLE, "rt")
