"""Passkey ceremonies against the installed webauthn library (3.x).

J2-011: `register/options` passed `authenticator_selection` and
`exclude_credentials` as dicts. webauthn 3.x reads attributes from them
(`.resident_key`, `.id`), so building registration options raised
AttributeError and registration never started. `authenticate/options` passed
`allow_credentials` as dicts with the same result, and stored credential ids
(base64url) were decoded as plain base64. A verified passkey sign-in then
called a method that does not exist.

These tests drive the real routes with a software authenticator (an ES256 key
and the "none" attestation format, built here with cbor2 and cryptography), so
the options Janua builds are checked by the same library that verifies the
response:

- registration options build, carry the stored passkey in excludeCredentials,
  and store the challenge strictly (J2's challenge storage is unchanged);
- a registration made against those options verifies and stores the passkey;
- authentication options list it in allowCredentials, and an assertion made
  against them signs the person in with a real, revocable session.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import cbor2
import fakeredis
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, Passkey, User, UserStatus
from app.models import Session as UserSession
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio

RP_ID = "passkeys.janua.test"
ORIGIN = f"https://{RP_ID}"


class SoftwareAuthenticator:
    """A minimal WebAuthn authenticator: one ES256 credential, "none" attestation."""

    def __init__(self, rp_id: str, origin: str):
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        # Bytes chosen so the base64url id contains both '-' and '_', which
        # plain base64 decoding mangles.
        self.credential_id = b"\xfb\xff\xbf" + os.urandom(13)
        self.sign_count = 0

    def _rp_id_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode()).digest()

    def _cose_public_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        ).encode()

    def register(self, options: dict) -> dict:
        flags = bytes([0x45])  # UP | UV | AT
        auth_data = (
            self._rp_id_hash()
            + flags
            + self.sign_count.to_bytes(4, "big")
            + bytes(16)  # AAGUID
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + self._cose_public_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client_data = self._client_data("webauthn.create", options["challenge"])
        cred_id = bytes_to_base64url(self.credential_id)
        return {
            "id": cred_id,
            "rawId": cred_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["usb"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "cross-platform",
        }

    def assert_(self, options: dict, user_handle: bytes) -> dict:
        self.sign_count += 1
        auth_data = self._rp_id_hash() + bytes([0x05]) + self.sign_count.to_bytes(4, "big")
        client_data = self._client_data("webauthn.get", options["challenge"])
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        cred_id = bytes_to_base64url(self.credential_id)
        return {
            "id": cred_id,
            "rawId": cred_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(user_handle),
            },
            "clientExtensionResults": {},
        }


@pytest_asyncio.fixture
async def env(monkeypatch):
    from app.core.database import get_db as core_get_db
    from app.database import get_db
    from app.dependencies import get_current_user
    from app.main import app

    monkeypatch.setattr(settings, "WEBAUTHN_RP_ID", RP_ID)
    monkeypatch.setattr(settings, "WEBAUTHN_ORIGIN", ORIGIN)

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    server = fakeredis.FakeServer()
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))

    user = User(
        id=uuid.uuid4(),
        email="passkey-person@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    async with factory() as session:
        session.add(user)
        await session.commit()

    async def override_get_db():
        async with factory() as session:
            yield session

    async def override_current_user():
        async with factory() as session:
            return await session.get(User, user.id)

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    get = AsyncMock(return_value=redis)
    with (
        patch("app.core.redis.get_redis", get),
        patch("app.services.auth_service.get_redis", get),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield SimpleNamespace(http=http, factory=factory, redis=redis, server=server, user=user)

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    await engine.dispose()


async def _register(env, authenticator, **body):
    options = await env.http.post("/api/v1/passkeys/register/options", json=body)
    assert options.status_code == 200, options.text
    credential = authenticator.register(options.json())
    verified = await env.http.post(
        "/api/v1/passkeys/register/verify", json={"credential": credential, "name": "Test key"}
    )
    return options.json(), verified


class TestRegistrationOptions:
    async def test_options_build_on_the_installed_library(self, env):
        resp = await env.http.post("/api/v1/passkeys/register/options", json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["rp"] == {"id": RP_ID, "name": settings.WEBAUTHN_RP_NAME}
        assert base64url_to_bytes(body["user"]["id"]) == str(env.user.id).encode()
        assert body["user"]["name"] == env.user.email
        # No attachment preference (J3-006): built-in and roaming
        # authenticators can both register.
        assert body["authenticatorSelection"] == {
            "residentKey": "discouraged",
            "requireResidentKey": False,
            "userVerification": "preferred",
        }
        assert body["attestation"] == "none"
        assert {"type": "public-key", "alg": -7} in body["pubKeyCredParams"]
        assert body["excludeCredentials"] == []
        # The challenge is stored server-side, strictly, keyed by the user.
        stored = await env.redis.strict_get(f"passkey_challenge:{env.user.id}")
        assert stored == body["challenge"]

    async def test_no_attachment_constraint_by_default(self, env):
        # Owner decision 2026-10-04 (J3-006): the options must not force
        # `cross-platform` (that excluded Touch ID / Windows Hello). With no
        # preference in the request, no attachment key is sent at all.
        for payload in ({}, {"authenticator_attachment": None}):
            resp = await env.http.post("/api/v1/passkeys/register/options", json=payload)
            assert resp.status_code == 200, resp.text
            selection = resp.json()["authenticatorSelection"]
            assert "authenticatorAttachment" not in selection
            assert "cross-platform" not in resp.text
            assert '"platform"' not in resp.text

    async def test_cross_platform_is_honoured_when_asked(self, env):
        resp = await env.http.post(
            "/api/v1/passkeys/register/options",
            json={"authenticator_attachment": "cross-platform"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["authenticatorSelection"]["authenticatorAttachment"] == "cross-platform"

    async def test_platform_attachment_is_honoured(self, env):
        resp = await env.http.post(
            "/api/v1/passkeys/register/options", json={"authenticator_attachment": "platform"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["authenticatorSelection"]["authenticatorAttachment"] == "platform"

    async def test_options_answer_503_when_redis_is_down(self, env):
        env.server.connected = False
        resp = await env.http.post("/api/v1/passkeys/register/options", json={})
        assert resp.status_code == 503
        assert resp.headers["retry-after"].isdigit()


class TestRegistrationCeremony:
    async def test_a_registration_against_the_options_verifies_and_is_stored(self, env):
        authenticator = SoftwareAuthenticator(RP_ID, ORIGIN)
        _, verified = await _register(env, authenticator)

        assert verified.status_code == 200, verified.text
        assert verified.json()["verified"] is True
        async with env.factory() as db:
            passkey = (
                await db.execute(select(Passkey).where(Passkey.user_id == env.user.id))
            ).scalar_one()
        assert passkey.credential_id == bytes_to_base64url(authenticator.credential_id)
        # The challenge was single-use.
        assert await env.redis.strict_get(f"passkey_challenge:{env.user.id}") is None

    async def test_a_stored_passkey_is_excluded_from_the_next_registration(self, env):
        authenticator = SoftwareAuthenticator(RP_ID, ORIGIN)
        _, verified = await _register(env, authenticator)
        assert verified.status_code == 200, verified.text

        resp = await env.http.post("/api/v1/passkeys/register/options", json={})
        assert resp.status_code == 200, resp.text
        excluded = [c["id"] for c in resp.json()["excludeCredentials"]]
        # Exact bytes: the base64url id round-trips (plain base64 would not).
        assert excluded == [bytes_to_base64url(authenticator.credential_id)]

    async def test_a_response_to_another_challenge_is_refused(self, env):
        authenticator = SoftwareAuthenticator(RP_ID, ORIGIN)
        options = await env.http.post("/api/v1/passkeys/register/options", json={})
        forged = dict(options.json(), challenge=bytes_to_base64url(b"not-the-challenge"))
        resp = await env.http.post(
            "/api/v1/passkeys/register/verify",
            json={"credential": authenticator.register(forged)},
        )
        assert resp.status_code == 400


class TestAuthenticationCeremony:
    async def test_options_list_the_passkey_and_an_assertion_signs_in(self, env):
        authenticator = SoftwareAuthenticator(RP_ID, ORIGIN)
        _, verified = await _register(env, authenticator)
        assert verified.status_code == 200, verified.text

        options = await env.http.post(
            "/api/v1/passkeys/authenticate/options", json={"email": env.user.email}
        )
        assert options.status_code == 200, options.text
        body = options.json()
        assert body["rpId"] == RP_ID
        assert body["allowCredentials"] == [
            {"id": bytes_to_base64url(authenticator.credential_id), "type": "public-key"}
        ]

        assertion = authenticator.assert_(body, str(env.user.id).encode())
        signed_in = await env.http.post(
            "/api/v1/passkeys/authenticate/verify",
            params={"session_id": body["sessionId"]},
            json={"credential": assertion},
        )
        assert signed_in.status_code == 200, signed_in.text
        tokens = signed_in.json()
        assert tokens["verified"] is True

        # A real session row with a refresh family: refresh works, and it is
        # revocable like any other session.
        async with env.factory() as db:
            row = (
                await db.execute(select(UserSession).where(UserSession.user_id == env.user.id))
            ).scalar_one()
            assert row.refresh_token_family
            assert await AuthService.refresh_tokens(db, tokens["refresh_token"]) is not None
