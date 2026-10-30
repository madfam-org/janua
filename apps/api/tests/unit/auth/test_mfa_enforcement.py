"""Unit tests for the shared MFA-enforcement gate (2026-08-23).

Guards the decision that fixes the audit's #1 P0 — MFA was bypassed on every
login path except JSON /signin. The gate must be OFF by default (so shipping it
cannot lock anyone out) and only True when BOTH the flag is on AND the user has
MFA configured. Pure functions — no DB, no app bootstrap.
"""

from types import SimpleNamespace

import jwt as pyjwt

from app.auth.mfa_enforcement import (
    MFA_CHALLENGE_TYPE,
    mfa_required_for,
    mint_mfa_challenge_token,
)
from app.config import settings


def _user(mfa_enabled=True, mfa_secret="SECRET"):
    return SimpleNamespace(id="u-1", mfa_enabled=mfa_enabled, mfa_secret=mfa_secret)


class TestGateDefaultOff:
    def test_voluntary_enrollment_is_enforced_with_flag_off(self, monkeypatch):
        # The flag defaults False; with it off, NO login path is interrupted —
        # this is the property that makes shipping enforcement lock-out-safe.
        monkeypatch.setattr(settings, "MFA_ENFORCE_ON_LOGIN", False, raising=False)
        assert mfa_required_for(_user(mfa_enabled=True)) is True

    def test_on_and_enabled_requires_mfa(self, monkeypatch):
        monkeypatch.setattr(settings, "MFA_ENFORCE_ON_LOGIN", True, raising=False)
        assert mfa_required_for(_user(mfa_enabled=True, mfa_secret="S")) is True

    def test_on_but_user_has_no_mfa_does_not_require(self, monkeypatch):
        monkeypatch.setattr(settings, "MFA_ENFORCE_ON_LOGIN", True, raising=False)
        assert mfa_required_for(_user(mfa_enabled=False, mfa_secret=None)) is False
        assert mfa_required_for(_user(mfa_enabled=True, mfa_secret=None)) is False


class TestChallengeToken:
    def test_token_is_a_challenge_not_a_session(self, monkeypatch):
        monkeypatch.setattr(settings, "MFA_ENFORCE_ON_LOGIN", True, raising=False)
        token = mint_mfa_challenge_token(_user())
        decoded = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY or "development-secret-key",
            algorithms=["HS256"],
            options={"verify_iss": False},
        )
        assert decoded["type"] == MFA_CHALLENGE_TYPE
        assert decoded["sub"] == "u-1"
        assert "exp" in decoded and "iat" in decoded


class TestChallengeSigningKey:
    def test_uses_configured_jwt_secret(self, monkeypatch):
        from app.auth.mfa_enforcement import mfa_challenge_signing_key

        monkeypatch.setattr(settings, "JWT_SECRET_KEY", "k" * 40, raising=False)
        assert mfa_challenge_signing_key() == "k" * 40

    def test_never_uses_dev_default_when_unset(self, monkeypatch):
        from app.auth.mfa_enforcement import mfa_challenge_signing_key

        monkeypatch.setattr(settings, "JWT_SECRET_KEY", None, raising=False)
        monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48, raising=False)
        key = mfa_challenge_signing_key()
        assert key and key != "development-secret-key"
        assert key != "s" * 48  # derived, not the raw application secret

    def test_dev_default_value_is_treated_as_unset(self, monkeypatch):
        from app.auth.mfa_enforcement import mfa_challenge_signing_key

        monkeypatch.setattr(settings, "JWT_SECRET_KEY", "development-secret-key", raising=False)
        monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48, raising=False)
        assert mfa_challenge_signing_key() != "development-secret-key"

    def test_refuses_outside_dev_when_nothing_configured(self, monkeypatch):
        import pytest

        from app.auth.mfa_enforcement import mfa_challenge_signing_key

        monkeypatch.setattr(settings, "JWT_SECRET_KEY", None, raising=False)
        monkeypatch.setattr(settings, "SECRET_KEY", None, raising=False)
        monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
        with pytest.raises(RuntimeError):
            mfa_challenge_signing_key()

    def test_minted_challenge_verifies_with_signing_key_only(self, monkeypatch):
        import pytest

        from app.auth.mfa_enforcement import mfa_challenge_signing_key

        monkeypatch.setattr(settings, "JWT_SECRET_KEY", None, raising=False)
        monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48, raising=False)
        token = mint_mfa_challenge_token(_user())
        decoded = pyjwt.decode(
            token,
            mfa_challenge_signing_key(),
            algorithms=["HS256"],
            options={"verify_iss": False},
        )
        assert decoded["sub"] == "u-1"
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(
                token,
                "development-secret-key",
                algorithms=["HS256"],
                options={"verify_iss": False},
            )


def test_opaque_auth_references_are_purpose_and_key_bound(monkeypatch):
    from app.auth.mfa_enforcement import opaque_auth_reference
    from app.config import settings

    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "synthetic-reference-key-one")
    first = opaque_auth_reference("synthetic-random-capability", purpose="mfa-challenge-use")
    assert first == opaque_auth_reference("synthetic-random-capability", purpose="mfa-challenge-use")
    assert len(first) == 64 and "synthetic" not in first
    assert first != opaque_auth_reference("synthetic-random-capability", purpose="totp-factor")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "synthetic-reference-key-two")
    assert first != opaque_auth_reference("synthetic-random-capability", purpose="mfa-challenge-use")
