"""The discovery documents advertise only routes the app serves.

`/.well-known/oauth-authorization-server` and `/.well-known/openid-configuration`
listed `registration_endpoint: …/api/v1/oauth/register` until 2026-11, but
Janua never had an RFC 7591 route there: it answered 404. An MCP client that
tries dynamic registration before CIMD (the Claude desktop app signing in to
the MAP's MCP server) failed before sign-in started. These tests ask the app's
router how it would dispatch each advertised URL, so the next endpoint that is
advertised but not served (or served under another method) fails here instead
of in a client.
"""

from __future__ import annotations

import pytest
from starlette.routing import Match

from app.core.oauth_metadata import authorization_server_metadata

ISSUER = "https://auth.madfam.io"

#: The HTTP method a client uses at each endpoint the metadata may name.
#: A new `*_endpoint` / `*_uri` key must be added here (the test below fails
#: until it is), which forces a decision on how clients call it.
ENDPOINT_METHODS = {
    "authorization_endpoint": "GET",
    "token_endpoint": "POST",
    "userinfo_endpoint": "GET",
    "jwks_uri": "GET",
    "introspection_endpoint": "POST",
    "revocation_endpoint": "POST",
    "end_session_endpoint": "GET",
    # RFC 7591. Not advertised today (see test_no_registration_endpoint); kept
    # here so that advertising it again requires a POST route at that path.
    "registration_endpoint": "POST",
}

WELL_KNOWN_METADATA_PATHS = (
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
)


@pytest.fixture(scope="module")
def janua_app():
    from app.main import app

    return app


def route_match(app, method: str, path: str) -> Match:
    """How the app's router would dispatch `method path`, without running it.

    FULL: a route answers it. PARTIAL: the path exists, not for this method
    (405). NONE: 404. This goes through Starlette's `BaseRoute.matches`, the
    call the router itself dispatches with, rather than reading `app.routes`
    as a flat list: since FastAPI 0.15x, `include_router` keeps a router's
    routes inside one included-router entry (CI installs 0.162), so a flat
    read finds only the routes declared directly on `app`.
    """
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": [],
    }
    result = Match.NONE
    for route in app.router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return Match.FULL
        if match == Match.PARTIAL:
            result = Match.PARTIAL
    return result


@pytest.fixture
def doc(monkeypatch) -> dict:
    monkeypatch.setenv("JANUA_CUSTOM_DOMAIN", "auth.madfam.io")
    return authorization_server_metadata()


def _endpoint_keys(doc: dict) -> list[str]:
    return [key for key in doc if key.endswith("_endpoint") or key.endswith("_uri")]


def test_the_matcher_sees_included_routers_and_unknown_paths(janua_app):
    """Guard against a vacuous check in either direction."""
    # Declared on `app` itself.
    assert route_match(janua_app, "GET", "/.well-known/openid-configuration") == Match.FULL
    # Declared on an included router (oauth_provider, prefix /api/v1).
    assert route_match(janua_app, "POST", "/api/v1/oauth/token") == Match.FULL
    assert route_match(janua_app, "GET", "/api/v1/oauth/token") == Match.PARTIAL
    assert route_match(janua_app, "GET", "/no-such-route-for-the-metadata-test") == Match.NONE


def test_every_endpoint_key_has_a_known_method(doc):
    unknown = sorted(set(_endpoint_keys(doc)) - set(ENDPOINT_METHODS))
    assert not unknown, (
        f"metadata keys with no entry in ENDPOINT_METHODS: {unknown}. Add the "
        "method clients use there so the route check below covers them."
    )


def test_every_endpoint_is_on_the_issuer(doc):
    assert doc["issuer"] == ISSUER
    off_issuer = {
        key: doc[key] for key in _endpoint_keys(doc) if not doc[key].startswith(ISSUER + "/")
    }
    assert not off_issuer, f"endpoints not served by this issuer: {off_issuer}"


def test_every_advertised_url_is_a_served_route(doc, janua_app):
    """Every URL on the issuer, under any key, routes somewhere (no 404)."""
    missing = {}
    for key, value in doc.items():
        if isinstance(value, str) and value.startswith(ISSUER + "/"):
            path = value[len(ISSUER) :]
            method = ENDPOINT_METHODS.get(key, "GET")
            if route_match(janua_app, method, path) == Match.NONE:
                missing[key] = path
    assert not missing, f"advertised but not served (404): {missing}"


def test_every_endpoint_answers_the_method_clients_use(doc, janua_app):
    wrong = {}
    for key in _endpoint_keys(doc):
        path = doc[key][len(ISSUER) :]
        method = ENDPOINT_METHODS[key]
        match = route_match(janua_app, method, path)
        if match != Match.FULL:
            wrong[key] = (method, path, match.name)
    assert not wrong, f"advertised endpoints that refuse the client's method: {wrong}"


def test_no_registration_endpoint(doc):
    """Janua has no RFC 7591 dynamic client registration, so none is advertised.

    `POST /api/v1/oauth/clients/register` is the internal service-to-service
    route (X-Internal-API-Key), not DCR. Clients use CIMD
    (`client_id_metadata_document_supported`) or an admin-registered client.
    Implementing DCR means a public POST route, the redirect policy from
    app/core/protected_resources.py, and updating this test.
    """
    assert "registration_endpoint" not in doc
    assert doc["client_id_metadata_document_supported"] is True


@pytest.mark.parametrize("path", WELL_KNOWN_METADATA_PATHS)
def test_both_well_known_paths_are_served_with_get(path, janua_app):
    assert route_match(janua_app, "GET", path) == Match.FULL


def test_both_well_known_handlers_return_the_same_document(doc):
    from app.main import oauth_authorization_server, openid_configuration

    assert openid_configuration() == doc
    assert oauth_authorization_server() == doc
