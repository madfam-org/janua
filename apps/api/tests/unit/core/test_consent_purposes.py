"""Purpose registry: shipped purposes are immutable (purpose limitation).

Consent was given to exactly one provider and one scope set. If a shipped
purpose's scopes change, every existing grant stops covering it and answers
`purpose_not_granted`. Consumers read that as the user's withdrawal and delete
data. New scopes therefore mean a NEW purpose id and a new consent, never an
edit here. If a test in this file fails, do not "fix" the fingerprint: revert
the scope change and register a new purpose id.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.core import consent_purposes
from app.core.consent_purposes import (
    PURPOSES,
    SHIPPED_PURPOSE_FINGERPRINTS,
    ConsentPurpose,
    get_purpose,
    purpose_drift,
    purpose_fingerprint,
)

YOUTUBE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"


def test_creator_census_youtube_is_exactly_google_youtube_readonly():
    purpose = get_purpose("creator-census.youtube")
    assert purpose is not None
    assert purpose.provider == "google"
    assert set(purpose.additional_scopes) == {YOUTUBE_READONLY}
    assert len(purpose.additional_scopes) == 1


def test_creator_census_youtube_clients_and_audience():
    purpose = get_purpose("creator-census.youtube")
    assert purpose.exchange_clients == frozenset({"creator-census"})
    assert purpose.offline_clients == frozenset({"creator-census-reauth"})
    assert purpose.allowed_subject_audiences == frozenset({"creator-census-api"})
    # One credential per path: a client may not sit on both lists.
    assert not (purpose.exchange_clients & purpose.offline_clients)


def test_shipped_purposes_are_unchanged():
    problems = purpose_drift()
    assert not problems, "\n".join(problems)


def test_every_registered_purpose_has_a_recorded_fingerprint():
    assert set(PURPOSES) <= set(SHIPPED_PURPOSE_FINGERPRINTS)


def test_fingerprint_ignores_scope_order_and_duplicates():
    a = purpose_fingerprint("google", ["b", "a"])
    assert a == purpose_fingerprint("google", ("a", "b", "a"))
    assert a != purpose_fingerprint("github", ["a", "b"])
    assert a != purpose_fingerprint("google", ["a"])


def _registry_with(monkeypatch, purpose: ConsentPurpose, fingerprints=None):
    monkeypatch.setattr(consent_purposes, "PURPOSES", MappingProxyType({purpose.id: purpose}))
    if fingerprints is not None:
        monkeypatch.setattr(
            consent_purposes, "SHIPPED_PURPOSE_FINGERPRINTS", MappingProxyType(fingerprints)
        )


@pytest.mark.parametrize(
    "provider,scopes",
    [
        ("google", (YOUTUBE_READONLY, "https://www.googleapis.com/auth/yt-analytics.readonly")),
        ("google", ()),
        ("microsoft", (YOUTUBE_READONLY,)),
    ],
    ids=["widened", "narrowed", "provider-changed"],
)
def test_changing_a_shipped_purpose_is_caught_with_guidance(monkeypatch, provider, scopes):
    shipped = get_purpose("creator-census.youtube")
    edited = ConsentPurpose(
        id=shipped.id,
        provider=provider,
        additional_scopes=scopes,
        exchange_clients=shipped.exchange_clients,
        offline_clients=shipped.offline_clients,
        allowed_subject_audiences=shipped.allowed_subject_audiences,
    )
    _registry_with(monkeypatch, edited)
    (problem,) = consent_purposes.purpose_drift()
    assert "creator-census.youtube" in problem
    assert "register a NEW purpose id" in problem


def test_unrecorded_new_purpose_is_caught(monkeypatch):
    new = ConsentPurpose(
        id="creator-census.youtube-analytics",
        provider="google",
        additional_scopes=("https://www.googleapis.com/auth/yt-analytics.readonly",),
        exchange_clients=frozenset({"creator-census"}),
        offline_clients=frozenset(),
        allowed_subject_audiences=frozenset({"creator-census-api"}),
    )
    _registry_with(monkeypatch, new, fingerprints={})
    (problem,) = consent_purposes.purpose_drift()
    assert "has no recorded fingerprint" in problem


def test_removing_a_shipped_purpose_is_caught(monkeypatch):
    monkeypatch.setattr(consent_purposes, "PURPOSES", MappingProxyType({}))
    (problem,) = consent_purposes.purpose_drift()
    assert "was removed from the registry" in problem


def test_unknown_purpose_is_none():
    assert get_purpose("made-up.purpose") is None
    assert get_purpose(None) is None
