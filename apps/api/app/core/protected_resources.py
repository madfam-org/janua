"""Protected resources: the closed list of APIs Janua mints audience-bound tokens for.

A *protected resource* is a resource server (today: one MCP server) that a
third-party client may ask Janua for an access token for, by naming it in the
RFC 8707 ``resource`` parameter on ``/oauth/authorize`` and ``/oauth/token``.
A token issued for a resource carries ``aud`` = the resource URI exactly, the
scopes the person consented to (requested ∩ the resource's scopes), and a short
lifetime. Nothing else Janua issues changes: a request without ``resource``
keeps the behavior it always had.

Each entry pins:

- ``resource``: the canonical URI (lowercase scheme and host, no default
  port, no fragment, no trailing slash). It is the ``aud`` of every token
  minted for it, byte for byte, and must equal the ``resource`` the MCP server
  publishes in its RFC 9728 protected-resource metadata.
- ``display_name`` and the scope descriptions: Spanish, shown on the consent
  screen. Write them for the person who will read them, not for engineers.
- ``client_policy``: WHICH clients may ask for the resource. A client
  identified by a Client ID Metadata Document (an ``https`` client_id) is
  accepted only when its host is in ``cimd_hosts`` AND the URL is one of the
  pinned ``cimd_client_ids``; Janua fetches nothing else, and what it fetches
  is the pinned URL from this file, never a string taken from the request.
  Every client, CIMD or registered in Janua's database, must redirect to one
  of ``redirect_uris`` exactly, or to a loopback address on any port when
  ``allow_loopback_redirects`` is set. A database client must additionally
  have *every* registered redirect URI inside that policy.
- token lifetimes: the access token is short (at most 15 minutes, enforced
  below). Refresh tokens rotate on every use; ``refresh_token_idle_seconds``
  ends a connection nobody used, ``refresh_token_max_lifetime_seconds`` ends
  every connection, used or not, so a person re-consents periodically.

The registry is code, not configuration, on purpose: adding a resource, a
scope, a CIMD host or a redirect URI widens who can obtain a token for whose
data, and that is a reviewed change, never a runtime toggle. Anything not
listed here is refused with ``invalid_target``.

See ``docs/reference/PROTECTED_RESOURCES_AND_MCP_CLIENTS.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional
from urllib.parse import urlsplit

#: The OIDC scope a client adds to ask for a refresh token. It is not a
#: resource scope: it never appears in an access token's ``scope`` claim.
OFFLINE_ACCESS_SCOPE = "offline_access"

#: Loopback hosts whose redirect URIs match with the port ignored. RFC 8252
#: §7.3 requires it for the IP literals; ``localhost`` is accepted for Claude
#: Code, whose Client ID Metadata Document declares it (RFC 8252 §8.3
#: discourages it, but a client that sends it would otherwise never connect).
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

#: Upper bound on a resource access token's lifetime (15 minutes).
MAX_ACCESS_TOKEN_TTL_SECONDS = 15 * 60

_SCOPE_NAME = re.compile(r"^[a-z][a-z0-9._-]*:[a-z][a-z0-9._-]*$")
_DEFAULT_PORTS = {"https": 443, "http": 80}


class InvalidResourceIndicator(ValueError):
    """A ``resource`` value that is not an absolute URI Janua can compare."""


@dataclass(frozen=True)
class ResourceScope:
    """One scope a protected resource accepts, with its consent-screen text."""

    name: str
    description: str  # Spanish, plain words


@dataclass(frozen=True)
class ClientPolicy:
    """Which clients may obtain tokens for a resource (see the module docstring)."""

    cimd_hosts: frozenset[str]
    cimd_client_ids: frozenset[str]
    redirect_uris: frozenset[str]
    allow_loopback_redirects: bool

    def pinned_client_id(self, client_id: object) -> Optional[str]:
        """The pinned CIMD URL equal to ``client_id`` (from this policy), or None."""
        for pinned in sorted(self.cimd_client_ids):
            if pinned == client_id:
                return pinned
        return None

    def allows_redirect(self, redirect_uri: str) -> bool:
        """Whether a redirect URI is inside this policy (exact, or loopback on any port)."""
        if redirect_uri in self.redirect_uris:
            return True
        return self.allow_loopback_redirects and is_loopback_redirect(redirect_uri)


@dataclass(frozen=True)
class ProtectedResource:
    resource: str
    display_name: str  # Spanish
    scopes: tuple[ResourceScope, ...]
    client_policy: ClientPolicy
    access_token_ttl_seconds: int = MAX_ACCESS_TOKEN_TTL_SECONDS
    refresh_token_idle_seconds: int = 7 * 24 * 3600
    refresh_token_max_lifetime_seconds: int = 30 * 24 * 3600
    #: Which hosted-login method to offer first when the person has no Janua
    #: session (``magic_link`` / ``password``). None keeps the deployment default.
    preferred_login_method: Optional[str] = None

    @property
    def scope_names(self) -> frozenset[str]:
        return frozenset(scope.name for scope in self.scopes)

    def scope(self, name: str) -> Optional[ResourceScope]:
        for scope in self.scopes:
            if scope.name == name:
                return scope
        return None


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: Claude's hosted apps (claude.ai on the web, Desktop, mobile, Cowork) send
#: this redirect URI; Claude Code uses a loopback redirect instead.
CLAUDE_HOSTED_CALLBACK = "https://claude.ai/api/mcp/auth_callback"

#: The Client ID Metadata Documents Anthropic publishes (checked 2026-10-06):
#: the hosted apps' (redirect: CLAUDE_HOSTED_CALLBACK) and Claude Code's
#: (redirects: http://localhost/callback, http://127.0.0.1/callback).
CLAUDE_HOSTED_CLIENT_ID = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_CODE_CLIENT_ID = "https://claude.ai/oauth/claude-code-client-metadata"

#: The MAP (operations app) of Crea Tu Mundo, as an MCP server. Owner decision
#: 2026-10: Claude and Claude Code only, read-only scopes, no clinical data.
MAP_CREA_TU_MUNDO = ProtectedResource(
    resource="https://map.creatumundo.mx/api/mcp",
    display_name="MAP de Crea Tu Mundo",
    scopes=(
        ResourceScope(
            name="map.ops:read",
            description="Consultar la operación del MAP, sin nombres ni datos clínicos",
        ),
        ResourceScope(
            name="map.cobro:read",
            description="Consultar la cobranza del MAP por clave de familia",
        ),
    ),
    client_policy=ClientPolicy(
        cimd_hosts=frozenset({"claude.ai"}),
        cimd_client_ids=frozenset({CLAUDE_HOSTED_CLIENT_ID, CLAUDE_CODE_CLIENT_ID}),
        redirect_uris=frozenset({CLAUDE_HOSTED_CALLBACK}),
        allow_loopback_redirects=True,
    ),
    access_token_ttl_seconds=15 * 60,
    # CTM staff sign in by emailed link; most have no Janua password.
    preferred_login_method="magic_link",
)

_REGISTRY: dict[str, ProtectedResource] = {
    resource.resource: resource for resource in (MAP_CREA_TU_MUNDO,)
}

PROTECTED_RESOURCES: Mapping[str, ProtectedResource] = MappingProxyType(_REGISTRY)


# ---------------------------------------------------------------------------
# Resource indicators (RFC 8707)
# ---------------------------------------------------------------------------


def canonical_resource(value: object) -> str:
    """The comparison form of a ``resource`` value, or InvalidResourceIndicator.

    RFC 8707 §2: the value is an absolute URI without a fragment. The MCP
    authorization spec asks servers to accept uppercase scheme and host, so
    both are lowercased and a default port is dropped; the path and query are
    compared exactly (a trailing slash is a different resource).
    """
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise InvalidResourceIndicator("resource must be a non-empty absolute URI")
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise InvalidResourceIndicator("resource contains whitespace or control characters")
    if "#" in value:
        raise InvalidResourceIndicator("resource must not contain a fragment")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise InvalidResourceIndicator("resource is not a valid URI") from exc
    scheme = parts.scheme.lower()
    host = parts.hostname
    if not scheme or not parts.netloc or not host:
        raise InvalidResourceIndicator("resource must be an absolute URI")
    if parts.username is not None or parts.password is not None:
        raise InvalidResourceIndicator("resource must not contain user information")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{netloc}:{port}"
    canonical = f"{scheme}://{netloc}{parts.path}"
    if parts.query:
        canonical = f"{canonical}?{parts.query}"
    return canonical


def lookup_resource(value: object) -> Optional[ProtectedResource]:
    """The registered resource a ``resource`` value names, or None if unknown.

    Raises InvalidResourceIndicator when the value is malformed.
    """
    return PROTECTED_RESOURCES.get(canonical_resource(value))


def all_resource_scopes() -> list[str]:
    """Every resource scope, for ``scopes_supported`` in discovery."""
    names: list[str] = []
    for resource in PROTECTED_RESOURCES.values():
        for scope in resource.scopes:
            if scope.name not in names:
                names.append(scope.name)
    return names


def all_cimd_hosts() -> frozenset[str]:
    """Every host any resource accepts Client ID Metadata Documents from."""
    hosts: set[str] = set()
    for resource in PROTECTED_RESOURCES.values():
        hosts.update(resource.client_policy.cimd_hosts)
    return frozenset(hosts)


def all_cimd_client_ids() -> frozenset[str]:
    """Every pinned Client ID Metadata Document URL, across resources."""
    client_ids: set[str] = set()
    for resource in PROTECTED_RESOURCES.values():
        client_ids.update(resource.client_policy.cimd_client_ids)
    return frozenset(client_ids)


def protected_resource_redirect_origins() -> list[str]:
    """Origins of the exact redirect URIs in every policy (for CSP form-action).

    The consent form posts to Janua, which answers with a 302 to the client's
    redirect URI; browsers apply ``form-action`` to that redirect, so a
    callback origin missing from the list makes "Permitir" silently do nothing.
    """
    origins: list[str] = []
    for resource in PROTECTED_RESOURCES.values():
        for uri in sorted(resource.client_policy.redirect_uris):
            parts = urlsplit(uri)
            origin = f"{parts.scheme}://{parts.netloc}"
            if origin not in origins:
                origins.append(origin)
    return origins


# ---------------------------------------------------------------------------
# Redirect URIs
# ---------------------------------------------------------------------------


def _loopback_parts(uri: str) -> Optional[tuple[str, str, str]]:
    """(host, path, query) of an ``http`` loopback redirect URI, else None."""
    if not isinstance(uri, str) or "#" in uri:
        return None
    try:
        parts = urlsplit(uri)
        parts.port  # noqa: B018 — validates the port; raises ValueError when bad
    except ValueError:
        return None
    if parts.scheme != "http":
        return None
    if parts.username is not None or parts.password is not None:
        return None
    host = parts.hostname
    if host not in LOOPBACK_HOSTS:
        return None
    return host, parts.path or "/", parts.query


def is_loopback_redirect(uri: str) -> bool:
    return _loopback_parts(uri) is not None


def redirect_uri_matches(requested: str, registered: Iterable[str]) -> bool:
    """Exact match, except that a loopback URI matches with any port.

    RFC 8252 §7.3: a native app binds an ephemeral port, so the authorization
    server must ignore the port of a loopback redirect URI. Scheme, host, path
    and query still have to match.
    """
    if not isinstance(requested, str) or not requested:
        return False
    registered_list = [uri for uri in registered if isinstance(uri, str)]
    if requested in registered_list:
        return True
    requested_loopback = _loopback_parts(requested)
    if requested_loopback is None:
        return False
    return any(_loopback_parts(uri) == requested_loopback for uri in registered_list)


def redirect_display_host(redirect_uri: str) -> str:
    """The host a person is sent back to, for the consent screen."""
    try:
        return urlsplit(redirect_uri).hostname or redirect_uri
    except ValueError:
        return redirect_uri


# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------


def granted_scopes(
    resource: ProtectedResource, requested: Optional[Iterable[str]]
) -> tuple[list[str], bool]:
    """(resource scopes granted, whether ``offline_access`` was requested).

    ``requested`` None means the client sent no ``scope``: every resource scope
    is requested, and no refresh token. Otherwise the grant is the intersection
    with the resource's scopes, in registry order; scopes the resource does not
    define are dropped (RFC 6749 §3.3 lets the server narrow the request and the
    response reports the granted scope).
    """
    if requested is None:
        return [scope.name for scope in resource.scopes], False
    wanted = set(requested)
    granted = [scope.name for scope in resource.scopes if scope.name in wanted]
    return granted, OFFLINE_ACCESS_SCOPE in wanted


# ---------------------------------------------------------------------------
# Import-time invariants: a registry entry that breaks one fails loudly at
# startup and in CI, never at a person's consent screen. Plain exceptions, not
# `assert`, so `python -O` cannot skip them.
# ---------------------------------------------------------------------------


def _require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(f"protected resource registry: {message}")


def check_registry(registry: Mapping[str, ProtectedResource]) -> None:
    for key, resource in registry.items():
        uri = resource.resource
        _require(key == uri, f"key {key!r} differs from its resource {uri!r}")
        _require(canonical_resource(uri) == uri, f"{uri!r} is not in canonical form")
        _require(uri.startswith("https://"), f"{uri!r} is not https")
        _require(not uri.endswith("/"), f"{uri!r} ends with a slash")
        _require(
            0 < resource.access_token_ttl_seconds <= MAX_ACCESS_TOKEN_TTL_SECONDS,
            f"{uri!r} access tokens must live at most 15 minutes",
        )
        _require(
            0 < resource.refresh_token_idle_seconds <= resource.refresh_token_max_lifetime_seconds,
            f"{uri!r} refresh idle lifetime exceeds its maximum lifetime",
        )
        _require(resource.display_name.strip(), f"{uri!r} has no display name")
        names = [scope.name for scope in resource.scopes]
        _require(names, f"{uri!r} has no scopes")
        _require(len(names) == len(set(names)), f"{uri!r} repeats a scope")
        for scope in resource.scopes:
            _require(_SCOPE_NAME.match(scope.name), f"scope {scope.name!r} is not namespaced")
            _require(scope.description.strip(), f"scope {scope.name!r} has no description")
        policy = resource.client_policy
        for host in policy.cimd_hosts:
            _require(
                host == host.lower() and host.strip() and not set("/:@?#") & set(host),
                f"CIMD host {host!r} must be a bare lowercase host name",
            )
        for client_id in policy.cimd_client_ids:
            parts = urlsplit(client_id)
            _require(
                client_id.startswith("https://")
                and parts.hostname in policy.cimd_hosts
                and parts.port is None
                and parts.path not in ("", "/")
                and not parts.query
                and "#" not in client_id
                and parts.username is None,
                f"CIMD client_id {client_id!r} must be an https URL with a path on a CIMD host",
            )
        for redirect in policy.redirect_uris:
            parts = urlsplit(redirect)
            _require(
                parts.scheme == "https" and parts.hostname and "#" not in redirect,
                f"redirect URI {redirect!r} must be an absolute https URI",
            )


check_registry(_REGISTRY)
