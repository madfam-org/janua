"""The `prompt=select_account` chooser speaks the language the client asked for.

A relying application sent `ui_locales=es` with `prompt=select_account`; every
other hosted page answered in Spanish, but the chooser was English only. These
tests pin:

* with a `ui_locales` that resolves to `es`, the chooser renders in Spanish
  (lang, title, heading, the "continue to" line, the other-account link and
  both fallbacks), from HOSTED_COPY;
* without `ui_locales` the chooser is byte for byte the page it was before
  (fixtures/account_chooser_default/*.html were rendered by the origin/main
  source of `_account_chooser_html` at 5635c3f5, before this change);
* a hostile `ui_locales` only ever yields the constant `es` on the page, never
  any byte of the raw value;
* the language survives the chooser: each account form's `next` and the
  "use another account" link carry `ui_locales=es`, and the switch lands back
  on `/authorize` with it.
"""

from __future__ import annotations

# The shared autouse fixture is imported by name, which pyflakes reads as unused.
# ruff: noqa: F401
import re
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from app.auth.sessions_cookie import SESSIONS_COOKIE_NAME, mint_sessions_cookie_value
from app.routers.v1.oauth_provider import _account_chooser_html

# The real-app chooser harness (estate, ASGI client, form parsing, and the
# autouse fixture that keeps organization MFA policy out of these cookie tests)
# is shared with the switch-form tests.
from tests.unit.routers.test_account_chooser_switch_form import (
    FORM,
    REDIRECT_URI,
    _authorize_query,
    _Estate,
    _forms,
    _http,
    _session,
    _sso_sid,
    _user,
    optional_organization_policy,
)

GOLDEN = Path(__file__).parent / "fixtures" / "account_chooser_default"

# The same arguments the goldens were rendered with.
ACCOUNTS = [
    ("sid-a", SimpleNamespace(email="ana@example.test", username=None)),
    ("sid-<b>", SimpleNamespace(email=None, username=None)),
]
NEXT = "/api/v1/oauth/authorize?response_type=code&client_id=rp&state=a%26b"
ADD = "/api/v1/auth/login?auth_request_id=req&client_id=rp&client_name=RP"
CLIENTS = {"named": 'Relying <App> & "Co"', "unnamed": ""}

ENGLISH = (
    "Choose an account",
    "to continue to",
    "Use another account",
    ">Account<",
    "the application",
)


def _render(client_name, **kwargs):
    return _account_chooser_html(
        ACCOUNTS, authorize_next=NEXT, add_account_url=ADD, client_name=client_name, **kwargs
    )


def _add_link(page):
    return unescape(re.search(r'<a class="add" href="([^"]+)"', page).group(1))


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class TestRendering:
    @pytest.mark.parametrize("name", sorted(CLIENTS))
    def test_default_english_is_byte_for_byte_the_previous_page(self, name):
        golden = (GOLDEN / f"{name}.html").read_bytes()
        assert _render(CLIENTS[name]).encode() == golden
        assert _render(CLIENTS[name], locale="en").encode() == golden

    def test_spanish(self):
        page = _render("")
        es = _render("", locale="es")
        assert '<html lang="es-MX">' in es
        assert "<title>Elige una cuenta - Janua</title>" in es
        assert "<h1>Elige una cuenta</h1>" in es
        assert '<p class="sub">para continuar a la aplicación</p>' in es
        assert ">Usar otra cuenta</a>" in es
        assert '<span class="account-email">Cuenta</span>' in es
        assert '<span class="account-avatar">C</span>' in es
        for text in ENGLISH:
            assert text not in es, text
        # Only the copy changed: the forms and the link are the English page's.
        assert _forms(es) == _forms(page)
        assert _add_link(es) == ADD

    def test_spanish_keeps_the_client_name_escaped(self):
        es = _render(CLIENTS["named"], locale="es")
        assert '<p class="sub">para continuar a Relying &lt;App&gt; &amp; &quot;Co&quot;</p>' in es
        assert "<App>" not in es
        assert 'value="sid-&lt;b&gt;"' in es


async def _chooser(ui_locales):
    """Render the chooser through the real /authorize; return (page, estate, held)."""
    alice, bob = _user("alice@example.test"), _user("bob@example.test")
    s_alice, s_bob = _session(alice, minutes_ago=30), _session(bob, minutes_ago=5)
    estate = _Estate([(alice, s_alice), (bob, s_bob)])
    held = mint_sessions_cookie_value([str(s_alice.id), str(s_bob.id)])
    query = _authorize_query("select_account")
    if ui_locales is not None:
        query["ui_locales"] = ui_locales

    async def run(http):
        with patch(
            "app.routers.v1.oauth_provider_shared.get_user_from_cookie_or_header",
            AsyncMock(return_value=None),
        ):
            return await http.get("/api/v1/oauth/authorize", params=query)

    page = await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)
    assert page.status_code == 200
    return page.text, (alice, s_alice, estate, held)


class TestThroughAuthorize:
    async def test_without_ui_locales_nothing_changes(self):
        page, _ = await _chooser(None)
        assert '<html lang="en">' in page
        assert "<h1>Choose an account</h1>" in page
        assert "to continue to madfam-rp" in page
        assert "ui_locales" not in page
        # `next` is the rebuilt authorize request, exactly as before.
        q = _authorize_query()
        expected = "/api/v1/oauth/authorize?" + urlencode(
            {
                "response_type": q["response_type"],
                "client_id": q["client_id"],
                "redirect_uri": q["redirect_uri"],
                "scope": q["scope"],
                "state": q["state"],
                "code_challenge": q["code_challenge"],
                "code_challenge_method": q["code_challenge_method"],
            }
        )
        forms = _forms(page)
        assert len(forms) == 2
        assert {nxt for _, _, nxt in forms} == {expected}

    @pytest.mark.parametrize("ui_locales", ["es", "es-MX en", "fr-CA es"])
    async def test_spanish_page_and_the_language_travels(self, ui_locales):
        page, _ = await _chooser(ui_locales)
        assert '<html lang="es-MX">' in page
        assert "<h1>Elige una cuenta</h1>" in page
        assert "para continuar a madfam-rp" in page
        assert ">Usar otra cuenta</a>" in page
        for text in ENGLISH:
            assert text not in page, text
        forms = _forms(page)
        assert len(forms) == 2
        for _, _, nxt in forms:
            assert urlparse(nxt).path == "/api/v1/oauth/authorize"
            assert _query(nxt)["ui_locales"] == "es"
        add = _add_link(page)
        assert urlparse(add).path == "/api/v1/auth/login"
        assert _query(add)["ui_locales"] == "es"

    @pytest.mark.parametrize(
        "hostile",
        [
            'es-"><script>alert(1)</script>',
            "es-MX' onmouseover=alert(1) x='",
            "es-x&next=https://evil.example/&ui_locales=fr",
        ],
    )
    async def test_a_hostile_value_only_ever_yields_the_constant(self, hostile):
        page, _ = await _chooser(hostile)
        assert '<html lang="es-MX">' in page
        for fragment in ("script", "alert", "onmouseover", "evil.example", "es-MX'", 'es-"'):
            assert fragment not in page, fragment
        values = re.findall(r"ui_locales=([^&\"]*)", unescape(page))
        assert values and set(values) == {"es"}

    async def test_an_unresolvable_hostile_value_is_the_english_page(self):
        english, _ = await _chooser(None)
        hostile, _ = await _chooser('"><script>alert(1)</script>')
        assert "script" not in hostile and "alert" not in hostile
        assert '<html lang="en">' in hostile

        # Session ids and the pending-request id differ per render; everything
        # else is the English page.
        def strip(page):
            page = re.sub(r'name="sid" value="[^"]+"', "", page)
            return re.sub(r"auth_request_id=[^&]+", "", page)

        assert strip(hostile) == strip(english)

    async def test_the_switch_returns_to_authorize_in_spanish(self):
        alice, bob = _user("alice@example.test"), _user("bob@example.test")
        s_alice, s_bob = _session(alice, minutes_ago=30), _session(bob, minutes_ago=5)
        estate = _Estate([(alice, s_alice), (bob, s_bob)])
        held = mint_sessions_cookie_value([str(s_alice.id), str(s_bob.id)])
        query = {**_authorize_query("select_account"), "ui_locales": "es-MX"}

        async def run(http):
            with patch(
                "app.routers.v1.oauth_provider_shared.get_user_from_cookie_or_header",
                AsyncMock(return_value=None),
            ):
                page = await http.get("/api/v1/oauth/authorize", params=query)
            action, sid, nxt = next(f for f in _forms(page.text) if f[1] == str(s_alice.id))
            assert action == FORM
            switched = await http.post(
                action, data={"sid": sid, "next": nxt}, headers={"Origin": "http://test"}
            )
            assert switched.status_code == 302
            assert _sso_sid(switched) == str(s_alice.id)
            location = switched.headers["location"]
            params = _query(location)
            assert urlparse(location).path == "/api/v1/oauth/authorize"
            assert params["ui_locales"] == "es"
            assert params["state"] == "rp-state"
            assert "prompt" not in params

            # The resumed request still issues the code for the chosen account.
            with (
                patch(
                    "app.routers.v1.oauth_provider_shared.get_user_from_cookie_or_header",
                    AsyncMock(return_value=alice),
                ),
                patch(
                    "app.routers.v1.oauth_provider.ConsentService.has_consent",
                    AsyncMock(return_value=False),
                ),
            ):
                resumed = await http.get(location)
            assert resumed.status_code == 302
            assert resumed.headers["location"].startswith(REDIRECT_URI)

        await _http(estate, {SESSIONS_COOKIE_NAME: held}, run)
