"""MAGIC_LINK_RATE_LIMIT — the per-client-IP ceiling (was: the only limit).

Until 2026-10-07 this knob was the ONLY limit on POST /magic-link: a slowapi
decorator, 5/hour, keyed on `request.client.host`. In production that key is
the tunnel pod's address for everyone, and a product's server asks for all of
its people, so the whole MAP got five links an hour. The email-bombing guard is
now per ADDRESS (MAGIC_LINK_EMAIL_RATE_LIMIT, 5/hour). This knob became a
per-client-IP ceiling far above one person (60/hour), so a whole office on one
IP can sign in. See tests/unit/routers/test_magic_link_limits.py for the
behaviour; these tests pin the knobs.
"""

from pathlib import Path

from app.config import Settings


class TestMagicLinkRateLimitKnob:
    def test_per_ip_default_is_a_ceiling_not_a_per_person_limit(self):
        assert Settings().MAGIC_LINK_RATE_LIMIT == "60/hour"

    def test_per_address_default_keeps_the_email_bombing_guard(self):
        assert Settings().MAGIC_LINK_EMAIL_RATE_LIMIT == "5/hour"

    def test_env_override_is_respected(self, monkeypatch):
        monkeypatch.setenv("MAGIC_LINK_RATE_LIMIT", "120/hour")
        monkeypatch.setenv("MAGIC_LINK_EMAIL_RATE_LIMIT", "3/hour")
        monkeypatch.setenv("MAGIC_LINK_SERVICE_RATE_LIMIT", "500/hour")
        s = Settings()
        assert (s.MAGIC_LINK_RATE_LIMIT, s.MAGIC_LINK_EMAIL_RATE_LIMIT) == ("120/hour", "3/hour")
        assert s.MAGIC_LINK_SERVICE_RATE_LIMIT == "500/hour"

    def test_a_malformed_limit_is_refused_at_boot(self, monkeypatch):
        import pytest
        from pydantic import ValidationError

        monkeypatch.setenv("MAGIC_LINK_EMAIL_RATE_LIMIT", "five an hour")
        with pytest.raises(ValidationError):
            Settings()

    def test_the_limits_read_the_settings_not_hardcoded_strings(self):
        source = Path("app/auth/magic_link_limits.py").read_text()
        for knob in (
            "settings.MAGIC_LINK_EMAIL_RATE_LIMIT",
            "settings.MAGIC_LINK_RATE_LIMIT",
            "settings.MAGIC_LINK_SERVICE_RATE_LIMIT",
        ):
            assert knob in source
        route = Path("app/routers/v1/auth.py").read_text()
        anchor = route.index('@router.post("/magic-link")')
        assert '@limiter.limit("5/hour")' not in route[anchor : anchor + 800]
