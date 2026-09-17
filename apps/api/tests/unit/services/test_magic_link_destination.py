"""The emailed magic link lands on the PRODUCT, not on api.janua.dev.

Found live 2026-08-15, mid client-ceremony rehearsal: the first email a new
client receives asked them to click an api.janua.dev URL — a host they have
never been told about — and, because the rehearsal host was missing from the
allowlist, the click signed them in at Janua and dead-ended on a recovery
page. Two rules fell out of that afternoon:

1. When the request names a redirect_url, the link in the email is built ON
   that host (`https://<product-host>/portal/verify?token=...`); the product
   exchanges the one-time token via POST /api/v1/auth/magic-link/verify.
2. A supplied-but-disallowed redirect_url fails the REQUEST with a 400. The
   old behaviour nulled it silently and mailed a link that could only ever
   dead-end — a failure neither the product nor the recipient could see
   coming.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_link_is_built_on_the_redirect_host():
    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "one-time-token",
            redirect_url="https://ensayo.madfam.io/portal/verify",
        )
    html = send.await_args.kwargs["html_content"]
    text = send.await_args.kwargs["text_content"]
    assert "https://ensayo.madfam.io/portal/verify?token=one-time-token" in html
    assert "https://ensayo.madfam.io/portal/verify?token=one-time-token" in text
    assert "magic-link/callback" not in html


@pytest.mark.asyncio
async def test_redirect_host_with_existing_query_appends_with_ampersand():
    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "tok",
            redirect_url="https://ensayo.madfam.io/portal/verify?next=%2Ffacturas",
        )
    # HTML entity-escapes the ampersand; the plain-text body carries it raw.
    html = send.await_args.kwargs["html_content"]
    text = send.await_args.kwargs["text_content"]
    assert "https://ensayo.madfam.io/portal/verify?next=%2Ffacturas&amp;token=tok" in html
    assert "https://ensayo.madfam.io/portal/verify?next=%2Ffacturas&token=tok" in text


@pytest.mark.asyncio
async def test_no_redirect_still_falls_back_to_the_janua_callback():
    """Products that never send redirect_url keep the GET-callback contract:
    a clicked link is a GET and only Janua can trade the token then."""
    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email("cliente@example.test", "tok")
    html = send.await_args.kwargs["html_content"]
    assert "/api/v1/auth/magic-link/callback?token=tok" in html
    # THE BUG THIS FILE EXISTS TO PREVENT: the fallback must never emit the
    # api.janua.dev DEV host. It used to (`API_BASE_URL or BASE_URL`, and
    # API_BASE_URL defaults to https://api.janua.dev, short-circuiting a
    # correctly-set BASE_URL) — a dev domain in a first-contact auth email.
    assert "api.janua.dev" not in html


@pytest.mark.asyncio
async def test_fallback_prefers_the_custom_domain(monkeypatch):
    """A white-label deployment (JANUA_CUSTOM_DOMAIN=auth.madfam.io) must emit
    the fallback callback on ITS domain, not api.janua.dev — even though
    API_BASE_URL still carries its dev-host default."""
    from app.services import email_service as es

    monkeypatch.setattr(es.settings, "JANUA_CUSTOM_DOMAIN", "auth.madfam.io", raising=False)
    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email("cliente@example.test", "tok")
    html = send.await_args.kwargs["html_content"]
    assert "https://auth.madfam.io/api/v1/auth/magic-link/callback?token=tok" in html
    assert "api.janua.dev" not in html


@pytest.mark.asyncio
async def test_brand_host_link_lands_on_janua_first(monkeypatch):
    """THE HOSTED HOP (J6).

    `map.creatumundo.mx` is outside the `.madfam.io` cookie domain, so a product
    link there could never carry the person into estate SSO: the product cannot
    relay a `janua_sso` cookie a browser would reject. Its link must land on
    janua, which is the one place the estate cookie can be set first-party.
    """
    from app.auth import hosted_hop
    from app.services import email_service as es

    monkeypatch.setattr(hosted_hop.settings, "COOKIE_DOMAIN", ".madfam.io", raising=False)
    monkeypatch.setattr(es.settings, "JANUA_CUSTOM_DOMAIN", "auth.madfam.io", raising=False)

    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "tok",
            redirect_url="https://map.creatumundo.mx/api/auth/magic-verify",
        )
    html = send.await_args.kwargs["html_content"]
    assert "https://auth.madfam.io/api/v1/auth/magic-link/callback?token=tok" in html
    # The link must NOT be built on the brand host: that is the path that cannot
    # produce an estate session, and mailing it is the live defect.
    assert "https://map.creatumundo.mx/api/auth/magic-verify?token=" not in html


@pytest.mark.asyncio
async def test_estate_host_keeps_the_direct_product_link(monkeypatch):
    """BLAST RADIUS. A host that works today keeps the byte-identical link it
    has today — the hop lights up only for hosts that are provably broken."""
    from app.auth import hosted_hop

    monkeypatch.setattr(hosted_hop.settings, "COOKIE_DOMAIN", ".madfam.io", raising=False)

    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "tok",
            redirect_url="https://crea-map.madfam.io/api/auth/magic-verify",
        )
    html = send.await_args.kwargs["html_content"]
    assert "https://crea-map.madfam.io/api/auth/magic-verify?token=tok" in html
    assert "magic-link/callback" not in html


@pytest.mark.asyncio
async def test_explicit_hosted_hop_flag_overrides_the_derived_rule(monkeypatch):
    """The escape hatch: a covered host can be forced onto the hop."""
    from app.auth import hosted_hop
    from app.services import email_service as es

    monkeypatch.setattr(hosted_hop.settings, "COOKIE_DOMAIN", ".madfam.io", raising=False)
    monkeypatch.setattr(es.settings, "JANUA_CUSTOM_DOMAIN", "auth.madfam.io", raising=False)

    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "tok",
            redirect_url="https://crea-map.madfam.io/api/auth/magic-verify",
            hosted_hop=True,
        )
    html = send.await_args.kwargs["html_content"]
    assert "https://auth.madfam.io/api/v1/auth/magic-link/callback?token=tok" in html


@pytest.mark.asyncio
async def test_hop_link_still_carries_the_client_branding(monkeypatch):
    """The hop changes the link's HOST, not whose email this is. Branding is
    resolved from the DESTINATION, so a CTM person still sees the Crea header —
    the sender, the frame and the destination must keep agreeing."""
    from app.auth import hosted_hop

    monkeypatch.setattr(hosted_hop.settings, "COOKIE_DOMAIN", ".madfam.io", raising=False)

    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
        await service.send_magic_link_email(
            "cliente@example.test",
            "tok",
            redirect_url="https://map.creatumundo.mx/api/auth/magic-verify",
        )
    html = send.await_args.kwargs["html_content"]
    assert "Crea Tu Mundo" in html


def test_get_callback_must_not_spend_the_token():
    """SCANNER-PROOFING (J6). The GET half of the callback must READ only.

    Until 2026-09-06 this route verified on the GET: it burned `used_at`, minted
    a session and redirected. A mail scanner's fetch therefore spent the link and
    the human's click replayed a spent token — the failure this estate already
    hit once (nauta portal, 2026-08-16). The hosted hop makes this route the
    PRIMARY path for the brand hosts, so the split is load-bearing.
    """
    import inspect

    from app.routers.v1 import auth

    get_source = inspect.getsource(auth.magic_link_callback_interstitial)
    assert "used_at = datetime.utcnow()" not in get_source, "the GET must not burn the token"
    assert "create_session" not in get_source, "the GET must not mint a session"
    assert "_set_session_cookies" not in get_source, "the GET must not set cookies"
    # The POST is where the exchange happens, and it must still do all of it.
    post_source = inspect.getsource(auth.magic_link_callback)
    assert "used_at = datetime.utcnow()" in post_source
    assert "_set_session_cookies" in post_source


def test_send_route_refuses_a_disallowed_destination_loudly():
    """The 400 must happen at request time. Silently nulling the redirect
    mails a link that signs the user in and then strands them — the exact
    rehearsal failure this file exists to prevent.

    Since 2026-09-17 the body of POST /magic-link lives in
    `_issue_magic_link`, shared with the hosted login page's magic-link form
    (POST /login-form/magic-link). The guard is asserted on that shared body,
    and the route is pinned to it, so both entry points keep refusing loudly."""
    import inspect

    from app.routers.v1 import auth

    assert "_issue_magic_link(" in inspect.getsource(auth.send_magic_link), (
        "POST /magic-link must issue through the shared helper"
    )
    source = inspect.getsource(auth._issue_magic_link)
    assert "raise HTTPException" in source.split("safe_redirect_url = validate_redirect_url")[1].split(
        "magic_token"
    )[0], "failed redirect validation must raise, not proceed"
    assert "we simply won't include a redirect" not in source
