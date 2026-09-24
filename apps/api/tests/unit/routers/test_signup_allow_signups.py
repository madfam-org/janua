"""`auth.allow_signups` DB toggle precedence over ENABLE_SIGNUPS.

The `auth.allow_signups` system setting was previously dead (defined in
SettingKeys.AUTH_ALLOW_SIGNUPS, read nowhere). It is now a live runtime switch:
`signups_enabled(db)` reads the DB setting first and falls back to the
`settings.ENABLE_SIGNUPS` config default.

Precedence under test:
  1. DB `auth.allow_signups` (if set) wins — flips signups without a redeploy.
  2. Otherwise `settings.ENABLE_SIGNUPS` (config default / fallback).
  3. A settings-backend error falls back to the config default (never silently
     hardens the gate shut).

Plus: verify the signup handler actually honours the resolved value (a False
resolution 403s before any user is created).
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.routers.v1.auth as auth_mod
from app.routers.v1.auth import SignUpRequest, signups_enabled, sign_up

pytestmark = pytest.mark.asyncio


def _setting_result(raw):
    setting = None
    if raw is not None:
        setting = MagicMock()
        setting.get_value = MagicMock(return_value=raw)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=setting)
    return result


def _db_returning_setting(raw):
    """AsyncMock session for signups_enabled() in isolation.

    signups_enabled issues exactly one execute (the SystemSetting lookup), so a
    single canned result is sufficient here.
    """
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_setting_result(raw))
    return db


def _db_for_signup(setting_raw):
    """AsyncMock session for the full sign_up() path.

    Execute call order in sign_up(): (1) signups_enabled -> SystemSetting lookup
    returns `setting_raw`; (2) email-exists check -> must be None; (3) username
    check (only if username given) -> None. We return the setting result first,
    then None-yielding results for the user lookups.
    """
    call = {"i": 0}

    def _make_result(*a, **k):
        idx = call["i"]
        call["i"] += 1
        if idx == 0:
            return _setting_result(setting_raw)
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=None)
        return r

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_make_result)
    return db


class TestResolutionPrecedence:
    async def test_db_true_overrides_config_false(self):
        db = _db_returning_setting("true")
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", False):
            assert await signups_enabled(db) is True

    async def test_db_false_overrides_config_true(self):
        db = _db_returning_setting("false")
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", True):
            assert await signups_enabled(db) is False

    async def test_unset_falls_back_to_config_true(self):
        db = _db_returning_setting(None)
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", True):
            assert await signups_enabled(db) is True

    async def test_unset_falls_back_to_config_false(self):
        db = _db_returning_setting(None)
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", False):
            assert await signups_enabled(db) is False

    async def test_settings_backend_error_falls_back_to_config(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("settings table unavailable"))
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", True):
            assert await signups_enabled(db) is True
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", False):
            assert await signups_enabled(db) is False

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            (True, True),
            (1, True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("", False),
            (False, False),
            (0, False),
        ],
    )
    async def test_string_and_scalar_coercion(self, raw, expected):
        db = _db_returning_setting(raw)
        # Config default is irrelevant when the DB value is present and coercible.
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", not expected):
            assert await signups_enabled(db) is expected


class TestSignupHandlerHonoursToggle:
    def _request(self):
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/signup",
                "headers": [(b"user-agent", b"pytest")],
                "client": ("198.51.100.7", 51234),
            }
        )

    async def test_db_toggle_off_blocks_signup(self):
        """DB says off, config says on -> 403 and no user created."""
        db = _db_for_signup("false")
        db.add = MagicMock()
        db.commit = AsyncMock()
        with patch.object(auth_mod.settings, "ENABLE_SIGNUPS", True):
            with pytest.raises(HTTPException) as exc:
                await sign_up(
                    request=self._request(),
                    signup_data=SignUpRequest(
                        email="blocked@example.com", password="Str0ng!Passw0rd"
                    ),
                    background_tasks=MagicMock(),
                    db=db,
                )
        assert exc.value.status_code == 403
        # Gate short-circuits before any User is added.
        from app.models import User

        assert [c for c in db.add.call_args_list if c.args and isinstance(c.args[0], User)] == []

    async def test_db_toggle_on_allows_signup_despite_config_off(self):
        """DB says on, config says off -> signup proceeds to create a user."""
        db = _db_for_signup("true")
        db.add = MagicMock()
        db.commit = AsyncMock()

        async def refresh(obj, *a, **k):
            for col, val in (
                ("id", uuid.uuid4()),
                ("email_verified", False),
                ("is_admin", False),
                ("created_at", datetime.utcnow()),
                ("updated_at", datetime.utcnow()),
            ):
                if getattr(obj, col, None) is None:
                    setattr(obj, col, val)

        db.refresh = AsyncMock(side_effect=refresh)

        session_stub = AsyncMock(return_value=("access", "refresh", MagicMock()))
        with (
            patch.object(auth_mod.settings, "ENABLE_SIGNUPS", False),
            patch.object(auth_mod.settings, "EMAIL_ENABLED", False),
            patch.object(auth_mod.AuthService, "create_session", session_stub),
        ):
            resp = await sign_up(
                request=self._request(),
                signup_data=SignUpRequest(
                    email="allowed@example.com", password="Str0ng!Passw0rd"
                ),
                background_tasks=MagicMock(),
                db=db,
            )

        assert resp.user.email == "allowed@example.com"
        from app.models import User

        created = [c.args[0] for c in db.add.call_args_list if c.args and isinstance(c.args[0], User)]
        assert len(created) == 1
