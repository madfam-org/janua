"""Required native authority/CAS proof, never hosted auth or browser delivery.

A generated scratch schema holds real ORM User/Session rows. Two independent
Redis clients touch only exact owned keys. No flush, shared scan or fakeRedis.
"""

import asyncio
import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import session_bridge_authority as authority
from app.auth.authentication_assurance import session_assurance
from app.auth.session_bridge_authority import InvalidSessionProof
from app.auth.session_bridge_state import BridgeStateStore, InvalidBridgeState
from app.core.jwt_manager import JWTManager
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE
from app.models import Base, OAuthClient, Organization, Session, User, UserStatus
from app.routers.v1 import session_bridge as bridge
from app.services import token_revocation

pytestmark = [pytest.mark.asyncio, pytest.mark.database]
SOURCE_URI = "https://map.example.test/bridge"
TARGET_URI = "https://erp.example.test/callback"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _services():
    raw = os.getenv("MIGRATION_TEST_DATABASE_URL")
    redis_url = os.getenv("JANUA_SESSION_BRIDGE_TEST_REDIS_URL")
    required = os.getenv("CI") == "true" or os.getenv("JANUA_SESSION_BRIDGE_NATIVE_REQUIRED") == "1"
    if not raw or not redis_url:
        if required:
            pytest.fail("Required bridge native service configuration is missing", pytrace=False)
        pytest.skip("Opt in with guarded PostgreSQL and Redis test services")
    db = make_url(raw)
    cache = urlsplit(redis_url)
    if (
        os.getenv("LOCAL_DB") != "yes"
        or db.drivername != "postgresql+asyncpg"
        or db.host not in {"localhost", "127.0.0.1"}
        or not db.database
        or not db.database.endswith("_test")
        or db.query
        or cache.scheme != "redis"
        or cache.hostname not in {"localhost", "127.0.0.1"}
        or cache.username
        or cache.password
        or cache.query
        or cache.fragment
        or cache.path != "/0"
    ):
        pytest.fail("Native bridge proof requires explicit loopback test services", pytrace=False)
    return db, redis_url


@pytest_asyncio.fixture
async def native(monkeypatch, signing_key):
    url, redis_url = _services()
    schema = "bridge_native_" + uuid4().hex
    admin = create_async_engine(url, hide_parameters=True)
    engine = create_async_engine(
        url, hide_parameters=True, connect_args={"server_settings": {"search_path": schema}}
    )
    clients = [redis_async.Redis.from_url(redis_url, decode_responses=True) for _ in range(2)]
    wrappers = [ResilientRedisClient(client) for client in clients]
    stores = [BridgeStateStore(client) for client in wrappers]
    keys = set()
    created = False
    try:
        # These are separate actual network clients/pools, not two aliases.
        assert clients[0].connection_pool is not clients[1].connection_pool
        await asyncio.gather(*(client.ping() for client in clients))
        assert await clients[0].client_id() != await clients[1].client_id()
        async with admin.begin() as conn:
            assert (
                await conn.execute(text("SELECT current_database()"))
            ).scalar_one() == url.database
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        async with engine.begin() as conn:
            # This qualifies current ORM authority, not an Alembic upgrade.
            await conn.run_sync(
                lambda conn: Base.metadata.create_all(
                    conn,
                    tables=[
                        User.__table__,
                        Organization.__table__,
                        Session.__table__,
                        OAuthClient.__table__,
                    ],
                )
            )
            assert (
                (await conn.execute(text("""SELECT n.nspname FROM pg_attribute a
                JOIN pg_type t ON t.oid=a.atttypid
                JOIN pg_namespace n ON n.oid=t.typnamespace
                WHERE a.attrelid='users'::regclass AND a.attname='status'"""))).scalar_one()
                == schema
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id, sid = uuid4(), uuid4()
        suffix = uuid4().hex
        stamp = datetime.utcnow().replace(microsecond=0) - timedelta(seconds=1)
        async with factory.begin() as db:
            db.add(
                User(
                    id=user_id,
                    email=f"u-901-{suffix}@example.test",
                    status=UserStatus.ACTIVE,
                    mfa_enabled=True,
                    mfa_secret="F-901",
                    is_service_account=False,
                )
            )
            await db.flush()
            db.add(
                Session(
                    id=sid,
                    user_id=user_id,
                    token="F-901-" + suffix,
                    access_token_jti="F-902-" + suffix,
                    refresh_token_jti="F-903-" + suffix,
                    refresh_token_family="F-904-" + suffix,
                    expires_at=stamp + timedelta(hours=1),
                    authentication_methods=["password", "otp"],
                    authenticated_at=stamp,
                    mfa_verified_at=stamp,
                    is_active=True,
                    revoked=False,
                )
            )
            await db.flush()
            for client_id, audience, uri in [
                ("jnc_F-901", "F-901", SOURCE_URI),
                ("jnc_F-902", "F-902", TARGET_URI),
            ]:
                db.add(
                    OAuthClient(
                        created_by=user_id,
                        client_id=client_id,
                        name="F-901",
                        client_secret_hash="F-901",
                        client_secret_prefix="F-901",
                        audience=audience,
                        redirect_uris=[uri],
                        allowed_scopes=["openid", "profile", "email", SILENT_AUTH_SCOPE],
                        grant_types=["authorization_code", "refresh_token"],
                        is_active=True,
                        is_confidential=True,
                    )
                )
        manager = object.__new__(JWTManager)
        manager.algorithm, manager.public_key = "RS256", signing_key.public_key()
        manager.issuer, manager.audience = "https://issuer.example.test", "F-901"
        # Configure test key material only. Real signature/issuer/audience/type
        # verification, SQL resolution, policy and revocation remain untouched.
        monkeypatch.setattr(authority, "jwt_manager", manager)
        async with factory() as db:
            parent = await db.get(Session, sid)
            evidence = session_assurance(parent)
            access_jti, refresh_jti, family = (
                parent.access_token_jti,
                parent.refresh_token_jti,
                parent.refresh_token_family,
            )

        def token(kind="access", oidc=False, **overrides):
            claims = {
                "sub": str(user_id),
                "jti": access_jti if kind == "access" else refresh_jti,
                "family": family,
                "type": kind,
                "iss": manager.issuer,
                "aud": manager.audience,
                "exp": int(time.time()) + 300,
                **evidence,
            }
            if oidc:
                claims.update(
                    client_id="jnc_F-901", jti="F-905-" + suffix, family="F-906-" + suffix
                )
            claims.update(overrides)
            return jwt.encode(claims, signing_key, algorithm="RS256")

        async def verify(kind="access", oidc=False, **overrides):
            async with factory() as db:
                return await authority.verify_source_proof(
                    db,
                    wrappers[0],
                    source_client_id="jnc_F-901",
                    source_audience=manager.audience,
                    **{f"{kind}_token": token(kind, oidc, **overrides)},
                )

        async def recheck(proof):
            async with factory() as db:
                return await authority.recheck_source_proof(db, wrappers[1], proof)

        async def mutate(model=Session, **values):
            async with factory.begin() as db:
                await db.execute(
                    update(model)
                    .where(model.id == (user_id if model is User else sid))
                    .values(**values)
                )

        async def stage(proof, reject_browser=False):
            begun = await stores[0].start(
                source_client_id="jnc_F-901",
                source_uri=SOURCE_URI,
                source_audience=manager.audience,
                target_client_id="jnc_F-902",
                authorization={
                    "response_type": "code",
                    "client_id": "jnc_F-902",
                    "redirect_uri": TARGET_URI,
                    "scope": f"openid profile email {SILENT_AUTH_SCOPE}",
                    "audience": "F-902",
                    "state": "F-907-" + "S" * 32,
                    "nonce": "F-908-" + "N" * 32,
                    "prompt": "none",
                    "code_challenge_method": "S256",
                    "code_challenge": "F" * 43,
                },
            )

            def digest(value):
                return hashlib.sha256(value.encode()).hexdigest()

            prefix = "auth:session-bridge:v1:"
            keys.add(prefix + "transaction:" + digest(begun.state))
            code = await stores[0].issue(begun.state, proof)
            keys.update(
                [prefix + "issued:" + digest(begun.state), prefix + "code:" + digest(code.code)]
            )
            if reject_browser:
                with pytest.raises(InvalidBridgeState):
                    await stores[1].bound(begun.state, code.code, secrets.token_urlsafe(32))
            bound = await stores[0].bound(begun.state, code.code, begun.browser_secret)
            approved = await stores[0].approve(bound)
            keys.add(prefix + "approved:" + digest(approved.code))
            return begun, code, approved

        yield SimpleNamespace(
            factory=factory,
            clients=clients,
            wrappers=wrappers,
            stores=stores,
            keys=keys,
            verify=verify,
            recheck=recheck,
            mutate=mutate,
            stage=stage,
            user_id=user_id,
            sid=sid,
            evidence=evidence,
            token=token,
        )
    finally:
        # Exact known synthetic keys only; never FLUSHDB or pattern deletion.
        try:
            if keys:
                await clients[0].delete(*keys)
        finally:
            try:
                await asyncio.gather(*(client.aclose() for client in clients))
            finally:
                await engine.dispose()
                try:
                    if created:
                        async with admin.begin() as conn:
                            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                finally:
                    await admin.dispose()


async def test_native_direct_proof_preserves_parent_and_stored_assurance(native):
    proof = await native.verify()
    _, _, issued = await native.stage(proof)
    user, parent = await native.recheck(proof)
    assert user.id == native.user_id and parent.id == native.sid
    assert session_assurance(parent) == native.evidence
    approved = await native.stores[1].approved(issued.code)
    await native.stores[1].consume_approval(approved)
    async with native.factory() as db:
        assert session_assurance(await db.get(Session, native.sid)) == native.evidence
        assert len((await db.execute(select(Session))).scalars().all()) == 1
        assert len((await db.execute(select(User))).scalars().all()) == 1


@pytest.mark.parametrize("kind", ["access", "refresh"])
async def test_native_committed_direct_rotation_refuses_old_proof_and_token(native, kind):
    proof = await native.verify(kind)
    await native.mutate(**{f"{kind}_token_jti": "F-909-" + uuid4().hex})
    with pytest.raises(InvalidSessionProof):
        await native.recheck(proof)
    with pytest.raises(InvalidSessionProof):
        await native.verify(kind)


@pytest.mark.parametrize(
    "change", ["revoked", "inactive", "expired", "user_disabled", "parent_family", "assurance"]
)
async def test_native_committed_parent_user_and_evidence_changes_refuse_approved_proof(
    native, change
):
    proof = await native.verify()
    await native.stage(proof)
    if change == "revoked":
        await native.mutate(revoked=True)
    elif change == "inactive":
        await native.mutate(is_active=False)
    elif change == "expired":
        await native.mutate(expires_at=datetime.utcnow() - timedelta(seconds=1))
    elif change == "user_disabled":
        await native.mutate(User, status=UserStatus.SUSPENDED)
    elif change == "parent_family":
        await native.mutate(refresh_token_family="F-910-" + uuid4().hex)
    else:
        await native.mutate(authentication_methods=["password"])
    with pytest.raises(InvalidSessionProof):
        await native.recheck(proof)


async def test_native_enrolled_mfa_refuses_primary_only_current_session(native):
    await native.mutate(authentication_methods=["password"], mfa_verified_at=None)
    with pytest.raises(InvalidSessionProof):
        await native.verify()


async def test_native_oidc_refresh_requires_actual_parent_and_exact_stored_evidence(native):
    proof = await native.verify("refresh", oidc=True)
    assert proof["proof_kind"] == "oidc" and proof["session_id"] == str(native.sid)
    await native.recheck(proof)
    with pytest.raises(InvalidSessionProof):
        await native.verify("refresh", oidc=True, sid=None)
    with pytest.raises(InvalidSessionProof):
        await native.verify("refresh", oidc=True, amr=["password"])


@pytest.mark.parametrize("revocation", ["proof_jti", "proof_family", "parent_family"])
async def test_native_redis_revocation_after_approval_is_observed_by_other_client(
    native, revocation
):
    proof = await native.verify("refresh", oidc=True)
    await native.stage(proof)
    if revocation == "proof_jti":
        key = token_revocation.jti_keys(proof[revocation])[0]
        native.keys.add(key)
        await token_revocation.revoke_jti(
            native.wrappers[0], proof[revocation], 60, reason="F-911", strict=True
        )
    else:
        key = token_revocation.family_key(proof[revocation])
        native.keys.add(key)
        await token_revocation.revoke_family(
            native.wrappers[0], proof[revocation], 60, reason="F-911", strict=True
        )
    assert await native.clients[1].exists(key) == 1
    with pytest.raises(InvalidSessionProof):
        await native.recheck(proof)


async def test_native_independent_redis_clients_compare_consume_exactly_once(native):
    proof = await native.verify()
    _, _, issued = await native.stage(proof)
    approvals = await asyncio.gather(*(store.approved(issued.code) for store in native.stores))
    results = await asyncio.gather(
        *(store.consume_approval(approval) for store, approval in zip(native.stores, approvals)),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, InvalidBridgeState) for result in results) == 1
    with pytest.raises(InvalidBridgeState):
        await native.stores[0].approved(issued.code)


async def test_native_wrong_browser_and_old_source_code_do_not_spend_final_approval(native):
    proof = await native.verify()
    begun, code, issued = await native.stage(proof, reject_browser=True)
    with pytest.raises(InvalidBridgeState):
        await native.stores[1].approved(begun.state)
    with pytest.raises(InvalidBridgeState):
        await native.stores[1].bound(begun.state, code.code, begun.browser_secret)
    approved = await native.stores[1].approved(issued.code)
    await native.stores[1].consume_approval(approved)


@pytest.mark.parametrize("change", ["uri", "audience", "disabled"])
async def test_native_jsonb_source_selection_and_current_registered_pair_after_approval(
    native, change
):
    # The exact JSONB containment expression used by mounted GETstart, not a
    # Python-side list filter or an injected client lookup.
    async with native.factory() as db:
        sources = (
            (
                await db.execute(
                    select(OAuthClient)
                    .where(
                        OAuthClient.is_active.is_(True),
                        OAuthClient.is_confidential.is_(True),
                        OAuthClient.redirect_uris.contains([SOURCE_URI]),
                    )
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        assert len(sources) == 1 and sources[0].client_id == "jnc_F-901"
    proof = await native.verify()
    _, _, issued = await native.stage(proof)
    approved = await native.stores[1].approved(issued.code)
    async with native.factory() as db:
        source, target, authorization = await bridge._pair(approved.transaction, db)
        assert source.client_id == "jnc_F-901" and target.client_id == "jnc_F-902"
        assert authorization == approved.transaction["authorization"]
    values = (
        {"redirect_uris": []}
        if change == "uri"
        else {"audience": "F-999"} if change == "audience" else {"is_active": False}
    )
    async with native.factory.begin() as db:
        await db.execute(
            update(OAuthClient).where(OAuthClient.client_id == "jnc_F-901").values(**values)
        )
    async with native.factory() as db:
        with pytest.raises(InvalidBridgeState):
            await bridge._pair(approved.transaction, db)
    # Policy re-read refusal is separate from HTTP response/cookie behavior.
    await native.stores[1].consume_approval(approved)
