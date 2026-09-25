"""First-party engagement measurement: who is instrumented, and how.

The rules under test (app/services/email_engagement.py):

- Instrumented ONLY when all hold: `track_engagement` asked, not token mail
  (flag false AND nothing credential-looking in the HTML), an HTML part on the
  wire, and a tracking host on the From domain of the resolved binding.
- The text part is never touched; every http(s) link is rewritten except
  mailto:/tel:/other schemes and links already on the tracking host; one pixel.
- The original targets are stored server-side under the token's hash; the
  token itself is never stored.

No network: the Resend SDK call is a recorder, keys are fakes, recipients are
example.com. The database is in-memory SQLite.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any, Dict, List
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.services.resend_email_service as resend_module
from app.config import settings
from app.dependencies import verify_internal_api_key
from app.main import app
from app.models import Base
from app.models.email_event import EmailTrackingLink
from app.services import email_engagement, resend_transport
from app.services.email_branding import CTM_ORG_ID
from app.services.email_engagement import (
    MAX_LINKS,
    engagement_decision,
    hash_token,
    instrument_html,
    new_token,
    possible_prefetch,
)
from app.services.sender_binding import (
    CTM_BINDING,
    PLATFORM_BINDING,
    tracking_bindings,
    tracking_host_for,
)

ORIGIN = "https://enlaces.creatumundo.mx"
CTM_CREDENTIAL_ENV = "CTM_RESEND_API_KEY"
BILL_HTML = (
    "<!DOCTYPE html><html><body>"
    "<p>Su estado de cuenta de octubre &amp; noviembre.</p>"
    '<a href="https://map.creatumundo.mx/pagos?familia=1&amp;mes=10">Ver estado de cuenta</a>'
    '<a href="mailto:hola@creatumundo.mx">Escríbanos</a>'
    '<a href="tel:+525512345678">Llámenos</a>'
    "<a href='https://www.creatumundo.mx/'>Sitio</a>"
    '<a href="https://enlaces.creatumundo.mx/ya-medido">ya en el host</a>'
    '<a name="ancla">sin href</a>'
    "</body></html>"
)
BILL_TEXT = "Su estado de cuenta: https://map.creatumundo.mx/pagos?familia=1&mes=10"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv(CTM_CREDENTIAL_ENV, raising=False)
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "", raising=False)
    monkeypatch.setattr(settings, "CTM_TRACKING_HOST", None, raising=False)
    email_engagement.throttle.reset()
    yield
    email_engagement.throttle.reset()


@pytest.fixture()
def tracking_on(monkeypatch):
    monkeypatch.setattr(settings, "CTM_TRACKING_HOST", ORIGIN)


@pytest_asyncio.fixture()
async def db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(email_engagement, "session_factory", factory)
    yield factory
    await engine.dispose()


async def _links(factory) -> List[EmailTrackingLink]:
    async with factory() as session:
        return list((await session.execute(select(EmailTrackingLink))).scalars().all())


# ---------------------------------------------------------------------------
# Binding: the tracking host
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("https://enlaces.creatumundo.mx", ORIGIN),
        ("https://Enlaces.CreaTuMundo.mx/", ORIGIN),
        ("http://enlaces.creatumundo.mx", None),  # https only
        ("https://enlaces.creatumundo.mx/e", None),  # no path
        ("https://enlaces.creatumundo.mx:8443", None),  # no port
        ("https://user@enlaces.creatumundo.mx", None),
        ("enlaces.creatumundo.mx", None),
    ],
)
def test_ctm_tracking_host_is_read_from_env_and_validated(monkeypatch, raw, expected):
    monkeypatch.setattr(settings, "CTM_TRACKING_HOST", raw)
    assert tracking_host_for(CTM_BINDING) == expected


def test_platform_has_no_tracking_host_and_default_sites(tracking_on):
    assert tracking_host_for(PLATFORM_BINDING) is None
    assert CTM_BINDING.default_site == "https://creatumundo.mx"
    assert PLATFORM_BINDING.default_site == "https://madfam.io"
    assert list(tracking_bindings()) == ["enlaces.creatumundo.mx"]


# ---------------------------------------------------------------------------
# The decision: all conditions, or nothing
# ---------------------------------------------------------------------------


def _decide(**overrides):
    args = {
        "requested": True,
        "html": BILL_HTML,
        "token_link": False,
        "binding": CTM_BINDING,
        "sender_address": "hola@creatumundo.mx",
    }
    args.update(overrides)
    return engagement_decision(**args)


def test_instrumented_only_when_every_condition_holds(tracking_on):
    assert _decide() == (ORIGIN, "instrumented")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"requested": False}, "not_requested"),
        ({"token_link": True}, "token_link_declared"),
        ({"html": None}, "no_html"),
        ({"html": "   "}, "no_html"),
        (
            {"html": '<a href="https://map.creatumundo.mx/entrar?token=abc">Entrar</a>'},
            "credential_link_detected",
        ),
        ({"html": '<a href="https://x.example/r#code=1">r</a>'}, "credential_link_detected"),
        ({"binding": PLATFORM_BINDING}, "no_tracking_host"),
        # The CTM message fell back to the platform sender: never measured on a CTM host.
        ({"sender_address": "hola@madfam.io"}, "tracking_host_not_on_sender_domain"),
    ],
)
def test_not_instrumented(tracking_on, overrides, reason):
    assert _decide(**overrides) == (None, reason)


def test_no_tracking_host_configured_means_never():
    assert _decide() == (None, "no_tracking_host")


def test_a_madfam_tracking_host_never_lands_on_ctm_mail(monkeypatch):
    monkeypatch.setattr(settings, "CTM_TRACKING_HOST", "https://enlaces.madfam.io")
    assert _decide() == (None, "tracking_host_not_on_sender_domain")


# ---------------------------------------------------------------------------
# The rewrite
# ---------------------------------------------------------------------------


def test_links_rewritten_except_mailto_tel_and_own_host_and_pixel_once():
    token, _ = new_token()
    out, links = instrument_html(BILL_HTML, ORIGIN, token)

    # Stored targets: http(s) only, entities decoded, in document order.
    assert links == [
        "https://map.creatumundo.mx/pagos?familia=1&mes=10",
        "https://www.creatumundo.mx/",
    ]
    hrefs = re.findall(r"""href=["']([^"']*)["']""", out)
    assert hrefs == [
        f"{ORIGIN}/e/c/{token}/0",
        "mailto:hola@creatumundo.mx",
        "tel:+525512345678",
        f"{ORIGIN}/e/c/{token}/1",
        "https://enlaces.creatumundo.mx/ya-medido",
    ]
    assert out.count("/e/o/") == 1
    pixel = f'<img src="{ORIGIN}/e/o/{token}.gif" width="1" height="1" alt="" border="0"'
    assert pixel in out
    assert out.index(pixel) < out.lower().rindex("</body>")
    # Escaping of the surrounding content is preserved byte for byte.
    assert "octubre &amp; noviembre" in out
    assert '<a name="ancla">sin href</a>' in out
    # Nothing but the hrefs and the pixel changed.
    stripped = out.replace(
        '<img src="' + f"{ORIGIN}/e/o/{token}.gif" + '" width="1" height="1" alt="" border="0" '
        'style="display:block;border:0;width:1px;height:1px">',
        "",
    )
    assert re.sub(r"""href=(["'])[^"']*\1""", "href", stripped) == re.sub(
        r"""href=(["'])[^"']*\1""", "href", BILL_HTML
    )


def test_pixel_appended_when_there_is_no_body_tag():
    token, _ = new_token()
    out, links = instrument_html("<p>Hola</p>", ORIGIN, token)
    assert links == []
    assert out.startswith("<p>Hola</p><img ")
    assert out.count("<img") == 1


def test_link_cap_leaves_the_rest_untouched():
    token, _ = new_token()
    html = "".join(f'<a href="https://x.example/{i}">{i}</a>' for i in range(MAX_LINKS + 3))
    out, links = instrument_html(html, ORIGIN, token)
    assert len(links) == MAX_LINKS
    assert f'href="https://x.example/{MAX_LINKS + 2}"' in out


def test_rewritten_urls_need_no_escaping():
    token, _ = new_token()
    out, _ = instrument_html(BILL_HTML, ORIGIN, token)
    for href in re.findall(r'href="([^"]*/e/c/[^"]*)"', out):
        assert html_lib.escape(href) == href


def test_tokens_are_256_bit_and_only_the_hash_is_derived():
    token, digest = new_token()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert digest == hash_token(token) and len(digest) == 64 and token not in digest
    assert new_token()[0] != token


# ---------------------------------------------------------------------------
# Prefetch heuristic (in memory only)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "ua", "purpose", "seconds", "expected"),
    [
        ("GET", "Mozilla/5.0", None, 3600, True),  # Apple Mail Privacy Protection
        ("GET", "", None, 3600, True),
        ("GET", None, None, 3600, True),
        ("HEAD", "Mozilla/5.0 (Macintosh) Safari/605", None, 3600, True),
        ("GET", "Mozilla/5.0 (Windows NT 10.0) Chrome/128", "prefetch", 3600, True),
        ("GET", "Mozilla/5.0 (compatible; Barracuda Sentinel)", None, 3600, True),
        ("GET", "python-requests/2.32", None, 3600, True),
        ("GET", "Mozilla/5.0 (iPhone) Mobile/15E148", None, 5, True),  # right at delivery
        ("GET", "Mozilla/5.0 (iPhone) Mobile/15E148", None, 3600, False),
        ("GET", "Mozilla/5.0 (Windows NT 10.0) Chrome/128", None, None, False),
        ("GET", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GoogleImageProxy", None, 3600, False),
    ],
)
def test_possible_prefetch(method, ua, purpose, seconds, expected):
    assert (
        possible_prefetch(method=method, user_agent=ua, purpose=purpose, seconds_since_send=seconds)
        is expected
    )


# ---------------------------------------------------------------------------
# The send path, end to end through POST /internal/email/send
# ---------------------------------------------------------------------------


@pytest.fixture()
def sdk_sends(monkeypatch) -> List[Dict[str, Any]]:
    captured: List[Dict[str, Any]] = []
    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(resend_module.settings, "ENVIRONMENT", "test", raising=False)
    monkeypatch.setenv(CTM_CREDENTIAL_ENV, "re_test_ctm_key_not_real")

    def _fake_send(params: Dict[str, Any]) -> Dict[str, str]:
        captured.append(params)
        return {"id": f"resend-email-id-{len(captured)}"}

    monkeypatch.setattr(resend_transport.resend.Emails, "send", staticmethod(_fake_send))
    return captured


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


def _body(**extra) -> Dict[str, Any]:
    body = {
        "to": ["familia@example.com"],
        "subject": "Estado de cuenta de octubre",
        "html": BILL_HTML,
        "text": BILL_TEXT,
        "source_app": "crea-map",
        "source_type": "billing",
        "org_id": CTM_ORG_ID,
        "track_engagement": True,
    }
    body.update(extra)
    return body


async def test_send_instruments_opted_in_ctm_mail_and_binds_email_id(
    client, sdk_sends, db, tracking_on
):
    response = await client.post("/api/v1/internal/email/send", json=_body())
    assert response.json()["success"] is True
    params = sdk_sends[0]
    assert params["from"].endswith("<hola@creatumundo.mx>")
    # Text part untouched, byte for byte.
    assert params["text"] == BILL_TEXT
    hosts = {urlsplit(u).hostname for u in re.findall(r'href="(https?://[^"]+)"', params["html"])}
    assert hosts == {"enlaces.creatumundo.mx"}
    assert params["html"].count("/e/o/") == 1

    [row] = await _links(db)
    token = re.search(r"/e/o/([A-Za-z0-9_-]{43})\.gif", params["html"]).group(1)
    assert row.token_hash == hash_token(token)
    assert token not in json.dumps(
        {c: getattr(row, c) for c in ("token_hash", "links", "email_id", "cuenta")}
    )
    assert row.email_id == "resend-email-id-1"
    assert row.cuenta == "ctm" and row.source_app == "crea-map" and row.org_id == CTM_ORG_ID
    assert json.loads(row.links) == [
        "https://map.creatumundo.mx/pagos?familia=1&mes=10",
        "https://www.creatumundo.mx/",
    ]


async def test_each_recipient_gets_its_own_token(client, sdk_sends, db, tracking_on):
    await client.post(
        "/api/v1/internal/email/send", json=_body(to=["a@example.com", "b@example.com"])
    )
    rows = await _links(db)
    assert len(rows) == 2 and rows[0].token_hash != rows[1].token_hash
    assert {r.email_id for r in rows} == {"resend-email-id-1", "resend-email-id-2"}


@pytest.mark.parametrize(
    "extra",
    [
        {"track_engagement": False},
        {"contains_token_link": True},
        {"html": '<a href="https://map.creatumundo.mx/entrar?token=T0KEN">Entrar</a>'},
    ],
    ids=["not-requested", "token-declared", "token-detected"],
)
async def test_send_leaves_html_untouched_otherwise(client, sdk_sends, db, tracking_on, extra):
    body = _body(**extra)
    await client.post("/api/v1/internal/email/send", json=body)
    assert sdk_sends[0]["html"] == body["html"]
    assert "/e/" not in sdk_sends[0]["html"]
    assert await _links(db) == []


async def test_send_without_tracking_host_is_unmodified(client, sdk_sends, db):
    await client.post("/api/v1/internal/email/send", json=_body())
    assert sdk_sends[0]["html"] == BILL_HTML
    assert await _links(db) == []


async def test_ctm_credential_missing_falls_back_to_platform_unmeasured(
    client, sdk_sends, db, tracking_on, monkeypatch
):
    monkeypatch.delenv(CTM_CREDENTIAL_ENV)
    await client.post("/api/v1/internal/email/send", json=_body())
    assert sdk_sends[0]["from"].endswith("<hola@madfam.io>")
    assert sdk_sends[0]["html"] == BILL_HTML
    assert await _links(db) == []


async def test_store_failure_sends_the_message_unmodified(
    client, sdk_sends, tracking_on, monkeypatch
):
    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(email_engagement, "session_factory", broken)
    response = await client.post("/api/v1/internal/email/send", json=_body())
    assert response.json()["success"] is True
    assert sdk_sends[0]["html"] == BILL_HTML


def test_the_flag_is_part_of_the_request_model():
    from app.routers.v1.email import SendEmailRequest

    assert SendEmailRequest.model_fields["track_engagement"].default is False
    # Unknown fields are ignored (pydantic's default), not rejected.
    parsed = SendEmailRequest.model_validate(
        {"to": ["a@example.com"], "subject": "s", "source_app": "x", "nope": 1}
    )
    assert not hasattr(parsed, "nope")
