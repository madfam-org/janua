"""Shared scaffolding for the purpose-scoped consent tests.

A real SQLite-backed app (not a MagicMock session) so the JSON columns,
status transitions and ActivityLog rows the consent layer writes are what the
assertions read back. Plus an RS256 signing key swapped into the process-wide
`jwt_manager`, so service tokens are minted and verified the way production
does it — no symmetric fallback.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator, Callable, Iterator
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs

# Imported at module import (collection) time on purpose: a session-scoped
# autouse fixture elsewhere in this directory swaps sys.modules["httpx"] for a
# Mock, so a lazy `import httpx` inside a helper can receive the Mock.
import httpx
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.consent_purposes import (
    CONNECTIONS_AUDIENCE,
    CONNECTIONS_DELEGATE_SCOPE,
    PURPOSE_STATUS_GRANTED,
)
from app.core.jwt_manager import jwt_manager
from app.database import get_db
from app.main import app
from app.models import ActivityLog, Base, OAuthClient, User, UserStatus
from app.models.connected_account import ConnectedAccount, ConnectedAccountStatus

YT_PURPOSE = "creator-census.youtube"
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
CENSUS_API_AUDIENCE = "creator-census-api"
GOOGLE_BASE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


@asynccontextmanager
async def sqlite_app(extra_overrides: dict | None = None) -> AsyncIterator[tuple]:
    """Yield (client, session_factory) with get_db bound to in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    for dep, override in (extra_overrides or {}).items():
        app.dependency_overrides[dep] = override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
        await engine.dispose()


def use_rs256(monkeypatch) -> None:
    """Swap an ephemeral RSA key into the global jwt_manager for this test."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(jwt_manager, "private_key", key)
    monkeypatch.setattr(jwt_manager, "public_key", key.public_key())
    monkeypatch.setattr(jwt_manager, "kid", "consent-test-kid")


def mint_service_token(
    client_id: str,
    *,
    scope: str = CONNECTIONS_DELEGATE_SCOPE,
    audience: str = CONNECTIONS_AUDIENCE,
    expires_in: timedelta = timedelta(seconds=3600),
) -> str:
    """Mint exactly the claim shape `_handle_client_credentials_grant` mints."""
    now = datetime.utcnow()
    token, _, _ = jwt_manager.create_access_token(
        user_id=f"service-account:{client_id}",
        email=f"{client_id}@service.example.com",
        additional_claims={
            "client_id": client_id,
            "scope": scope,
            "token_use": "client_credentials",
            "actor_type": "service_account",
            "roles": ["service_account"],
            "aud": audience,
            "iat": now if expires_in > timedelta(0) else now + expires_in - timedelta(seconds=60),
            "exp": now + expires_in,
        },
    )
    return token


def mint_user_token(
    user_id: uuid.UUID,
    *,
    audience: str = CENSUS_API_AUDIENCE,
    expires_in: timedelta = timedelta(minutes=15),
    extra: dict | None = None,
) -> str:
    """A person's Janua access token as the census API would receive it."""
    now = datetime.utcnow()
    claims = {
        "aud": audience,
        "client_id": "jnc_census_web_fixture",
        "scope": "openid profile email",
        "iat": now - timedelta(seconds=5),
        "exp": now + expires_in,
    }
    claims.update(extra or {})
    token, _, _ = jwt_manager.create_access_token(
        user_id=str(user_id), email="person@example.com", additional_claims=claims
    )
    return token


async def add_user(
    factory, email: str, *, status: UserStatus = UserStatus.ACTIVE, service_account: bool = False
) -> User:
    async with factory() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            status=status,
            password_hash="not-a-real-hash",
            is_service_account=service_account,
        )
        db.add(user)
        await db.commit()
        return user


async def add_service_client(
    factory,
    *,
    name: str,
    client_id: str,
    created_by: uuid.UUID,
    allowed_scopes: list[str] | None = None,
    audience: str = CONNECTIONS_AUDIENCE,
    is_active: bool = True,
) -> OAuthClient:
    async with factory() as db:
        client = OAuthClient(
            id=uuid.uuid4(),
            created_by=created_by,
            client_id=client_id,
            client_secret_hash="hash-placeholder",
            client_secret_prefix="jns_placeholder",
            name=name,
            redirect_uris=[],
            allowed_scopes=(
                allowed_scopes if allowed_scopes is not None else [CONNECTIONS_DELEGATE_SCOPE]
            ),
            grant_types=["client_credentials"],
            audience=audience,
            is_active=is_active,
            is_confidential=True,
        )
        db.add(client)
        await db.commit()
        return client


async def add_connection(
    factory,
    *,
    user_id: uuid.UUID,
    provider_type: str = "google",
    scopes: list[str] | None = None,
    purposes: dict | None = None,
    expires_in: timedelta | None = timedelta(hours=1),
    access_token: str = "provider-access-placeholder",
    refresh_token: str | None = "provider-refresh-placeholder",
    status: str = ConnectedAccountStatus.ACTIVE.value,
) -> ConnectedAccount:
    metadata: dict = {"source": "test"}
    if purposes is not None:
        metadata["purposes"] = purposes
    async with factory() as db:
        conn = ConnectedAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            provider_type=provider_type,
            provider_name=f"{provider_type} connection",
            provider_id="provider-user-1",
            access_token_encrypted=access_token,
            refresh_token_encrypted=refresh_token,
            oauth_scopes=scopes if scopes is not None else GOOGLE_BASE_SCOPES + YT_SCOPES,
            oauth_expires_at=(datetime.utcnow() + expires_in) if expires_in is not None else None,
            status=status,
            account_metadata=metadata,
            created_by=user_id,
        )
        db.add(conn)
        await db.commit()
        return conn


def granted(purpose_id: str = YT_PURPOSE) -> dict:
    return {
        purpose_id: {
            "status": PURPOSE_STATUS_GRANTED,
            "scopes": list(YT_SCOPES),
            "granted_at": "2026-09-24T00:00:00Z",
        }
    }


async def get_connection(factory, connection_id: uuid.UUID) -> ConnectedAccount:
    async with factory() as db:
        result = await db.execute(
            select(ConnectedAccount).where(ConnectedAccount.id == connection_id)
        )
        return result.scalar_one()


async def activity(factory, action: str) -> list[ActivityLog]:
    async with factory() as db:
        result = await db.execute(select(ActivityLog).where(ActivityLog.action == action))
        return list(result.scalars().all())


def as_user(user: User) -> Callable:
    async def _current_user():
        return user

    return _current_user


def reason(resp) -> str:
    """The refusal reason from Janua's error envelope (`error.message`)."""
    return resp.json()["error"]["message"]


GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


@contextmanager
def mocked_google_revoke(*responses) -> Iterator[tuple]:
    """Mock Google's revoke endpoint (and block every other outbound call).

    `responses` are returned in order (an Exception instance is raised);
    with none, every call answers 200. Backoff sleeps are replaced with an
    AsyncMock so tests stay fast and can assert the schedule. Yields
    (route, sleep_mock).
    """
    with respx.mock(assert_all_called=False) as router:
        route = router.post(GOOGLE_REVOKE_URL)
        if responses:
            route.mock(side_effect=list(responses))
        else:
            route.mock(return_value=httpx.Response(200))
        sleep = AsyncMock()
        with patch("app.services.oauth.asyncio.sleep", sleep):
            yield route, sleep


def revoked_token(route, call: int = 0) -> str:
    """The `token` form field Google received on the given call."""
    body = route.calls[call].request.content.decode()
    return parse_qs(body)["token"][0]
