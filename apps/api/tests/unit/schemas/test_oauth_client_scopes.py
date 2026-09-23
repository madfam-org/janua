"""OAuth client registration scope validation (OAuthClientCreate.allowed_scopes)."""

import pytest
from pydantic import ValidationError

from app.schemas.oauth_client import OAuthClientCreate
from app.services.payment_mail_auth import PAYMENT_MAIL_SCOPE


def _create(scopes):
    return OAuthClientCreate(
        name="scope validation fixture",
        redirect_uris=[],
        allowed_scopes=scopes,
        grant_types=["client_credentials"],
    )


@pytest.mark.parametrize(
    "scope",
    [
        "openid",
        "billing:read",
        "hcm:hr",
        "cards_v2:write",
        # The scope janua's own payment-notice boundary requires (#635).
        "crea-map:payment-mail",
        "crea-map:read_all",
    ],
)
def test_accepts_base_and_namespaced_scopes(scope):
    assert _create([scope]).allowed_scopes == [scope]


def test_payment_mail_scope_is_registrable():
    # Registration and the endpoint's authorization must agree, or the
    # client the endpoint requires can never be created.
    assert _create([PAYMENT_MAIL_SCOPE]).allowed_scopes == [PAYMENT_MAIL_SCOPE]


@pytest.mark.parametrize(
    "scope",
    [
        "Crea-map:payment-mail",  # uppercase
        "crea map:payment",  # whitespace
        ":read",  # empty namespace
        "billing:",  # empty action
        "-crea:read",  # namespace must start with a letter
        "crea:-read",  # action must start with a letter
        "crea:read:extra",  # exactly one separator
        "crea/map:read",  # path characters
    ],
)
def test_rejects_malformed_scopes(scope):
    with pytest.raises(ValidationError):
        _create([scope])
