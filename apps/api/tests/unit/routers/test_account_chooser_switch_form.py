"""The `prompt=select_account` chooser works as a plain HTML form, end to end.

Found live on 2026-10-04: every account in the chooser was a form-encoded
`<form method="post" action="/api/v1/auth/switch-session">`, but that route
takes a JSON body, so a click answered 422 VALIDATION_ERROR and left the browser
on a JSON page. And a person who had signed in five times was listed five times.

These tests drive the real app over ASGI: render the chooser at `/authorize`,
post the chosen account exactly as a browser posts the form, and follow the
redirect back into `/authorize`, which issues the code for the chosen account.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from html import unescape
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import fakeredis
import pytest

# Imported at collection time on purpose (a session fixture can swap httpx).
from httpx import ASGITransport, AsyncClient

from app.auth.sessions_cookie import SESSIONS_COOKIE_NAME, mint_sessions_cookie_value
from app.auth.sso_cookie import SSO_COOKIE_NAME, SSO_TOKEN_TYPE
from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import UserStatus
from app.routers.v1 import auth as auth_router
from app.routers.v1 import oauth_provider

pytestmark = pytest.mark.asyncio

REDIRECT_URI = "https://rp.example/api/auth/callback/janua"
FORM = "/api/v1/auth/switch-session/form"


def _user(email):
    return SimpleNamespace(
        id=uuid4(),
        email=email,
        username=email,
        status=UserStatus.ACTIVE,
        email_verified=True,
        created_at=None,
    )


def _session(user, *, minutes_ago):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        revoked=False,
        is_active=True,
        created_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
        expires_at=datetime.utcnow() + timedelta(days=7),
        revoked_at=None,
        revoked_reason=None,
    )


def _client():
    # A first-party client (pre-consented), as in the live report.
    return SimpleNamespace(
        id="c1",
        client_id="madfam-rp",
        name="madfam-rp",
        is_active=True,
        is_confidential=True,
        allowed_scopes=["openid", "profile", "email"],
        redirect_uris=[REDIRECT_URI],
        audience=None,
        last_used_at=None,
    )


class _Estate:
    """Users, their session rows, and a resolver over them."""

    def __init__(self, rows):
        self.rows = {str(s.id): (u, s) for u, s in rows}

    async def resolve(self, sid, db):
        return self.rows.get(str(sid), (None, None))


async def _http(estate, cookies, run):
    """Run `run(http)` against the real app with the estate wired in."""
    from app import main

    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))
    saved = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[oauth_provider.get_redis] = lambda: redis
    main.app.dependency_overrides[oauth_provider.get_db] = lambda: AsyncMock()
    main.app.dependency_overrides[auth_router.get_db] = lambda: AsyncMock()
    try:
        with (
            patch(
                "app.routers.v1.auth.resolve_session_by_id", AsyncMock(side_effect=estate.resolve)
            ),
            patch(
                "app.routers.v1.oauth_provider.resolve_session_by_id",
                AsyncMock(side_effect=estate.resolve),
            ),
            patch(
                "app.routers.v1.oauth_provider._get_oauth_client",
                AsyncMock(return_value=_client()),
            ),
            patch(
                "app.routers.v1.oauth_provider._validate_redirect_uri",
                MagicMock(return_value=True),
            ),
        ):
            transport = ASGITransport(app=main.app)
            async with AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as http:
                return await run(http)
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(saved)


def _authorize_query(prompt=None):
    q = {
        "response_type": "code",
        "client_id": "madfam-rp",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
        "state": "rp-state",
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
    }
    if prompt:
        q["prompt"] = prompt
    return q


def _forms(html):
    """(action, sid, next) for every account form on the chooser page."""
    out = []
    for block in re.findall(r"<form .*?</form>", html, flags=re.S):
        action = re.search(r'action="([^"]+)"', block).group(1)
        sid = re.search(r'name="sid" value="([^"]+)"', block).group(1)
        nxt = unescape(re.search(r'name="next" value="([^"]+)"', block).group(1))
        out.append((action, sid, nxt))
    return out


def _sso_sid(resp):
    for key, value in resp.headers.multi_items():
        if key.lower() == "set-cookie" and value.startswith(f"{SSO_COOKIE_NAME}="):
            token = value.split("=", 1)[1].split(";", 1)[0]
            payload = jwt_manager.verify_token(
                token, token_type=SSO_TOKEN_TYPE, verify_audience=False
            )
            return payload["sid"]
    return None


class TestChooserSwitchesByForm:
    async def test_chooser_form_switches_and_the_authorize_request_resumes(self):
        alice, bob = _user("alice@example.test"), _user("bob@example.test")
        s_alice, s_bob = _session(alice, minutes_ago=30), _session(bob, minutes_ago=5)
        estate = _Estate([(alice, s_alice), (bob, s_bob)])
        held = mint_sessions_cookie_value([str(s_alice.id), str(s_bob.id)])

        async def run(http):
            with patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ):
                page = await http.get(
                    "/api/v1/oauth/authorize", params=_authorize_query("select_account")
                )
            assert page.status_code == 200
            forms = _forms(page.text)
            assert len(forms) == 2
            action, sid, nxt = next(f for f in forms if f[1] == str(s_alice.id))
            assert action == FORM

            # Exactly what a browser sends for the chooser's form.
            switched = await http.post(
                action,
                data={"sid": sid, "next": nxt},
                headers={"Origin": "http://test"},
            )
            assert switched.status_code == 302
            assert _sso_sid(switched) == str(s_alice.id)
            location = switched.headers["location"]
            target = urlparse(location)
            assert target.path == "/api/v1/oauth/authorize"
            params = {k: v[0] for k, v in parse_qs(target.query).items()}
            assert params["state"] == "rp-state"
            assert params["client_id"] == "madfam-rp"
            assert params["code_challenge"] == _authorize_query()["code_challenge"]
            assert "prompt" not in params  # resuming must not reopen the chooser

            # Resume: /authorize now sees the chosen account and issues a code.
            with (
                patch(
                    "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                    AsyncMock(return_value=alice),
                ),
                patch(
                    "app.routers.v1.oauth_provider.ConsentService.has_consent",
                    AsyncMock(return_value=False),  # first party: pre-consented anyway
                ),
            ):
                resumed = await http.get(location)
            assert resumed.status_code == 302
            final = resumed.headers["location"]
            assert final.startswith(REDIRECT_URI)
            assert "code=" in final and "state=rp-state" in final

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_an_unheld_sid_is_refused_with_a_page_not_json(self):
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([str(uuid4())])  # alice's sid NOT held

        async def run(http):
            resp = await http.post(
                FORM,
                data={"sid": str(s_alice.id), "next": "/api/v1/oauth/authorize"},
                headers={"Origin": "http://test"},
            )
            assert resp.status_code == 400
            assert resp.headers["content-type"].startswith("text/html")
            assert SSO_COOKIE_NAME not in resp.headers.get("set-cookie", "")

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_a_held_but_dead_sid_is_refused(self):
        dead = str(uuid4())
        estate = _Estate([])
        held = mint_sessions_cookie_value([dead])

        async def run(http):
            resp = await http.post(FORM, data={"sid": dead}, headers={"Origin": "http://test"})
            assert resp.status_code == 400

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    @pytest.mark.parametrize(
        "headers",
        [
            {"Origin": "https://other.example"},
            {"Origin": "null"},
            {},
            {"Referer": "https://other.example/page"},
        ],
    )
    async def test_cross_origin_or_unattributed_posts_are_refused(self, headers):
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([str(s_alice.id)])

        async def run(http):
            resp = await http.post(FORM, data={"sid": str(s_alice.id)}, headers=headers)
            assert resp.status_code == 403
            assert _sso_sid(resp) is None

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_referer_from_janua_is_accepted_when_origin_is_absent(self):
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([str(s_alice.id)])

        async def run(http):
            resp = await http.post(
                FORM,
                data={"sid": str(s_alice.id)},
                headers={"Referer": "http://test/api/v1/oauth/authorize?x=1"},
            )
            assert resp.status_code == 302
            assert _sso_sid(resp) == str(s_alice.id)

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_the_json_route_answers_a_form_body_with_422(self):
        """The live bug: the chooser posted this form to the JSON route."""
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([str(s_alice.id)])

        async def run(http):
            resp = await http.post(
                "/api/v1/auth/switch-session",
                data={"sid": str(s_alice.id), "next": "/"},
                headers={"Origin": "http://test"},
            )
            assert resp.status_code == 422

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_the_json_route_is_unchanged(self):
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([str(s_alice.id)])

        async def run(http):
            resp = await http.post(
                "/api/v1/auth/switch-session", json={"sid": str(s_alice.id), "next": "/"}
            )
            assert resp.status_code == 302
            assert _sso_sid(resp) == str(s_alice.id)

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)


class TestChooserListsEachPersonOnce:
    async def test_dedup_through_the_rendered_chooser(self):
        alice, bob = _user("alice@example.test"), _user("bob@example.test")
        alice_sessions = [_session(alice, minutes_ago=m) for m in (50, 40, 5, 30, 20)]
        s_bob = _session(bob, minutes_ago=10)
        estate = _Estate([(alice, s) for s in alice_sessions] + [(bob, s_bob)])
        held = mint_sessions_cookie_value([str(s.id) for s in alice_sessions] + [str(s_bob.id)])

        async def run(http):
            with patch(
                "app.routers.v1.oauth_provider.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ):
                page = await http.get(
                    "/api/v1/oauth/authorize", params=_authorize_query("select_account")
                )
            forms = _forms(page.text)
            assert page.text.count("alice@example.test") == 1
            assert page.text.count("bob@example.test") == 1
            sids = [sid for _, sid, _ in forms]
            # Alice's newest live session (5 minutes old) is the one offered.
            assert str(alice_sessions[2].id) in sids
            assert len(sids) == 2

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_a_dead_newest_session_falls_back_to_the_newest_live_one(self):
        alice = _user("alice@example.test")
        old, newer = _session(alice, minutes_ago=60), _session(alice, minutes_ago=30)
        newest_dead = str(uuid4())  # not resolvable: revoked or expired
        estate = _Estate([(alice, old), (alice, newer)])
        with patch(
            "app.routers.v1.oauth_provider.resolve_session_by_id",
            AsyncMock(side_effect=estate.resolve),
        ):
            accounts = await oauth_provider._resolve_held_accounts(
                [str(old.id), str(newer.id), newest_dead], AsyncMock()
            )
        assert [sid for sid, _ in accounts] == [str(newer.id)]

    async def test_undatable_rows_keep_the_later_held_position(self):
        alice = _user("alice@example.test")
        first, second = _session(alice, minutes_ago=1), _session(alice, minutes_ago=1)
        first.created_at = None
        second.created_at = None
        estate = _Estate([(alice, first), (alice, second)])
        with patch(
            "app.routers.v1.oauth_provider.resolve_session_by_id",
            AsyncMock(side_effect=estate.resolve),
        ):
            accounts = await oauth_provider._resolve_held_accounts(
                [str(first.id), str(second.id)], AsyncMock()
            )
        assert [sid for sid, _ in accounts] == [str(second.id)]

    async def test_order_follows_the_kept_sessions(self):
        alice, bob = _user("alice@example.test"), _user("bob@example.test")
        a_old, b, a_new = (
            _session(alice, minutes_ago=50),
            _session(bob, minutes_ago=40),
            _session(alice, minutes_ago=1),
        )
        estate = _Estate([(alice, a_old), (bob, b), (alice, a_new)])
        with patch(
            "app.routers.v1.oauth_provider.resolve_session_by_id",
            AsyncMock(side_effect=estate.resolve),
        ):
            accounts = await oauth_provider._resolve_held_accounts(
                [str(a_old.id), str(b.id), str(a_new.id)], AsyncMock()
            )
        assert [sid for sid, _ in accounts] == [str(b.id), str(a_new.id)]
