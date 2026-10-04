"""The shared email frame (templates/email/base.html) per tenant.

Two guarantees, one per class:

  * Every NON-CTM render of the frame is byte-for-byte what it was before the
    Crea tenant got its own small print (2026-09-28). The golden files under
    `fixtures/email_frame/` were rendered from base.html as it stood on janua
    main 3267a8c3, BEFORE the tenant gate was added, and every case here must
    keep matching them. Only the frame is compared (everything outside
    `<div class="content">`), so a later change to a message body does not
    trip this test; a change to the header or footer does, on purpose.
  * The Crea Tu Mundo frame carries the Crea small print only: no MADFAM
    tagline, no «© Innovaciones MADFAM», no madfam.io legal links, no
    `mailto:hola@madfam.io` — and still the «Con tecnología de MADFAM» credit.

Regenerating a golden file is a deliberate act: it means MADFAM's own frame
changed. Do it with `JANUA_UPDATE_EMAIL_FRAME_GOLDEN=1 pytest <this file>`
and review the diff as a change to every MADFAM email.
"""

import os
from pathlib import Path

import pytest

from app.services.email_branding import CTM_BRANDING, resolve_branding
from app.services.email_service import EmailService

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "email_frame"
UPDATE_GOLDEN = os.environ.get("JANUA_UPDATE_EMAIL_FRAME_GOLDEN") == "1"

CTM_REDIRECT = "https://map.creatumundo.mx/portal/verify?next=/"
#: A pinned year, so the © line does not make the golden files expire.
PINNED_YEAR = 2026


def _render(template, locale, formality=None, branding=None):
    data = {
        "magic_link": "https://x.test/a",
        "magic_url": "https://x.test/a",
        "verification_link": "https://x.test/v",
        "user_name": "persona",
        "current_year": PINNED_YEAR,
    }
    if branding is not None:
        data.update(branding)
    return EmailService()._render_template(template, data, locale=locale, formality=formality)


def _frame(html):
    """The header (everything before the content div) and the footer (from the
    footer div on), joined by a marker. The message body is left out."""
    head, _, rest = html.partition('<div class="content">')
    _, _, foot = rest.partition('<div class="footer">')
    return f'{head}<!-- body elided -->\n<div class="footer">{foot}'


#: Non-CTM renders of the frame. `branding=None` is a caller that passes no
#: branding at all (most mailers); `resolve_branding(...)` is the magic-link
#: path, which always merges a branding dict — the MADFAM one here.
NON_CTM_CASES = {
    "magic_link_en_no_branding": ("magic_link.html", "en", None, None),
    "magic_link_es_usted_madfam_branding": (
        "magic_link.html",
        "es",
        "usted",
        resolve_branding(),
    ),
    "magic_link_es_tu_madfam_own_host": (
        "magic_link.html",
        "es",
        "tu",
        resolve_branding(redirect_url="https://app.madfam.io/x"),
    ),
    "verification_es_no_branding": ("verification.html", "es", None, None),
    # Conversation mail (R101, 2026-10-04): welcome keeps the frame it had
    # before the automated-mail notice existed. Rendered BEFORE that notice was
    # added to base.html, so it pins "conversation mail is unchanged".
    "welcome_es_usted_no_branding": ("welcome.html", "es", "usted", None),
    "welcome_en_no_branding": ("welcome.html", "en", None, None),
}


class TestNonCtmFrameIsUnchanged:
    @pytest.mark.parametrize("case", sorted(NON_CTM_CASES))
    def test_frame_matches_golden(self, case):
        template, locale, formality, branding = NON_CTM_CASES[case]
        frame = _frame(_render(template, locale, formality, branding))
        golden = GOLDEN_DIR / f"{case}.html"
        if UPDATE_GOLDEN:
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_text(frame, encoding="utf-8")
        assert golden.exists(), f"missing golden file {golden.name}"
        assert frame == golden.read_text(encoding="utf-8")

    def test_madfam_frame_keeps_its_small_print(self):
        """Belt and braces on top of the golden: the four pieces the CTM frame
        drops are all still in MADFAM's."""
        html = _render("magic_link.html", "es", "usted", resolve_branding())
        assert "Tecnología, diseñada para su operación" in html
        assert "Innovaciones MADFAM S.A.S. de C.V." in html
        assert "https://madfam.io/es/privacy" in html
        assert "mailto:hola@madfam.io" in html


class TestCtmFrame:
    def _ctm(self, locale="es", formality="tu"):
        return _render(
            "magic_link.html", locale, formality, resolve_branding(redirect_url=CTM_REDIRECT)
        )

    @pytest.mark.parametrize("locale", ["es", "en"])
    def test_ctm_frame_drops_madfam_small_print(self, locale):
        html = self._ctm(locale=locale)
        # MADFAM's tagline, in either register or language.
        assert "Tecnología, diseñada para" not in html
        assert "Technology, engineered for your operation" not in html
        # «© Innovaciones MADFAM» and the legal-entity address line.
        assert "Innovaciones MADFAM" not in html
        assert "©" not in html
        # The madfam.io legal links and MADFAM's support mailbox.
        assert "madfam.io/es/privacy" not in html
        assert "madfam.io/en/privacy" not in html
        assert "/terms" not in html
        assert "mailto:hola@madfam.io" not in html
        # «...porque tienes una cuenta con MADFAM» is MADFAM's small print too.
        assert "cuenta con MADFAM" not in html
        assert "account with MADFAM" not in html

    def test_ctm_frame_keeps_the_madfam_credit(self):
        html = self._ctm()
        footer = html.partition('<div class="footer">')[2]
        assert "Con tecnología de" in footer
        assert '<a href="https://madfam.io">MADFAM</a>' in footer
        assert CTM_BRANDING["footer_logo_url"] in footer

    def test_ctm_frame_is_the_brand_blue(self):
        html = self._ctm()
        assert "#2d2f86" in html
        assert "#1a2a8f" not in html
        assert CTM_BRANDING["header_logo_url"] in html.partition('<div class="content">')[0]

    def test_ctm_frame_keeps_the_message_body(self):
        """Only the frame changes; the sign-in body and its link are intact."""
        html = self._ctm()
        assert "https://x.test/a" in html.partition('<div class="content">')[2]
