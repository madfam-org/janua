"""Tests for the hosted password-recovery pages (2026-08-13).

Regression suite for three defects that made self-service recovery a dead
end: the hosted login page rendered no forgot-password affordance; the reset
email's default link pointed at an auth-walled frontend route; and the
redirect allowlist contained no Janua-own page. The hosted pages under
/api/v1/auth/{forgot-password,reset-password} are the fix — served by the
same host that mints the token, so they cannot be auth-walled away.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _db_returning(row):
    """AsyncMock db whose execute() resolves to a result yielding `row`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()  # session.add is sync
    return db


# ---------------------------------------------------------------------------
# Hosted pages
# ---------------------------------------------------------------------------


class TestRecoveryPages:
    def test_login_page_offers_forgot_password(self):
        """The affordance defect: the login page must link to recovery."""
        resp = _client().get("/api/v1/auth/login")
        assert resp.status_code == 200
        assert 'href="/api/v1/auth/forgot-password"' in resp.text

    def test_forgot_page_renders_form(self):
        resp = _client().get("/api/v1/auth/forgot-password")
        assert resp.status_code == 200
        assert 'action="/api/v1/auth/forgot-password-form"' in resp.text
        assert 'name="email"' in resp.text

    def test_reset_page_embeds_token(self):
        resp = _client().get("/api/v1/auth/reset-password", params={"token": "tok-abc123"})
        assert resp.status_code == 200
        assert 'name="token" value="tok-abc123"' in resp.text
        assert 'action="/api/v1/auth/reset-password-form"' in resp.text

    def test_reset_page_escapes_token(self):
        resp = _client().get(
            "/api/v1/auth/reset-password",
            params={"token": '"><script>alert(1)</script>'},
        )
        assert resp.status_code == 200
        assert "<script>alert(1)</script>" not in resp.text

    def test_reset_page_without_token_points_at_forgot(self):
        resp = _client().get("/api/v1/auth/reset-password")
        assert resp.status_code == 400
        assert "/api/v1/auth/forgot-password" in resp.text

    def test_reset_form_mismatch_rerenders_with_token_preserved(self):
        """A mismatch must not burn the token — the same link stays usable."""
        resp = _client().post(
            "/api/v1/auth/reset-password-form",
            data={
                "token": "tok-x",
                "new_password": "Aa1!Aa1!Aa1!",
                "confirm_password": "Bb2@Bb2@Bb2@",
            },
        )
        assert resp.status_code == 400
        assert "match" in resp.text
        assert 'value="tok-x"' in resp.text


# ---------------------------------------------------------------------------
# _consume_password_reset — shared by JSON endpoint and hosted form
# ---------------------------------------------------------------------------


class TestConsumePasswordReset:
    async def test_invalid_token(self):
        from app.routers.v1.auth import _consume_password_reset

        db = _db_returning(None)
        ok, message = await _consume_password_reset("ghost", "Sufficient1!Pass", db)
        assert (ok, message) == (False, "Invalid or expired reset token")
        db.commit.assert_not_awaited()

    async def test_weak_password_leaves_token_live(self):
        from app.routers.v1.auth import _consume_password_reset

        reset = SimpleNamespace(user_id=uuid.uuid4(), used=False, used_at=None)
        db = _db_returning(reset)
        ok, message = await _consume_password_reset("tok", "weak", db)
        assert ok is False
        assert "12 characters" in message
        assert reset.used is False
        db.get.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_happy_path_sets_password_verifies_email_and_burns_token(self):
        from app.routers.v1.auth import _consume_password_reset
        from app.services.auth_service import AuthService

        user = SimpleNamespace(id=uuid.uuid4(), password_hash="old", email_verified=False)
        reset = SimpleNamespace(user_id=user.id, used=False, used_at=None)
        db = _db_returning(reset)
        db.get = AsyncMock(return_value=user)

        password_at_revoke = []

        async def invalidate(*args, **kwargs):
            password_at_revoke.append(user.password_hash)
            return 0

        invalidate_mock = AsyncMock(side_effect=invalidate)
        with (
            patch("app.routers.v1.auth.log_activity", new=AsyncMock()),
            patch("app.routers.v1.auth.log_audit_event", new=AsyncMock()),
            patch.object(AuthService, "invalidate_user_sessions", new=invalidate_mock),
        ):
            ok, message = await _consume_password_reset("tok", "Sufficient1!Pass", db)

        assert ok is True
        # Every session is revoked (none kept), strictly, inside the reset's
        # own transaction and BEFORE the password changes (J3-003).
        first = invalidate_mock.await_args_list[0]
        assert first.args[1] == user.id
        assert first.kwargs["reason"] == "password_reset"
        assert first.kwargs["strict"] is True
        assert first.kwargs["commit"] is False
        assert "exclude_session_id" not in first.kwargs
        assert password_at_revoke[0] == "old"
        # After the commit, one best-effort sweep for a session a concurrent
        # sign-in with the old password committed meanwhile.
        assert invalidate_mock.await_count == 2
        sweep = invalidate_mock.await_args_list[1]
        assert sweep.kwargs["reason"] == "password_reset"
        assert not sweep.kwargs.get("strict", False)
        assert password_at_revoke[1] != "old"
        assert AuthService.verify_password("Sufficient1!Pass", user.password_hash)
        # Completing a reset proves control of the mailbox — without this an
        # unverified account recovers its password only to be blocked at the
        # authorize endpoint's verification gate (observed live 2026-08-13).
        assert user.email_verified is True
        assert reset.used is True
        assert reset.used_at is not None
        db.commit.assert_awaited()


# ---------------------------------------------------------------------------
# _dispatch_password_reset — enumeration safety and real-mailer dispatch
# ---------------------------------------------------------------------------


class TestDispatchPasswordReset:
    async def test_unknown_email_is_silent_and_sends_nothing(self):
        from app.routers.v1.auth import _dispatch_password_reset

        db = _db_returning(None)
        bg = MagicMock()
        await _dispatch_password_reset("ghost@example.test", None, bg, db)
        bg.add_task.assert_not_called()
        db.add.assert_not_called()

    async def test_known_email_queues_the_real_mailer(self):
        import app.routers.v1.auth as auth_module
        from app.routers.v1.auth import _dispatch_password_reset

        user = SimpleNamespace(id=uuid.uuid4(), email="known@example.test")
        db = _db_returning(user)
        bg = MagicMock()

        with patch.object(auth_module.settings, "EMAIL_ENABLED", True):
            await _dispatch_password_reset("known@example.test", None, bg, db)

        bg.add_task.assert_called_once()
        args = bg.add_task.call_args.args
        assert args[0] is auth_module.send_password_reset_email_task
        assert args[1] == "known@example.test"
        assert isinstance(args[2], str) and len(args[2]) > 20  # the stored token
        assert args[3] is None  # no redirect_base: default = API-hosted page


# ---------------------------------------------------------------------------
# The reset pages in the email's language (ui_locales, 2026-10-27)
# ---------------------------------------------------------------------------

RESET_URL = "/api/v1/auth/reset-password"
RESET_FORM_URL = "/api/v1/auth/reset-password-form"
ES_HIDDEN = '<input type="hidden" name="ui_locales" value="es">'
MATCHING = {"token": "tok-x", "new_password": "Aa1!Aa1!Aa1!", "confirm_password": "Aa1!Aa1!Aa1!"}
MISMATCHED = {"token": "tok-x", "new_password": "Aa1!Aa1!Aa1!", "confirm_password": "Bb2@Bb2@Bb2@"}


def _post_with_outcome(outcome, data):
    """POST the reset form with _consume_password_reset answering `outcome`."""
    with patch("app.routers.v1.auth._consume_password_reset", new=AsyncMock(return_value=outcome)):
        return _client().post(RESET_FORM_URL, data=data)


class TestResetPagesInSpanish:
    def test_form(self):
        resp = _client().get(RESET_URL, params={"token": "tok-abc", "ui_locales": "es-MX en"})
        assert resp.status_code == 200
        body = resp.text
        assert '<html lang="es-MX">' in body
        assert "<title>Recuperar contraseña - Janua</title>" in body
        assert "Elige una contraseña nueva" in body
        assert '<label for="new_password">Contraseña nueva</label>' in body
        assert '<label for="confirm_password">Confirma la contraseña nueva</label>' in body
        assert "Al menos 12 caracteres, con una mayúscula" in body
        assert '<button type="submit">Guardar contraseña</button>' in body
        assert 'name="token" value="tok-abc"' in body
        # The language rides the POST.
        assert body.count(ES_HIDDEN) == 1
        assert "Choose a new password" not in body

    def test_missing_token(self):
        resp = _client().get(RESET_URL, params={"ui_locales": "es"})
        assert resp.status_code == 400
        assert '<html lang="es-MX">' in resp.text
        assert "Esta página necesita el enlace del correo" in resp.text
        assert '<a href="/api/v1/auth/forgot-password?ui_locales=es">Pídelo aquí</a>' in resp.text

    def test_mismatch_rerenders_in_spanish_and_keeps_the_language(self):
        resp = _client().post(RESET_FORM_URL, data={**MISMATCHED, "ui_locales": "es"})
        assert resp.status_code == 400
        assert "Las dos contraseñas no coinciden." in resp.text
        assert 'value="tok-x"' in resp.text
        assert ES_HIDDEN in resp.text

    def test_success(self):
        resp = _post_with_outcome(
            (True, "Password successfully reset"), {**MATCHING, "ui_locales": "es"}
        )
        assert resp.status_code == 200
        assert '<html lang="es-MX">' in resp.text
        assert "Contraseña actualizada" in resp.text
        assert (
            "Tu contraseña quedó lista. Vuelve a la aplicación de donde venías y "
            "entra con tu correo y tu nueva contraseña."
        ) in resp.text
        assert "Close this tab" not in resp.text

    def test_expired_link(self):
        resp = _post_with_outcome(
            (False, "Invalid or expired reset token"), {**MATCHING, "ui_locales": "es"}
        )
        assert resp.status_code == 400
        assert "Este enlace para cambiar la contraseña no es válido o ya venció" in resp.text
        assert '<a href="/api/v1/auth/forgot-password?ui_locales=es">aquí</a>' in resp.text

    def test_policy_rejection_is_translated_and_keeps_the_language(self):
        resp = _post_with_outcome(
            (False, "Password must contain at least one number"),
            {**MATCHING, "ui_locales": "es"},
        )
        assert resp.status_code == 400
        assert "La contraseña debe tener al menos un número." in resp.text
        assert "Password must" not in resp.text
        assert ES_HIDDEN in resp.text and 'value="tok-x"' in resp.text

    def test_an_untranslated_policy_message_still_shows(self):
        resp = _post_with_outcome(
            (False, "Some future policy rule"), {**MATCHING, "ui_locales": "es"}
        )
        assert resp.status_code == 400
        assert "Some future policy rule" in resp.text


class TestResetPagesStayEnglishByDefault:
    """No ui_locales (and an unsupported one) renders the English pages the
    regression tests above have always pinned."""

    def test_form(self):
        for params in ({"token": "tok-abc"}, {"token": "tok-abc", "ui_locales": "fr-CA"}):
            body = _client().get(RESET_URL, params=params).text
            assert '<html lang="en">' in body
            assert "<title>Password recovery - Janua</title>" in body
            assert "<p>Choose a new password</p>" in body
            assert '<button type="submit">Set new password</button>' in body
            assert 'name="ui_locales"' not in body

    def test_missing_token(self):
        body = _client().get(RESET_URL).text
        assert "This page needs the link from your reset email." in body
        assert '<a href="/api/v1/auth/forgot-password">Request one here</a>' in body

    def test_mismatch(self):
        resp = _client().post(RESET_FORM_URL, data=MISMATCHED)
        assert "The two passwords don&#x27;t match." in resp.text
        assert 'name="ui_locales"' not in resp.text

    def test_success(self):
        resp = _post_with_outcome((True, "Password successfully reset"), MATCHING)
        assert resp.status_code == 200
        assert (
            "Your password has been updated. Close this tab and sign in again from "
            "the application you came from."
        ) in resp.text

    def test_expired_link(self):
        resp = _post_with_outcome((False, "Invalid or expired reset token"), MATCHING)
        assert resp.status_code == 400
        assert "This reset link is invalid or has expired" in resp.text
        assert '<a href="/api/v1/auth/forgot-password">here</a>' in resp.text

    def test_policy_rejection(self):
        resp = _post_with_outcome((False, "Password must contain at least one number"), MATCHING)
        assert "Password must contain at least one number" in resp.text


class TestPasswordPolicyTranslations:
    def test_every_policy_message_has_a_spanish_line(self):
        """A message the validator can return must not fall back to English
        on the Spanish page. If a rule is added, add its line too."""
        from app.auth.hosted_locale import PASSWORD_POLICY_COPY
        from app.services.auth_service import AuthService

        samples = ["Aa1!", "aa1!aa1!aa1!", "AA1!AA1!AA1!", "Aa!!Aa!!Aa!!", "Aa11Aa11Aa11"]
        messages = {AuthService.validate_password_strength(p)[1] for p in samples}
        assert len(messages) == 5
        assert messages == set(PASSWORD_POLICY_COPY["es"])

    def test_the_json_api_message_stays_english(self):
        from app.services.auth_service import AuthService

        assert AuthService.validate_password_strength("Aa1!") == (
            False,
            "Password must be at least 12 characters long",
        )
