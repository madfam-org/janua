"""The protected-resource registry, resource indicators, loopback redirects and
the authorization-server metadata (RFC 8707, RFC 8252 §7.3, RFC 8414).

Owner decision (2026-10): the center's Director connects the MAP to Claude as a
custom connector, and Claude Code must work too. The registry is the closed
list of what Janua mints audience-bound tokens for; these tests pin the MAP
entry and the rules every entry must keep.
"""

from __future__ import annotations

import dataclasses

import fakeredis
import pytest

from app.core.oauth_metadata import authorization_server_metadata, oauth_issuer
from app.core.protected_resources import (
    CLAUDE_HOSTED_CALLBACK,
    MAP_CREA_TU_MUNDO,
    MAX_ACCESS_TOKEN_TTL_SECONDS,
    OFFLINE_ACCESS_SCOPE,
    PROTECTED_RESOURCES,
    InvalidResourceIndicator,
    canonical_resource,
    check_registry,
    granted_scopes,
    is_loopback_redirect,
    lookup_resource,
    protected_resource_redirect_origins,
    redirect_uri_matches,
)
from app.core.redis_circuit_breaker import ResilientRedisClient

MAP = "https://map.creatumundo.mx/api/mcp"


class TestTheMapEntry:
    def test_registered_under_its_exact_uri(self):
        assert MAP in PROTECTED_RESOURCES
        assert PROTECTED_RESOURCES[MAP] is MAP_CREA_TU_MUNDO
        assert MAP_CREA_TU_MUNDO.resource == MAP

    def test_spanish_name_and_scopes(self):
        assert MAP_CREA_TU_MUNDO.display_name == "MAP de Crea Tu Mundo"
        assert [(s.name, s.description) for s in MAP_CREA_TU_MUNDO.scopes] == [
            ("map.ops:read", "Consultar la operación del MAP, sin nombres ni datos clínicos"),
            ("map.cobro:read", "Consultar la cobranza del MAP por clave de familia"),
        ]

    def test_access_tokens_live_at_most_15_minutes(self):
        assert 0 < MAP_CREA_TU_MUNDO.access_token_ttl_seconds <= 15 * 60
        assert MAX_ACCESS_TOKEN_TTL_SECONDS == 15 * 60

    def test_client_policy_is_claude_and_claude_code_only(self):
        policy = MAP_CREA_TU_MUNDO.client_policy
        assert policy.cimd_hosts == frozenset({"claude.ai"})
        assert policy.redirect_uris == frozenset({"https://claude.ai/api/mcp/auth_callback"})
        assert policy.allow_loopback_redirects is True
        assert CLAUDE_HOSTED_CALLBACK == "https://claude.ai/api/mcp/auth_callback"

    def test_policy_allows_claude_callback_and_loopback_only(self):
        policy = MAP_CREA_TU_MUNDO.client_policy
        assert policy.allows_redirect("https://claude.ai/api/mcp/auth_callback")
        assert policy.allows_redirect("http://localhost:3118/callback")
        assert policy.allows_redirect("http://127.0.0.1:61000/callback")
        assert policy.allows_redirect("http://[::1]:61000/callback")
        assert not policy.allows_redirect("https://claude.ai/api/mcp/auth_callback/")
        assert not policy.allows_redirect("https://claude.ai.evil.example/api/mcp/auth_callback")
        assert not policy.allows_redirect("https://app.example.test/callback")
        assert not policy.allows_redirect("https://localhost:3118/callback")

    def test_registry_is_read_only(self):
        with pytest.raises(TypeError):
            PROTECTED_RESOURCES["https://other.example/mcp"] = MAP_CREA_TU_MUNDO  # type: ignore[index]

    def test_csp_origins_come_from_the_policies(self):
        assert protected_resource_redirect_origins() == ["https://claude.ai"]


class TestRegistryInvariants:
    def _registry_with(self, **changes):
        entry = dataclasses.replace(MAP_CREA_TU_MUNDO, **changes)
        return {entry.resource: entry}

    def test_the_shipped_registry_passes(self):
        check_registry(PROTECTED_RESOURCES)

    @pytest.mark.parametrize(
        "changes",
        [
            {"access_token_ttl_seconds": 16 * 60},
            {"access_token_ttl_seconds": 0},
            {"resource": "https://MAP.creatumundo.mx/api/mcp"},
            {"resource": "https://map.creatumundo.mx/api/mcp/"},
            {"resource": "http://map.creatumundo.mx/api/mcp"},
            {"display_name": " "},
            {"scopes": ()},
            {"refresh_token_idle_seconds": 40 * 86400},
        ],
    )
    def test_a_bad_entry_fails_loudly(self, changes):
        with pytest.raises(RuntimeError):
            check_registry(self._registry_with(**changes))

    def test_a_scope_must_be_namespaced(self):
        bad_scope = dataclasses.replace(MAP_CREA_TU_MUNDO.scopes[0], name="offline_access")
        with pytest.raises(RuntimeError):
            check_registry(self._registry_with(scopes=(bad_scope,)))

    def test_a_cimd_host_is_a_bare_host_name(self):
        policy = dataclasses.replace(
            MAP_CREA_TU_MUNDO.client_policy, cimd_hosts=frozenset({"https://claude.ai"})
        )
        with pytest.raises(RuntimeError):
            check_registry(self._registry_with(client_policy=policy))

    def test_a_policy_redirect_must_be_https(self):
        policy = dataclasses.replace(
            MAP_CREA_TU_MUNDO.client_policy,
            redirect_uris=frozenset({"http://claude.ai/api/mcp/auth_callback"}),
        )
        with pytest.raises(RuntimeError):
            check_registry(self._registry_with(client_policy=policy))


class TestResourceIndicators:
    @pytest.mark.parametrize(
        "value",
        [
            MAP,
            "HTTPS://MAP.CREATUMUNDO.MX/api/mcp",
            "https://map.creatumundo.mx:443/api/mcp",
        ],
    )
    def test_equivalent_spellings_name_the_map(self, value):
        assert canonical_resource(value) == MAP
        assert lookup_resource(value) is MAP_CREA_TU_MUNDO

    @pytest.mark.parametrize(
        "value",
        [
            "https://map.creatumundo.mx/api/mcp/",
            "https://map.creatumundo.mx/api/MCP",
            "https://map.creatumundo.mx/api/mcp?x=1",
            "https://map.creatumundo.mx:8443/api/mcp",
            "https://evil.example/api/mcp",
        ],
    )
    def test_anything_else_is_unknown(self, value):
        assert lookup_resource(value) is None

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "map.creatumundo.mx/api/mcp",
            "/api/mcp",
            "https://map.creatumundo.mx/api/mcp#tools",
            "https://map.creatumundo.mx/api/mcp#",
            "https://user:pw@map.creatumundo.mx/api/mcp",
            "https://map.creatumundo.mx/api/mcp\n",
            "https:///api/mcp",
            "https://map.creatumundo.mx:99999/api/mcp",
            None,
            123,
        ],
    )
    def test_malformed_values_raise(self, value):
        with pytest.raises(InvalidResourceIndicator):
            canonical_resource(value)


class TestLoopbackRedirects:
    """RFC 8252 §7.3, plus `localhost` because Claude Code declares it."""

    @pytest.mark.parametrize(
        "registered,requested",
        [
            ("http://127.0.0.1/callback", "http://127.0.0.1:61234/callback"),
            ("http://[::1]/callback", "http://[::1]:61234/callback"),
            ("http://localhost/callback", "http://localhost:3118/callback"),
            ("http://localhost:6274/callback", "http://localhost:9999/callback"),
            ("http://localhost/callback", "http://localhost/callback"),
        ],
    )
    def test_port_is_ignored(self, registered, requested):
        assert redirect_uri_matches(requested, [registered])

    @pytest.mark.parametrize(
        "registered,requested",
        [
            ("http://localhost/callback", "http://localhost:3118/other"),
            ("http://localhost/callback", "http://127.0.0.1:3118/callback"),
            ("http://127.0.0.1/callback", "https://127.0.0.1:3118/callback"),
            ("http://localhost/callback", "http://localhost:3118/callback?x=1"),
            ("http://localhost/callback", "http://localhost:3118/callback#frag"),
            ("http://localhost/callback", "http://user@localhost:3118/callback"),
            ("http://localhost/callback", "http://localhost.evil.example:3118/callback"),
        ],
    )
    def test_everything_else_must_match(self, registered, requested):
        assert not redirect_uri_matches(requested, [registered])

    def test_non_loopback_needs_the_exact_string(self):
        registered = ["https://claude.ai/api/mcp/auth_callback"]
        assert redirect_uri_matches("https://claude.ai/api/mcp/auth_callback", registered)
        assert not redirect_uri_matches("https://claude.ai/api/mcp/auth_callback/", registered)
        assert not redirect_uri_matches("https://claude.ai/api/mcp/auth_callback?x=1", registered)
        assert not redirect_uri_matches("https://claude.ai:443/api/mcp/auth_callback", registered)

    def test_is_loopback(self):
        assert is_loopback_redirect("http://127.0.0.1:1/cb")
        assert is_loopback_redirect("http://[::1]/cb")
        assert is_loopback_redirect("http://LOCALHOST:5/cb")
        assert not is_loopback_redirect("https://localhost/cb")
        assert not is_loopback_redirect("http://127.0.0.2/cb")


class TestScopeIntersection:
    def test_requested_intersect_allowed(self):
        scopes, offline = granted_scopes(
            MAP_CREA_TU_MUNDO, ["openid", "map.cobro:read", "profile", "admin:all"]
        )
        assert scopes == ["map.cobro:read"]
        assert offline is False

    def test_offline_access_is_tracked_not_granted_as_a_scope(self):
        scopes, offline = granted_scopes(
            MAP_CREA_TU_MUNDO, ["map.ops:read", "map.cobro:read", OFFLINE_ACCESS_SCOPE]
        )
        assert scopes == ["map.ops:read", "map.cobro:read"]
        assert offline is True

    def test_no_scope_parameter_means_every_resource_scope_and_no_refresh(self):
        assert granted_scopes(MAP_CREA_TU_MUNDO, None) == (
            ["map.ops:read", "map.cobro:read"],
            False,
        )

    def test_nothing_in_common(self):
        assert granted_scopes(MAP_CREA_TU_MUNDO, ["openid", "email"]) == ([], False)


class TestAuthorizationServerMetadata:
    def test_the_document(self, monkeypatch):
        monkeypatch.setenv("JANUA_CUSTOM_DOMAIN", "auth.madfam.io")
        doc = authorization_server_metadata()
        issuer = "https://auth.madfam.io"
        assert doc["issuer"] == issuer == oauth_issuer()
        assert doc["authorization_endpoint"] == f"{issuer}/api/v1/oauth/authorize"
        assert doc["token_endpoint"] == f"{issuer}/api/v1/oauth/token"
        assert doc["jwks_uri"] == f"{issuer}/.well-known/jwks.json"
        assert doc["revocation_endpoint"] == f"{issuer}/api/v1/oauth/revoke"
        assert doc["code_challenge_methods_supported"] == ["S256"]
        assert doc["response_types_supported"] == ["code"]
        assert doc["authorization_response_iss_parameter_supported"] is True
        assert doc["client_id_metadata_document_supported"] is True
        assert "none" in doc["token_endpoint_auth_methods_supported"]
        assert {"map.ops:read", "map.cobro:read", "offline_access", "openid"} <= set(
            doc["scopes_supported"]
        )
        assert len(doc["scopes_supported"]) == len(set(doc["scopes_supported"]))

    def test_issuer_without_custom_domain_is_the_api_base_url(self, monkeypatch):
        from app.config import settings

        monkeypatch.delenv("JANUA_CUSTOM_DOMAIN", raising=False)
        assert oauth_issuer() == settings.API_BASE_URL.rstrip("/")


class TestStrictSetNx:
    @pytest.mark.asyncio
    async def test_only_the_first_caller_wins_across_replicas(self):
        server = fakeredis.FakeServer()
        replica_a = ResilientRedisClient(
            fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        )
        replica_b = ResilientRedisClient(
            fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        )
        assert await replica_a.strict_set_nx("k", "1", ex=60) is True
        assert await replica_b.strict_set_nx("k", "1", ex=60) is False
        assert await replica_a.strict_set_nx("k", "1", ex=60) is False

    @pytest.mark.asyncio
    async def test_redis_down_raises(self):
        from app.core.redis_circuit_breaker import RedisUnavailableError

        server = fakeredis.FakeServer()
        replica = ResilientRedisClient(
            fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        )
        server.connected = False
        with pytest.raises(RedisUnavailableError):
            await replica.strict_set_nx("k", "1", ex=60)
