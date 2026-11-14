"""A browser bridge reuses live authority; a signed JWT alone cannot restore it."""

import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import fakeredis.aioredis
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import session_bridge_authority as authority
from app.auth.session_bridge_authority import InvalidSessionProof
from app.core.jwt_manager import JWTManager
from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient

USER = "00000000-0000-4000-8000-000000000901"
SESSION = "00000000-0000-4000-8000-000000000902"
CLIENT = "jnc_U-901"
AUDIENCE = "source-U-901"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest_asyncio.fixture
async def setup(monkeypatch, key):
    manager = object.__new__(JWTManager)
    manager.algorithm, manager.public_key = "RS256", key.public_key()
    manager.issuer, manager.audience = "https://issuer.example.test", AUDIENCE
    monkeypatch.setattr(authority, "jwt_manager", manager)
    parent = SimpleNamespace(
        id=UUID(SESSION),
        user_id=UUID(USER),
        refresh_token_family="U-903",
        access_token_jti="U-904",
        refresh_token_jti="U-905",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        authentication_methods=[],
        authenticated_at=None,
        mfa_verified_at=None,
    )
    user = SimpleNamespace(id=UUID(USER))
    resolve = AsyncMock(return_value=(user, parent))
    monkeypatch.setattr(authority, "resolve_session_by_id", resolve)
    policy = AsyncMock(return_value=False)
    monkeypatch.setattr(authority, "user_requires_mfa", policy)
    db = AsyncMock()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=parent))
    client = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    redis = ResilientRedisClient(client)

    def token(kind="access", **overrides):
        claims = {
            "sub": USER,
            "jti": "U-904" if kind == "access" else "U-905",
            "family": "U-903",
            "type": kind,
            "iss": manager.issuer,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 300,
        }
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm="RS256")

    env = SimpleNamespace(
        db=db,
        redis=redis,
        client=client,
        parent=parent,
        user=user,
        resolve=resolve,
        policy=policy,
        token=token,
        manager=manager,
    )
    try:
        yield env
    finally:
        await client.aclose()


async def verify(env, **tokens):
    return await authority.verify_source_proof(
        env.db, env.redis, source_client_id=CLIENT, source_audience=AUDIENCE, **tokens
    )


@pytest.mark.asyncio
async def test_current_direct_legacy_access_reuses_its_exact_parent(setup):
    env = setup
    proof = await verify(env, access_token=env.token())
    assert proof["proof_kind"] == "direct"
    assert proof["session_id"] == SESSION
    assert proof["proof_jti"] == env.parent.access_token_jti
    assert proof["proof_family"] == env.parent.refresh_token_family
    assert "access_token" not in proof and "refresh_token" not in proof
    assert await authority.recheck_source_proof(env.db, env.redis, proof) == (env.user, env.parent)
    env.db.commit.assert_not_called()
    env.db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"jti": "U-rotated"},
        {"family": "U-other"},
        {"sid": "00000000-0000-4000-8000-000000000999"},
        {"sub": "00000000-0000-4000-8000-000000000999"},
        {"amr": ["otp"]},
        {"aud": "other-U-901"},
        {"iss": "https://other.example.test"},
        {"exp": 1},
        {"exp": None},
    ],
)
async def test_direct_wrong_current_identity_audience_assurance_or_expiry_is_refused(
    setup, overrides
):
    with pytest.raises(InvalidSessionProof):
        await verify(setup, access_token=setup.token(**overrides))


@pytest.mark.asyncio
async def test_oidc_access_alone_is_not_a_parent_restoration_credential(setup):
    with pytest.raises(InvalidSessionProof):
        await verify(setup, access_token=setup.token(client_id=CLIENT, sid=SESSION, amr=[]))


@pytest.mark.asyncio
async def test_oidc_refresh_is_source_bound_and_reuses_live_signed_parent(setup):
    env = setup
    proof = await verify(
        env,
        refresh_token=env.token(
            "refresh",
            jti="U-oauth-grant",
            family="U-oauth-family",
            client_id=CLIENT,
            sid=SESSION,
            amr=[],
        ),
    )
    assert proof["proof_kind"] == "oidc"
    assert proof["proof_family"] == "U-oauth-family"
    assert proof["parent_family"] == "U-903"
    # Deliberately not the AuthService row's refresh JTI: no invented OAuth current ledger.
    assert proof["proof_jti"] != env.parent.refresh_token_jti
    assert await authority.recheck_source_proof(env.db, env.redis, proof) == (env.user, env.parent)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"sid": None},
        {"family": None},
        {"client_id": "jnc_other_U-901"},
        {"amr": ["otp"]},
    ],
)
async def test_oidc_refresh_cannot_invent_parent_client_family_or_assurance(setup, overrides):
    claims = {
        "client_id": CLIENT,
        "sid": SESSION,
        "amr": [],
        "jti": "U-oauth-grant",
        "family": "U-oauth-family",
    }
    claims.update(overrides)
    with pytest.raises(InvalidSessionProof):
        await verify(setup, refresh_token=setup.token("refresh", **claims))


@pytest.mark.asyncio
async def test_mismatched_access_and_refresh_subjects_are_refused(setup):
    with pytest.raises(InvalidSessionProof):
        await verify(
            setup,
            access_token=setup.token(),
            refresh_token=setup.token("refresh", sub="00000000-0000-4000-8000-000000000999"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked_key", ["blacklist:access:U-904", "revoked_family:U-903"])
async def test_revoked_token_or_parent_family_is_refused(setup, revoked_key):
    await setup.client.set(revoked_key, "1")
    with pytest.raises(InvalidSessionProof):
        await verify(setup, access_token=setup.token())


@pytest.mark.asyncio
async def test_missing_parent_and_required_mfa_do_not_restore(setup):
    env = setup
    env.resolve.return_value = (None, None)
    with pytest.raises(InvalidSessionProof):
        await verify(env, access_token=env.token())
    env.resolve.return_value = (env.user, env.parent)
    env.policy.return_value = True
    with pytest.raises(InvalidSessionProof):
        await verify(env, access_token=env.token())


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["jti", "family", "assurance", "revocation", "policy", "parent"])
async def test_authority_is_rechecked_before_consumption(setup, change):
    env = setup
    proof = await verify(env, access_token=env.token())
    if change == "jti":
        env.parent.access_token_jti = "U-rotated"
    elif change == "family":
        env.parent.refresh_token_family = "U-other"
    elif change == "assurance":
        env.parent.authentication_methods = ["pwd"]
    elif change == "revocation":
        await env.client.set("blacklist:access:U-904", "1")
    elif change == "policy":
        env.policy.return_value = True
    elif change == "parent":
        env.resolve.return_value = (None, None)
    with pytest.raises(InvalidSessionProof):
        await authority.recheck_source_proof(env.db, env.redis, proof)


@pytest.mark.asyncio
async def test_shared_revocation_outage_fails_closed(setup):
    with pytest.raises(RedisUnavailableError):
        await authority.verify_source_proof(
            setup.db,
            ResilientRedisClient(None),
            source_client_id=CLIENT,
            source_audience=AUDIENCE,
            access_token=setup.token(),
        )


def test_hs256_cannot_pass_the_bridge_decoder():
    token = jwt.encode(
        {"sub": USER, "type": "access", "aud": AUDIENCE},
        "synthetic-U-901-key-material",
        algorithm="HS256",
    )
    with pytest.raises(InvalidSessionProof):
        authority._decode(token, "access", AUDIENCE)


@pytest.mark.asyncio
async def test_a_signed_token_without_expiry_is_not_restoration_proof(setup, key):
    token = jwt.encode(
        {
            "sub": USER,
            "jti": "U-904",
            "type": "access",
            "iss": setup.manager.issuer,
            "aud": AUDIENCE,
        },
        key,
        algorithm="RS256",
    )
    with pytest.raises(InvalidSessionProof):
        authority._decode(token, "access", AUDIENCE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "revoked_key",
    [
        "blacklist:refresh:U-oauth-grant",
        "revoked_family:U-oauth-family",
        "revoked_family:U-903",
    ],
)
async def test_oidc_grant_and_parent_revocation_after_prepare_are_rechecked(setup, revoked_key):
    env = setup
    proof = await verify(
        env,
        refresh_token=env.token(
            "refresh",
            jti="U-oauth-grant",
            family="U-oauth-family",
            client_id=CLIENT,
            sid=SESSION,
            amr=[],
        ),
    )
    await env.client.set(revoked_key, "1")
    with pytest.raises(InvalidSessionProof):
        await authority.recheck_source_proof(env.db, env.redis, proof)
