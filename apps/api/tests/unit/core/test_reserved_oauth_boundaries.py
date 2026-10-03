"""The reserved OAuth-client registry: known members and matching rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import reserved_oauth_boundaries as reserved
from app.core.consent_purposes import PURPOSES
from app.services import payment_mail_auth


def test_service_auth_modules_read_the_registry_constants():
    assert payment_mail_auth.MAIL_AUDIENCE is reserved.MAIL_AUDIENCE
    assert payment_mail_auth.PAYMENT_MAIL_SCOPE is reserved.PAYMENT_MAIL_SCOPE


@pytest.mark.parametrize(
    "audience",
    [
        "janua-email",
        "janua-white-label",
        "janua-connections",
        "janua-anything-new",
        "karafiel-api",
        "dhanam-api",
        "yantra4d-api",
        "pravara-api",
        "asset-shells-api",
        " janua-email ",
    ],
)
def test_reserved_audiences(audience):
    assert reserved.is_reserved_audience(audience)


@pytest.mark.parametrize("audience", [None, "", "tenant-api", "my-janua-app", "janua"])
def test_ordinary_audiences(audience):
    assert not reserved.is_reserved_audience(audience)


def test_consent_purpose_audiences_and_names_are_reserved_by_construction():
    for purpose in PURPOSES.values():
        for audience in purpose.allowed_subject_audiences:
            assert reserved.is_reserved_audience(audience)
        for name in (*purpose.exchange_clients, *purpose.offline_clients):
            assert reserved.is_reserved_name(name)


@pytest.mark.parametrize(
    "scope",
    [
        "crea-map:payment-mail",
        "white-label:branding",
        "connections:delegate",
        "madfam:silent_auth",
        "admin",
        "hcm:admin",
        "cfdi:issue",
        "billing:events",
        "legal:draft",
        "legal:client-profile",
        "yantra4d:render",
        "pravara-mes:jobs",
        "pravara-mes:nodes",
        "pravara-mes:passports",
        "pravara-mes:read",
        "pravara-mes:admin",
        "asset-shells:read",
        "asset-shells:publish-types",
        "asset-shells:publish-instances",
    ],
)
def test_reserved_scopes(scope):
    assert reserved.is_reserved_scope(scope)


@pytest.mark.parametrize(
    "scope",
    [
        "openid",
        "profile",
        "email",
        "offline_access",
        "hcm:hr",
        "data-api",
        "billing:read",
        "pravara-mes:other",
        "asset-shells:write",
    ],
)
def test_ordinary_scopes(scope):
    assert not reserved.is_reserved_scope(scope)


@pytest.mark.parametrize(
    "name", ["madfam-portal", "MADFAM-portal", "selva-office-web", " madfam-x", "creator-census"]
)
def test_reserved_names(name):
    assert reserved.is_reserved_name(name)


def test_first_party_predicate_keeps_its_exact_prefix_rule():
    # Registration trims; the trust predicate does not widen to padded names.
    assert reserved.is_first_party_name("madfam-portal")
    assert reserved.is_first_party_name("Selva-Office")
    assert not reserved.is_first_party_name(" madfam-portal")
    assert not reserved.is_first_party_name("tenant-madfam-portal")


def test_reserved_fields_names_fields_never_values():
    fields = reserved.reserved_fields(
        name="madfam-x", audience="janua-email", scopes=["openid", "crea-map:payment-mail"]
    )
    assert fields == ["name", "audience", "allowed_scopes"]
    assert reserved.reserved_fields(name="tenant", audience="tenant-api", scopes=["openid"]) == []


def test_client_is_reserved_reads_a_row():
    row = SimpleNamespace(name="tenant", audience=None, allowed_scopes=["hcm:hr"])
    assert not reserved.client_is_reserved(row)
    row.allowed_scopes = ["white-label:branding"]
    assert reserved.client_is_reserved(row)
