"""Synthetic tenant-password and cookie-bound MFA acceptance; no external services."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pyotp
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.auth.authentication_assurance import (
    assurance_claims,
    has_mfa_assurance,
    require_recent_authentication,
    session_assurance,
)
from app.auth.hosted_security import COOKIE
from app.auth.tenant_login_context import login_client_context, login_user
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.models import (
    Base,
    OAuthClient,
    Organization,
    OrganizationMember,
    PasswordReset,
    User,
    UserStatus,
)
from app.models import Session as UserSession
from app.models.organization_authentication_policy import OrganizationAuthenticationPolicy
from app.services.auth_service import AuthService

PASSWORD = "Synthetic-Password-7!"
RETURN = "https://map.test/api/auth/login?siguiente=/ajustes/seguridad"


@pytest_asyncio.fixture
async def env(monkeypatch):
    import app.auth.hosted_security as hosted
    import app.services.auth_service as service
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.main import app
    from app.routers.v1 import auth

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # Model PostgreSQL partial indexes faithfully on SQLite (the PostgreSQL
        # dialect predicate is otherwise dropped and falsely makes email global).
        await connection.exec_driver_sql("DROP INDEX uq_users_email_global")
        await connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_users_email_global ON users(email) WHERE tenant_id IS NULL"
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))

    async def get_session():
        async with factory() as db:
            yield db

    get_memory_redis = AsyncMock(return_value=redis)
    for module in (core_redis, auth, hosted, service):
        monkeypatch.setattr(module, "get_redis", get_memory_redis)
    monkeypatch.setattr(auth, "send_password_reset_email_task", AsyncMock())
    previous = dict(app.dependency_overrides)
    for key in (get_db, core_get_db):
        app.dependency_overrides[key] = get_session
    for key in (core_redis.get_redis, dependencies.get_redis, auth.get_redis):
        app.dependency_overrides[key] = lambda: redis
    # Production DI captures the original function before the test monkeypatch.
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for child in dependant.dependencies:
                if getattr(child.call, "__name__", "") in ("get_redis", "mock_get_redis"):
                    app.dependency_overrides[child.call] = lambda: redis
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=org_id,
        email="member@example.com",
        password_hash=AuthService.hash_password(PASSWORD),
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    async with factory() as db:
        db.add(user)
        db.add(Organization(id=org_id, name="Synthetic org", slug="synthetic", owner_id=user_id))
        db.add(
            OrganizationMember(
                user_id=user_id, organization_id=org_id, role="owner", status="active"
            )
        )
        db.add(
            OAuthClient(
                client_id="synthetic-map",
                name="Synthetic MAP",
                organization_id=org_id,
                created_by=user_id,
                client_secret_hash="not-a-real-secret",
                client_secret_prefix="synthetic",
                redirect_uris=["https://map.test/api/auth/callback"],
                is_active=True,
                is_confidential=False,
                audience="synthetic-map",
            )
        )
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
        yield SimpleNamespace(
            http=http,
            factory=factory,
            redis=redis,
            user=user,
            org_id=org_id,
            mail=auth.send_password_reset_email_task,
        )
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    await engine.dispose()


async def _login(env):
    return await env.http.post(
        "/api/v1/auth/login-form",
        data={
            "email": env.user.email,
            "password": PASSWORD,
            "client_id": "synthetic-map",
            "next": "/",
        },
    )


async def _require(env, requirement="organization"):
    async with env.factory() as db:
        if requirement == "technical-role":
            from app.models.app_role import OrganizationMemberAppRole

            member = (await db.execute(select(OrganizationMember))).scalar_one()
            db.add(OrganizationMemberAppRole(
                organization_member_id=member.id, app="crea-map", role="mfa-required"
            ))
            await db.commit()
            return
        db.add(
            OrganizationAuthenticationPolicy(
                organization_id=env.org_id, mfa_mode="required", version=1, updated_by=env.user.id
            )
        )
        await db.commit()


async def _flow(env):
    response = await _login(env)
    assert response.status_code == 200
    match = re.search(r'name="flow_id" value="([^"]+)"', response.text)
    assert match, response.text
    flow = match.group(1)
    data = json.loads(await env.redis.strict_get("auth:factor:" + flow))
    return flow, data, response


async def test_tenant_password_uses_existing_subject_and_never_global_same_email(env):
    async with env.factory() as db:
        db.add(
            User(
                email=env.user.email,
                password_hash=AuthService.hash_password("Different-Pass-1!"),
                status=UserStatus.ACTIVE,
                is_active=True,
            )
        )
        await db.commit()
    response = await _login(env)
    assert response.status_code == 302
    async with env.factory() as db:
        sessions = (await db.execute(select(UserSession))).scalars().all()
        assert len(sessions) == 1 and sessions[0].user_id == env.user.id
        assert sessions[0].authentication_methods == ["pwd"]
        assert sessions[0].authenticated_at is not None


async def test_bound_prelogin_rejects_forged_client(env):
    await env.redis.strict_set(
        "oauth:pre_login:one",
        json.dumps(
            {
                "client_id": "synthetic-map",
                "redirect_uri": "https://map.test/api/auth/callback",
            }
        ),
        ex=600,
    )
    async with env.factory() as db:
        with pytest.raises(HTTPException) as error:
            await login_client_context(db, env.redis, auth_request_id="one", client_id="other")
        assert error.value.status_code == 400


async def test_scoped_recovery_targets_passwordless_same_subject(env, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.password_hash = None
        db.add(
            User(
                email=user.email,
                password_hash=AuthService.hash_password(PASSWORD),
                status=UserStatus.ACTIVE,
                is_active=True,
            )
        )
        await db.commit()
    response = await env.http.post(
        "/api/v1/auth/password/forgot",
        json={
            "email": env.user.email,
            "client_id": "synthetic-map",
            "return_url": RETURN,
        },
    )
    assert response.status_code == 200, response.text
    async with env.factory() as db:
        reset = (await db.execute(select(PasswordReset))).scalar_one()
        assert reset.user_id == env.user.id
        token = reset.token
    response = await env.http.post(
        "/api/v1/auth/reset-password-form",
        data={
            "token": token,
            "new_password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )
    assert response.status_code == 200 and "Contraseña guardada" in response.text
    assert "https://map.test/api/auth/login" in response.text
    assert (await _login(env)).status_code == 302


@pytest.mark.parametrize("requirement", ["organization", "technical-role"])
async def test_required_unenrolled_has_no_session_until_factor_and_flow_is_one_use(env, requirement):
    await _require(env, requirement)
    flow, data, response = await _flow(env)
    assert "style-src 'sha256-" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert COOKIE + "=" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"] and "Secure" in response.headers["set-cookie"]
    async with env.factory() as db:
        assert not (await db.execute(select(UserSession))).scalars().all()
    code = pyotp.TOTP(data["setup_secret"]).now()
    result = await env.http.post(
        "/api/v1/auth/factor/complete", data={"flow_id": flow, "code": code}
    )
    assert result.status_code == 200 and "códigos de recuperación" in result.text
    async with env.factory() as db:
        session = (await db.execute(select(UserSession))).scalar_one()
        assert session.user_id == env.user.id
        assert session.authentication_methods == ["pwd", "otp"]
        assert (
            int(
                session.authenticated_at.replace(
                    tzinfo=__import__("datetime").timezone.utc
                ).timestamp()
            )
            == data["auth_time"]
        )
        assert has_mfa_assurance(session_assurance(session))
    replay = await env.http.post(
        "/api/v1/auth/factor/complete", data={"flow_id": flow, "code": code}
    )
    assert replay.status_code in (400, 403)
    async with env.factory() as db:
        assert len((await db.execute(select(UserSession))).scalars().all()) == 1


async def test_flow_cannot_be_spent_in_another_browser(env):
    await _require(env)
    flow, data, _ = await _flow(env)
    env.http.cookies.clear()
    result = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={"flow_id": flow, "code": pyotp.TOTP(data["setup_secret"]).now()},
    )
    assert result.status_code == 403


async def test_membership_removed_during_continuation_is_refused(env):
    await _require(env)
    flow, data, _ = await _flow(env)
    async with env.factory() as db:
        member = (await db.execute(select(OrganizationMember))).scalar_one()
        member.status = "removed"
        await db.commit()
    result = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={"flow_id": flow, "code": pyotp.TOTP(data["setup_secret"]).now()},
    )
    assert result.status_code == 403


async def test_backup_spend_persists_across_sqlalchemy_sessions(env):
    from app.routers.v1.mfa import consume_backup_code, hash_backup_code

    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.mfa_backup_codes = [{"hash": hash_backup_code("ABCD-1234"), "used": False}]
        await db.commit()
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        assert consume_backup_code(user, "ABCD-1234")
        await db.commit()
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        assert not consume_backup_code(user, "ABCD-1234")


async def test_recent_assurance_requires_live_bound_session_and_not_refreshed_time(env):
    now = datetime.utcnow()
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        access, refresh, session = await AuthService.create_session(
            db,
            user,
            authentication_methods=["pwd", "otp"],
            authenticated_at=now - timedelta(seconds=30),
            mfa_verified_at=now - timedelta(seconds=20),
        )
        original = session_assurance(session)
        new_access, _ = await AuthService.refresh_tokens(db, refresh)
        claims = await AuthService.verify_token(new_access)
        assert {k: claims.get(k) for k in original} == original
        request = Request(
            {"type": "http", "headers": [(b"authorization", ("Bearer " + new_access).encode())]}
        )
        await require_recent_authentication(request, db, user, require_mfa=True)
        session.revoked = True
        await db.commit()
        with pytest.raises(HTTPException) as error:
            await require_recent_authentication(request, db, user, require_mfa=True)
        assert error.value.status_code == 401


async def test_optional_enrolled_user_is_challenged_even_with_legacy_flag_off(env):
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.mfa_enabled, user.mfa_secret = True, pyotp.random_base32()
        await db.commit()
    flow, data, _ = await _flow(env)
    assert data["setup_secret"] is None
    assert not data["methods"] == ["pwd", "otp"]


@pytest.mark.parametrize("requirement", ["organization", "technical-role"])
async def test_current_policy_blocks_refresh_of_weak_existing_session(env, requirement):
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        _, refresh, _ = await AuthService.create_session(
            db, user, authentication_methods=["pwd"], authenticated_at=datetime.utcnow()
        )
    await _require(env, requirement)
    async with env.factory() as db:
        assert await AuthService.refresh_tokens(db, refresh) is None


@pytest.mark.parametrize("requirement", ["organization", "technical-role"])
async def test_unpinned_platform_member_obeys_required_organization(env, requirement):
    from app.auth.authentication_assurance import user_requires_mfa

    await _require(env, requirement)
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.tenant_id = None
        await db.commit()
        assert await user_requires_mfa(db, user)


async def _oauth_code(env, monkeypatch):
    from app.routers.v1 import oauth_provider

    monkeypatch.setattr(oauth_provider.ConsentService, "has_consent", AsyncMock(return_value=True))
    response = await env.http.get(
        "/api/v1/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "synthetic-map",
            "redirect_uri": "https://map.test/api/auth/callback",
            "scope": "openid profile email",
            "state": "synthetic-state",
            "code_challenge": "synthetic-challenge",
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 302, response.text
    from urllib.parse import parse_qs, urlsplit

    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query.get("state") == ["synthetic-state"]
    assert query.get("code"), response.headers["location"]
    return query["code"][0]


@pytest.mark.parametrize("requirement", ["organization", "technical-role"])
async def test_mfa_oauth_does_not_loop_and_code_refresh_keep_same_session_proof(env, monkeypatch, requirement):
    from app.routers.v1 import oauth_provider

    await _require(env, requirement)
    flow, data, _ = await _flow(env)
    response = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={"flow_id": flow, "code": pyotp.TOTP(data["setup_secret"]).now()},
    )
    assert response.status_code == 200
    code = await _oauth_code(env, monkeypatch)
    async with env.factory() as db:
        client = (await db.execute(select(OAuthClient))).scalar_one()
        # A real verifier is checked at /token; replace only the test's fixed
        # challenge with SHA256(verifier) in its already-issued synthetic record.
        record = await oauth_provider._get_auth_code(code, env.redis)
        import base64

        verifier = "verifier-value-with-at-least-forty-three-characters"
        record["code_challenge"] = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        await oauth_provider._store_auth_code(code, record, env.redis)
        tokens = await oauth_provider._handle_authorization_code_grant(
            code, "https://map.test/api/auth/callback", client, verifier, db, env.redis
        )
        claims = await AuthService.verify_token(tokens.access_token)
        assert claims["amr"] == ["pwd", "otp"]
        assert claims["auth_time"] == data["auth_time"]
        refreshed = await oauth_provider._handle_refresh_token_grant(
            tokens.refresh_token, client, db, env.redis
        )
        again = await AuthService.verify_token(refreshed.access_token)
        for key in ("sid", "amr", "auth_time", "mfa_time"):
            assert again[key] == claims[key]


@pytest.mark.parametrize("requirement", ["organization", "technical-role"])
async def test_policy_change_between_authorize_and_token_refuses_weak_code(env, monkeypatch, requirement):
    from app.routers.v1 import oauth_provider

    assert (await _login(env)).status_code == 302
    code = await _oauth_code(env, monkeypatch)
    await _require(env, requirement)
    monkeypatch.setattr(oauth_provider, "_verify_pkce", lambda *args: True)
    async with env.factory() as db:
        client = (await db.execute(select(OAuthClient))).scalar_one()
        with pytest.raises(HTTPException) as error:
            await oauth_provider._handle_authorization_code_grant(
                code,
                "https://map.test/api/auth/callback",
                client,
                "synthetic-verifier",
                db,
                env.redis,
            )
        assert error.value.status_code == 400
        assert "multi-factor" in str(error.value.detail)


async def test_scoped_reset_page_and_policy_errors_are_spanish(env):
    response = await env.http.get(
        "/api/v1/auth/reset-password", params={"token": "synthetic-token", "ui_locales": "es"}
    )
    assert response.status_code == 200
    assert "Elige tu contraseña" in response.text and "Guardar contraseña" in response.text
    response = await env.http.post(
        "/api/v1/auth/reset-password-form",
        data={
            "token": "synthetic-token",
            "new_password": "Different-1!",
            "confirm_password": "Other-2!",
            "ui_locales": "es",
        },
    )
    assert response.status_code == 400 and "no coinciden" in response.text


async def test_disabling_optional_factor_revokes_previously_strong_sessions(env):
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.mfa_enabled, user.mfa_secret = True, pyotp.random_base32()
        secret = user.mfa_secret
        access, _, session = await AuthService.create_session(
            db,
            user,
            authentication_methods=["pwd", "otp"],
            authenticated_at=datetime.utcnow(),
            mfa_verified_at=datetime.utcnow(),
        )
        sid = session.id
    response = await env.http.post(
        "/api/v1/mfa/disable",
        json={"password": PASSWORD, "code": pyotp.TOTP(secret).now()},
        headers={"authorization": "Bearer " + access},
    )
    assert response.status_code == 200, response.text
    assert await AuthService.verify_token(access) is None
    async with env.factory() as db:
        session = await db.get(UserSession, sid)
        assert session.revoked and not session.is_active
        user = await db.get(User, env.user.id)
        assert not user.mfa_enabled and user.mfa_secret is None


async def test_hosted_password_recovery_link_retains_validated_client_context(env):
    response = await env.http.get(
        "/api/v1/auth/login",
        params={"client_id": "synthetic-map", "login_method": "password", "ui_locales": "es"},
    )
    assert response.status_code == 200
    assert "Crear o recuperar mi contraseña" in response.text
    assert "client_id=synthetic-map" in response.text
    assert "forgot-password?ui_locales=es&amp;client_id=synthetic-map" in response.text


@pytest.mark.parametrize("password", ["Strong-Password-7!" * 6, "Ä" * 36 + "Aa1!"])
def test_password_strength_rejects_bcrypt_truncation(password):
    assert not AuthService.validate_password_strength(password)[0]


async def test_factor_disable_locks_actor_before_reading_current_policy(monkeypatch):
    from unittest.mock import MagicMock

    import app.services.organization_authentication_policy as policy
    from app.routers.v1.mfa import MFADisableRequest, disable_mfa

    actor_id, org_id = uuid.uuid4(), uuid.uuid4()
    stale = SimpleNamespace(id=actor_id, tenant_id=org_id, mfa_enabled=True)
    refreshed = SimpleNamespace(id=actor_id, tenant_id=org_id, mfa_enabled=True)
    statements = []
    locked_result = MagicMock()
    locked_result.scalar_one.return_value = refreshed
    memberships_result = MagicMock()
    memberships_result.scalars.return_value.all.return_value = []

    async def execute(statement):
        statements.append(statement)
        return locked_result if len(statements) == 1 else memberships_result

    db = SimpleNamespace(execute=execute)

    async def requires(_db, _org):
        assert statements[0]._for_update_arg is not None
        assert statements[0].get_execution_options()["populate_existing"] is True
        assert len(statements) == 2  # actor lock, then the current membership read
        return True

    monkeypatch.setattr(policy, "organization_requires_mfa", requires)
    with pytest.raises(HTTPException) as error:
        await disable_mfa(
            MFADisableRequest(password=PASSWORD, code="123456"), current_user=stale, db=db
        )
    assert error.value.status_code == 403


async def test_factor_screen_names_escaped_actual_identity(env):
    await _require(env)
    _, _, response = await _flow(env)
    assert "Cuenta: <strong>" + env.user.email + "</strong>" in response.text


async def test_account_disabled_while_factor_is_pending_is_refused(env):
    await _require(env)
    flow, data, _ = await _flow(env)
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.is_active = False
        await db.commit()
    response = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={
            "flow_id": flow,
            "code": pyotp.TOTP(data["setup_secret"]).now(),
        },
    )
    assert response.status_code == 403
    async with env.factory() as db:
        assert not (await db.execute(select(UserSession))).scalars().all()


@pytest.mark.parametrize('channel', ['hosted', 'json'])
async def test_technical_role_magic_link_never_mints_a_session_without_factor(env, channel):
    from app.models import MagicLink

    await _require(env, 'technical-role')
    token = 'synthetic-magic-token-never-emailed'
    async with env.factory() as db:
        db.add(MagicLink(user_id=env.user.id, email=env.user.email, token=token,
                         redirect_url='https://map.test/api/auth/callback',
                         expires_at=datetime.utcnow() + timedelta(minutes=15)))
        await db.commit()
    if channel == 'json':
        response = await env.http.post('/api/v1/auth/magic-link/verify', json={'token': token})
        assert response.status_code == 200
        assert response.json()['mfa_required'] is True
        assert response.json()['tokens'] is None
    else:
        await env.http.get('/api/v1/auth/magic-link/callback', params={'token': token})
        response = await env.http.post('/api/v1/auth/magic-link/callback', data={'token': token})
        assert response.status_code == 200
        match = re.search(r'name="flow_id" value="([^"]+)"', response.text)
        assert match
        flow_id = match.group(1)
        data = json.loads(await env.redis.strict_get('auth:factor:' + flow_id))
        assert data['methods'] == ['email']
    async with env.factory() as db:
        assert not (await db.execute(select(UserSession))).scalars().all()
    if channel == 'hosted':
        result = await env.http.post('/api/v1/auth/factor/complete', data={
            'flow_id': flow_id, 'code': pyotp.TOTP(data['setup_secret']).now()
        })
        assert result.status_code == 200
        async with env.factory() as db:
            session = (await db.execute(select(UserSession))).scalar_one()
            assert session.authentication_methods == ['email', 'otp']
            assert has_mfa_assurance(session_assurance(session))


async def test_technical_role_cannot_disable_factor_under_optional_team_policy(env):
    from app.routers.v1.mfa import MFADisableRequest, disable_mfa
    await _require(env, 'technical-role')
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        with pytest.raises(HTTPException) as error:
            await disable_mfa(MFADisableRequest(password=PASSWORD, code='123456'),
                              current_user=user, db=db)
        assert error.value.status_code == 403


@pytest.mark.parametrize('change', ['revoked', 'inactive', 'other-app', 'other-org'])
async def test_role_requirement_is_live_and_scoped(env, change):
    from app.models.app_role import OrganizationMemberAppRole
    from app.services.organization_authentication_policy import member_requires_mfa
    await _require(env, 'technical-role')
    async with env.factory() as db:
        assert await member_requires_mfa(db, env.user.id, env.org_id)
        grant = (await db.execute(select(OrganizationMemberAppRole))).scalar_one()
        if change == 'revoked':
            grant.revoked_at = datetime.utcnow()
        if change == 'other-app':
            grant.app = 'another-app'
        if change == 'inactive':
            member = (await db.execute(select(OrganizationMember))).scalar_one()
            member.status = 'inactive'
        await db.commit()
        org_id = uuid.uuid4() if change == 'other-org' else env.org_id
        assert not await member_requires_mfa(db, env.user.id, org_id)


async def test_technical_role_blocks_weak_sso_authorization(env, monkeypatch):
    from app.routers.v1 import oauth_provider
    assert (await _login(env)).status_code == 302
    await _require(env, 'technical-role')
    monkeypatch.setattr(oauth_provider.ConsentService, 'has_consent', AsyncMock(return_value=True))
    response = await env.http.get('/api/v1/oauth/authorize', params={
        'response_type':'code', 'client_id':'synthetic-map',
        'redirect_uri':'https://map.test/api/auth/callback', 'scope':'openid',
        'state':'synthetic-state', 'code_challenge':'synthetic-challenge',
        'code_challenge_method':'S256', 'prompt':'none',
    })
    assert response.status_code == 302
    assert 'interaction_required' in response.headers['location']
    assert 'code=' not in response.headers['location']


async def test_unreadable_role_requirement_is_not_optional(monkeypatch):
    from app.services import organization_authentication_policy as policy
    monkeypatch.setattr(policy, 'organization_requires_mfa', AsyncMock(return_value=False))
    db = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError('synthetic read failure')))
    with pytest.raises(RuntimeError):
        await policy.member_requires_mfa(db, uuid.uuid4(), uuid.uuid4())
