"""Unit tests for POST /api/v1/mfa/challenge/verify (the sign-in second factor).

This is the endpoint the TypeScript SDK's verifyMfaChallenge(), the dashboard
MFA step, and the hosted-login MFA screen all depend on to exchange a password
challenge for real session tokens.

Two things are guarded here:

1. The happy path returns the SignInResponse contract ({user, tokens}) for both
   a valid TOTP code and a valid backup code.

2. Regression: every ActivityLog these paths write must use the model's
   `activity_metadata` column, NOT a `details=` kwarg (which is not a mapped
   attribute and raises TypeError → 500). The success path always writes an
   ActivityLog, so if that kwarg ever regresses these tests turn the resulting
   500 red. This bug shipped undetected precisely because the comprehensive MFA
   tests were quarantined out of the CI lane.
"""

from __future__ import annotations

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
from app.routers.v1.mfa import hash_backup_code

CHALLENGE_URL = "/api/v1/mfa/challenge/verify"
TEST_SECRET = pyotp.random_base32()


def _mint_challenge(user_id: str, *, expired: bool = False, wrong_type: bool = False) -> str:
    """Mint an MFA challenge token matching what the login paths issue."""
    exp = datetime.utcnow() + (timedelta(minutes=-1) if expired else timedelta(minutes=5))
    payload = {
        "sub": str(user_id),
        "type": "session" if wrong_type else "mfa_challenge",
        "exp": exp,
        "iat": datetime.utcnow(),
        "iss": settings.JWT_ISSUER,
    }
    return pyjwt.encode(
        payload, settings.JWT_SECRET_KEY or "development-secret-key", algorithm="HS256"
    )


@pytest_asyncio.fixture
async def mfa_client(monkeypatch):
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

    # AuthService.create_session talks to Redis directly (session store + token
    # blacklist), via its own module-level `get_redis` binding — not the FastAPI
    # dependency. Point that binding (and the mfa router's) at an in-memory
    # fakeredis so the token-issuing path actually completes.
    import fakeredis.aioredis

    import app.services.auth_service as auth_service_module

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def strict_set_nx(key, value, ex):
        return bool(await fake_redis.set(key, value, ex=ex, nx=True))

    fake_redis.strict_set_nx = strict_set_nx

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr("app.core.redis.get_redis", _fake_get_redis)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = _fake_get_redis
    _orig_get_redis = auth_service_module.get_redis
    auth_service_module.get_redis = _fake_get_redis

    # Seed an MFA-enabled user. mfa_secret is an EncryptedString; with no
    # FIELD_ENCRYPTION_KEY in the test env it stores plaintext, so TOTP verifies
    # against the same value on read-back.
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="mfa-user@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
        mfa_enabled=True,
        mfa_secret=TEST_SECRET,
        mfa_backup_codes=[{"hash": hash_backup_code("ABCD-1234"), "used": False}],
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
async def test_valid_totp_returns_tokens(mfa_client):
    user_id = mfa_client.__dict__["_seeded_user_id"]
    code = pyotp.TOTP(TEST_SECRET).now()

    resp = await mfa_client.post(
        CHALLENGE_URL, json={"mfa_token": _mint_challenge(user_id), "code": code}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # SignInResponse contract the SDK relies on.
    assert body["user"]["email"] == "mfa-user@janua.test"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]


@pytest.mark.asyncio
async def test_valid_backup_code_returns_tokens(mfa_client):
    """The backup-code branch writes an extra ActivityLog — this would 500 under
    the old `details=` kwarg. Proves that branch works end-to-end."""
    user_id = mfa_client.__dict__["_seeded_user_id"]

    resp = await mfa_client.post(
        CHALLENGE_URL, json={"mfa_token": _mint_challenge(user_id), "code": "ABCD-1234"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_invalid_code_is_rejected(mfa_client):
    user_id = mfa_client.__dict__["_seeded_user_id"]

    resp = await mfa_client.post(
        CHALLENGE_URL, json={"mfa_token": _mint_challenge(user_id), "code": "000000"}
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_challenge_is_rejected(mfa_client):
    user_id = mfa_client.__dict__["_seeded_user_id"]
    code = pyotp.TOTP(TEST_SECRET).now()

    resp = await mfa_client.post(
        CHALLENGE_URL,
        json={"mfa_token": _mint_challenge(user_id, expired=True), "code": code},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_challenge_token_is_rejected(mfa_client):
    """A real session token must not be accepted as a challenge token."""
    user_id = mfa_client.__dict__["_seeded_user_id"]
    code = pyotp.TOTP(TEST_SECRET).now()

    resp = await mfa_client.post(
        CHALLENGE_URL,
        json={"mfa_token": _mint_challenge(user_id, wrong_type=True), "code": code},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_codes_lock_the_account(mfa_client, monkeypatch):
    """Wrong second-factor codes count against the account lockout, so a
    correct code is refused once the threshold is reached."""
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_THRESHOLD", 3, raising=False)
    user_id = mfa_client.__dict__["_seeded_user_id"]

    for _ in range(3):
        resp = await mfa_client.post(
            CHALLENGE_URL, json={"mfa_token": _mint_challenge(user_id), "code": "000000"}
        )
        assert resp.status_code == 401

    resp = await mfa_client.post(
        CHALLENGE_URL,
        json={"mfa_token": _mint_challenge(user_id), "code": pyotp.TOTP(TEST_SECRET).now()},
    )

    assert resp.status_code == 401
    assert "tokens" not in resp.text


@pytest.mark.asyncio
async def test_password_step_keeps_second_factor_failures(mfa_client, monkeypatch):
    """A correct password for an MFA user must not clear the failure counter
    before the second factor is verified."""
    from sqlalchemy import select

    from app.services.auth_service import AuthService

    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ACCOUNT_LOCKOUT_THRESHOLD", 5, raising=False)
    factory = mfa_client.__dict__["_session_factory"]
    user_id = uuid.UUID(mfa_client.__dict__["_seeded_user_id"])
    password = "Correct-Horse-Battery-9!"
    async with factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        user.password_hash = AuthService.hash_password(password)
        user.failed_login_attempts = 2
        user.username = "mfa-user"
        await session.commit()

    resp = await mfa_client.post(
        "/api/v1/auth/signin", json={"username": "mfa-user", "password": password}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("tokens") is None

    async with factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        assert user.failed_login_attempts == 2


@pytest.mark.asyncio
async def test_challenge_signed_with_dev_default_is_rejected_without_jwt_secret(
    mfa_client, monkeypatch
):
    """With JWT_SECRET_KEY unset, a challenge signed with the development
    default must not be accepted: that default is not a secret."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", None, raising=False)
    monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48, raising=False)
    user_id = mfa_client.__dict__["_seeded_user_id"]
    token = pyjwt.encode(
        {
            "sub": user_id,
            "type": "mfa_challenge",
            "exp": datetime.utcnow() + timedelta(minutes=5),
            "iat": datetime.utcnow(),
            "iss": settings.JWT_ISSUER,
        },
        "development-secret-key",
        algorithm="HS256",
    )

    resp = await mfa_client.post(
        CHALLENGE_URL, json={"mfa_token": token, "code": pyotp.TOTP(TEST_SECRET).now()}
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_successful_challenge_cannot_be_spent_again_with_same_live_totp(mfa_client):
    token = _mint_challenge(mfa_client.__dict__["_seeded_user_id"])
    payload = {"mfa_token": token, "code": pyotp.TOTP(TEST_SECRET).now()}
    first = await mfa_client.post(CHALLENGE_URL, json=payload)
    assert first.status_code == 200
    second = await mfa_client.post(CHALLENGE_URL, json=payload)
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_totp_time_step_cannot_complete_two_distinct_challenges(mfa_client):
    from types import SimpleNamespace

    from app.auth.mfa_enforcement import mint_mfa_challenge_token

    user = SimpleNamespace(id=mfa_client.__dict__["_seeded_user_id"])
    first_token, second_token = mint_mfa_challenge_token(user), mint_mfa_challenge_token(user)
    assert first_token != second_token
    code = pyotp.TOTP(TEST_SECRET).now()
    assert (
        await mfa_client.post(CHALLENGE_URL, json={"mfa_token": first_token, "code": code})
    ).status_code == 200
    assert (
        await mfa_client.post(CHALLENGE_URL, json={"mfa_token": second_token, "code": code})
    ).status_code == 401


@pytest.mark.asyncio
async def test_disabled_account_cannot_complete_a_pending_json_mfa_challenge(mfa_client):
    """Deactivation after primary authentication must invalidate pending MFA."""
    from sqlalchemy import select

    user_id = mfa_client.__dict__["_seeded_user_id"]
    token = _mint_challenge(user_id)
    factory = mfa_client.__dict__["_session_factory"]
    async with factory() as session:
        user = (
            await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        ).scalar_one()
        user.is_active = False
        await session.commit()

    response = await mfa_client.post(
        CHALLENGE_URL, json={"mfa_token": token, "code": pyotp.TOTP(TEST_SECRET).now()}
    )

    assert response.status_code == 401
    assert "tokens" not in response.json()
