"""Unit tests for POST /api/v1/auth/login-form/mfa (hosted OAuth MFA screen).

This is the browser/OAuth equivalent of /mfa/challenge/verify (P1 #3): the hosted
login form (GET /login → POST /login-form) renders a real second-factor screen on
MFA-required, and that screen POSTs here. On a valid code this sets the session
cookies and 302-redirects to resume the OAuth flow; on an invalid code it
re-renders the challenge screen (401) with a fresh challenge token.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

import jwt as pyjwt
import pyotp
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, User, UserStatus

MFA_FORM_URL = "/api/v1/auth/login-form/mfa"
TEST_SECRET = pyotp.random_base32()


def _mint_challenge(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "jti": secrets.token_urlsafe(24),
        "type": "mfa_challenge",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
        "iss": settings.JWT_ISSUER,
    }
    return pyjwt.encode(
        payload, settings.JWT_SECRET_KEY or "development-secret-key", algorithm="HS256"
    )


@pytest_asyncio.fixture
async def mfa_form_client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    import fakeredis.aioredis

    import app.services.auth_service as auth_service_module

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def strict_set(key, value, ex):
        return await fake_redis.set(key, value, ex=ex)

    async def strict_set_nx(key, value, ex):
        return bool(await fake_redis.set(key, value, ex=ex, nx=True))

    fake_redis.strict_set = strict_set
    fake_redis.strict_set_nx = strict_set_nx
    fake_redis.strict_get = fake_redis.get
    fake_redis.strict_exists = fake_redis.exists
    fake_redis.strict_delete = fake_redis.delete

    async def _fake_get_redis():
        return fake_redis

    import app.auth.hosted_security as hosted_security
    from app.routers.v1 import auth as auth_router

    monkeypatch.setattr(hosted_security, "get_redis", _fake_get_redis)
    app.dependency_overrides[auth_router.get_redis] = _fake_get_redis
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = _fake_get_redis
    _orig_get_redis = auth_service_module.get_redis
    auth_service_module.get_redis = _fake_get_redis

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="mfa-form-user@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
        mfa_enabled=True,
        mfa_secret=TEST_SECRET,
        mfa_backup_codes=[],
    )
    async with session_factory() as session:
        session.add(user)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.__dict__["_seeded_user_id"] = str(user_id)
        client.__dict__["_session_factory"] = session_factory
        yield client

    app.dependency_overrides.clear()
    auth_service_module.get_redis = _orig_get_redis
    await engine.dispose()


@pytest.mark.asyncio
async def test_valid_code_sets_cookies_and_redirects(mfa_form_client):
    user_id = mfa_form_client.__dict__["_seeded_user_id"]
    code = pyotp.TOTP(TEST_SECRET).now()

    resp = await mfa_form_client.post(
        MFA_FORM_URL,
        data={"mfa_token": _mint_challenge(user_id), "code": code, "next": "/dashboard"},
    )

    # 302 redirect to the (validated) next target, with session cookies set.
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == "/dashboard"
    set_cookie = resp.headers.get_list("set-cookie")
    joined = " ".join(set_cookie)
    assert "janua_access_token=" in joined
    assert "janua_refresh_token=" in joined


@pytest.mark.asyncio
async def test_invalid_code_rerenders_challenge(mfa_form_client):
    user_id = mfa_form_client.__dict__["_seeded_user_id"]

    resp = await mfa_form_client.post(
        MFA_FORM_URL,
        data={"mfa_token": _mint_challenge(user_id), "code": "000000"},
    )

    # Re-renders the challenge screen (not a redirect, no session cookies).
    assert resp.status_code == 401
    assert "Verification code" in resp.text
    assert "Invalid verification code" in resp.text
    assert "janua_access_token=" not in " ".join(resp.headers.get_list("set-cookie"))


@pytest.mark.asyncio
async def test_wrong_codes_lock_the_account(mfa_form_client, monkeypatch):
    """Wrong codes on the hosted screen count against the account lockout."""
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_THRESHOLD", 3, raising=False)
    user_id = mfa_form_client.__dict__["_seeded_user_id"]

    for _ in range(3):
        resp = await mfa_form_client.post(
            MFA_FORM_URL, data={"mfa_token": _mint_challenge(user_id), "code": "000000"}
        )
        assert resp.status_code == 401

    resp = await mfa_form_client.post(
        MFA_FORM_URL,
        data={
            "mfa_token": _mint_challenge(user_id),
            "code": pyotp.TOTP(TEST_SECRET).now(),
            "next": "/dashboard",
        },
    )

    assert resp.status_code != 302


@pytest.mark.asyncio
async def test_password_form_challenges_enrolled_user_with_flag_off(mfa_form_client, monkeypatch):
    """A user who enrolled in MFA gets the second-factor screen from the hosted
    password form even while MFA_ENFORCE_ON_LOGIN is off, as /signin does."""
    from sqlalchemy import select

    from app.services.auth_service import AuthService

    monkeypatch.setattr(settings, "MFA_ENFORCE_ON_LOGIN", False, raising=False)
    factory = mfa_form_client.__dict__["_session_factory"]
    user_id = uuid.UUID(mfa_form_client.__dict__["_seeded_user_id"])
    password = "Correct-Horse-Battery-9!"
    async with factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        user.password_hash = AuthService.hash_password(password)
        await session.commit()

    resp = await mfa_form_client.post(
        "/api/v1/auth/login-form",
        data={"email": "mfa-form-user@janua.test", "password": password, "next": "/dashboard"},
    )

    assert resp.status_code != 302
    assert "Confirma tu segundo factor" in resp.text
    assert "janua_access_token=" not in " ".join(resp.headers.get_list("set-cookie"))
