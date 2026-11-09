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
        "karafiel-app",
        "karafiel-staging-api",
        "dhanam-api",
        "dhanam-money-moves",
        "phynd-crm",
        "yantra4d-api",
        "pravara-api",
        "asset-shells-api",
        "fabrication-prep-api",
        " janua-email ",
    ],
)
def test_reserved_audiences(audience):
    assert reserved.is_reserved_audience(audience)


@pytest.mark.parametrize(
    "audience",
    [None, "", "tenant-api", "my-janua-app", "janua", "symbiosis-hcm", "selva-office"],
)
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
        "legal:employment-draft",
        "legal:contractor-draft",
        "legal:client-profile",
        "fiscal:invoice",
        "fiscal:csf-intake",
        "familia:documents",
        "dhanam-scheduled-payments:write",
        "dhanam:scheduled-payments:write",
        "dhanam-cost-events:write",
        "dhanam:merchant-read",
        "phynd-crm-engagements:read",
        " phynd-crm-engagements:read ",
        "hcm-benchmarks:read",
        "yantra4d:render",
        "pravara-mes:jobs",
        "pravara-mes:nodes",
        "pravara-mes:passports",
        "pravara-mes:read",
        "pravara-mes:admin",
        "asset-shells:read",
        "asset-shells:publish-types",
        "asset-shells:publish-instances",
        "fabrication-prep:slice",
        "fabrication-prep:admin",
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
        "hcm:payroll",
        "selva:infer",
        "legal:other",
        "familia:other",
        "data-api",
        "billing:read",
        # PhyndCRM look-alikes no consumer honours (exact-match scopes).
        "phynd-crm:read",
        "phynd-crm-engagements:write",
        "engagements:read",
        "pravara-mes:other",
        "asset-shells:write",
        "fabrication-prep:read",
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


def test_phynd_crm_machine_audience_is_reserved_but_its_sso_audience_is_not():
    # Machine tokens carry ``phynd-crm`` (PHYND_CRM_MACHINE_AUDIENCE); the staff
    # SSO client's ``phynd-crm-api`` is an ordinary interactive audience.
    assert reserved.is_reserved_audience("phynd-crm")
    assert not reserved.is_reserved_audience("phynd-crm-api")
    assert reserved.PHYND_CRM_SCOPES == frozenset({"phynd-crm-engagements:read"})
    assert reserved.PHYND_CRM_SCOPES <= reserved.RESERVED_SCOPES
    assert "phynd-crm-engagements:read" not in reserved.TENANT_BOUND_MACHINE_SCOPES
    assert "phynd-crm" not in reserved.TENANT_BOUND_SERVICE_AUDIENCES
    assert reserved.reserved_fields(
        name="nauta-phynd-crm", audience="phynd-crm", scopes=["phynd-crm-engagements:read"]
    ) == ["audience", "allowed_scopes"]
