"""Per-IP rate limits count the client, not the hop in front of Janua.

Production log, 2026-10-27: a 5/minute login limit reported as exceeded for
the tunnel pod's address while the request log named the real client. With
the socket peer as the key, every person behind the tunnel shares one bucket.

These pin:

1. `client_ip_key` believes forwarded headers only from `TRUSTED_PROXIES`
   (a spoofed `X-Forwarded-For` / `CF-Connecting-IP` from anyone else buys
   nothing), and counts IPv6 per /64;
2. a real slowapi limiter keyed on it gives two clients behind the same
   trusted proxy separate buckets, and an untrusted caller cannot escape its
   bucket by rotating headers;
3. every slowapi limiter in the API is keyed on it (source-level, because the
   test suite replaces `slowapi.Limiter` with a no-op).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.extension import Limiter as RealLimiter

from app.auth import magic_link_limits
from app.core.rate_limit_keys import client_ip_key

TUNNEL_POD = "10.42.8.3"
TUNNEL_RANGE = "10.42.0.0/16"


def _request(peer: str, headers: dict | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": raw,
            "client": (peer, 40000),
            "query_string": b"",
        }
    )


def _trusting(value: str):
    return patch.object(magic_link_limits.settings, "TRUSTED_PROXIES", value)


class TestClientIpKey:
    def test_untrusted_peer_is_its_own_key_whatever_it_claims(self):
        with _trusting("127.0.0.1,::1"):
            req = _request(
                "203.0.113.9",
                {"X-Forwarded-For": "198.51.100.1", "CF-Connecting-IP": "198.51.100.2"},
            )
            assert client_ip_key(req) == "203.0.113.9"

    def test_trusted_proxy_passes_cloudflares_client_address(self):
        with _trusting(TUNNEL_RANGE):
            req = _request(TUNNEL_POD, {"CF-Connecting-IP": "187.226.35.216"})
            assert client_ip_key(req) == "187.226.35.216"

    def test_trusted_proxy_uses_the_rightmost_untrusted_forwarded_hop(self):
        with _trusting(TUNNEL_RANGE):
            req = _request(TUNNEL_POD, {"X-Forwarded-For": "1.2.3.4, 187.226.35.216, 10.42.0.7"})
            assert client_ip_key(req) == "187.226.35.216"

    def test_trusted_proxy_without_forwarding_headers_is_itself(self):
        with _trusting(TUNNEL_RANGE):
            assert client_ip_key(_request(TUNNEL_POD)) == TUNNEL_POD

    def test_ipv6_clients_share_a_slash_64(self):
        with _trusting(TUNNEL_RANGE):
            a = client_ip_key(_request(TUNNEL_POD, {"CF-Connecting-IP": "2001:db8:1:2::a"}))
            b = client_ip_key(_request(TUNNEL_POD, {"CF-Connecting-IP": "2001:db8:1:2::b"}))
            assert a == b == "2001:db8:1:2::/64"


def _limited_app() -> FastAPI:
    limiter = RealLimiter(key_func=client_ip_key)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/login")
    @limiter.limit("5/minute")
    async def login(request: Request):
        return {"ok": True}

    return app


async def _post(app: FastAPI, peer: str, headers: dict | None = None) -> int:
    transport = ASGITransport(app=app, client=(peer, 40000))
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        return (await http.post("/login", headers=headers or {})).status_code


@pytest.mark.asyncio
class TestLimiterBuckets:
    async def test_clients_behind_the_same_trusted_proxy_do_not_share_a_bucket(self):
        app = _limited_app()
        with _trusting(TUNNEL_RANGE):
            for _ in range(5):
                assert await _post(app, TUNNEL_POD, {"CF-Connecting-IP": "198.51.100.1"}) == 200
            assert await _post(app, TUNNEL_POD, {"CF-Connecting-IP": "198.51.100.1"}) == 429
            # Someone else, through the very same tunnel pod, is unaffected.
            assert await _post(app, TUNNEL_POD, {"CF-Connecting-IP": "198.51.100.2"}) == 200

    async def test_an_untrusted_caller_cannot_rotate_out_of_its_bucket(self):
        app = _limited_app()
        with _trusting(TUNNEL_RANGE):
            for i in range(5):
                headers = {"X-Forwarded-For": f"198.51.100.{i}", "CF-Connecting-IP": f"192.0.2.{i}"}
                assert await _post(app, "203.0.113.9", headers) == 200
            assert await _post(app, "203.0.113.9", {"X-Forwarded-For": "198.51.100.99"}) == 429


class TestEveryLimiterUsesTheTrustedKey:
    MODULES = (
        "app/main.py",
        "app/beta_auth.py",
        "app/routers/v1/auth.py",
        "app/routers/v1/organization_app_roles.py",
    )

    def _api_root(self) -> Path:
        import app as app_pkg

        return Path(inspect.getfile(app_pkg)).parent.parent

    def test_no_module_keys_a_limiter_on_the_socket_peer(self):
        root = self._api_root()
        offenders = [
            str(path.relative_to(root))
            for path in (root / "app").rglob("*.py")
            if "import get_remote_address" in (text := path.read_text(encoding="utf-8"))
            or "key_func=get_remote_address" in text
        ]
        assert offenders == []

    @pytest.mark.parametrize("module", MODULES)
    def test_each_slowapi_limiter_is_keyed_on_client_ip_key(self, module):
        source = (self._api_root() / module).read_text(encoding="utf-8")
        assert "Limiter(key_func=client_ip_key)" in source
