"""Actual authenticated cookie encryption; no service, token or identity fixture."""

import secrets
import time

import pytest

from app.auth.session_bridge_state import InvalidBridgeState
from app.routers.v1 import session_bridge as bridge


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(bridge.settings, "SECRET_KEY", "F-901-" + "K" * 48)


@pytest.mark.parametrize("purpose", [bridge.COOKIE, bridge.FINAL_COOKIE])
def test_private_random_challenge_is_encrypted_and_authenticated(purpose):
    challenge = secrets.token_urlsafe(32)
    first, second = bridge._seal_cookie(challenge, purpose), bridge._seal_cookie(challenge, purpose)
    assert first != challenge and challenge not in first
    assert first != second
    assert 100 <= len(first) <= bridge.MAX_COOKIE_LENGTH
    assert bridge._open_cookie(first, purpose) == challenge
    assert bridge._open_cookie(second, purpose) == challenge


@pytest.mark.parametrize("purpose", [bridge.COOKIE, bridge.FINAL_COOKIE])
def test_cookie_expiry_uses_real_authenticated_timestamp_and_purpose_ttl(purpose):
    challenge = secrets.token_urlsafe(32).encode()
    cipher = bridge._cookie_cipher(purpose)
    old = cipher.encrypt_at_time(challenge, int(time.time()) - bridge.COOKIE_LIFETIMES[purpose] - 1)
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(old.decode(), purpose)
    future = cipher.encrypt_at_time(challenge, int(time.time()) + 120)
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(future.decode(), purpose)


def test_initializer_and_finalizer_are_cryptographically_separate():
    challenge = secrets.token_urlsafe(32)
    initial = bridge._seal_cookie(challenge, bridge.COOKIE)
    final = bridge._seal_cookie(challenge, bridge.FINAL_COOKIE)
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(initial, bridge.FINAL_COOKIE)
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(final, bridge.COOKIE)


def test_modified_key_or_ciphertext_never_falls_back_to_plaintext(monkeypatch):
    challenge = secrets.token_urlsafe(32)
    cookie = bridge._seal_cookie(challenge, bridge.COOKIE)
    modified = cookie[:70] + ("A" if cookie[70] != "A" else "B") + cookie[71:]
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(modified, bridge.COOKIE)
    monkeypatch.setattr(bridge.settings, "SECRET_KEY", "F-902-" + "L" * 48)
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(cookie, bridge.COOKIE)


@pytest.mark.parametrize("value", [None, "", "W" * 43, "!" * 140, "X" * 513, "á" * 140])
def test_missing_raw_malformed_or_oversized_cookie_is_refused(value):
    with pytest.raises(InvalidBridgeState):
        bridge._open_cookie(value, bridge.COOKIE)


@pytest.mark.parametrize("key", [None, "", "F-903"])
def test_missing_or_insufficient_existing_key_is_refused(monkeypatch, key):
    monkeypatch.setattr(bridge.settings, "SECRET_KEY", key)
    with pytest.raises(InvalidBridgeState):
        bridge._seal_cookie(secrets.token_urlsafe(32), bridge.COOKIE)


def test_authenticated_but_wrong_plaintext_shape_or_unknown_purpose_is_refused():
    cipher = bridge._cookie_cipher(bridge.COOKIE)
    for value in (b"F-904", b"!" * 43):
        cookie = cipher.encrypt(value).decode()
        with pytest.raises(InvalidBridgeState):
            bridge._open_cookie(cookie, bridge.COOKIE)
    with pytest.raises(InvalidBridgeState):
        bridge._seal_cookie(secrets.token_urlsafe(32), "F-905")
    with pytest.raises(InvalidBridgeState):
        bridge._seal_cookie("!" * 43, bridge.COOKIE)
