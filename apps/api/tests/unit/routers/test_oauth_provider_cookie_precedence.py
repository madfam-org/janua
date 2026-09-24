"""J9 — at `/authorize`, the estate session outranks a stale hosted-login cookie.

## The production failure this pins (2026-09-07)

A person signed into the MAP (`crea-map.madfam.io`) by magic link. The MAP's
verify exchange is server-to-server, so the only browser-visible trace of that
login is the relayed `janua_sso` cookie on `.madfam.io`. The ERP
(`crea-erp.madfam.io`) then ran silent SSO —
`GET /oauth/authorize?…&prompt=none` — and Janua issued a code for **a different
person**: the same browser still held a `janua_access_token` from an unrelated
hosted login on `auth.madfam.io` (an operator's `enclii login`), and resolution
read that cookie first. nauta logged `portal.silent_sso not_a_member` twice.

Nothing can clear that cookie from the MAP's side: it is scoped to the issuer
host, and `crea-map.madfam.io` cannot delete a cookie on `auth.madfam.io`.
`/signout` does not clear it either — only the OIDC `end_session` endpoint does.
Precedence at this one seam is therefore the only robust fix, and these tests
are what keep it.

## The rule

1. `Authorization: Bearer` — unchanged, still first (an API client names the
   identity it means to act as, explicitly, per request).
2. `janua_sso` — the estate session. Preferred over the hosted cookie because it
   is by definition the most recent estate login and because it is the only one
   of the three that is re-read from `sessions` on every use, hence revocable.
3. `janua_access_token` — the hosted-login session, used when no valid estate
   session exists.

Both valid and naming different people → the **newer** session by
`sessions.created_at`, logged at info with both ids redacted to a prefix. An
undatable hosted session (refresh rotation moves `access_token_jti`) cannot be
shown to be newer, so the estate session keeps precedence, as it does on a tie.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.auth.sso_cookie import SSO_COOKIE_NAME, mint_sso_cookie_value
from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.models import UserStatus
from app.routers.v1 import oauth_provider as oauth_provider_router
from app.routers.v1.oauth_provider import get_user_from_cookie_or_header

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------


def _user(user_id=None, email="persona@example.test"):
    return SimpleNamespace(
        id=user_id or uuid4(),
        email=email,
        email_verified=True,
        username="persona",
        first_name="Per",
        last_name="Sona",
        profile_image_url=None,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_sign_in_at=None,
        status=UserStatus.ACTIVE,
    )


def _session_row(user_id, *, created_at=None, revoked=False, is_active=True, jti=None):
    started = created_at or datetime.utcnow()
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        revoked=revoked,
        is_active=is_active,
        expires_at=datetime.utcnow() + timedelta(days=7),
        revoked_at=None,
        revoked_reason=None,
        created_at=started,
        last_activity=started,
        access_token_jti=jti,
    )


def _hosted_cookie(user, *, jti=None, audience=None):
    """A `janua_access_token` value: an access token Janua minted for `user`."""
    now = int(time.time())
    return jwt_manager.encode_token(
        {
            "sub": str(user.id),
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "aud": audience or settings.JWT_AUDIENCE,
            "iat": now,
            "exp": now + 3600,
            "jti": jti or str(uuid4()),
        }
    )


def _request(cookies, headers=None):
    request = MagicMock()
    request.headers = headers or {}
    request.cookies = cookies
    return request


def _db(*, sessions=None, users=None):
    """A db that answers the two query shapes resolution issues.

    `select(Session).where(...)` and `select(User).where(...)` are told apart by
    the entity the statement selects, so the order of lookups inside the resolver
    is not baked into the test — only the data is.
    """
    sessions = list(sessions or [])
    users = list(users or [])

    async def execute(statement):
        entity = statement.column_descriptions[0]["entity"]
        name = getattr(entity, "__name__", "")
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if name == "Session":
            match = next(
                (
                    s
                    for s in sessions
                    if str(s.id) in compiled
                    or (s.access_token_jti and f"'{s.access_token_jti}'" in compiled)
                ),
                None,
            )
        else:
            match = next((u for u in users if str(u.id) in compiled), None)
        return SimpleNamespace(scalar_one_or_none=lambda m=match: m)

    return SimpleNamespace(execute=AsyncMock(side_effect=execute), commit=AsyncMock())


# --------------------------------------------------------------------------
# (a) estate cookie only  /  (b) hosted cookie only
# --------------------------------------------------------------------------


class TestOneCookie:
    async def test_estate_cookie_alone_resolves(self):
        """Unchanged from R1: the MAP → ERP hop carries only this cookie."""
        user = _user()
        session = _session_row(user.id)
        resolved = await get_user_from_cookie_or_header(
            _request({SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), str(session.id))}),
            _db(sessions=[session], users=[user]),
        )
        assert resolved is user

    async def test_hosted_cookie_alone_resolves(self):
        """The hosted password form still works — it is a fallback, not a casualty."""
        user = _user()
        resolved = await get_user_from_cookie_or_header(
            _request({"janua_access_token": _hosted_cookie(user)}),
            _db(users=[user]),
        )
        assert resolved is user

    async def test_no_cookies_resolves_nobody(self):
        assert await get_user_from_cookie_or_header(_request({}), _db()) is None


# --------------------------------------------------------------------------
# (c) both valid, different users → the estate/newest session wins
# --------------------------------------------------------------------------


class TestDisagreement:
    def _both(self, *, estate_started, hosted_started):
        """The production shape: a fresh MAP login, a stale hosted login."""
        map_user = _user(email="creatumundomx@example.test")
        operator = _user(email="admin@example.test")
        estate_session = _session_row(map_user.id, created_at=estate_started)
        hosted_jti = str(uuid4())
        hosted_session = _session_row(
            operator.id, created_at=hosted_started, jti=hosted_jti
        )
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(
                    str(map_user.id), str(estate_session.id)
                ),
                "janua_access_token": _hosted_cookie(operator, jti=hosted_jti),
            }
        )
        db = _db(
            sessions=[estate_session, hosted_session], users=[map_user, operator]
        )
        return map_user, operator, request, db

    async def test_fresh_estate_session_beats_stale_hosted_cookie(self):
        """The exact production failure: the ERP must see the MAP's person."""
        now = datetime.utcnow()
        map_user, operator, request, db = self._both(
            estate_started=now - timedelta(minutes=3),  # 04:46 MAP magic link
            hosted_started=now - timedelta(minutes=46),  # 04:03 enclii login
        )
        resolved = await get_user_from_cookie_or_header(request, db)
        assert resolved is map_user
        assert resolved is not operator

    async def test_newer_hosted_session_beats_older_estate_session(self):
        """The rule is *newest*, not *estate always* — the symmetric case holds."""
        now = datetime.utcnow()
        map_user, operator, request, db = self._both(
            estate_started=now - timedelta(hours=6),
            hosted_started=now - timedelta(minutes=1),
        )
        resolved = await get_user_from_cookie_or_header(request, db)
        assert resolved is operator

    async def test_a_tie_goes_to_the_estate_session(self):
        now = datetime.utcnow()
        map_user, _operator, request, db = self._both(
            estate_started=now, hosted_started=now
        )
        assert await get_user_from_cookie_or_header(request, db) is map_user

    async def test_undatable_hosted_session_loses(self):
        """Refresh rotation moves `access_token_jti`, so the row may not be found.

        Unfindable is "cannot be shown to be newer", not "invalid" — the estate
        session keeps precedence rather than the request failing.
        """
        map_user = _user()
        operator = _user(email="admin@example.test")
        estate_session = _session_row(map_user.id, created_at=datetime.utcnow() - timedelta(days=2))
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(str(map_user.id), str(estate_session.id)),
                # jti belongs to no session row (rotated away).
                "janua_access_token": _hosted_cookie(operator),
            }
        )
        db = _db(sessions=[estate_session], users=[map_user, operator])
        assert await get_user_from_cookie_or_header(request, db) is map_user

    async def test_disagreement_is_logged_with_redacted_ids(self):
        """An operator must be able to see this happened, without full ids in logs."""
        now = datetime.utcnow()
        map_user, operator, request, db = self._both(
            estate_started=now - timedelta(minutes=3),
            hosted_started=now - timedelta(minutes=46),
        )
        with patch.object(oauth_provider_router, "logger") as log:
            await get_user_from_cookie_or_header(request, db)

        assert log.info.called
        kwargs = log.info.call_args.kwargs
        assert kwargs["winner"] == SSO_COOKIE_NAME
        assert kwargs["estate_user"] == f"{str(map_user.id)[:8]}…"
        assert kwargs["hosted_user"] == f"{str(operator.id)[:8]}…"
        # Full ids never reach the log line.
        rendered = repr(log.info.call_args)
        assert str(map_user.id) not in rendered
        assert str(operator.id) not in rendered


# --------------------------------------------------------------------------
# (d) both cookies, same user
# --------------------------------------------------------------------------


class TestSameUserInBothCookies:
    async def test_same_user_resolves_without_a_contest(self):
        user = _user()
        session = _session_row(user.id)
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), str(session.id)),
                "janua_access_token": _hosted_cookie(user),
            }
        )
        with patch.object(oauth_provider_router, "logger") as log:
            resolved = await get_user_from_cookie_or_header(
                request, _db(sessions=[session], users=[user])
            )
        assert resolved is user
        assert not log.info.called  # nothing disagreed; nothing to report


# --------------------------------------------------------------------------
# (e) a revoked estate session falls back to the hosted cookie
# --------------------------------------------------------------------------


class TestRevokedEstateSession:
    async def _run(self, **row_kwargs):
        map_user = _user()
        operator = _user(email="admin@example.test")
        estate_session = _session_row(map_user.id, **row_kwargs)
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(str(map_user.id), str(estate_session.id)),
                "janua_access_token": _hosted_cookie(operator),
            }
        )
        db = _db(sessions=[estate_session], users=[map_user, operator])
        return operator, await get_user_from_cookie_or_header(request, db)

    async def test_revoked_estate_session_falls_back_to_the_hosted_cookie(self):
        """Precedence is not immunity: a revoked row stops authenticating at once."""
        operator, resolved = await self._run(revoked=True)
        assert resolved is operator

    async def test_deactivated_estate_session_falls_back(self):
        operator, resolved = await self._run(is_active=False)
        assert resolved is operator

    async def test_revoked_estate_session_with_no_hosted_cookie_resolves_nobody(self):
        user = _user()
        estate_session = _session_row(user.id, revoked=True)
        request = _request(
            {SSO_COOKIE_NAME: mint_sso_cookie_value(str(user.id), str(estate_session.id))}
        )
        db = _db(sessions=[estate_session], users=[user])
        assert await get_user_from_cookie_or_header(request, db) is None


# --------------------------------------------------------------------------
# Bearer stays first
# --------------------------------------------------------------------------


class TestBearerStaysFirst:
    async def test_bearer_outranks_both_cookies(self):
        """API clients name their identity explicitly; nothing ambient overrides it."""
        api_user = _user(email="api@example.test")
        estate_user = _user()
        estate_session = _session_row(estate_user.id)
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(
                    str(estate_user.id), str(estate_session.id)
                ),
                "janua_access_token": _hosted_cookie(_user(email="admin@example.test")),
            },
            headers={"Authorization": f"Bearer {_hosted_cookie(api_user)}"},
        )
        db = _db(sessions=[estate_session], users=[api_user, estate_user])
        assert await get_user_from_cookie_or_header(request, db) is api_user


# --------------------------------------------------------------------------
# The precedence reaches /authorize itself, silently and interactively
# --------------------------------------------------------------------------


def _oauth_client(name="madfam-erp"):
    return SimpleNamespace(
        client_id=name,
        is_active=True,
        is_confidential=True,
        name=name,
        allowed_scopes=["openid", "profile", "email", "madfam:silent_auth"],
        redirect_uris=["https://erp.example.test/auth/callback"],
        audience=None,
        last_used_at=None,
    )


class TestAuthorizeHonoursThePrecedence:
    """End to end at the endpoint, because a helper that is right and an endpoint
    that is wrong is exactly the shape of the bug this lane fixes."""

    async def _authorize(self, prompt):
        now = datetime.utcnow()
        map_user = _user(email="creatumundomx@example.test")
        operator = _user(email="admin@example.test")
        estate_session = _session_row(map_user.id, created_at=now - timedelta(minutes=3))
        hosted_jti = str(uuid4())
        hosted_session = _session_row(
            operator.id, created_at=now - timedelta(minutes=46), jti=hosted_jti
        )
        request = _request(
            {
                SSO_COOKIE_NAME: mint_sso_cookie_value(
                    str(map_user.id), str(estate_session.id)
                ),
                "janua_access_token": _hosted_cookie(operator, jti=hosted_jti),
            }
        )
        db = _db(sessions=[estate_session, hosted_session], users=[map_user, operator])

        issued: dict = {}

        async def _capture_code(_code, data, _redis):
            """`_store_auth_code(code, data, redis)` — `data["user_id"]` is the
            identity the code will mint tokens for, which is the whole question."""
            issued.update(data)

        with (
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=_oauth_client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.parse_scopes",
                MagicMock(return_value=["openid", "profile"]),
            ),
            patch(
                "app.routers.v1.oauth_provider.ConsentService.has_consent",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.routers.v1.oauth_provider._store_auth_code",
                AsyncMock(side_effect=_capture_code),
            ),
            patch(
                "app.routers.v1.oauth_provider.settings",
                MagicMock(REQUIRE_EMAIL_VERIFICATION=False),
            ),
        ):
            response = await oauth_provider_router.authorize_get(
                request=request,
                response_type="code",
                client_id="madfam-erp",
                redirect_uri="https://erp.example.test/auth/callback",
                scope="openid profile email madfam:silent_auth",
                state="csrf-xyz",
                nonce=None,
                code_challenge="abc",
                code_challenge_method="S256",
                prompt=prompt,
                db=db,
                redis=AsyncMock(),
            )
        return map_user, operator, response, issued

    async def test_prompt_none_issues_a_code_for_the_estate_user(self):
        """The ERP's silent hop. Before J9 this issued a code for the operator."""
        map_user, operator, response, issued = await self._authorize("none")
        assert response.status_code == 302
        assert "code=" in response.headers["location"]
        assert "error=" not in response.headers["location"]
        assert str(issued["user_id"]) == str(map_user.id)
        assert str(issued["user_id"]) != str(operator.id)

    async def test_interactive_authorize_also_uses_the_estate_user(self):
        map_user, operator, response, issued = await self._authorize(None)
        assert response.status_code == 302
        assert "code=" in response.headers["location"]
        assert str(issued["user_id"]) == str(map_user.id)
        assert str(issued["user_id"]) != str(operator.id)
