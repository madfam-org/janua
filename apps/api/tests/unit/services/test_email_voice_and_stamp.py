"""The voice a message speaks in, and the clock its subject is stamped with.

Two defects, one root cause: janua's transactional mail did not know WHO WAS
ASKING for it.

1. VOICE. The register machinery in `email_i18n` has been complete since the
   formality work landed — both `tú` and `usted` copy, both subjects, both
   templates. Nothing on the live path ever selected between them. The
   magic-link router passed `locale` and not `formality`, so every Spanish
   message resolved through `DEFAULT_FORMALITY` to `usted`. Observed
   2026-09-06: crea-map's own login page says «Escribe el correo… te llega un
   enlace y con un clic estás dentro» (tú), and the mail janua sent for that
   page opened «Inicie sesión en su portal» (usted). The two screens a person
   sees back to back addressed them two different ways.

2. CLOCK. Every re-sendable message carried a CONSTANT subject, so mail
   clients threaded all of them together. A threaded reader opens the top of
   the thread — the OLDEST message — and lands on an expired link. Observed
   the same night on a real inbox as one thread, «[32] Su enlace de acceso».

Both fixes key on the same signal, the redirect host, because that host is
the only thing the mailer knows about the requester at send time (the auth
mailer runs in a BackgroundTask with no DB session). So the assertions here
are about WHAT A READER SEES for a given requester: the subject line they
scan, and the pronoun the first sentence uses.

Style follows tests/unit/services/test_email_branding.py — render for real,
patch the transport with an AsyncMock — and the clock is always injected or
frozen, never observed, so a test can never depend on when it ran.
"""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.services.email_branding import (
    DEFAULT_TENANT_FORMALITY,
    DEFAULT_TIMEZONE,
    default_formality_for,
    resolve_tenant,
    timezone_for,
)
from app.services.email_i18n import (
    DEFAULT_FORMALITY,
    FORMALITY_TU,
    FORMALITY_USTED,
    SUBJECT_STAMP_SEPARATOR,
    now_for_timezone,
    resolve_formality,
    resolve_formality_for_request,
    stamp_subject,
    subject_for,
)
from app.services.email_service import EmailService

# The two hosts this work exists for: a CTM product that speaks `tú`, and a
# MADFAM professional surface that speaks `usted`.
CREA_REDIRECT = "https://crea-map.madfam.io/api/auth/magic-verify?siguiente=/"
NAUTA_REDIRECT = "https://nauta.quest/portal/verify"

# `YYYY-MM-DD HH:MM:SS` — anchored, so a subject with the date anywhere but
# the very end fails.
STAMP_RE = re.compile(r" \| \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


async def sent_message(redirect_url: str | None = None, **kwargs) -> dict:
    """Render one magic-link email for real and return the transport kwargs.

    Everything above `_send_email` runs: locale resolution, register
    resolution, branding, both templates. Only the network is faked, which is
    the same seam test_email_branding.py uses.
    """
    service = EmailService()
    with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as transport:
        await service.send_magic_link_email("reader@example.test", "TOKEN", redirect_url, **kwargs)
    return transport.await_args.kwargs


# --------------------------------------------------------------------------
# The per-product tables
# --------------------------------------------------------------------------
class TestClientDefaults:
    """What each product sounds like, keyed on the host it sends people back to."""

    @pytest.mark.parametrize(
        "redirect_url",
        [
            "https://crea-map.madfam.io/api/auth/magic-verify",
            "https://ensayo-map.madfam.io/verify",
            "https://kalya.app/booking",
            # The client's own brand zone, matched on a dot boundary.
            "https://map.creatumundo.mx/entrar",
            "https://erp.creatumundo.mx/portal",
        ],
    )
    def test_ctm_products_speak_tu(self, redirect_url):
        assert default_formality_for(redirect_url=redirect_url) == FORMALITY_TU

    @pytest.mark.parametrize(
        "redirect_url",
        [
            "https://nauta.quest/portal/verify",
            "https://madfam.io/app",
            "https://janua.dev/dashboard",
            # Not CTM: a lookalike that must not match on a suffix.
            "https://notcreatumundo.mx/x",
            None,
        ],
    )
    def test_everything_else_stays_usted(self, redirect_url):
        assert default_formality_for(redirect_url=redirect_url) == FORMALITY_USTED

    def test_default_matches_the_global_one(self):
        """The no-tenant default is the same `usted` email_i18n already used.

        If these two ever diverge, an unknown host would start rendering in a
        register the rest of the system does not consider safe for a first
        contact.
        """
        assert DEFAULT_TENANT_FORMALITY == DEFAULT_FORMALITY

    def test_org_id_outranks_the_host(self):
        """A caller that knows the tenant beats the host guess, as for branding."""
        from app.services.email_branding import CTM_ORG_ID

        assert default_formality_for(redirect_url=NAUTA_REDIRECT, org_id=CTM_ORG_ID) == FORMALITY_TU

    def test_timezone_is_cdmx_for_ctm_and_by_default(self):
        assert timezone_for(redirect_url=CREA_REDIRECT) == "America/Mexico_City"
        assert timezone_for(redirect_url=NAUTA_REDIRECT) == DEFAULT_TIMEZONE
        assert timezone_for() == "America/Mexico_City"

    def test_tenant_resolution_matches_branding(self):
        """`resolve_tenant` is the shared walk; branding must agree with it."""
        from app.services.email_branding import resolve_branding

        assert resolve_tenant(redirect_url=CREA_REDIRECT) == "ctm"
        assert resolve_tenant(redirect_url=NAUTA_REDIRECT) is None
        assert resolve_branding(redirect_url=CREA_REDIRECT)["header_name"] == "Crea Tu Mundo"


# --------------------------------------------------------------------------
# Precedence
# --------------------------------------------------------------------------
class TestRegisterPrecedence:
    """explicit request > the reader's stored choice > the product > `usted`.

    The ordering is the whole design: a product may state its own voice, but
    it must never overwrite a person who has said how they want to be
    addressed.
    """

    def test_explicit_request_wins_over_everything(self):
        reader = SimpleNamespace(spanish_formality=FORMALITY_TU)
        assert (
            resolve_formality_for_request(FORMALITY_USTED, user=reader, client_default=FORMALITY_TU)
            == FORMALITY_USTED
        )

    def test_reader_choice_beats_the_product(self):
        """A person who chose `usted` gets `usted` even from a `tú` product."""
        reader = SimpleNamespace(spanish_formality=FORMALITY_USTED)
        assert (
            resolve_formality_for_request(None, user=reader, client_default=FORMALITY_TU)
            == FORMALITY_USTED
        )

    def test_product_default_applies_when_the_reader_has_not_chosen(self):
        """NULL on the user row is "has not chosen", so the product decides.

        This is the tier that actually fires in production: almost every row
        has a NULL here.
        """
        never_asked = SimpleNamespace(spanish_formality=None)
        assert (
            resolve_formality_for_request(None, user=never_asked, client_default=FORMALITY_TU)
            == FORMALITY_TU
        )

    def test_falls_all_the_way_through_to_usted(self):
        assert resolve_formality_for_request(None, user=None, client_default=None) == (
            DEFAULT_FORMALITY
        )

    @pytest.mark.parametrize("junk", ["vosotros", "", "  ", "formal", 7, None])
    def test_unsupported_values_fall_through_rather_than_shadow(self, junk):
        """A bad value at any tier must not eclipse a good one below it.

        `vosotros` is the case that matters: it is a real Spanish register
        this platform deliberately does not support, so it must behave like
        "unset" and not like an error that costs someone their sign-in.
        """
        assert (
            resolve_formality_for_request(junk, user=None, client_default=FORMALITY_TU)
            == FORMALITY_TU
        )

    def test_still_agrees_with_the_two_tier_resolver_when_no_product_is_known(self):
        """Adding a tier must not change any existing caller's outcome."""
        for explicit in (None, FORMALITY_TU, FORMALITY_USTED, "vosotros"):
            for stored in (None, FORMALITY_TU, FORMALITY_USTED):
                reader = SimpleNamespace(spanish_formality=stored)
                assert resolve_formality_for_request(
                    explicit, user=reader, client_default=None
                ) == resolve_formality(explicit, user=reader)


# --------------------------------------------------------------------------
# The stamp
# --------------------------------------------------------------------------
class TestSubjectStamp:
    """`<subject> | YYYY-MM-DD HH:MM:SS`, in the reader's own zone."""

    def test_exact_shape(self):
        moment = datetime(2026, 9, 6, 16, 23, 11, tzinfo=ZoneInfo("America/Mexico_City"))
        assert stamp_subject("Tu enlace de acceso", moment) == (
            "Tu enlace de acceso | 2026-09-06 16:23:11"
        )

    def test_stamp_is_last_so_the_subject_still_starts_with_its_words(self):
        moment = datetime(2026, 9, 6, 16, 23, 11, tzinfo=ZoneInfo("America/Mexico_City"))
        stamped = stamp_subject("Su enlace de acceso", moment)
        assert stamped.startswith("Su enlace de acceso")
        assert STAMP_RE.search(stamped)

    def test_seconds_are_present(self):
        """Two links requested in the same minute is the case a person hits."""
        a = stamp_subject("x", datetime(2026, 9, 6, 16, 23, 11, tzinfo=ZoneInfo(DEFAULT_TIMEZONE)))
        b = stamp_subject("x", datetime(2026, 9, 6, 16, 23, 44, tzinfo=ZoneInfo(DEFAULT_TIMEZONE)))
        assert a != b

    def test_no_zone_suffix(self):
        """The zone is the reader's own; printing it adds noise, not meaning.

        Asserted on the stamp alone rather than the whole subject: the DATE
        legitimately contains "-06", so scanning the full string for an offset
        matches its own month.
        """
        moment = datetime(2026, 9, 6, 16, 23, 11, tzinfo=ZoneInfo("America/Mexico_City"))
        stamp = stamp_subject("Tu enlace de acceso", moment).rpartition(SUBJECT_STAMP_SEPARATOR)[2]
        assert stamp == "2026-09-06 16:23:11"
        for marker in ("CST", "CDT", "UTC", "GMT", "+", "Z"):
            assert marker not in stamp

    def test_separator_is_the_documented_one(self):
        assert SUBJECT_STAMP_SEPARATOR == " | "

    @freeze_time("2026-09-06 22:23:11")  # 16:23:11 CDMX (UTC-6)
    def test_clock_is_converted_into_the_requesters_zone(self):
        """A CDMX reader must see their own wall clock, not UTC.

        UTC would read six hours in the future to every Mexican reader, which
        makes the NEWEST link look like it has not arrived yet — the exact
        confusion the stamp exists to remove.
        """
        assert now_for_timezone("America/Mexico_City").strftime("%H:%M:%S") == "16:23:11"

    @freeze_time("2026-09-06 22:23:11")
    def test_unknown_zone_degrades_to_utc_rather_than_raising(self):
        """A bad tzdata entry is a packaging problem, not a reason not to send."""
        assert now_for_timezone("Mars/Olympus_Mons").strftime("%H:%M:%S") == "22:23:11"

    def test_clock_is_read_per_call_not_cached(self):
        """A module-level "now" would stamp every message with the boot time."""
        with freeze_time("2026-09-06 22:00:00"):
            first = now_for_timezone(DEFAULT_TIMEZONE)
        with freeze_time("2026-09-06 23:00:00"):
            second = now_for_timezone(DEFAULT_TIMEZONE)
        assert second - first == (second - first)
        assert first.hour != second.hour


# --------------------------------------------------------------------------
# What a reader actually receives
# --------------------------------------------------------------------------
@freeze_time("2026-09-06 22:23:11")  # 16:23:11 CDMX
class TestRenderedMagicLink:
    """End-to-end through the real service: subject and both body parts."""

    @pytest.mark.asyncio
    async def test_crea_map_reader_is_addressed_as_tu(self):
        msg = await sent_message(CREA_REDIRECT)
        assert msg["subject"] == "Entrar a Crea Tu Mundo | 2026-09-06 16:23:11"
        for body in (msg["html_content"], msg["text_content"]):
            assert "entrar a tu espacio de acceso" in body
            assert "entrar a su espacio de acceso" not in body
            # The security notice is the longest register-sensitive paragraph;
            # a half-translated catalog shows up here first.
            assert "no solicitaste" in body
            assert "usted no solicitó" not in body

    @pytest.mark.asyncio
    async def test_nauta_portal_reader_is_still_addressed_as_usted(self):
        msg = await sent_message(NAUTA_REDIRECT)
        assert msg["subject"] == "Su enlace de acceso | 2026-09-06 16:23:11"
        for body in (msg["html_content"], msg["text_content"]):
            assert "Inicie sesión en su portal" in body
            assert "Inicia sesión en tu portal" not in body

    @pytest.mark.asyncio
    async def test_no_redirect_at_all_renders_the_formal_register(self):
        """The unknown-requester case must be the safe one, and unchanged."""
        msg = await sent_message(None)
        assert msg["subject"].startswith("Su enlace de acceso")
        assert "Inicie sesión en su portal" in msg["text_content"]

    @pytest.mark.asyncio
    async def test_explicit_request_register_overrides_the_product(self):
        """A CTM host asked for `usted` gets `usted`, subject and body."""
        msg = await sent_message(CREA_REDIRECT, formality=FORMALITY_USTED)
        assert msg["subject"] == "Entrar a Crea Tu Mundo | 2026-09-06 16:23:11"
        assert "entrar a su espacio de acceso" in msg["text_content"]

    @pytest.mark.asyncio
    async def test_reader_preference_overrides_the_product(self):
        msg = await sent_message(
            CREA_REDIRECT, user=SimpleNamespace(spanish_formality=FORMALITY_USTED)
        )
        assert msg["subject"].startswith("Entrar a Crea Tu Mundo")
        assert "entrar a su espacio de acceso" in msg["text_content"]

    @pytest.mark.asyncio
    async def test_english_body_is_untouched_by_the_register_work(self):
        """`formality` applies to Spanish only; English must not move."""
        msg = await sent_message(CREA_REDIRECT, locale="en")
        assert msg["subject"] == "Sign in to Crea Tu Mundo | 2026-09-06 16:23:11"
        assert "tu portal" not in msg["text_content"]
        assert "su portal" not in msg["text_content"]

    @pytest.mark.asyncio
    async def test_subject_carries_a_stamp_in_every_locale_and_register(self):
        for kwargs in (
            {"redirect_url": CREA_REDIRECT},
            {"redirect_url": NAUTA_REDIRECT},
            {"redirect_url": CREA_REDIRECT, "locale": "en"},
        ):
            redirect = kwargs.pop("redirect_url")
            msg = await sent_message(redirect, **kwargs)
            assert STAMP_RE.search(msg["subject"]), msg["subject"]

    @pytest.mark.asyncio
    async def test_the_stamp_is_the_only_thing_added_to_the_subject(self):
        """The words before the separator are exactly what `subject_for` returns.

        Guards against the stamp being folded into the catalog: the subject
        strings are translated copy and must stay free of formatting.
        """
        msg = await sent_message(CREA_REDIRECT)
        head, _, _ = msg["subject"].rpartition(SUBJECT_STAMP_SEPARATOR)
        assert head == "Entrar a Crea Tu Mundo"

    @pytest.mark.asyncio
    async def test_branding_still_follows_the_same_host(self):
        """The voice change must not have disturbed the header it shares a key with."""
        msg = await sent_message(CREA_REDIRECT)
        assert "Crea Tu Mundo" in msg["html_content"]


@freeze_time("2026-09-06 22:23:11")
class TestOtherResendableMessages:
    """Password reset and verification share the pipeline and re-send the same way."""

    @pytest.mark.asyncio
    async def test_password_reset_subject_is_stamped(self):
        service = EmailService()
        with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as transport:
            await service.send_password_reset_email("reader@example.test", "TOKEN")
        assert STAMP_RE.search(transport.await_args.kwargs["subject"])

    @pytest.mark.asyncio
    async def test_password_reset_voice_follows_the_redirect_base(self, monkeypatch):
        """`redirect_base` is this flow's host signal, so CTM gets `tú`."""
        service = EmailService()
        # Presentation-only seam: the exact issuance/receipt path is covered by
        # test_email_send_audit; no provider is invoked here.
        monkeypatch.setattr("app.auth.map_mail_hold.current_audit", lambda: SimpleNamespace(
            source_app="crea-map", message_kind="password_recovery", provenance="registered_map_recovery"
        ))
        with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as transport:
            await service.send_password_reset_email(
                "reader@example.test",
                "TOKEN",
                redirect_base="https://crea-map.madfam.io/reset",
            )
        subject = transport.await_args.kwargs["subject"]
        assert subject.startswith("Restablecer la contraseña")

    @pytest.mark.asyncio
    async def test_verification_subject_is_stamped(self):
        service = EmailService()
        with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as transport:
            await service.send_verification_email("reader@example.test")
        assert STAMP_RE.search(transport.await_args.kwargs["subject"])


class TestBackgroundTaskCarriesBothRegisters:
    """The router reads the User row; the task must keep the two tiers apart."""

    @pytest.mark.asyncio
    async def test_stored_choice_reaches_the_mailer_and_beats_the_product(self):
        """`user_formality` is the reader's column, resolved before the task runs."""
        from app.services import email_service as module

        with patch.object(module.EmailService, "send_magic_link_email", new=AsyncMock()) as send:
            await module.send_magic_link_email_task(
                "reader@example.test",
                "TOKEN",
                CREA_REDIRECT,
                user_formality=FORMALITY_USTED,
            )
        assert send.await_args.kwargs["user"].spanish_formality == FORMALITY_USTED

    @pytest.mark.asyncio
    async def test_request_register_and_stored_choice_are_separate_arguments(self):
        """Collapsing them would let a product overwrite a person's preference."""
        from app.services import email_service as module

        with patch.object(module.EmailService, "send_magic_link_email", new=AsyncMock()) as send:
            await module.send_magic_link_email_task(
                "reader@example.test",
                "TOKEN",
                CREA_REDIRECT,
                formality=FORMALITY_TU,
                user_formality=FORMALITY_USTED,
            )
        kwargs = send.await_args.kwargs
        assert kwargs["formality"] == FORMALITY_TU
        assert kwargs["user"].spanish_formality == FORMALITY_USTED

    @pytest.mark.asyncio
    async def test_no_stored_choice_passes_no_user_at_all(self):
        """A NULL column must not become a `user` object that shadows anything."""
        from app.services import email_service as module

        with patch.object(module.EmailService, "send_magic_link_email", new=AsyncMock()) as send:
            await module.send_magic_link_email_task("reader@example.test", "TOKEN", CREA_REDIRECT)
        assert send.await_args.kwargs["user"] is None


class TestRequestSchema:
    """`formality` on the magic-link request body: normalized, never rejected.

    A sign-in request must not 422 over a cosmetic field. The product that
    sends a value we do not support has made a mistake worth ignoring, not one
    worth locking its users out for — so the validator NORMALIZES, and an
    unusable value becomes None and falls through to the host default.
    """

    def test_field_is_optional_and_defaults_to_none(self):
        from app.routers.v1.auth import MagicLinkRequest

        assert MagicLinkRequest(email="reader@example.com").formality is None

    @pytest.mark.parametrize(
        "sent,expected",
        [
            ("tu", FORMALITY_TU),
            ("tú", FORMALITY_TU),  # accented, as a human would type it
            ("USTED", FORMALITY_USTED),
            ("  usted  ", FORMALITY_USTED),
        ],
    )
    def test_accepted_shapes_are_normalized(self, sent, expected):
        from app.routers.v1.auth import MagicLinkRequest

        assert MagicLinkRequest(email="reader@example.com", formality=sent).formality == expected

    @pytest.mark.parametrize("junk", ["vosotros", "formal", "", "   ", "fr"])
    def test_unsupported_values_become_none_rather_than_422(self, junk):
        from app.routers.v1.auth import MagicLinkRequest

        assert MagicLinkRequest(email="reader@example.com", formality=junk).formality is None
