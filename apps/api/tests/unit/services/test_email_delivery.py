"""Guards for the mail path that had never delivered a message.

On 2026-08-13 prod could not send any email, four independent ways at once:
the transport spoke SMTP into a namespace that only permits 443; the
magic-link sender did not exist; verification mail was scheduled as an
unbound instance method; and half the templates extended a path the loader
could not resolve, so the body silently degraded to a one-line fallback.

Every fault was invisible to the request path — the API returned 200 and the
UI said "check your inbox" — so these tests assert the things a 200 cannot.
"""

import importlib
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import email_service as email_module
from app.services.email_i18n import resolve_locale, subject_for
from app.services.email_service import EmailService

# Messages with a full Spanish translation. Parametrizing from one list keeps
# a newly localized template from being added without a guard.
LOCALIZED_TEMPLATES = [
    "magic_link",
    "password_reset",
    "verification",
    "welcome",
    "invitation",
]

# Enough context that every action button in every template has an href.
TEMPLATE_CONTEXT = {
    "user_name": "Ana",
    "magic_link": "https://example.test/go?token=abc",
    "magic_url": "https://example.test/go?token=abc",
    "reset_link": "https://example.test/go?token=abc",
    "reset_url": "https://example.test/go?token=abc",
    "verification_link": "https://example.test/go?token=abc",
    "verification_url": "https://example.test/go?token=abc",
    "dashboard_link": "https://example.test/go?token=abc",
    "dashboard_url": "https://example.test/go?token=abc",
    "invitation_url": "https://example.test/go?token=abc",
    "inviter_name": "Luis",
    "organization_name": "Acme",
    "role": "admin",
    "expires_at": "2026-09-01",
    "support_email": "soporte@janua.dev",
    "base_url": "https://janua.dev",
}


class TestSendersExist:
    """The magic-link route called a method that was never defined."""

    def test_magic_link_sender_exists(self):
        assert hasattr(EmailService, "send_magic_link_email")

    @pytest.mark.parametrize(
        "task_name",
        ["send_magic_link_email_task", "send_password_reset_email_task",
         "send_verification_email_task"],
    )
    def test_background_entrypoints_are_module_level(self, task_name):
        """Routers must schedule module-level coroutines.

        `background_tasks.add_task(EmailService.send_x, email, token)` calls an
        instance method unbound, binding `email` to `self` — it dies on the
        first attribute access. Module-level functions cannot be misused
        that way.
        """
        task = getattr(email_module, task_name)
        assert inspect.iscoroutinefunction(task)
        assert "self" not in inspect.signature(task).parameters

    def test_routers_do_not_schedule_unbound_methods(self):
        """Regression for the call convention itself."""
        source = inspect.getsource(inspect.getmodule(EmailService))
        from app.routers.v1 import auth

        # The /auth router is several modules since the 2026-11-19 split.
        auth_source = "".join(
            inspect.getsource(importlib.import_module(f"app.routers.v1.{m}")) for m in auth.MODULES
        )
        assert "EmailService.send_verification_email," not in auth_source
        assert "EmailService.send_magic_link_email," not in auth_source
        assert source  # module imported cleanly


class TestTransport:
    """SMTP is unreachable from the cluster; 443 is not."""

    @pytest.mark.asyncio
    async def test_resend_provider_uses_https_api_not_smtp(self):
        service = EmailService()
        with patch.object(
            service, "_send_via_resend", new=AsyncMock(return_value=True)
        ) as resend, patch("smtplib.SMTP") as smtp:
            with patch.object(email_module.settings, "EMAIL_PROVIDER", "resend"), patch.object(
                email_module.settings, "RESEND_API_KEY", "re_test_key"
            ):
                sent = await service._send_email("a@b.test", "subject", "<p>hi</p>", "hi")
        assert sent is True
        resend.assert_awaited_once()
        smtp.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_transport_reports_failure_rather_than_success(self):
        """This returned True before, making an undeliverable mail look sent."""
        service = EmailService()
        with patch.object(email_module.settings, "EMAIL_PROVIDER", "smtp"), patch.object(
            email_module.settings, "SMTP_HOST", None
        ):
            sent = await service._send_email("a@b.test", "subject", "<p>hi</p>", "hi")
        assert sent is False


class TestTemplatesRender:
    """The loader is rooted at templates/email, so `email/base.html` is wrong."""

    @pytest.mark.parametrize(
        "template",
        ["password_reset.html", "verification.html", "welcome.html", "magic_link.html",
         "security_alert.html", "mfa_recovery.html",
         # Localized templates live in a subdirectory but inherit the same
         # base.html — the loader root, not the template's own folder, is
         # what `{% extends %}` resolves against.
         "es/password_reset.html", "es/verification.html", "es/welcome.html",
         "es/magic_link.html", "es/invitation.html"],
    )
    # Name kept short on purpose: a longer snake_case name here matched
    # TruffleHog's Lob API-key pattern and failed secret scanning (2026-08-13).
    def test_template_resolves_base(self, template):
        service = EmailService()
        rendered = service.jinja_env.get_template(template).render(
            user_name="x", current_year=2026, subject="s"
        )
        assert "<html" in rendered.lower()

    @pytest.mark.parametrize(
        ("template", "link_var"),
        [
            ("password_reset.html", "reset_link"),
            ("verification.html", "verification_link"),
            ("magic_link.html", "magic_link"),
            ("welcome.html", "dashboard_link"),
            ("invitation.html", "invitation_url"),
            ("es/password_reset.html", "reset_link"),
            ("es/verification.html", "verification_link"),
            ("es/magic_link.html", "magic_link"),
            ("es/welcome.html", "dashboard_link"),
            ("es/invitation.html", "invitation_url"),
        ],
    )
    def test_action_button_carries_a_real_href(self, template, link_var):
        """Templates referenced *_link while the service passed only *_url,
        so every button rendered with an empty href."""
        service = EmailService()
        rendered = service.jinja_env.get_template(template).render(
            **{link_var: "https://example.test/go?token=abc"},
            user_name="x",
            current_year=2026,
            subject="s",
        )
        assert 'href=""' not in rendered
        assert "https://example.test/go?token=abc" in rendered

    def test_render_helper_injects_shared_context(self):
        service = EmailService()
        rendered = service._render_template("magic_link.html", {"magic_link": "https://x.test/a"})
        assert "https://x.test/a" in rendered
        # base.html footer needs current_year; absent, Jinja renders "" silently.
        assert str(__import__("datetime").datetime.utcnow().year) in rendered


class TestLocaleResolution:
    """Spanish-speaking recipients were getting English as their first
    touchpoint; there was no locale concept in the mail path at all."""

    def test_explicit_argument_wins_over_stored_preference(self):
        user = SimpleNamespace(locale="en")
        assert resolve_locale("es-MX", user=user, default="en") == "es"

    def test_stored_user_locale_wins_over_deployment_default(self):
        """`users.locale` is a real nullable column on the User model."""
        user = SimpleNamespace(locale="en")
        assert resolve_locale(None, user=user, default="es") == "en"

    def test_deployment_default_used_when_recipient_has_no_preference(self):
        assert resolve_locale(None, user=SimpleNamespace(locale=None), default="en") == "en"

    def test_falls_back_to_spanish_when_nothing_is_configured(self):
        """es-MX is the default for client-facing mail: this platform's users
        are predominantly Mexican."""
        assert resolve_locale(None, None, None) == "es"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("es", "es"), ("es-MX", "es"), ("es_MX", "es"), ("ES-mx", "es"), ("es-419", "es"),
         ("en", "en"), ("en-US", "en")],
    )
    def test_regional_variants_share_one_translation_set(self, raw, expected):
        assert resolve_locale(raw) == expected

    @pytest.mark.parametrize("raw", ["fr-CA", "de", "", None, "  ", 42, "zz"])
    def test_unsupported_tag_does_not_shadow_the_next_tier(self, raw):
        """An untranslated stored locale must fall through, not win — otherwise
        it selects a language with no templates behind it."""
        assert resolve_locale(raw, default="en") == "en"


class TestTemplateLocalization:
    """A Spanish recipient must get the Spanish body, an English one English."""

    @pytest.mark.parametrize("template", LOCALIZED_TEMPLATES)
    @pytest.mark.parametrize("extension", ["html", "txt"])
    def test_es_recipient_body(self, template, extension):
        service = EmailService()
        rendered = service._render_template(f"{template}.{extension}", TEMPLATE_CONTEXT, "es-MX")
        english = service._render_template(f"{template}.{extension}", TEMPLATE_CONTEXT, "en")
        assert rendered != english
        assert "Email content unavailable" not in rendered
        # A machine-translation smell test: es-MX transactional copy is
        # usted-form and says "correo electrónico", never "email".
        assert "Hola" in rendered or "Le invitaron" in rendered

    @pytest.mark.parametrize("template", LOCALIZED_TEMPLATES)
    def test_localized_html_still_renders_a_real_href(self, template):
        """The localized copies must not lose the action button the English
        ones only just got."""
        service = EmailService()
        rendered = service._render_template(f"{template}.html", TEMPLATE_CONTEXT, "es")
        assert 'href=""' not in rendered
        assert "https://example.test/go?token=abc" in rendered
        assert "<html" in rendered.lower()

    def test_english_is_still_available(self):
        """This is localization, not replacement."""
        service = EmailService()
        rendered = service._render_template("magic_link.html", TEMPLATE_CONTEXT, "en")
        # Was "Sign in to Janua". The headline names the recipient's portal, not
        # the platform, because the platform is credited and never branded as
        # the sender (docs/EMAIL_SENDER_POLICY.md). Still a locale-specific
        # string, so this keeps proving English rendered rather than Spanish.
        assert "Sign in to your portal" in rendered
        assert 'lang="en"' in rendered

    def test_untranslated_message_falls_back_to_english_rather_than_failing(self):
        """security_alert has no Spanish copy yet; it must still send."""
        service = EmailService()
        rendered = service._render_template("security_alert.html", TEMPLATE_CONTEXT, "es")
        assert "<html" in rendered.lower()
        assert "Email content unavailable" not in rendered

    def test_frame_language_matches_body_language(self):
        """base.html's header/footer sit outside every content block. A
        Spanish body inside an English frame — or vice versa — is a worse
        email than a consistent one."""
        service = EmailService()
        spanish = service._render_template("magic_link.html", TEMPLATE_CONTEXT, "es")
        assert 'lang="es-MX"' in spanish
        # The tagline is MADFAM's now, not one platform's — the header reads
        # MADFAM on every message (see docs/EMAIL_SENDER_POLICY.md). What this
        # test guards is unchanged: the frame's language must match the body's.
        # "tu operación" → "su operación": the frame settled on the usted
        # register as the DEFAULT. It is no longer the only register — #540
        # added the reader's tú/usted choice, and ES_TU carries the tú variant
        # ("para tu operación"). This asserts the default the render path uses
        # when no formality is passed.
        assert "Tecnología, diseñada para su operación" in spanish
        assert "Technology, engineered for your operation" not in spanish

        # Untranslated body → English body → English frame, not a mix.
        fallback = service._render_template("security_alert.html", TEMPLATE_CONTEXT, "es")
        assert 'lang="en"' in fallback
        assert "Technology, engineered for your operation" in fallback

    def test_default_locale_setting_drives_unspecified_sends(self):
        service = EmailService()
        # Headlines were "Sign in to Janua" / "Inicie sesión en Janua" before the
        # sender-identity change. They still differ per locale, which is the
        # whole point of this test — DEFAULT_EMAIL_LOCALE must pick the body.
        with patch.object(email_module.settings, "DEFAULT_EMAIL_LOCALE", "en"):
            assert "Sign in to your portal" in service._render_template(
                "magic_link.html", TEMPLATE_CONTEXT
            )
        with patch.object(email_module.settings, "DEFAULT_EMAIL_LOCALE", "es"):
            assert "Inicie sesión en su portal" in service._render_template(
                "magic_link.html", TEMPLATE_CONTEXT
            )

    def test_template_globals_registered_on_every_shared_environment(self):
        """base.html calls t() and lang(); Jinja raises on calling an
        undefined name, so an environment over this directory without them
        cannot render anything."""
        from app.services.resend_email_service import ResendEmailService

        for env in (EmailService().jinja_env, ResendEmailService().jinja_env):
            assert "t" in env.globals
            assert "lang" in env.globals


class TestSubjectLocalization:
    """Subjects were English string literals at each call site."""

    @pytest.mark.parametrize(
        "message_key", ["verification", "password_reset", "magic_link", "welcome", "invitation"]
    )
    def test_every_message_has_both_languages(self, message_key):
        spanish = subject_for(message_key, "es", organization_name="Acme")
        english = subject_for(message_key, "en", organization_name="Acme")
        assert spanish and english and spanish != english

    def test_subject_resolves_through_the_same_mechanism_as_the_body(self):
        assert subject_for("magic_link", "es-MX") == subject_for("magic_link", "es")

    def test_unknown_locale_gets_english_subject_not_an_empty_one(self):
        assert subject_for("magic_link", "fr") == subject_for("magic_link", "en")

    def test_invitation_subject_interpolates_the_organization(self):
        assert "Acme" in subject_for("invitation", "es", organization_name="Acme")

    @pytest.mark.asyncio
    async def test_sender_passes_the_localized_subject_to_the_transport(self):
        """The subject a recipient sees must follow the same locale as the
        body — it is the only part visible before opening.

        `startswith` rather than `==` since 2026-09-06: every re-sendable
        subject now carries a send-time stamp after a " | " separator, so the
        LOCALIZED WORDS are the head of the subject rather than the whole of
        it. The stamp's own shape is pinned in
        tests/unit/services/test_email_voice_and_stamp.py; what this assertion
        is about is which language those words are in.
        """
        service = EmailService()
        with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
            await service.send_magic_link_email("a@b.test", "tok", locale="es-MX")
        assert send.await_args.kwargs["subject"].startswith(subject_for("magic_link", "es"))

        with patch.object(service, "_send_email", new=AsyncMock(return_value=True)) as send:
            await service.send_magic_link_email("a@b.test", "tok", locale="en")
        # Was "Your Janua sign-in link". The subject dropped the platform name
        # for the same reason the headline did. Deliberately still the literal
        # English string rather than subject_for(...): comparing against the
        # table the code reads would pass whatever the table said.
        assert send.await_args.kwargs["subject"].startswith("Your sign-in link")


class TestSendersAcceptLocale:
    """Routers resolve the recipient's language while they still hold a DB
    session; background tasks have none of their own."""

    @pytest.mark.parametrize(
        "task_name",
        ["send_magic_link_email_task", "send_password_reset_email_task",
         "send_verification_email_task"],
    )
    def test_background_entrypoints_take_a_locale(self, task_name):
        task = getattr(email_module, task_name)
        assert "locale" in inspect.signature(task).parameters

    @pytest.mark.parametrize(
        "method_name",
        ["send_magic_link_email", "send_password_reset_email", "send_verification_email",
         "send_welcome_email"],
    )
    def test_senders_take_an_explicit_locale_and_a_user(self, method_name):
        params = inspect.signature(getattr(EmailService, method_name)).parameters
        assert "locale" in params
        assert "user" in params

    def test_routers_pass_the_recipient_locale(self):
        """Without this the stored preference never reaches the mailer, and
        every recipient silently gets the deployment default.

        Read defensively: the password-reset dispatch is the one path a
        locked-out user depends on, so a recipient object without the
        attribute must not raise there.
        """
        from app.routers.v1 import auth

        # The /auth router is several modules since the 2026-11-19 split.
        source = "".join(
            inspect.getsource(importlib.import_module(f"app.routers.v1.{m}")) for m in auth.MODULES
        )
        assert 'getattr(user, "locale", None)' in source
        assert 'getattr(current_user, "locale", None)' in source
        assert "user.locale," not in source  # the unguarded read

    @pytest.mark.asyncio
    async def test_verification_task_sends_a_button_href(self):
        """This path passed only verification_url, while the template renders
        href="{{ verification_link }}" — so the mail every new account gets
        shipped with an empty button."""
        with patch.object(email_module.EmailService, "_send_email",
                          new=AsyncMock(return_value=True)) as send:
            await email_module.send_verification_email_task("a@b.test", "tok123", locale="es")
        html = send.await_args.kwargs["html_content"]
        assert 'href=""' not in html
        assert "tok123" in html
        assert "Verifique su correo electrónico" in html


class TestMagicLinkCallbackRoute:
    """A clicked link is a GET; /magic-link/verify is a POST returning JSON."""

    def test_get_callback_route_is_registered(self):
        from app.routers.v1.auth import router

        get_paths = {
            route.path
            for route in router.routes
            if "GET" in getattr(route, "methods", set())
        }
        assert any(path.endswith("/magic-link/callback") for path in get_paths), get_paths
