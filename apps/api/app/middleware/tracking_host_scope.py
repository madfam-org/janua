"""Tracking hosts serve the first-party pixel and click redirect, and nothing else.

A tracking host (e.g. enlaces.creatumundo.mx, from CTM_TRACKING_HOST) is added to
TrustedHostMiddleware's list so that /e/o and /e/c answer on it. That list is
global, not per path: without this middleware the same host would also serve
sign-in, password reset, OIDC discovery and the rest of the API under a tenant's
marketing domain. Here any request on a tracking host whose path is not
/e/o/... or /e/c/... gets a plain 404 before it reaches a router.

The hosts are fixed at startup, like TrustedHostMiddleware's list: a change to
CTM_TRACKING_HOST takes effect when the pods restart. With no tracking host
configured the middleware does nothing.
"""

from typing import Iterable, Optional

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

TRACKING_PATH_PREFIXES = ("/e/o/", "/e/c/")


def _request_host(scope: Scope) -> Optional[str]:
    """The Host header, lowercased, without a port."""
    for name, value in scope.get("headers") or ():
        if name == b"host":
            host = value.decode("latin-1").strip().lower()
            if host.startswith("["):  # IPv6 literal: keep the brackets, drop the port
                return host.split("]", 1)[0] + "]"
            return host.split(":", 1)[0]
    return None


class TrackingHostScopeMiddleware:
    """404 for everything on a tracking host except /e/o/* and /e/c/*; no websockets."""

    def __init__(self, app: ASGIApp, hosts: Iterable[str]) -> None:
        self.app = app
        self.hosts = frozenset(h.strip().lower() for h in hosts if h and h.strip())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.hosts and scope["type"] in ("http", "websocket"):
            if _request_host(scope) in self.hosts:
                if scope["type"] == "websocket":
                    # Refused before accept: the client sees an HTTP 403.
                    await WebSocketClose(code=1008)(scope, receive, send)
                    return
                if not scope["path"].startswith(TRACKING_PATH_PREFIXES):
                    await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)
                    return
        await self.app(scope, receive, send)
