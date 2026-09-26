"""A tracking host answers /e/o/* and /e/c/* and nothing else.

TrustedHostMiddleware's list is global, so trusting a tracking host (e.g.
enlaces.creatumundo.mx) for the pixel and the click redirect would otherwise
also expose sign-in, password reset and OIDC discovery under a tenant's
marketing domain. Every other host is untouched.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.middleware.tracking_host_scope import TrackingHostScopeMiddleware

TRACKING = "enlaces.creatumundo.mx"


async def _ok(request):
    return PlainTextResponse("ok")


async def _ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("ok")
    await websocket.close()


def _app(hosts):
    inner = Starlette(
        routes=[
            Route("/e/o/{rest:path}", _ok, methods=["GET", "HEAD"]),
            Route("/e/c/{rest:path}", _ok, methods=["GET", "HEAD"]),
            Route("/api/v1/health", _ok, methods=["GET", "HEAD"]),
            Route("/api/v1/auth/signin", _ok, methods=["POST"]),
            Route("/.well-known/openid-configuration", _ok),
            Route("/e/x", _ok),
            WebSocketRoute("/ws", _ws),
        ]
    )
    return TrackingHostScopeMiddleware(inner, hosts=hosts)


async def _status(app, host, path, method="GET"):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://placeholder"
    ) as client:
        response = await client.request(method, path, headers={"host": host})
        return response.status_code


@pytest.mark.parametrize("path", ["/e/o/abc.gif", "/e/c/abc/0"])
async def test_the_tracking_paths_answer_on_the_tracking_host(path):
    assert await _status(_app([TRACKING]), TRACKING, path) == 200
    assert await _status(_app([TRACKING]), TRACKING, path, "HEAD") == 200


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/health", "GET"),
        ("/api/v1/health", "HEAD"),
        ("/api/v1/auth/signin", "POST"),
        ("/.well-known/openid-configuration", "GET"),
        ("/e/x", "GET"),
        ("/e/o", "GET"),
        ("/", "GET"),
    ],
)
async def test_everything_else_is_a_404_on_the_tracking_host(path, method):
    assert await _status(_app([TRACKING]), TRACKING, path, method) == 404


@pytest.mark.parametrize(
    "host", ["ENLACES.creatumundo.mx", "enlaces.creatumundo.mx:443", " enlaces.creatumundo.mx "]
)
async def test_the_host_match_ignores_case_port_and_spaces(host):
    assert await _status(_app([TRACKING]), host, "/api/v1/health") == 404
    assert await _status(_app([TRACKING]), host, "/e/o/abc.gif") == 200


@pytest.mark.parametrize(
    "host", ["auth.madfam.io", "creatumundo.mx", "evil-enlaces.creatumundo.mx"]
)
async def test_other_hosts_are_untouched(host):
    assert await _status(_app([TRACKING]), host, "/api/v1/health") == 200
    assert await _status(_app([TRACKING]), host, "/.well-known/openid-configuration") == 200


async def test_with_no_tracking_host_it_does_nothing():
    assert await _status(_app([]), TRACKING, "/api/v1/health") == 200
    assert await _status(_app(["", "  "]), TRACKING, "/api/v1/health") == 200


def test_websockets_are_refused_on_the_tracking_host_only():
    # TestClient sends Host: testserver on websockets whatever the base_url
    # says, so the header is set explicitly.
    with TestClient(_app([TRACKING])) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect("/ws", headers={"host": TRACKING}):
                pass
        assert refused.value.code == 1008
        with client.websocket_connect("/ws", headers={"host": "auth.madfam.io"}) as ws:
            assert ws.receive_text() == "ok"


def test_the_api_registers_it():
    from app.main import app

    assert any(m.cls is TrackingHostScopeMiddleware for m in app.user_middleware)
