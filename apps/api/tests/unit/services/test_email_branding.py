"""Per-tenant BODY branding, and the invariants that keep it Phase-1 safe.

Context: docs/EMAIL_SENDER_POLICY.md. Phase 1 keeps ONE sender —
`MADFAM <hola@madfam.io>` — for every message from every platform. This suite
pins a refinement of Phase 1: the BODY may carry a client tenant's name in the
header and credit MADFAM in the footer, while the From line does not move.

The load-bearing guarantees, each with a test that fails loudly if it breaks:

  * a CTM-context send still comes FROM MADFAM (the policy line)
  * a non-CTM / unknown / absent signal renders TODAY's MADFAM frame
  * the footer reads "Con tecnología de" (es) / "Powered by" (en), never
    "Impulsado por"
  * a CTM context puts "Crea Tu Mundo" in the header and MADFAM in the footer

Style follows tests/unit/services/test_email_delivery.py: render templates
directly and patch the transport with an AsyncMock rather than standing up a
live provider.
"""

import os
from email.utils import formataddr
from unittest.mock import AsyncMock, patch

import pytest

from app.services import email_sender as sender_module
from app.services import email_service as email_module
from app.services.email_branding import (
    CTM_ORG_ID,
    MADFAM_BRANDING,
    _tenant_for_host,
    resolve_branding,
)
from app.services.email_service import EmailService, resolve_sender

CTM_REDIRECT = "https://crea-map.madfam.io/portal/verify?next=/"

#: The env var CTM's binding names, and a fake value that never leaves the
#: process. Since 2026-09-07 CTM sends on its OWN Resend account, so this key's
#: presence is what decides whether the branded From ships.
CTM_CREDENTIAL_ENV = "CTM_RESEND_API_KEY"
FAKE_CTM_KEY = "re_test_ctm_key_not_real"


def with_ctm_credential(value: str = FAKE_CTM_KEY):
    """Put CTM's own Resend key in the environment for a with-block."""
    return patch.dict(os.environ, {CTM_CREDENTIAL_ENV: value})


@pytest.fixture(autouse=True)
def _no_ambient_ctm_credential():
    """No test inherits a real CTM key from the developer's shell."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(CTM_CREDENTIAL_ENV, None)
        yield


# --------------------------------------------------------------------------
# The resolver
# --------------------------------------------------------------------------
class TestResolveBranding:
    def test_no_signal_is_madfam(self):
        assert resolve_branding() == MADFAM_BRANDING
        assert resolve_branding()["header_name"] == "MADFAM"
        assert resolve_branding()["platform_name"] == "Janua"

    def test_unknown_host_is_madfam(self):
        b = resolve_branding(redirect_url="https://example.test/go?token=abc")
        assert b["header_name"] == "MADFAM"

    def test_madfam_own_host_stays_madfam(self):
        """madfam.io is MADFAM's own host and must NOT resolve to a tenant."""
        b = resolve_branding(redirect_url="https://app.madfam.io/x")
        assert b["header_name"] == "MADFAM"

    @pytest.mark.parametrize(
        "url",
        [
            "https://crea-map.madfam.io/portal/verify",
            "https://ensayo-map.madfam.io/x",
            "https://kalya.app/verify?token=abc",
            "https://app.kalya.app/verify",  # subdomain of an allowed host
        ],
    )
    def test_ctm_hosts_resolve_to_ctm(self, url):
        b = resolve_branding(redirect_url=url)
        assert b["header_name"] == "Crea Tu Mundo"
        # Footer credits MADFAM (the platform underneath a client tenant).
        assert b["platform_name"] == "MADFAM"
        assert b["header_bg"] == "#1a2a8f"
        # CTM carries the client's header mark and MADFAM's footer mark (the
        # same public crea-map assets the kalya booking emails use).
        assert b["header_logo_url"] == "https://map.creatumundo.mx/crea-logo-email.png"
        assert b["footer_logo_url"] == "https://map.creatumundo.mx/madfam-logo.png"

    def test_madfam_default_has_no_hotlinked_logos(self):
        """The MADFAM default keeps its INLINE mark; the hotlinked slots are
        empty so nothing changes for existing callers."""
        b = resolve_branding()
        assert b["header_logo_url"] == ""
        assert b["footer_logo_url"] == ""

    def test_lookalike_host_does_not_match(self):
        """Suffix match is on a dot boundary; `evilkalya.app` is not kalya."""
        b = resolve_branding(redirect_url="https://evilkalya.app/x")
        assert b["header_name"] == "MADFAM"

    @pytest.mark.parametrize(
        "host",
        ["map.creatumundo.mx", "erp.creatumundo.mx", "creatumundo.mx"],
    )
    def test_creatumundo_brand_hosts_resolve_to_ctm(self, host):
        """The client's own zone is CTM: sign-in mail for the brand hosts must
        not silently revert to MADFAM branding (J7)."""
        assert _tenant_for_host(host) == "ctm"
        b = resolve_branding(redirect_url=f"https://{host}/portal/verify?token=abc")
        assert b["header_name"] == "Crea Tu Mundo"
        assert b["platform_name"] == "MADFAM"

    def test_creatumundo_lookalike_host_does_not_match(self):
        """`notcreatumundo.mx` shares a suffix but not a dot boundary."""
        assert _tenant_for_host("notcreatumundo.mx") is None
        b = resolve_branding(redirect_url="https://notcreatumundo.mx/x")
        assert b["header_name"] == "MADFAM"

    def test_org_id_resolves_ctm(self):
        b = resolve_branding(org_id=CTM_ORG_ID)
        assert b["header_name"] == "Crea Tu Mundo"

    def test_org_id_takes_precedence_over_host(self):
        """A caller that knows the org id is authoritative over the host."""
        b = resolve_branding(redirect_url="https://example.test/go", org_id=CTM_ORG_ID)
        assert b["header_name"] == "Crea Tu Mundo"

    def test_resolver_never_returns_a_from_address(self):
        """Branding must not carry anything usable as a sender."""
        b = resolve_branding(redirect_url=CTM_REDIRECT)
        for key in b:
            assert "from" not in key.lower()
            assert "sender" not in key.lower()
            assert "email" not in key.lower()


# --------------------------------------------------------------------------
# The From line — Phase 2, gated on the sending domain being verified
# --------------------------------------------------------------------------
class TestSenderUnderTheVerifiedDomainGate:
    """These used to pin "the sender NEVER changes" (Phase 1), then "the CTM
    NAME on the MADFAM address" (Phase 2, #603). Both are superseded.

    2026-09-07: the display name follows the address. A CTM message that cannot
    ship its branded address is the PLATFORM sender whole —
    `MADFAM <hola@madfam.io>`. The intermediate state this class used to
    assert, `Crea Tu Mundo <hola@madfam.io>`, reached a real CTM inbox at
    02:32:21 CDMX that morning and was rejected: only MADFAM sends from
    `hola@madfam.io`.

    LATER THAT DAY THE TRIGGER MOVED. CTM went onto its OWN Resend account,
    where `creatumundo.mx` is verified, so the deciding fact is no longer the
    global `RESEND_VERIFIED_DOMAINS` (which describes MADFAM's account) but
    whether this process holds CTM's key, env `CTM_RESEND_API_KEY`. Without it
    the branded address would be presented to MADFAM's account, which has never
    verified that domain, and Resend would reject the magic link outright — so
    the send degrades to the platform sender instead. The tests below therefore
    withhold or supply that env var where they used to edit a domain list.

    BODY branding is unaffected and still asserted below — the tenant header,
    palette and voice render on both sides of that line.
    """

    def test_resolve_sender_is_the_platform_sender_without_ctms_key(self):
        """CTM's key absent: neither the unreachable account's address NOR the
        brand name."""
        name, address = resolve_sender(CTM_REDIRECT)
        assert (name, address) == ("MADFAM", "hola@madfam.io")

    def test_resolve_sender_is_the_brand_with_ctms_key(self):
        """The enabled state, through the same one-line resolver the mailer
        calls."""
        with with_ctm_credential():
            assert resolve_sender(CTM_REDIRECT) == ("Crea Tu Mundo", "hola@creatumundo.mx")

    def test_resolve_sender_is_madfam_without_a_tenant_signal(self):
        """No signal is still, and always, MADFAM."""
        assert resolve_sender(None) == ("MADFAM", "hola@madfam.io")
        assert resolve_sender("https://example.test/go") == ("MADFAM", "hola@madfam.io")

    @pytest.mark.asyncio
    async def test_ctm_magic_link_is_the_platform_sender_without_ctms_key(self):
        """A CTM magic link is sent as `MADFAM <hola@madfam.io>` — the platform
        sender whole — while CTM's own Resend key is absent.

        This is the deliverability line: Resend REJECTS a send from a domain
        the SENDING ACCOUNT has not verified, so putting CTM's address on
        MADFAM's account would break every CTM sign-in link. We drive the real
        send path and read the From header AND the Authorization header off the
        Resend call — which is precisely how the 2026-09-07 production header
        would have been caught, and how an envelope/account mismatch would be.
        """
        captured = {}

        async def fake_post(url, headers=None, json=None):
            captured["from"] = json["from"]
            captured["auth"] = (headers or {}).get("Authorization")

            class _Resp:
                status_code = 200
                text = ""

            return _Resp()

        service = EmailService()
        with (
            patch.object(email_module.settings, "EMAIL_PROVIDER", "resend"),
            patch.object(email_module.settings, "RESEND_API_KEY", "re_test_key"),
            patch("app.services.email_service.httpx.AsyncClient") as client_cls,
        ):
            client = client_cls.return_value.__aenter__.return_value
            client.post = AsyncMock(side_effect=fake_post)
            sent = await service.send_magic_link_email(
                "ana@creatumundo.mx",
                "tok123",
                redirect_url=CTM_REDIRECT,
                locale="es",
            )
        # The link still goes out. #607's rule: a missing tenant credential
        # degrades the From line, it never blocks a sign-in link.
        assert sent is True
        # Neither the name nor the address is CTM's: the credential gate
        # returns the platform binding whole.
        assert captured["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        assert captured["from"] != formataddr(("Crea Tu Mundo", "hola@madfam.io"))
        # ...and it leaves on MADFAM's account, which is the account that
        # verified `madfam.io`. Envelope and account agree.
        assert captured["auth"] == "Bearer re_test_key"

    @pytest.mark.asyncio
    async def test_ctm_magic_link_leaves_on_ctms_own_account(self):
        """The enabled state, end to end: the branded From AND the tenant's own
        key on the same call.

        This is the assertion that would have caught the bug this pair exists
        for. `_send_via_resend` resolved the From through `sender_for` but sent
        with `settings.RESEND_API_KEY` unconditionally, so a tenant-account
        binding produced `Crea Tu Mundo <hola@creatumundo.mx>` presented to
        MADFAM's account — a domain that account has never verified, and a hard
        rejection on a magic link. The From line and the account that carries it
        are one decision, and this pins them to the same call.
        """
        captured = {}

        async def fake_post(url, headers=None, json=None):
            captured.update(json)
            captured["auth"] = (headers or {}).get("Authorization")

            class _Resp:
                status_code = 200
                text = ""

            return _Resp()

        service = EmailService()
        with (
            patch.object(email_module.settings, "EMAIL_PROVIDER", "resend"),
            patch.object(email_module.settings, "RESEND_API_KEY", "re_test_key"),
            with_ctm_credential(),
            patch("app.services.email_service.httpx.AsyncClient") as client_cls,
        ):
            client = client_cls.return_value.__aenter__.return_value
            client.post = AsyncMock(side_effect=fake_post)
            sent = await service.send_magic_link_email(
                "ana@creatumundo.mx", "tok123", redirect_url=CTM_REDIRECT, locale="es"
            )
        assert sent is True
        assert captured["from"] == formataddr(("Crea Tu Mundo", "hola@creatumundo.mx"))
        # CTM's own key, NOT MADFAM's — the account that verified the domain.
        assert captured["auth"] == f"Bearer {FAKE_CTM_KEY}"
        assert captured["auth"] != "Bearer re_test_key"

    @pytest.mark.asyncio
    async def test_ctm_body_carries_the_brand_while_the_envelope_waits(self):
        """Same send: the BODY reads Crea Tu Mundo, the ENVELOPE is MADFAM's,
        whole. This is the split the 2026-09-07 rule draws — body branding is
        the tenant's presence in the message, the From line is a claim about
        who owns the mailbox, and only the second one waits for an account we
        can actually authenticate to.

        Which is why a missing tenant credential is a DEGRADED send and not a
        failed one: the recipient still gets a message that reads as Crea Tu
        Mundo throughout, and can still sign in."""
        captured = {}

        async def fake_post(url, headers=None, json=None):
            captured.update(json)

            class _Resp:
                status_code = 200
                text = ""

            return _Resp()

        service = EmailService()
        with (
            patch.object(email_module.settings, "EMAIL_PROVIDER", "resend"),
            patch.object(email_module.settings, "RESEND_API_KEY", "re_test_key"),
            patch("app.services.email_service.httpx.AsyncClient") as client_cls,
        ):
            client = client_cls.return_value.__aenter__.return_value
            client.post = AsyncMock(side_effect=fake_post)
            await service.send_magic_link_email(
                "ana@creatumundo.mx", "tok123", redirect_url=CTM_REDIRECT, locale="es"
            )
        assert captured["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        # The brand is in the BODY, which is what was never gated.
        assert "Crea Tu Mundo" in captured["html"]
        assert "Con tecnología de" in captured["html"]
        assert "Impulsado por" not in captured["html"]

    @pytest.mark.asyncio
    async def test_ctm_from_is_creatumundo_once_the_key_is_in_place(self):
        """Put CTM's own key in the environment and the SAME send path puts the
        client's own address on the envelope, with a matching Reply-To. This is
        the production cutover, exercised as a test so the cutover is not also
        the first execution of this branch.

        The global RESEND_VERIFIED_DOMAINS is patched to include
        `creatumundo.mx` here only to prove it is IRRELEVANT to the outcome:
        CTM's binding carries its own `verified_domains`, and the companion
        test above reaches the same branded From with the global list left at
        `madfam.io` alone."""
        captured = {}

        async def fake_post(url, headers=None, json=None):
            captured.update(json)

            class _Resp:
                status_code = 200
                text = ""

            return _Resp()

        service = EmailService()
        with (
            patch.object(email_module.settings, "EMAIL_PROVIDER", "resend"),
            patch.object(email_module.settings, "RESEND_API_KEY", "re_test_key"),
            patch.object(
                sender_module.settings, "RESEND_VERIFIED_DOMAINS", "madfam.io,creatumundo.mx"
            ),
            with_ctm_credential(),
            patch("app.services.email_service.httpx.AsyncClient") as client_cls,
        ):
            client = client_cls.return_value.__aenter__.return_value
            client.post = AsyncMock(side_effect=fake_post)
            sent = await service.send_magic_link_email(
                "ana@creatumundo.mx", "tok123", redirect_url=CTM_REDIRECT, locale="es"
            )
        assert sent is True
        assert captured["from"] == formataddr(("Crea Tu Mundo", "hola@creatumundo.mx"))
        # Reply-To equals From here, so it is omitted rather than duplicated.
        assert "reply_to" not in captured
        # The body is unaffected by the sender switch.
        assert "Crea Tu Mundo" in captured["html"]


# --------------------------------------------------------------------------
# The rendered frame
# --------------------------------------------------------------------------
class TestRenderedFrame:
    def _render(self, locale=None, branding_url=None):
        service = EmailService()
        ctx = {"magic_link": "https://x.test/a"}
        if branding_url is not None:
            ctx.update(resolve_branding(redirect_url=branding_url))
        return service._render_template("magic_link.html", ctx, locale=locale)

    def test_default_render_is_madfam_frame(self):
        """No branding signal -> today's MADFAM header, byte-for-byte."""
        html = self._render(locale="en")
        assert '<h1 style="margin: 0; font-size: 24px; font-weight: 600;">MADFAM</h1>' in html
        assert "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)" in html
        assert "#1a2a8f" not in html
        # The MADFAM logo block is present for the MADFAM header.
        assert 'alt="MADFAM"' in html

    def test_default_es_footer_is_con_tecnologia_de_not_impulsado(self):
        html = self._render(locale="es")
        assert "Con tecnología de" in html
        assert "Impulsado por" not in html

    def test_ctm_header_reads_crea_tu_mundo(self):
        html = self._render(locale="es", branding_url=CTM_REDIRECT)
        assert "Crea Tu Mundo" in html
        assert "#1a2a8f" in html

    def test_ctm_header_drops_madfam_logo(self):
        """CTM header carries the CREA mark, never the MADFAM one. The MADFAM
        inline logo (alt="MADFAM") must not appear in the header segment; the
        Crea mark (alt="Crea Tu Mundo") is what's there instead."""
        html = self._render(locale="es", branding_url=CTM_REDIRECT)
        header_seg = html.split('class="content"')[0]
        assert 'alt="MADFAM"' not in header_seg
        # The CTM header carries the Crea mark (hotlinked, alt = the brand name).
        assert "crea-logo-email.png" in header_seg
        assert 'alt="Crea Tu Mundo"' in header_seg

    def test_ctm_footer_carries_madfam_mark(self):
        """The CTM footer credits MADFAM WITH the MADFAM mark, in the footer
        segment (below the content), so the header-segment assertions above are
        unaffected."""
        html = self._render(locale="es", branding_url=CTM_REDIRECT)
        footer_seg = html.split('class="content"')[-1]
        assert "madfam-logo.png" in footer_seg

    def test_default_render_has_no_hotlinked_logos(self):
        """No branding signal -> the inline MADFAM mark only; neither hotlinked
        CTM asset appears."""
        html = self._render(locale="en")
        assert "crea-logo-email.png" not in html
        assert "madfam-logo.png" not in html

    def test_ctm_es_footer_credits_madfam_with_con_tecnologia_de(self):
        html = self._render(locale="es", branding_url=CTM_REDIRECT)
        assert "Con tecnología de" in html
        assert "Impulsado por" not in html
        # The credited platform is MADFAM (madfam.io link in the footer).
        assert "madfam.io" in html

    def test_ctm_en_footer_says_powered_by(self):
        html = self._render(locale="en", branding_url=CTM_REDIRECT)
        assert "Powered by" in html
        assert "Impulsado" not in html
