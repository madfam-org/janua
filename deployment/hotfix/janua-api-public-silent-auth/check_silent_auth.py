"""Run inside an image: print how its /oauth/authorize trusts first-party clients, for the workflow.

Runs in the base image too, where janua#833's names do not exist, so they are
looked up defensively. Importing the router imports the application, so this
also proves the image imports cleanly. Nothing connects to a database.

Prints two lines:

- ``UNCHANGED=`` the first-party predicates every client already went through
  (`_is_silent_auth_allowed`, `_is_first_party_preconsented`), evaluated for a
  matrix of clients, marked and unmarked, public and confidential: it must be
  the same in both images, so no client is trusted differently by them;
- ``SILENT=`` the properties janua#833 adds (all true on the hotfix, all false
  on production's image).
"""

import inspect
import json
from types import SimpleNamespace

from app.routers.v1 import oauth_provider

MARKER = "madfam:silent_auth"
CALLBACK = "https://app.example.test/auth/callback"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"  # RFC 7636 appendix B


def _client(*, active=True, confidential=False, marked=False, name="hotfix-check-app", scopes=None):
    allowed = list(scopes or ["openid", "profile", "email"]) + ([MARKER] if marked else [])
    return SimpleNamespace(
        is_active=active,
        is_confidential=confidential,
        allowed_scopes=allowed,
        name=name,
        redirect_uris=[CALLBACK],
    )


CLIENTS = {
    f"{'active' if active else 'inactive'}-{'confidential' if confidential else 'public'}-{kind}": _client(
        active=active,
        confidential=confidential,
        marked=kind == "marked",
        name="madfam-hotfix-check" if kind == "first-party-name" else "hotfix-check-app",
    )
    for active in (True, False)
    for confidential in (True, False)
    for kind in ("plain", "marked", "first-party-name")
}


def _unchanged() -> dict:
    return {
        name: [
            oauth_provider._is_silent_auth_allowed(client),
            oauth_provider._is_first_party_preconsented(client),
        ]
        for name, client in CLIENTS.items()
    }


def _marked_public_client_recognised() -> bool:
    marked = getattr(oauth_provider, "_is_marked_public_client", None)
    if marked is None:
        return False
    # Only an active PUBLIC client carrying the marker; a first-party NAME is not enough.
    expected = {name: name == "active-public-marked" for name in CLIENTS}
    return {name: marked(client) for name, client in CLIENTS.items()} == expected


def _request_conditions_enforced() -> bool:
    refusal_of = getattr(oauth_provider, "_public_first_party_refusal", None)
    if refusal_of is None:
        return False
    client = _client(marked=True)

    def refusal(**overrides):
        request = {
            "redirect_uri": CALLBACK,
            "requested_scope": "openid profile",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        }
        request.update(overrides)
        return refusal_of(client, **request)

    pkce = ("interaction_required", "pkce_s256_required")
    return (
        refusal() is None
        and refusal(code_challenge_method=None) == pkce
        and refusal(code_challenge_method="plain") == pkce
        and refusal(code_challenge="short") == pkce
        and refusal(code_challenge=None) == pkce
        and refusal(redirect_uri=CALLBACK + "/")
        == ("interaction_required", "redirect_uri_not_exact")
        and refusal(redirect_uri=CALLBACK + "?x=1")
        == ("interaction_required", "redirect_uri_not_exact")
        and refusal(requested_scope="openid billing:admin")
        == ("consent_required", "scope_not_registered")
    )


def _authorize_source() -> str:
    # A request handler needs a database to run, so its wiring is read from the
    # code the image ships.
    return inspect.getsource(oauth_provider.authorize_get)


def _platform_admin_registration_required() -> bool:
    source = _authorize_source()
    return (
        "if _is_marked_public_client(client):" in source
        and "not await client_registered_by_platform_admin(db, client)" in source
        and "public_first_party = public_refusal is None" in source
    )


def _silent_gate_admits_only_first_party_or_applied() -> bool:
    return (
        "if silent_auth and not (_is_silent_auth_allowed(client) or public_first_party):"
        in _authorize_source()
    )


def _reserved_scopes_need_own_consent() -> bool:
    source = _authorize_source()
    return (
        "elif not has_consent and public_first_party:" in source
        and "reserved_requested = {s for s in requested_scopes if is_reserved_scope(s)}" in source
        and "if not reserved_requested or await ConsentService.has_consent(" in source
    )


unchanged = _unchanged()
print("UNCHANGED=" + json.dumps(unchanged, sort_keys=True))
print(
    "SILENT="
    + json.dumps(
        {
            "marked_public_client_recognised": _marked_public_client_recognised(),
            "request_conditions_enforced": _request_conditions_enforced(),
            "platform_admin_registration_required": _platform_admin_registration_required(),
            "silent_gate_admits_only_first_party_or_applied": _silent_gate_admits_only_first_party_or_applied(),
            "reserved_scopes_need_own_consent": _reserved_scopes_need_own_consent(),
        },
        sort_keys=True,
    )
)
