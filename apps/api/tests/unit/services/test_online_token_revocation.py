"""Mounted online token revocation regression tests; real DB and signed tokens."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.jwt_manager import jwt_manager
from app.dependencies import get_current_user
from app.models import Base, Session, User, UserStatus
from app.routers.v1 import admin, auth, oauth_provider, sessions
from app.services.auth_service import AuthService


class MemoryRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, **kw):
        if kw.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def setex(self, key, ttl, value):
        self.values[key] = value


@pytest_asyncio.fixture
async def fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: Base.metadata.create_all(sync, tables=[User.__table__, Session.__table__])
        )
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        user = User(
            id=uuid4(),
            email="fixture@example.test",
            status=UserStatus.ACTIVE,
            is_active=True,
            is_admin=True,
        )
        token, jti, _ = jwt_manager.create_access_token(str(user.id), user.email)
        session = Session(
            id=uuid4(),
            user_id=user.id,
            token=token,
            access_token_jti=jti,
            refresh_token_jti="fixture-refresh",
            revoked=False,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        db.add_all([user, session])
        await db.commit()
        redis = MemoryRedis()
        with (
            patch("app.core.redis.get_redis", AsyncMock(return_value=redis)),
            patch("app.services.auth_service.get_redis", AsyncMock(return_value=redis)),
            patch("app.services.token_state.get_redis", AsyncMock(return_value=redis)),
            patch("app.routers.v1.oauth_provider.get_redis", AsyncMock(return_value=redis)),
        ):
            yield db, user, token, jti, session, redis
    await engine.dispose()


def test_handlers_are_actually_mounted():
    from app.main import app

    routes = {(r.path, m): r.endpoint for r in app.routes for m in getattr(r, "methods", [])}
    assert routes[("/api/v1/auth/me", "GET")] is auth.get_current_user_info
    assert routes[("/api/v1/sessions/{session_id}", "DELETE")] is sessions.revoke_session
    assert routes[("/api/v1/admin/sessions/revoke-all", "POST")] is admin.revoke_all_sessions_admin
    assert routes[("/api/v1/oauth/revoke", "POST")] is oauth_provider.revoke


@pytest.mark.asyncio
async def test_admin_revoke_marks_row_and_denies_bearer(fixture):
    db, user, token, jti, session, redis = fixture
    await admin.revoke_all_sessions_admin(str(user.id), user, db)
    await db.refresh(session)
    assert session.revoked is True
    with pytest.raises(HTTPException) as denied:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, redis
        )
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_session_delete_persists_revocation(fixture):
    db, user, token, jti, session, redis = fixture
    result = await sessions.revoke_session(str(session.id), user, db)
    await db.refresh(session)
    assert result["message"] == "Session revoked successfully"
    assert session.revoked is True and session.is_active is False


@pytest.mark.asyncio
async def test_typed_blacklist_rejects_online_verification(fixture):
    db, user, token, jti, session, redis = fixture
    await jwt_manager.blacklist_token(jti, "access")
    assert redis.values[f"blacklist:access:{jti}"] == "revoked"
    assert jwt_manager.verify_token(token, "access") is not None
    assert await AuthService.verify_token(token, "access") is None
    with pytest.raises(HTTPException) as denied:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, redis
        )
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_boolean_inactive_and_suspended_status_both_deny(fixture):
    db, user, token, jti, session, redis = fixture
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user.is_active = False
    await db.commit()
    with pytest.raises(HTTPException) as inactive:
        await get_current_user(credentials, db, redis)
    assert inactive.value.status_code == 401
    user.status = UserStatus.SUSPENDED
    redis.values.clear()
    user.is_active = True
    await db.commit()
    with pytest.raises(HTTPException) as denied:
        await get_current_user(credentials, db, redis)
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_redis_failure_denies_bearer(fixture):
    db, user, token, jti, session, redis = fixture
    failing = AsyncMock()
    failing.get.side_effect = ConnectionError("fixture unavailable")
    failing.set.side_effect = ConnectionError("fixture unavailable")
    session.revoked = True
    await db.commit()
    with pytest.raises(HTTPException) as unavailable:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, failing
        )
    assert unavailable.value.status_code == 503


@pytest.mark.asyncio
async def test_oauth_revoke_stops_introspection(fixture):
    from types import SimpleNamespace

    from starlette.requests import Request

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(
        client_id="fixture-client",
        audience=jwt_manager.audience,
        is_active=True,
        is_confidential=True,
        verify_secret=lambda value: value == "fixture-secret",
    )
    oauth_token, _, _ = jwt_manager.create_access_token(
        str(user.id), user.email, {"client_id": client.client_id}
    )
    request = Request({"type": "http", "headers": []})
    with patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=client)):
        response = await oauth_provider.revoke(
            request, oauth_token, "access", client.client_id, "fixture-secret", db
        )
        introspected = await oauth_provider.introspect(
            request, oauth_token, "access", client.client_id, "fixture-secret", db
        )
    assert response == {"message": "Token revoked"}
    assert introspected["active"] is False


@pytest.mark.asyncio
async def test_oauth_refresh_rotates_once_and_replay_invalidates_family(fixture):
    from types import SimpleNamespace

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(client_id="fixture-client", audience=jwt_manager.audience)
    refresh, _, _, _ = jwt_manager.create_refresh_token(
        str(user.id), additional_claims={"client_id": client.client_id, "scope": "openid"}
    )
    claims = {"tier": "community", "roles": [], "sub_status": "active", "is_admin": False}
    with (
        patch.object(oauth_provider, "_get_user_entitlements", AsyncMock(return_value=claims)),
        patch.object(oauth_provider, "get_user_entitlements", AsyncMock(return_value=[])),
        patch.object(oauth_provider, "_get_user_org_claims", AsyncMock(return_value={})),
    ):
        first = await oauth_provider._handle_refresh_token_grant(refresh, client, db)
        with pytest.raises(HTTPException) as replay:
            await oauth_provider._handle_refresh_token_grant(refresh, client, db)
        assert replay.value.status_code == 400
        with pytest.raises(HTTPException) as family:
            await oauth_provider._handle_refresh_token_grant(first.refresh_token, client, db)
        assert family.value.status_code == 400
    assert jwt_manager.verify_token(first.access_token, "access") is not None


@pytest.mark.asyncio
async def test_password_refresh_rejects_revoked_flag_and_typed_refresh_blacklist(fixture):
    db, user, token, jti, session, redis = fixture
    refresh, refresh_jti, family, _ = AuthService.create_refresh_token(
        str(user.id), "fixture-tenant"
    )
    session.refresh_token_jti = refresh_jti
    session.refresh_token_family = family
    session.revoked = True
    await db.commit()
    await jwt_manager.blacklist_token(refresh_jti, "refresh")
    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements", AsyncMock(return_value=[])
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe", AsyncMock(return_value={})
        ),
    ):
        issued = await AuthService.refresh_tokens(db, refresh)
    assert issued is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("revoked", True),
        ("is_active", False),
        ("revoked_at", datetime(2026, 1, 1)),
        ("expires_at", datetime(2020, 1, 1)),
    ],
)
async def test_mapped_session_must_be_live_without_any_denylist_entry(fixture, field, value):
    db, user, token, jti, session, redis = fixture
    setattr(session, field, value)
    await db.commit()
    with pytest.raises(HTTPException) as denied:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, redis
        )
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_resilient_redis_missing_raw_client_never_falls_back_to_jwt_only(fixture):
    from app.core.redis_circuit_breaker import ResilientRedisClient

    db, user, token, jti, session, redis = fixture
    with patch("app.services.token_state.recover_security_redis", AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as unavailable:
            await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
                db,
                ResilientRedisClient(None),
            )
    assert unavailable.value.status_code == 503


@pytest.mark.asyncio
async def test_bearer_recovers_after_initial_redis_outage_without_restart(fixture, monkeypatch):
    import asyncio
    from unittest.mock import Mock

    from app.core import redis as redis_module
    from app.core.redis_circuit_breaker import ResilientRedisClient

    db, user, token, jti, session, redis = fixture
    raw = AsyncMock()
    raw.ping.side_effect = [ConnectionError("synthetic startup outage"), True]
    raw.get.return_value = None
    clock = Mock()
    clock.monotonic.return_value = 100.0
    monkeypatch.setattr(redis_module, "time", clock)
    monkeypatch.setattr(redis_module, "_security_redis_client", None)
    monkeypatch.setattr(redis_module, "_security_recovery_lock", asyncio.Lock())
    monkeypatch.setattr(redis_module, "_security_retry_at", 0.0)
    monkeypatch.setattr(redis_module.redis, "from_url", Mock(return_value=raw))
    cache = ResilientRedisClient(None)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as unavailable:
        await get_current_user(credentials, db, cache)
    assert unavailable.value.status_code == 503
    clock.monotonic.return_value = 105.0
    assert await get_current_user(credentials, db, cache) is user
    assert raw.ping.await_count == 2
    assert cache.redis is None
    # A recovered pool must still enforce the revoked-token predicate.
    raw.get.return_value = "revoked"
    with pytest.raises(HTTPException) as revoked:
        await get_current_user(credentials, db, cache)
    assert revoked.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_denylist_keys_remain_enforced(fixture):
    db, user, token, jti, session, redis = fixture
    redis.values[f"blacklist:{jti}"] = "1"
    assert await AuthService.verify_token(token, "access") is None
    with pytest.raises(HTTPException) as denied:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, redis
        )
    assert denied.value.status_code == 401


@pytest.mark.asyncio
async def test_atomic_refresh_consumption_allows_one_winner_and_blocks_family(fixture):
    import asyncio

    from app.services.token_state import consume_refresh, token_is_revoked

    db, user, token, jti, session, redis = fixture
    refresh, _, family, _ = jwt_manager.create_refresh_token(str(user.id))
    payload = jwt_manager.verify_token(refresh, "refresh")
    results = await asyncio.gather(consume_refresh(payload, redis), consume_refresh(payload, redis))
    assert sorted(results) == [False, True]
    child, _, _, _ = jwt_manager.create_refresh_token(str(user.id), family=family)
    assert await token_is_revoked(jwt_manager.verify_token(child, "refresh"), redis)


@pytest.mark.asyncio
async def test_password_refresh_invalidates_outgoing_access_and_accepts_new_pair(fixture):
    db, user, token, jti, session, redis = fixture
    refresh, refresh_jti, family, _ = AuthService.create_refresh_token(str(user.id), str(uuid4()))
    session.refresh_token_jti = refresh_jti
    session.refresh_token_family = family
    await db.commit()
    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements", AsyncMock(return_value=[])
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe", AsyncMock(return_value={})
        ),
    ):
        issued = await AuthService.refresh_tokens(db, refresh)
    assert issued is not None
    assert await AuthService.verify_token(token, "access") is None
    assert (
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=issued[0]), db, redis
        )
        is user
    )
    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements", AsyncMock(return_value=[])
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe", AsyncMock(return_value={})
        ),
    ):
        assert await AuthService.refresh_tokens(db, refresh) is None
        assert await AuthService.refresh_tokens(db, issued[1]) is None


@pytest.mark.asyncio
async def test_logout_persists_and_denies_bearer(fixture):
    db, user, token, jti, session, redis = fixture
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with (
        patch.object(auth, "log_activity", AsyncMock()),
        patch.object(auth, "log_audit_event", AsyncMock()),
    ):
        response = await auth.sign_out(user, credentials, db)
    assert response == {"message": "Successfully signed out"}
    await db.refresh(session)
    assert session.revoked and not session.is_active
    assert await AuthService.verify_token(token, "access") is None


@pytest.mark.asyncio
async def test_logout_does_not_acknowledge_storage_failure(fixture):
    db, user, token, jti, session, redis = fixture
    with patch.object(redis, "set", AsyncMock(side_effect=ConnectionError("fixture offline"))):
        with pytest.raises(HTTPException) as unavailable:
            await auth.sign_out(
                user, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db
            )
    assert unavailable.value.status_code == 503
    assert session.revoked is False


@pytest.mark.asyncio
async def test_oauth_refresh_rejects_suspended_user_before_issuing_tokens(fixture):
    from types import SimpleNamespace

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(client_id="fixture-client", audience=jwt_manager.audience)
    refresh, _, _, _ = jwt_manager.create_refresh_token(
        str(user.id), additional_claims={"client_id": client.client_id}
    )
    user.status = UserStatus.SUSPENDED
    await db.commit()
    with pytest.raises(HTTPException) as denied:
        await oauth_provider._handle_refresh_token_grant(refresh, client, db)
    assert denied.value.status_code == 400


@pytest.mark.asyncio
async def test_oauth_cannot_revoke_another_clients_token(fixture):
    from types import SimpleNamespace

    from starlette.requests import Request

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(
        client_id="client-a",
        audience=jwt_manager.audience,
        is_active=True,
        is_confidential=True,
        verify_secret=lambda secret: secret == "fixture-secret",
    )
    other_token, other_jti, _ = jwt_manager.create_access_token(
        str(user.id), user.email, {"client_id": "client-b"}
    )
    request = Request({"type": "http", "headers": []})
    with patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=client)):
        response = await oauth_provider.revoke(
            request, other_token, "access", client.client_id, "fixture-secret", db
        )
    assert response == {"message": "Token revoked"}
    assert f"blacklist:access:{other_jti}" not in redis.values


@pytest.mark.asyncio
async def test_rs256_signature_and_revocation_are_both_required(fixture):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    db, user, token, jti, session, redis = fixture
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with patch.multiple(
        jwt_manager, algorithm="RS256", private_key=private, public_key=private.public_key()
    ):
        signed, signed_jti, _ = jwt_manager.create_access_token(str(user.id), user.email)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=signed)
        assert await get_current_user(credentials, db, redis) is user
        claims = jwt_manager.verify_token(signed, "access")
        forged = jwt.encode(claims, impostor, algorithm="RS256")
        with pytest.raises(HTTPException) as invalid:
            await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged), db, redis
            )
        assert invalid.value.status_code == 401
        await jwt_manager.blacklist_token(signed_jti, "access")
        with pytest.raises(HTTPException) as revoked:
            await get_current_user(credentials, db, redis)
        assert revoked.value.status_code == 401


@pytest.mark.asyncio
async def test_oidc_logout_does_not_acknowledge_db_revocation_failure(fixture):
    from types import SimpleNamespace

    from starlette.requests import Request

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(is_active=True, redirect_uris=["https://example.test/callback"])
    request = Request({"type": "http", "headers": []})
    with (
        patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=client)),
        patch.object(
            oauth_provider,
            "revoke_sso_cookie_session",
            AsyncMock(side_effect=RuntimeError("fixture DB failure")),
        ),
    ):
        with pytest.raises(HTTPException) as unavailable:
            await oauth_provider._perform_oidc_end_session(
                "fixture-client", "https://example.test/callback", None, db, request
            )
    assert unavailable.value.status_code == 503


@pytest.mark.asyncio
async def test_oauth_introspection_fails_closed_during_redis_outage(fixture):
    from types import SimpleNamespace

    from starlette.requests import Request

    db, user, token, jti, session, redis = fixture
    client = SimpleNamespace(
        client_id="fixture-client",
        audience=jwt_manager.audience,
        is_active=True,
        is_confidential=True,
        verify_secret=lambda value: value == "fixture-secret",
    )
    oauth_token, _, _ = jwt_manager.create_access_token(
        str(user.id), user.email, {"client_id": client.client_id}
    )
    with (
        patch.object(oauth_provider, "_get_oauth_client", AsyncMock(return_value=client)),
        patch.object(redis, "get", AsyncMock(side_effect=ConnectionError("fixture offline"))),
    ):
        result = await oauth_provider.introspect(
            Request({"type": "http", "headers": []}),
            oauth_token,
            "access_token",
            client.client_id,
            "fixture-secret",
            db,
        )
    assert result == {"active": False}


@pytest.mark.asyncio
async def test_existing_redis_client_outage_cannot_use_its_missing_key_fallback(fixture):
    from app.core.redis_circuit_breaker import ResilientRedisClient

    db, user, token, jti, session, redis = fixture
    raw = AsyncMock()
    raw.get.side_effect = ConnectionError("fixture offline")
    resilient = ResilientRedisClient(raw)
    with pytest.raises(HTTPException) as unavailable:
        await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, resilient
        )
    assert unavailable.value.status_code == 503
    assert resilient.circuit_breaker.fallback_calls == 0


@pytest.mark.asyncio
async def test_database_failure_does_not_authenticate_even_with_valid_signature(fixture):
    db, user, token, jti, session, redis = fixture
    with patch.object(db, "execute", AsyncMock(side_effect=RuntimeError("fixture DB unavailable"))):
        with pytest.raises(RuntimeError, match="fixture DB unavailable"):
            await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, redis
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["header", "hosted_cookie", "session_endpoint"])
async def test_revoked_tokens_cannot_reauthorize_via_alternate_session_paths(fixture, transport):
    from starlette.requests import Request

    db, user, token, jti, session, redis = fixture
    if transport == "hosted_cookie":
        headers = [(b"cookie", f"janua_access_token={token}".encode())]
    else:
        headers = [(b"authorization", f"Bearer {token}".encode())]
    request = Request({"type": "http", "headers": headers})
    if transport == "session_endpoint":
        assert (await auth.check_session(request, db))["authenticated"] is True
    else:
        assert await oauth_provider.get_user_from_cookie_or_header(request, db) is user
    await admin.revoke_all_sessions_admin(str(user.id), user, db)
    if transport == "session_endpoint":
        with pytest.raises(HTTPException) as denied:
            await auth.check_session(request, db)
        assert denied.value.status_code == 401
    else:
        assert await oauth_provider.get_user_from_cookie_or_header(request, db) is None
