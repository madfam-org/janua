"""Client ID Metadata Documents (CIMD) for protected-resource clients.

draft-ietf-oauth-client-id-metadata-document: a client identifies itself with
an ``https`` URL as its ``client_id``; the URL serves a JSON document with the
client's metadata (name, redirect URIs, auth method). Janua fetches it at
``/oauth/authorize`` instead of keeping a registration row. Claude uses this:

- claude.ai, Desktop, mobile and Cowork send
  ``https://claude.ai/oauth/mcp-oauth-client-metadata`` (redirect
  ``https://claude.ai/api/mcp/auth_callback``);
- Claude Code sends ``https://claude.ai/oauth/claude-code-client-metadata``
  (loopback redirects ``http://localhost/callback`` and
  ``http://127.0.0.1/callback``, any port).

A URL client_id makes Janua issue an outbound request whose target the CLIENT
chose, so the fetch is fenced in on every side (server-side request forgery):

- only hosts on the requested resource's allowlist
  (``ClientPolicy.cimd_hosts``) are fetched — anything else is refused before
  any DNS lookup;
- ``https`` only, default port, no user info, query or fragment, a real path
  without dot segments;
- every address the host resolves to must be a public (global unicast)
  address, and the connection goes to the address that was checked (the TLS
  certificate is still verified against the host name), so DNS cannot be
  re-pointed between the check and the connection;
- redirects are not followed (any 3xx is a refusal), only a 200 with a JSON
  content type is read, at most ``MAX_DOCUMENT_BYTES``, within
  ``FETCH_TIMEOUT_SECONDS`` overall;
- valid documents are cached per process (bounded LRU) for their
  ``Cache-Control: max-age``, at most an hour; failures are never cached.

The document must name itself (``client_id`` equal to the URL, exactly), be a
public client (``token_endpoint_auth_method: none`` — it then needs PKCE), and
list its ``redirect_uris``; it must not carry a client secret.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import unquote, urlsplit

# Imported at module import on purpose: parts of the test suite swap
# sys.modules["httpx"] for a Mock later in a session, and a lazy import would
# pick that up.
import httpx
import structlog

logger = structlog.get_logger()

FETCH_TIMEOUT_SECONDS = 5.0
MAX_DOCUMENT_BYTES = 10 * 1024
CACHE_MAX_ENTRIES = 64
CACHE_DEFAULT_TTL_SECONDS = 300
CACHE_MAX_TTL_SECONDS = 3600
MAX_CLIENT_ID_LENGTH = 2048
MAX_REDIRECT_URIS = 20
USER_AGENT = "Janua-CIMD/1.0 (+https://docs.janua.dev)"


class ClientMetadataError(Exception):
    """The client_id URL cannot be used. ``error`` is the OAuth error code."""

    def __init__(self, description: str, *, error: str = "invalid_client") -> None:
        super().__init__(description)
        self.error = error
        self.description = description


@dataclass(frozen=True)
class ClientMetadata:
    """A validated Client ID Metadata Document."""

    client_id: str
    host: str
    client_name: Optional[str]
    redirect_uris: tuple[str, ...]
    grant_types: tuple[str, ...]
    response_types: tuple[str, ...]
    token_endpoint_auth_method: str


def is_url_client_id(client_id: object) -> bool:
    """Whether a client_id is a URL (a CIMD client) rather than a registered id.

    Registered clients are ``jnc_…`` identifiers (the schema refuses anything
    else), so any value with a scheme separator is a URL attempt — and an
    ``http://`` or otherwise malformed one is refused, not looked up.
    """
    return isinstance(client_id, str) and "://" in client_id


def client_id_host(client_id: str) -> str:
    """The validated host of a URL client_id (raises ClientMetadataError)."""
    if not isinstance(client_id, str) or not client_id or len(client_id) > MAX_CLIENT_ID_LENGTH:
        raise ClientMetadataError("client_id is not a usable URL")
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in client_id):
        raise ClientMetadataError("client_id contains whitespace or control characters")
    if "#" in client_id:
        raise ClientMetadataError("client_id must not contain a fragment")
    try:
        parts = urlsplit(client_id)
        port = parts.port
    except ValueError as exc:
        raise ClientMetadataError("client_id is not a valid URL") from exc
    if parts.scheme != "https" or not client_id.startswith("https://"):
        raise ClientMetadataError("client_id URL must use https")
    if parts.username is not None or parts.password is not None:
        raise ClientMetadataError("client_id URL must not contain user information")
    if port is not None:
        raise ClientMetadataError("client_id URL must use the default https port")
    if parts.query:
        raise ClientMetadataError("client_id URL must not contain a query")
    host = parts.hostname
    if not host:
        raise ClientMetadataError("client_id URL has no host")
    if parts.path in ("", "/"):
        raise ClientMetadataError("client_id URL must contain a path")
    for segment in parts.path.split("/"):
        if unquote(segment) in (".", ".."):
            raise ClientMetadataError("client_id URL must not contain dot segments")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ClientMetadataError("client_id URL must name a host, not an IP address")
    return host


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class _MetadataCache:
    """Bounded per-process LRU of validated documents with per-entry expiry."""

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[float, ClientMetadata]] = OrderedDict()

    def get(self, key: str) -> Optional[ClientMetadata]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: str, value: ClientMetadata, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self._entries[key] = (time.monotonic() + ttl_seconds, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


_cache = _MetadataCache(CACHE_MAX_ENTRIES)


def clear_cache() -> None:
    _cache.clear()


def _cache_ttl(cache_control: Optional[str]) -> int:
    """Seconds to keep a document, from its Cache-Control header (capped)."""
    if not cache_control:
        return CACHE_DEFAULT_TTL_SECONDS
    directives = [part.strip().lower() for part in cache_control.split(",")]
    if "no-store" in directives or "no-cache" in directives:
        return 0
    for directive in directives:
        if directive.startswith("max-age="):
            try:
                return max(
                    0, min(int(directive.split("=", 1)[1].strip('"')), CACHE_MAX_TTL_SECONDS)
                )
            except ValueError:
                return CACHE_DEFAULT_TTL_SECONDS
    return CACHE_DEFAULT_TTL_SECONDS


# ---------------------------------------------------------------------------
# Network (DNS and HTTP are module attributes so tests can substitute them)
# ---------------------------------------------------------------------------


async def _system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


#: host -> list of IP address strings
resolver: Callable[[str], Awaitable[list[str]]] = _system_resolver


def _default_transport() -> Optional[httpx.AsyncBaseTransport]:
    return None  # httpx's own transport; tests return an httpx.MockTransport


transport_factory: Callable[[], Optional[httpx.AsyncBaseTransport]] = _default_transport


def is_public_address(address: str) -> bool:
    """True only for a global unicast address (no private, loopback, link-local…)."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_global
        and not ip.is_private
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
    )


async def _public_address(host: str) -> str:
    """The address to connect to; every resolved address must be public."""
    try:
        addresses = await resolver(host)
    except (OSError, UnicodeError) as exc:
        raise ClientMetadataError("client_id host does not resolve") from exc
    addresses = [address for address in addresses if address]
    if not addresses:
        raise ClientMetadataError("client_id host does not resolve")
    if not all(is_public_address(address) for address in addresses):
        raise ClientMetadataError("client_id host resolves to a non-public address")
    ipv4 = [address for address in addresses if ":" not in address]
    return (ipv4 or addresses)[0]


async def _fetch_document(client_id: str, host: str, address: str) -> tuple[bytes, Optional[str]]:
    """GET the document from the checked address; (body, Cache-Control)."""
    path = urlsplit(client_id).path
    target = f"[{address}]" if ":" in address else address
    request_headers = {
        "Host": host,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(FETCH_TIMEOUT_SECONDS),
        follow_redirects=False,
        trust_env=False,
        transport=transport_factory(),
    ) as client:
        async with client.stream(
            "GET",
            f"https://{target}{path}",
            headers=request_headers,
            # TLS SNI and certificate verification use the host name, not the
            # address the connection is pinned to.
            extensions={"sni_hostname": host},
        ) as response:
            if 300 <= response.status_code < 400:
                raise ClientMetadataError(
                    "client metadata document redirects; redirects are not followed"
                )
            if response.status_code != 200:
                raise ClientMetadataError(
                    f"client metadata document answered HTTP {response.status_code}"
                )
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type != "application/json" and not (
                media_type.startswith("application/") and media_type.endswith("+json")
            ):
                raise ClientMetadataError("client metadata document is not JSON")
            declared = response.headers.get("content-length")
            if declared is not None:
                try:
                    declared_length = int(declared)
                except ValueError:
                    raise ClientMetadataError("client metadata document has a bad length") from None
                if declared_length > MAX_DOCUMENT_BYTES:
                    raise ClientMetadataError("client metadata document is too large")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_DOCUMENT_BYTES:
                    raise ClientMetadataError("client metadata document is too large")
            return bytes(body), response.headers.get("cache-control")


# ---------------------------------------------------------------------------
# Document validation
# ---------------------------------------------------------------------------


def _string_list(
    value: Any, field: str, *, required: bool, default: tuple[str, ...]
) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ClientMetadataError(f"client metadata document has no {field}")
        return default
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ClientMetadataError(f"client metadata {field} must be a list of strings")
    return tuple(value)


def parse_document(raw: bytes, client_id: str, host: str) -> ClientMetadata:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientMetadataError("client metadata document is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ClientMetadataError("client metadata document is not a JSON object")
    if document.get("client_id") != client_id:
        raise ClientMetadataError("client metadata document names a different client_id")
    if "client_secret" in document or "client_secret_expires_at" in document:
        raise ClientMetadataError("client metadata document must not carry a client secret")

    redirect_uris = _string_list(
        document.get("redirect_uris"), "redirect_uris", required=True, default=()
    )
    if not redirect_uris or len(redirect_uris) > MAX_REDIRECT_URIS:
        raise ClientMetadataError("client metadata document must list 1 to 20 redirect_uris")

    auth_method = document.get("token_endpoint_auth_method")
    if auth_method != "none":
        raise ClientMetadataError(
            "only public clients (token_endpoint_auth_method none, with PKCE) are accepted"
        )

    # RFC 7591 defaults: authorization_code / code.
    grant_types = _string_list(
        document.get("grant_types"), "grant_types", required=False, default=("authorization_code",)
    )
    if "authorization_code" not in grant_types:
        raise ClientMetadataError("client does not use the authorization_code grant")
    response_types = _string_list(
        document.get("response_types"), "response_types", required=False, default=("code",)
    )
    if "code" not in response_types:
        raise ClientMetadataError("client does not use response_type code")

    client_name = document.get("client_name")
    if client_name is not None and not isinstance(client_name, str):
        raise ClientMetadataError("client metadata client_name must be a string")
    client_name = (client_name or "").strip()[:120] or None

    return ClientMetadata(
        client_id=client_id,
        host=host,
        client_name=client_name,
        redirect_uris=redirect_uris,
        grant_types=grant_types,
        response_types=response_types,
        token_endpoint_auth_method=auth_method,
    )


async def resolve_client_metadata(
    client_id: str, *, allowed_hosts: frozenset[str]
) -> ClientMetadata:
    """The validated document for ``client_id``, fetched only from an allowed host.

    Raises ClientMetadataError (with ``error`` set to the OAuth error code)
    for anything Janua will not use: a malformed URL, a host off the
    allowlist, a non-public address, a redirect, a non-200, a non-JSON or
    oversized body, a timeout, or a document that fails validation.
    """
    host = client_id_host(client_id)
    if host not in allowed_hosts:
        logger.warning("oauth.cimd.rejected", reason="host_not_allowed", host=host)
        raise ClientMetadataError("this client is not allowed to request this resource")

    cached = _cache.get(client_id)
    if cached is not None:
        return cached

    async def _load() -> tuple[ClientMetadata, int]:
        address = await _public_address(host)
        raw, cache_control = await _fetch_document(client_id, host, address)
        return parse_document(raw, client_id, host), _cache_ttl(cache_control)

    try:
        metadata, ttl = await asyncio.wait_for(_load(), timeout=FETCH_TIMEOUT_SECONDS)
    except ClientMetadataError as exc:
        logger.warning("oauth.cimd.rejected", reason=exc.description, host=host)
        raise
    except asyncio.TimeoutError as exc:
        logger.warning("oauth.cimd.rejected", reason="timeout", host=host)
        raise ClientMetadataError("client metadata document did not arrive in time") from exc
    except httpx.HTTPError as exc:
        logger.warning("oauth.cimd.rejected", reason=type(exc).__name__, host=host)
        raise ClientMetadataError("client metadata document could not be fetched") from exc

    _cache.put(client_id, metadata, ttl)
    logger.info("oauth.cimd.fetched", host=host, cache_seconds=ttl)
    return metadata
