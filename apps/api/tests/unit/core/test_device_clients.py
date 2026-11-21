"""Pure rules of shared-device clients (`app/core/device_clients.py`)."""

from __future__ import annotations

import base64
import secrets

import pytest

from app.core import device_clients as dc
from app.core import reserved_oauth_boundaries as reserved


def test_device_tokens_live_fifteen_minutes_and_service_tokens_an_hour():
    assert dc.token_ttl_seconds(dc.CLIENT_KIND_DEVICE) == 15 * 60
    assert dc.token_ttl_seconds(dc.CLIENT_KIND_SERVICE) == 60 * 60


def test_client_kind_follows_the_device_prefix():
    assert dc.client_kind_for(dc.generate_device_client_id()) == dc.CLIENT_KIND_DEVICE
    assert dc.client_kind_for("jnc_some_service") == dc.CLIENT_KIND_SERVICE
    assert dc.client_kind_for(None) == dc.CLIENT_KIND_SERVICE
    assert not dc.is_device_client_id("")


def test_every_template_holds_only_reserved_values_and_client_credentials():
    """A device's scope and audience are reserved, so no organization admin can
    register an ordinary client that claims them."""
    for template in dc.DEVICE_TEMPLATES.values():
        assert reserved.is_reserved_audience(template.audience)
        assert template.scopes and all(reserved.is_reserved_scope(s) for s in template.scopes)
        assert template.grant_types == frozenset({"client_credentials"})


def test_the_terminal_template_carries_the_terminal_scope_on_pravaras_audience():
    template = dc.get_device_template(dc.DEFAULT_DEVICE_TEMPLATE)
    assert template is dc.NAUTA_EDGE_TERMINAL
    assert template.audience == "pravara-api"
    assert template.scopes == frozenset({"pravara-mes:terminal"})
    assert dc.get_device_template("unknown") is None
    assert dc.get_device_template(None) is None


@pytest.mark.parametrize(
    "secret",
    [
        secrets.token_hex(32),
        secrets.token_hex(32).upper(),
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
    ],
)
def test_a_32_byte_secret_is_accepted_as_hex_or_base64url(secret):
    assert dc.device_secret_is_valid(secret)


@pytest.mark.parametrize(
    "secret",
    [
        None,
        "",
        secrets.token_hex(31),
        secrets.token_hex(33),
        "00" * 32,
        base64.urlsafe_b64encode(bytes(32)).decode().rstrip("="),
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),  # padded
        "z" * 64,
    ],
)
def test_anything_else_is_refused(secret):
    assert not dc.device_secret_is_valid(secret)


def test_user_codes_have_no_vowels_and_normalize():
    for _ in range(50):
        code = dc.generate_user_code()
        assert len(code) == 9 and code[4] == "-"
        assert all(c in dc.USER_CODE_ALPHABET for c in code.replace("-", ""))
        assert not set("AEIOU01") & set(code)
    assert dc.normalize_user_code("bcdf ghjk") == "BCDF-GHJK"
    assert dc.normalize_user_code("BCDFGHJK") == "BCDF-GHJK"
    assert dc.normalize_user_code("BCDF-GHJA") is None
    assert dc.normalize_user_code("BCD") is None
    assert dc.normalize_user_code(None) is None


def test_boot_ids_are_validated_and_stored_only_as_digests():
    boot = secrets.token_urlsafe(16)
    assert dc.boot_id_is_valid(boot)
    assert not dc.boot_id_is_valid("short")
    assert not dc.boot_id_is_valid("x" * 129)
    assert not dc.boot_id_is_valid("has spaces in it ok")
    assert not dc.boot_id_is_valid(None)
    digest = dc.boot_id_digest(boot)
    assert len(digest) == dc.BOOT_ID_DIGEST_HEX_CHARS and boot not in digest


def _boots(*names):
    return [f"boot-{name}-{'x' * 16}" for name in names]


def _replay(sequence):
    recent: list[str] = []
    flags = []
    for boot in sequence:
        observation = dc.observe_boot_id(recent, boot)
        recent = observation.recent
        flags.append(observation.alternated)
    return recent, flags


def test_one_device_that_restarts_is_never_flagged():
    _, flags = _replay(_boots("a", "a", "b", "b", "c", "d", "d", "e"))
    assert flags == [False] * 8


def test_two_devices_taking_turns_are_flagged_when_the_first_returns():
    a, b = _boots("a", "b")
    _, flags = _replay([a, a, b, a, b])
    assert flags == [False, False, False, True, True]


def test_three_holders_taking_turns_are_flagged_too():
    a, b, c = _boots("a", "b", "c")
    _, flags = _replay([a, b, c, a, b, c])
    assert flags == [False, False, False, True, True, True]


def test_the_recent_list_is_bounded_and_round_trips():
    recent, _ = _replay(_boots(*[str(i) for i in range(20)]))
    assert len(recent) == dc.RECENT_BOOT_IDS_KEPT
    assert dc.parse_recent_boot_ids(dc.serialize_recent_boot_ids(recent)) == recent
    assert dc.parse_recent_boot_ids(None) == []
