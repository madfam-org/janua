"""The MCP tools call janua's OWN HTTP API. This is how the pilot preserves auth.

The single most important design choice in this pilot: an MCP tool does NOT import a
router handler, touch the database, or re-implement any endpoint. It makes the same
HTTP request a human/service caller would, against the running janua API, carrying the
same ``X-Internal-API-Key`` header the HTTP endpoint requires. Every gate the HTTP
layer enforces -- ``verify_internal_api_key`` (503 if janua has no key configured, 401
on a wrong key), the sender-domain gate in ``resend_email_service`` /
``email_sender``, the template whitelist, per-tenant sender resolution -- runs exactly
once, on the server side, unchanged. There is no code path by which an MCP tool reaches
an effect the HTTP endpoint would have refused. That is the roadmap's "an MCP tool must
never be a back door around a gate the HTTP endpoint enforces", made structural rather
than promised.

The key comes from the environment (``JANUA_INTERNAL_API_KEY``), never from a tool
argument, so an agent driving the MCP server cannot supply or override it -- the MCP
process holds the credential the same way any internal service caller does, and the
agent only chooses which typed tool to call. If the key is absent the server refuses to
start rather than issue unauthenticated calls (fail closed, never a back door).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


class MCPConfigError(RuntimeError):
    """Raised at startup when the MCP server is not configured to authenticate."""


@dataclass(frozen=True)
class HttpConfig:
    base_url: str
    internal_api_key: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> HttpConfig:
        base_url = os.environ.get("JANUA_API_BASE_URL", "").rstrip("/")
        key = os.environ.get("JANUA_INTERNAL_API_KEY", "")
        if not base_url:
            raise MCPConfigError(
                "JANUA_API_BASE_URL is required (e.g. https://auth.madfam.io) so the MCP "
                "server calls the real janua HTTP API and its auth gate runs."
            )
        if not key:
            raise MCPConfigError(
                "JANUA_INTERNAL_API_KEY is required. The MCP server authenticates to janua "
                "exactly as an internal service caller does (X-Internal-API-Key); without it "
                "the server refuses to start rather than issue unauthenticated calls."
            )
        return cls(base_url=base_url, internal_api_key=key)


class JanuaHttpClient:
    """Thin async client that always attaches the internal-API-key gate header."""

    def __init__(self, config: HttpConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url, timeout=config.timeout_seconds
        )

    @property
    def _headers(self) -> dict[str, str]:
        # The gate header is set here, from configured state, on every request. It is
        # never taken from tool arguments -- an agent cannot supply, alter or omit it.
        return {"X-Internal-API-Key": self._config.internal_api_key}

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> httpx.Response:
        return await self._client.request(
            method.upper(),
            path,
            params={k: v for k, v in (query or {}).items() if v is not None} or None,
            json=json_body,
            headers=self._headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
