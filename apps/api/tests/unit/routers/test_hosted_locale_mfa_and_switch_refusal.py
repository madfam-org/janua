"""Two hosted pages that did not follow the ``ui_locales`` rule.

Every hosted page renders English unless the request asks for Spanish, and only
the normalized constant ``es`` ever travels (``app/auth/hosted_locale.py``).
Two places broke that rule:

* The second-factor branch of ``GET /oauth/authorize`` stored the RAW
  ``ui_locales`` with the pending request and sent ``ui_locales or "es"`` to the
  login page, so a request that asked for no language got a Spanish page, and a
  hostile value was stored and forwarded as given.
* The page ``POST /auth/switch-session/form`` answers when it refuses a chooser
  click was English only, although the chooser's ``next`` carries
  ``ui_locales=es`` when the chooser spoke Spanish.

These tests pin the fix. The English refusal pages are compared byte for byte
with fixtures/switch_refused_default/*.html, rendered by the origin/main source
of ``_switch_refused_html`` at fb9a18d3, before this change.
"""

from __future__ import annotations

# The shared autouse fixture is imported by name, which pyflakes reads as unused.
# ruff: noqa: F401
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

import pytest

from app.auth.sessions_cookie import SESSIONS_COOKIE_NAME, mint_sessions_cookie_value
from app.routers.v1 import oauth_provider, oauth_provider_shared
from app.routers.v1.auth import (
    HOSTED_FORM_SCRIPT_TAG,
    _switch_page_locale,
    _switch_refused_html,
)
from tests.unit.routers.test_account_chooser_switch_form import (
    FORM,
    _authorize_query,
    _Estate,
    _http,
    _session,
    _user,
    optional_organization_policy,
)

GOLDEN = Path(__file__).parent / "fixtures" / "switch_refused_default"

HOSTILE = [
    'es-"><script>alert(1)</script>',
    "es-MX' onmouseover=alert(1) x='",
    "es-x&next=https://evil.example/&ui_locales=fr",
]


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def _without_the_hosted_form_script(page: str) -> str:
    """The login page minus its one reviewed script tag.

    Since the 2026-11-19 double-submit fix every hosted form loads exactly one
    script, the same-origin file ``/api/v1/auth/hosted-form.js`` (no inline
    code). That exact tag must appear once; everything else on the page is held
    to the old rule, so any other ``script`` (an injected tag, an inline block, a
    ``javascript:`` URL) still fails the checks below.
    """
    assert page.count(HOSTED_FORM_SCRIPT_TAG) == 1, "the reviewed script tag, exactly once"
    rest = page.replace(HOSTED_FORM_SCRIPT_TAG, "")
    assert "<script" not in rest.lower(), "no other script tag, inline or not"
    return rest


# --------------------------------------------------------------------------
# 1. The second-factor branch of /authorize
# --------------------------------------------------------------------------


async def _mfa_authorize(ui_locales):
    """Run /authorize for a signed-in user whose policy needs a second factor
    and whose sign-in is not recent; follow the redirect to the login page.

    Returns (authorize response, stored pending request, login page response).
    """
    alice = _user("alice@example.test")
    estate = _Estate([])
    query = _authorize_query()
    if ui_locales is not None:
        query["ui_locales"] = ui_locales

    async def run(http):
        # The harness's fakeredis (it patches this name for the run), the same
        # store the /authorize and login-page dependencies are given.
        redis = await oauth_provider_shared.get_redis()
        with (
            patch(
                "app.routers.v1.oauth_provider_shared.get_user_from_cookie_or_header",
                AsyncMock(return_value=alice),
            ),
            patch("app.routers.v1.oauth_provider_shared.user_requires_mfa", AsyncMock(return_value=True)),
            patch(
                "app.routers.v1.oauth_provider_shared.assurance_for_request", AsyncMock(return_value={})
            ),
        ):
            resp = await http.get("/api/v1/oauth/authorize", params=query)
        assert resp.status_code == 302, resp.text
        location = resp.headers["location"]
        assert urlparse(location).path == "/api/v1/auth/login"
        pending_id = _query(location)["auth_request_id"]
        pending = json.loads(await redis.get(f"oauth:pre_login:{pending_id}"))
        login = await http.get(location)
        return resp, pending, login

    return await _http(estate, {}, run)


class TestSecondFactorBranch:
    async def test_without_ui_locales_the_login_page_is_english(self):
        resp, pending, login = await _mfa_authorize(None)
        location = resp.headers["location"]
        assert "ui_locales" not in location
        assert set(_query(location)) == {"client_id", "auth_request_id"}
        assert pending["ui_locales"] is None
        assert login.status_code == 200
        assert '<html lang="en">' in login.text
        assert "Sign in - Janua" in login.text
        assert "Iniciar sesión" not in login.text
        assert 'name="ui_locales"' not in login.text

    @pytest.mark.parametrize("ui_locales", ["es", "es-MX en", "fr-CA es"])
    async def test_spanish_is_asked_for_and_only_the_constant_travels(self, ui_locales):
        resp, pending, login = await _mfa_authorize(ui_locales)
        assert _query(resp.headers["location"])["ui_locales"] == "es"
        assert pending["ui_locales"] == "es"
        assert login.status_code == 200
        assert '<html lang="es-MX">' in login.text
        assert "Iniciar sesión - Janua" in login.text
        assert '<input type="hidden" name="ui_locales" value="es">' in login.text

    async def test_english_asked_for_is_the_english_page(self):
        resp, pending, login = await _mfa_authorize("en")
        # The constant "en" travels, as on the unauthenticated branch.
        assert _query(resp.headers["location"])["ui_locales"] == "en"
        assert pending["ui_locales"] == "en"
        assert '<html lang="en">' in login.text

    @pytest.mark.parametrize("hostile", HOSTILE)
    async def test_a_hostile_value_is_never_stored_or_forwarded(self, hostile):
        resp, pending, login = await _mfa_authorize(hostile)
        location = resp.headers["location"]
        assert _query(location)["ui_locales"] == "es"
        assert pending["ui_locales"] == "es"
        page = _without_the_hosted_form_script(login.text)
        for fragment in ("script", "alert", "onmouseover", "evil.example", "es-MX'", 'es-"'):
            assert fragment not in location, fragment
            assert fragment not in json.dumps(pending), fragment
            assert fragment not in page, fragment

    async def test_an_unresolvable_value_is_dropped(self):
        resp, pending, login = await _mfa_authorize('fr"><script>alert(1)</script>')
        assert "ui_locales" not in resp.headers["location"]
        assert pending["ui_locales"] is None
        assert '<html lang="en">' in login.text
        page = _without_the_hosted_form_script(login.text)
        assert "script" not in page
        assert "alert" not in page


# --------------------------------------------------------------------------
# 2. The page /auth/switch-session/form answers when it refuses a click
# --------------------------------------------------------------------------

REASONS = {
    "cross_origin": "switch_refused_cross_origin",
    "not_held": "switch_refused_not_held",
}


class TestRefusalPage:
    @pytest.mark.parametrize("name", sorted(REASONS))
    def test_english_is_byte_for_byte_the_previous_page(self, name):
        golden = (GOLDEN / f"{name}.html").read_bytes()
        assert _switch_refused_html(REASONS[name]).encode() == golden
        assert _switch_refused_html(REASONS[name], "en").encode() == golden

    def test_spanish(self):
        es = _switch_refused_html("switch_refused_not_held", "es")
        assert '<html lang="es-MX">' in es
        assert "<title>Elige una cuenta - Janua</title>" in es
        assert "<h1>Esa cuenta no se puede usar aquí</h1>" in es
        assert (
            "<p>Esa cuenta ya no tiene una sesión abierta en este navegador. "
            "Regresa a la aplicación y vuelve a iniciar sesión.</p>"
        ) in es
        cross = _switch_refused_html("switch_refused_cross_origin", "es")
        assert "Esta solicitud no vino de la página para elegir una cuenta." in cross
        for text in ("Choose an account", "can't be used", "Go back", "signed in"):
            assert text not in es, text
            assert text not in cross, text

    @pytest.mark.parametrize(
        ("next_url", "expected"),
        [
            (None, "en"),
            ("", "en"),
            ("/api/v1/oauth/authorize?client_id=rp", "en"),
            ("/api/v1/oauth/authorize?client_id=rp&ui_locales=es", "es"),
            ("/api/v1/oauth/authorize?ui_locales=es-MX+en", "es"),
            ("/api/v1/oauth/authorize?ui_locales=fr", "en"),
            ("/api/v1/oauth/authorize?ui_locales=en", "en"),
            (
                "/api/v1/oauth/authorize?ui_locales="
                + "es-%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E",
                "es",
            ),
        ],
    )
    def test_the_locale_comes_from_next(self, next_url, expected):
        assert _switch_page_locale(next_url) == expected


def _next(ui_locales=None):
    q = _authorize_query()
    if ui_locales is not None:
        q["ui_locales"] = ui_locales
    return "/api/v1/oauth/authorize?" + urlencode(q)


class TestThroughTheForm:
    async def _post(self, data, headers, *, held_sid=None):
        alice = _user("alice@example.test")
        s_alice = _session(alice, minutes_ago=1)
        estate = _Estate([(alice, s_alice)])
        held = mint_sessions_cookie_value([held_sid or str(uuid4())])  # alice NOT held

        async def run(http):
            return await http.post(FORM, data={"sid": str(s_alice.id), **data}, headers=headers)

        return await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)

    async def test_unheld_sid_without_ui_locales_is_the_english_page(self):
        resp = await self._post({"next": _next()}, {"Origin": "http://test"})
        assert resp.status_code == 400
        assert resp.text.encode() == (GOLDEN / "not_held.html").read_bytes()

    async def test_unheld_sid_without_next_is_the_english_page(self):
        resp = await self._post({}, {"Origin": "http://test"})
        assert resp.status_code == 400
        assert resp.text.encode() == (GOLDEN / "not_held.html").read_bytes()

    async def test_unheld_sid_in_spanish(self):
        resp = await self._post({"next": _next("es")}, {"Origin": "http://test"})
        assert resp.status_code == 400
        assert resp.text == _switch_refused_html("switch_refused_not_held", "es")

    async def test_cross_origin_without_ui_locales_is_the_english_page(self):
        resp = await self._post({"next": _next()}, {"Origin": "https://other.example"})
        assert resp.status_code == 403
        assert resp.text.encode() == (GOLDEN / "cross_origin.html").read_bytes()

    async def test_cross_origin_in_spanish(self):
        resp = await self._post({"next": _next("es-MX")}, {"Origin": "https://other.example"})
        assert resp.status_code == 403
        assert resp.text == _switch_refused_html("switch_refused_cross_origin", "es")

    @pytest.mark.parametrize("hostile", HOSTILE)
    async def test_a_hostile_next_only_picks_a_constant(self, hostile):
        resp = await self._post({"next": _next(hostile)}, {"Origin": "http://test"})
        assert resp.status_code == 400
        assert resp.text == _switch_refused_html("switch_refused_not_held", "es")
        assert not re.search(r"script|alert|onmouseover|evil\.example", resp.text)
