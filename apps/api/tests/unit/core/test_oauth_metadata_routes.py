"""The discovery documents advertise only routes the app serves.

`/.well-known/oauth-authorization-server` and `/.well-known/openid-configuration`
listed `registration_endpoint: …/api/v1/oauth/register` until 2026-11, but
Janua never had an RFC 7591 route there: it answered 404. An MCP client that
tries dynamic registration before CIMD (the Claude desktop app signing in to
the MAP's MCP server) failed before sign-in started. These tests read the app's
real route table, so the next endpoint that is advertised but not served (or
served under another method) fails here instead of in a client.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.oauth_metadata import authorization_server_metadata

ISSUER = "https://auth.madfam.io"

API_ROOT = Path(__file__).resolve().parents[3]

_ROUTE_TABLE_SCRIPT = """
import json
from app.main import app
table = {}
for route in app.routes:
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", None)
    if methods and path:
        table.setdefault(path, set()).update(methods)
print("ROUTE_TABLE=" + json.dumps({path: sorted(m) for path, m in table.items()}))
"""

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
def served() -> dict[str, set[str]]:
    """Path -> HTTP methods, from a fresh `import app.main` in a child process.

    Not this process's `app.main.app`: in the full unit suite under
    pytest-xdist, an earlier test leaves that object without the OAuth
    provider routes (seen in CI on 2026-11-05), which would fail this check
    for reasons unrelated to the metadata. A fresh interpreter builds the
    route table the way the server does. It inherits this process's
    environment (pytest.ini's `env`).
    """
    result = subprocess.run(
        [sys.executable, "-c", _ROUTE_TABLE_SCRIPT],
        cwd=API_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    line = next(
        line for line in reversed(result.stdout.splitlines()) if line.startswith("ROUTE_TABLE=")
    )
    table = {path: set(methods) for path, methods in json.loads(line.split("=", 1)[1]).items()}
    # Guard against a vacuous table: the well-known documents are always served.
    assert set(WELL_KNOWN_METADATA_PATHS) <= set(table)
    return table


@pytest.fixture
def doc(monkeypatch) -> dict:
    monkeypatch.setenv("JANUA_CUSTOM_DOMAIN", "auth.madfam.io")
    return authorization_server_metadata()


def _endpoint_keys(doc: dict) -> list[str]:
    return [key for key in doc if key.endswith("_endpoint") or key.endswith("_uri")]


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


def test_every_advertised_url_is_a_served_route(doc, served):
    """Every URL on the issuer, under any key, is a path in the route table."""
    missing = {}
    for key, value in doc.items():
        if isinstance(value, str) and value.startswith(ISSUER + "/"):
            path = value[len(ISSUER) :]
            if path not in served:
                missing[key] = path
    assert not missing, f"advertised but not served (404): {missing}"


def test_every_endpoint_answers_the_method_clients_use(doc, served):
    wrong = {}
    for key in _endpoint_keys(doc):
        path = doc[key][len(ISSUER) :]
        method = ENDPOINT_METHODS[key]
        if method not in served.get(path, set()):
            wrong[key] = (method, path, sorted(served.get(path, set())))
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
def test_both_well_known_paths_are_served_with_get(path, served):
    assert "GET" in served[path]


def test_both_well_known_handlers_return_the_same_document(doc):
    from app.main import oauth_authorization_server, openid_configuration

    assert openid_configuration() == doc
    assert oauth_authorization_server() == doc
