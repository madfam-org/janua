"""A client's own privacy notice on Janua's hosted sign-in page (CLIENT_PRIVACY_NOTICES).

Owner ruling A5 (2026-11-15): MADFAM CV's short privacy notice is shown where
the person first hands over data, which is Janua's hosted login. These tests pin:

* a listed client's page carries one line naming the product and linking its
  notice, in the page's language (es from ui_locales, en otherwise);
* every other page (no setting, a client not listed, no client) is byte for byte
  what it was, so the regression baseline of the shared pages holds;
* a value that is not a plain https URL is never rendered, and the product name
  stays escaped inside the new line.
"""

from __future__ import annotations

# The shared pytest fixtures are imported by name and requested as arguments, which
# pyflakes reads as a redefinition.
# ruff: noqa: F811
from pathlib import Path

import pytest

from app.config import settings
from app.services.client_privacy_notices import (
    client_privacy_notice_url,
    parse_client_privacy_notices,
)

# The hosted-login fixture (SQLite, fakeredis, ASGI) is shared with the magic-link tests.
from tests.unit.routers.test_hosted_login_magic_link import (  # noqa: F401
    LOGIN_URL,
    hosted_client,
    mail_enabled,
)

CV = "jnc_cv_fixture"
NOTICE = "https://cv.madfam.io/privacidad"


class TestParse:
    def test_pairs_and_whitespace(self):
        assert parse_client_privacy_notices(f" {CV} = {NOTICE} , other=https://x.example/p ") == {
            CV: NOTICE,
            "other": "https://x.example/p",
        }

    def test_empty_means_nothing(self):
        assert parse_client_privacy_notices("") == {}
        assert parse_client_privacy_notices(None) == {}

    @pytest.mark.parametrize(
        "bad",
        [
            "http://cv.madfam.io/privacidad",
            "javascript:alert(1)",
            "https:///nohost",
            "https://u:p@cv.madfam.io/privacidad",
            "https://cv.madfam.io/a b",
            "cv.madfam.io/privacidad",
            "",
            "https://" + "a" * 600 + ".example",
        ],
    )
    def test_anything_but_plain_https_is_dropped(self, bad):
        assert parse_client_privacy_notices(f"{CV}={bad}") == {}

    def test_entry_without_client_is_dropped(self):
        assert parse_client_privacy_notices(f"={NOTICE}") == {}

    def test_lookup(self, monkeypatch):
        monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}={NOTICE}")
        assert client_privacy_notice_url(CV) == NOTICE
        assert client_privacy_notice_url("someone-else") is None
        assert client_privacy_notice_url(None) is None


async def _page(client, **params):
    resp = await client.get(LOGIN_URL, params=params)
    assert resp.status_code == 200
    return resp.text


@pytest.mark.asyncio
async def test_listed_client_shows_its_notice_in_spanish(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}={NOTICE}")
    page = await _page(hosted_client, client_id=CV, client_name="MADFAM CV", ui_locales="es")
    assert '<p class="privacy-notice">' in page
    assert "Al continuar, <strong>MADFAM CV</strong> tratará tus datos como explica su" in page
    assert (
        f'<a href="{NOTICE}" target="_blank" rel="noopener noreferrer">aviso de privacidad</a>'
        in page
    )
    # The line sits after the form and before Janua's own footer.
    assert page.index('privacy-notice">') < page.index('class="footer"')


@pytest.mark.asyncio
async def test_listed_client_shows_its_notice_in_english(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}={NOTICE}")
    page = await _page(hosted_client, client_id=CV, client_name="MADFAM CV")
    assert "By continuing, <strong>MADFAM CV</strong> will handle your data as its" in page
    assert ">privacy notice</a>" in page


@pytest.mark.asyncio
async def test_every_other_page_is_unchanged(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", "")
    before = {
        "listed": await _page(
            hosted_client, client_id=CV, client_name="MADFAM CV", ui_locales="es"
        ),
        "other": await _page(hosted_client, client_id="other", client_name="Otra app"),
        "none": await _page(hosted_client),
    }
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}={NOTICE}")
    after = {
        "other": await _page(hosted_client, client_id="other", client_name="Otra app"),
        "none": await _page(hosted_client),
    }
    assert after == {k: before[k] for k in after}, "a client not listed renders exactly as before"
    for page in before.values():
        assert "privacy-notice" not in page, "without the setting there is no line and no style"


@pytest.mark.asyncio
async def test_bad_value_is_never_rendered_and_the_name_stays_escaped(hosted_client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}=javascript:alert(1)")
    page = await _page(hosted_client, client_id=CV, client_name="MADFAM CV")
    assert "privacy-notice" not in page and "javascript:" not in page
    monkeypatch.setattr(settings, "CLIENT_PRIVACY_NOTICES", f"{CV}={NOTICE}")
    page = await _page(hosted_client, client_id=CV, client_name='<img src=x onerror="1">')
    assert "<img src=x" not in page
    assert "<strong>&lt;img src=x onerror=&quot;1&quot;&gt;</strong> will handle your data" in page


def test_an_unlisted_page_is_byte_for_byte_what_production_rendered():
    """The template with no notice is exactly the template production's source
    (b16869d7) rendered: an empty notice adds no byte, not even a blank line.
    fixtures/hosted_login_unlisted/{en,es}.html are those renders (their SHA-256,
    6eb9f5de… and 44b1b17a…, were taken from that source with the same
    arguments); a hotfix image carrying this file proves the same thing against
    the running image.

    Since 2026-11-19 the page also carries the one-press busy state (the
    same-origin script tag and the form's `data-busy-label`): removing exactly
    those two insertions gives the golden render back, byte for byte."""
    from app.auth.hosted_locale import hosted_copy
    from app.routers.v1.auth import HOSTED_FORM_SCRIPT_TAG, _hosted_login_page_html

    golden = Path(__file__).parent / "fixtures" / "hosted_login_unlisted"
    common = {"app_name": "MADFAM CV", "hidden_fields": "", "method": "password", "switch_url": None}
    for locale in ("en", "es"):
        page = _hosted_login_page_html(**common, locale=locale)
        busy = f' data-busy-label="{hosted_copy(locale)["busy_signing_in"]}"'
        assert page.count(HOSTED_FORM_SCRIPT_TAG) == 1 and page.count(busy) == 1, locale
        before = page.replace(HOSTED_FORM_SCRIPT_TAG, "").replace(busy, "")
        assert before.encode() == (golden / f"{locale}.html").read_bytes(), locale
