"""Client ID Metadata Documents: allowlist, SSRF guards, validation and cache.

A URL client_id makes Janua fetch a URL the client chose. These tests pin every
fence around that fetch: the allowlist is checked before any DNS lookup, only
https on the default port, only public addresses (and the connection goes to
the address that was checked), no redirects, 200 + JSON + at most 10 KB within
5 seconds, and only valid documents are cached.

The documents below are the two Claude publishes (fetched 2026-10-06).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.services import client_id_metadata as cimd
from app.services.client_id_metadata import (
    ClientMetadataError,
    _cache_ttl,
    _MetadataCache,
    client_id_host,
    is_public_address,
    is_url_client_id,
    parse_document,
    resolve_client_metadata,
)

CLAUDE = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_CODE = "https://claude.ai/oauth/claude-code-client-metadata"
CLAUDE_DOC = {
    "client_id": CLAUDE,
    "client_name": "Claude",
    "client_uri": "https://claude.ai",
    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
    "grant_types": [
        "authorization_code",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
    ],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
CLAUDE_CODE_DOC = {
    "client_id": CLAUDE_CODE,
    "client_name": "Claude Code",
    "client_uri": "https://claude.ai",
    "redirect_uris": ["http://localhost/callback", "http://127.0.0.1/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
ALLOWED = frozenset({"claude.ai"})
PUBLIC_IP = "104.18.32.47"


class _ChunkStream(httpx.AsyncByteStream):
    """A body with no Content-Length, delivered in chunks."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk


class FakeNet:
    """DNS answers and HTTP responses for the CIMD fetcher, with a request log."""

    def __init__(self):
        self.addresses = {"claude.ai": [PUBLIC_IP]}
        self.lookups: list[str] = []
        self.requests: list[httpx.Request] = []
        self.responses: dict[str, object] = {
            "/oauth/mcp-oauth-client-metadata": self.json(CLAUDE_DOC),
            "/oauth/claude-code-client-metadata": self.json(CLAUDE_CODE_DOC),
        }

    @staticmethod
    def json(document, *, status=200, headers=None):
        merged = {"content-type": "application/json", "cache-control": "public, max-age=300"}
        merged.update(headers or {})
        return lambda: httpx.Response(status, headers=merged, content=json.dumps(document).encode())

    async def resolve(self, host):
        self.lookups.append(host)
        answer = self.addresses.get(host)
        if isinstance(answer, BaseException):
            raise answer
        if answer is None:
            raise OSError("no such host")
        return list(answer)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        make = self.responses.get(request.url.path)
        if make is None:
            return httpx.Response(404)
        if isinstance(make, BaseException):
            raise make
        return make()


@pytest.fixture
def net(monkeypatch):
    fake = FakeNet()
    monkeypatch.setattr(cimd, "resolver", fake.resolve)
    monkeypatch.setattr(cimd, "transport_factory", lambda: httpx.MockTransport(fake.handler))
    cimd.clear_cache()
    yield fake
    cimd.clear_cache()


class TestClientIdUrl:
    def test_url_client_ids_are_recognized(self):
        assert is_url_client_id(CLAUDE)
        assert is_url_client_id("http://claude.ai/x")
        assert not is_url_client_id("jnc_AbCdEf")
        assert not is_url_client_id(None)

    @pytest.mark.parametrize("client_id", [CLAUDE, CLAUDE_CODE])
    def test_claude_urls_are_valid(self, client_id):
        assert client_id_host(client_id) == "claude.ai"

    @pytest.mark.parametrize(
        "client_id",
        [
            "http://claude.ai/oauth/mcp-oauth-client-metadata",
            "HTTPS://claude.ai/oauth/mcp-oauth-client-metadata",
            "https://user@claude.ai/oauth/mcp-oauth-client-metadata",
            "https://claude.ai:8443/oauth/mcp-oauth-client-metadata",
            "https://claude.ai:443/oauth/mcp-oauth-client-metadata",
            "https://claude.ai/oauth/mcp-oauth-client-metadata?x=1",
            "https://claude.ai/oauth/mcp-oauth-client-metadata#x",
            "https://claude.ai",
            "https://claude.ai/",
            "https://claude.ai/oauth/../metadata",
            "https://claude.ai/oauth/./metadata",
            "https://claude.ai/oauth/%2e%2e/metadata",
            "https://104.18.32.47/oauth/metadata",
            "https://[2606:4700::1]/oauth/metadata",
            "https://claude.ai/oauth/meta data",
            "https://claude.ai/" + "a" * 2100,
        ],
    )
    def test_malformed_urls_are_refused(self, client_id):
        with pytest.raises(ClientMetadataError):
            client_id_host(client_id)


class TestPublicAddresses:
    @pytest.mark.parametrize(
        "address",
        [
            "10.0.0.7",
            "127.0.0.1",
            "169.254.169.254",
            "192.168.1.10",
            "172.16.5.4",
            "100.64.0.1",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fe80::1",
            "fc00::1",
            "::ffff:10.0.0.7",
            "not-an-ip",
        ],
    )
    def test_special_use_addresses_are_not_public(self, address):
        assert not is_public_address(address)

    @pytest.mark.parametrize("address", [PUBLIC_IP, "2606:4700::6812:202f"])
    def test_global_unicast_is_public(self, address):
        assert is_public_address(address)


class TestFetch:
    async def test_claude_document_is_fetched_from_the_checked_address(self, net):
        metadata = await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)

        assert metadata.client_id == CLAUDE
        assert metadata.host == "claude.ai"
        assert metadata.client_name == "Claude"
        assert metadata.redirect_uris == ("https://claude.ai/api/mcp/auth_callback",)
        assert metadata.token_endpoint_auth_method == "none"
        (request,) = net.requests
        # Pinned to the address that passed the check; TLS still names the host.
        assert str(request.url) == f"https://{PUBLIC_IP}/oauth/mcp-oauth-client-metadata"
        assert request.headers["host"] == "claude.ai"
        assert request.extensions["sni_hostname"] == "claude.ai"
        assert request.method == "GET"

    async def test_claude_code_document(self, net):
        metadata = await resolve_client_metadata(CLAUDE_CODE, allowed_hosts=ALLOWED)
        assert metadata.redirect_uris == (
            "http://localhost/callback",
            "http://127.0.0.1/callback",
        )

    async def test_ipv6_only_host_connects_to_the_bracketed_address(self, net):
        net.addresses["claude.ai"] = ["2606:4700::6812:202f"]
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert str(net.requests[0].url).startswith("https://[2606:4700::6812:202f]/")

    async def test_valid_documents_are_cached(self, net):
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert len(net.requests) == 1

    async def test_no_store_is_not_cached(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(
            CLAUDE_DOC, headers={"cache-control": "no-store"}
        )
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert len(net.requests) == 2

    async def test_failures_are_never_cached(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json({}, status=500)
        for _ in range(2):
            with pytest.raises(ClientMetadataError):
                await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert len(net.requests) == 2
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(CLAUDE_DOC)
        assert (await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)).client_id == CLAUDE

    async def test_an_allowed_host_is_cached_per_url_but_rechecked_per_resource(self, net):
        await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(CLAUDE, allowed_hosts=frozenset({"other.example"}))


class TestSsrfRefusals:
    async def test_host_off_the_allowlist_is_refused_before_any_lookup(self, net):
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(
                "https://evil.example/oauth/client.json", allowed_hosts=ALLOWED
            )
        assert excinfo.value.error == "invalid_client"
        assert net.lookups == [] and net.requests == []

    async def test_subdomain_of_an_allowed_host_is_not_allowed(self, net):
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(
                "https://evil.claude.ai/oauth/client.json", allowed_hosts=ALLOWED
            )
        assert net.lookups == []

    async def test_non_https_is_refused_before_any_lookup(self, net):
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(
                "http://claude.ai/oauth/mcp-oauth-client-metadata", allowed_hosts=ALLOWED
            )
        assert net.lookups == [] and net.requests == []

    @pytest.mark.parametrize(
        "addresses",
        [["10.0.0.7"], ["127.0.0.1"], ["169.254.169.254"], [PUBLIC_IP, "192.168.1.1"], ["::1"]],
    )
    async def test_private_addresses_are_refused_without_connecting(self, net, addresses):
        net.addresses["claude.ai"] = addresses
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert "non-public" in excinfo.value.description
        assert net.requests == []

    async def test_unresolvable_host(self, net):
        net.addresses["claude.ai"] = OSError("NXDOMAIN")
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)

    @pytest.mark.parametrize("status", [301, 302, 307, 308])
    async def test_redirects_are_not_followed(self, net, status):
        net.responses["/oauth/mcp-oauth-client-metadata"] = lambda: httpx.Response(
            status, headers={"location": "http://169.254.169.254/latest/meta-data"}
        )
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert "redirect" in excinfo.value.description
        assert len(net.requests) == 1

    async def test_non_200_is_refused(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(CLAUDE_DOC, status=203)
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)

    async def test_oversized_declared_body_is_refused(self, net):
        big = dict(CLAUDE_DOC, padding="x" * (11 * 1024))
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(big)
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert "too large" in excinfo.value.description

    async def test_oversized_streamed_body_is_cut_off(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = lambda: httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=_ChunkStream([b"{" + b" " * 6000, b" " * 6000, b"}"]),
        )
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert "too large" in excinfo.value.description

    @pytest.mark.parametrize("content_type", ["text/html", "text/plain", "application/xml", ""])
    async def test_non_json_content_type_is_refused(self, net, content_type):
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(
            CLAUDE_DOC, headers={"content-type": content_type}
        )
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)

    async def test_json_with_parameters_is_accepted(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = net.json(
            CLAUDE_DOC, headers={"content-type": "application/json; charset=utf-8"}
        )
        assert (await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)).client_id == CLAUDE

    async def test_connect_timeout_is_a_refusal(self, net):
        net.responses["/oauth/mcp-oauth-client-metadata"] = httpx.ConnectTimeout("slow")
        with pytest.raises(ClientMetadataError):
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)

    async def test_overall_deadline(self, net, monkeypatch):
        monkeypatch.setattr(cimd, "FETCH_TIMEOUT_SECONDS", 0.05)

        async def slow_resolve(host):
            await asyncio.sleep(1)
            return [PUBLIC_IP]

        monkeypatch.setattr(cimd, "resolver", slow_resolve)
        with pytest.raises(ClientMetadataError) as excinfo:
            await resolve_client_metadata(CLAUDE, allowed_hosts=ALLOWED)
        assert "in time" in excinfo.value.description


class TestDocumentValidation:
    def _parse(self, document, client_id=CLAUDE):
        return parse_document(json.dumps(document).encode(), client_id, "claude.ai")

    def test_claude_documents_parse(self):
        assert self._parse(CLAUDE_DOC).client_name == "Claude"
        assert self._parse(CLAUDE_CODE_DOC, CLAUDE_CODE).grant_types == (
            "authorization_code",
            "refresh_token",
        )

    @pytest.mark.parametrize(
        "change",
        [
            {"client_id": CLAUDE_CODE},
            {"client_id": CLAUDE + "/"},
            {"client_secret": "x"},
            {"client_secret_expires_at": 0},
            {"token_endpoint_auth_method": "client_secret_basic"},
            {"token_endpoint_auth_method": "private_key_jwt"},
            {"redirect_uris": []},
            {"redirect_uris": "https://claude.ai/api/mcp/auth_callback"},
            {"redirect_uris": [1]},
            {"redirect_uris": ["https://claude.ai/cb"] * 21},
            {"grant_types": ["refresh_token"]},
            {"response_types": ["token"]},
            {"client_name": 7},
        ],
    )
    def test_invalid_documents_are_refused(self, change):
        with pytest.raises(ClientMetadataError):
            self._parse(dict(CLAUDE_DOC, **change))

    def test_missing_auth_method_is_refused(self):
        document = dict(CLAUDE_DOC)
        del document["token_endpoint_auth_method"]
        with pytest.raises(ClientMetadataError):
            self._parse(document)

    @pytest.mark.parametrize("raw", [b"not json", b"[]", b"\xff\xfe", b'"string"'])
    def test_not_a_json_object(self, raw):
        with pytest.raises(ClientMetadataError):
            parse_document(raw, CLAUDE, "claude.ai")

    def test_defaults_follow_rfc_7591(self):
        document = {
            k: v for k, v in CLAUDE_DOC.items() if k not in ("grant_types", "response_types")
        }
        metadata = self._parse(document)
        assert metadata.grant_types == ("authorization_code",)
        assert metadata.response_types == ("code",)


class TestCache:
    def test_bounded_lru(self):
        cache = _MetadataCache(max_entries=64)
        metadata = TestDocumentValidation()._parse(CLAUDE_DOC)
        for i in range(70):
            cache.put(f"https://claude.ai/c/{i}", metadata, 300)
        assert len(cache) == 64
        assert cache.get("https://claude.ai/c/0") is None
        assert cache.get("https://claude.ai/c/69") is metadata

    def test_entries_expire(self, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr(cimd.time, "monotonic", lambda: clock[0])
        cache = _MetadataCache(max_entries=4)
        metadata = TestDocumentValidation()._parse(CLAUDE_DOC)
        cache.put("k", metadata, 300)
        clock[0] += 299
        assert cache.get("k") is metadata
        clock[0] += 2
        assert cache.get("k") is None

    @pytest.mark.parametrize(
        "header,ttl",
        [
            (None, 300),
            ("public, max-age=300", 300),
            ("max-age=60", 60),
            ("max-age=999999", 3600),
            ("no-store", 0),
            ("no-cache, max-age=60", 0),
            ("max-age=abc", 300),
            ("private", 300),
        ],
    )
    def test_ttl_from_cache_control(self, header, ttl):
        assert _cache_ttl(header) == ttl
