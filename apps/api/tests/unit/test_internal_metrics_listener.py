"""
Internal-only Prometheus metrics (fleet rule 2026-09-25, design 1).

- The public app (8080) serves no Prometheus exposition: public-style
  requests to /metrics and /metrics/ get 404.
- The dedicated listener (METRICS_PORT, default 9464) serves the REAL default
  registry: after one request through the app, janua_requests_total carries
  that request, labelled by route template.
- None of the old hardcoded series remain.
"""

from __future__ import annotations

import http.client
import inspect
import os
import socket
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import AsyncClient
from prometheus_client import REGISTRY, CollectorRegistry, Counter

from app.monitoring.metrics import UNMATCHED_ROUTE, method_label, route_label
from app.monitoring.metrics_server import (
    DEFAULT_METRICS_PORT,
    METRICS_PATH,
    resolve_metrics_port,
    start_metrics_server,
)

# The series the removed /metrics handler on the public app emitted as
# hardcoded constants.
FAKE_SERIES = (
    "janua_http_requests_total",
    "janua_http_request_duration_seconds",
    "janua_database_connections_active",
    "janua_redis_connected",
    "janua_app_health_status",
    "janua_metrics_collection_errors_total",
)

SCRAPER_HOST = "10.42.1.2"


def _scrape(port: int, path: str = METRICS_PATH, method: str = "GET"):
    """Request the listener the way Prometheus does: pod-IP Host, no CF headers."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers={"Host": f"{SCRAPER_HOST}:{port}"})
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read().decode()
    finally:
        conn.close()


def _requests_total(method: str, path: str, status: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "janua_requests_total", {"method": method, "path": path, "status": status}
        )
        or 0.0
    )


@pytest.fixture
def listener():
    server = start_metrics_server(0, addr="127.0.0.1")
    try:
        yield server
    finally:
        server.close()


# ---------------------------------------------------------------------------
# Public app: no metrics
# ---------------------------------------------------------------------------


def test_public_app_registers_no_prometheus_route():
    from app.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/metrics" not in paths
    assert "/metrics/" not in paths


@pytest.mark.parametrize("path", ["/metrics", "/metrics/"])
@pytest.mark.parametrize(
    "headers",
    [
        {"host": "api.janua.dev"},
        {"host": "api.janua.dev", "cf-connecting-ip": "203.0.113.7", "cf-ray": "8f0-MEX"},
    ],
    ids=["public-host", "cloudflare-edge"],
)
async def test_public_style_metrics_request_is_404(path, headers):
    from app.main import app

    async with AsyncClient(app=app, base_url="http://api.janua.dev") as client:
        resp = await client.get(path, headers=headers, follow_redirects=False)

    assert resp.status_code == 404
    assert "# TYPE" not in resp.text


# ---------------------------------------------------------------------------
# Listener: real registry, scraper-style access
# ---------------------------------------------------------------------------


async def test_listener_serves_real_counters_after_one_request(listener):
    from app.main import app

    user_id = str(uuid.uuid4())
    root_before = _requests_total("GET", "/", "200")

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        assert (await client.get("/")).status_code == 200
        param_resp = await client.get(f"/api/v1/users/{user_id}")

    assert _requests_total("GET", "/", "200") == root_before + 1

    status, headers, body = _scrape(listener.port)
    assert status == 200
    assert headers["Content-Type"].startswith("text/plain; version=")

    # The request above, as a real counter and histogram observation.
    assert 'janua_requests_total{method="GET",path="/",status="200"}' in body
    assert "janua_request_latency_milliseconds_bucket{" in body
    # Route template, never the raw id.
    param_series = (
        'janua_requests_total{method="GET",path="/api/v1/users/{user_id}",'
        f'status="{param_resp.status_code}"}}'
    )
    assert param_series in body
    assert user_id not in body
    # Default-registry collectors come along.
    assert "python_info{" in body


async def test_no_hardcoded_series_remain(listener):
    _, _, body = _scrape(listener.port)
    for name in FAKE_SERIES:
        assert name not in body, name

    main_source = (Path(__file__).resolve().parents[2] / "app" / "main.py").read_text()
    assert "JanuaMetricsCollector" not in main_source
    for name in FAKE_SERIES:
        assert name not in main_source, name


def test_listener_serves_only_get_metrics(listener):
    assert _scrape(listener.port, "/")[0] == 404
    assert _scrape(listener.port, "/metrics/")[0] == 404
    assert _scrape(listener.port, "/api/v1/health")[0] == 404
    assert _scrape(listener.port, "/metrics?name[]=python_info")[0] == 200

    status, headers, _ = _scrape(listener.port, method="POST")
    assert status == 405
    assert headers["Allow"] == "GET"
    assert _scrape(listener.port, "/other", method="POST")[0] == 404


def test_listener_serves_the_given_registry():
    registry = CollectorRegistry()
    Counter("lane_probe_total", "probe", registry=registry).inc()
    server = start_metrics_server(0, addr="127.0.0.1", registry=registry)
    try:
        status, _, body = _scrape(server.port)
    finally:
        server.close()
    assert status == 200
    assert "lane_probe_total 1.0" in body


def test_close_frees_the_port():
    server = start_metrics_server(0, addr="127.0.0.1")
    port = server.port
    server.close()
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=1).close()


# ---------------------------------------------------------------------------
# Startup wiring
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_startup_starts_listener_outside_test_env():
    import app.main as main

    port = _free_port()
    with patch.object(main, "settings", SimpleNamespace(ENVIRONMENT="production")):
        with patch.dict(os.environ, {"METRICS_PORT": str(port), "PORT": "8080"}):
            main._start_metrics_listener()
    try:
        assert main.app.state.metrics_server.port == port
        assert _scrape(port)[0] == 200
    finally:
        main._stop_metrics_listener()
    assert main.app.state.metrics_server is None


def test_startup_skips_listener_in_test_env():
    import app.main as main

    main.app.state.metrics_server = None
    with patch.object(main, "settings", SimpleNamespace(ENVIRONMENT="test")):
        main._start_metrics_listener()
    assert main.app.state.metrics_server is None


def test_startup_fails_loudly_on_bad_metrics_port():
    import app.main as main

    with patch.object(main, "settings", SimpleNamespace(ENVIRONMENT="production")):
        with patch.dict(os.environ, {"METRICS_PORT": "8080", "PORT": "8080"}):
            with pytest.raises(ValueError, match="must differ from PORT"):
                main._start_metrics_listener()


def test_startup_and_shutdown_events_wire_the_listener():
    import app.main as main

    assert "_start_metrics_listener()" in inspect.getsource(main.startup_event)
    assert "_stop_metrics_listener()" in inspect.getsource(main.shutdown_event)


# ---------------------------------------------------------------------------
# resolve_metrics_port
# ---------------------------------------------------------------------------


def test_resolve_metrics_port_default():
    assert resolve_metrics_port({}) == DEFAULT_METRICS_PORT == 9464
    assert resolve_metrics_port({"METRICS_PORT": " ", "PORT": "8080"}) == 9464


def test_resolve_metrics_port_explicit():
    assert resolve_metrics_port({"METRICS_PORT": "9100", "PORT": "8080"}) == 9100


@pytest.mark.parametrize(
    "env, message",
    [
        ({"METRICS_PORT": "nine"}, "must be an integer"),
        ({"METRICS_PORT": "0"}, "between 1 and 65535"),
        ({"METRICS_PORT": "70000"}, "between 1 and 65535"),
        ({"METRICS_PORT": "8080", "PORT": "8080"}, "must differ from PORT"),
        ({"PORT": "9464"}, "must differ from PORT"),
        ({"WEB_CONCURRENCY": "4"}, "multiple uvicorn workers"),
    ],
)
def test_resolve_metrics_port_rejects(env, message):
    with pytest.raises(ValueError, match=message):
        resolve_metrics_port(env)


# ---------------------------------------------------------------------------
# Bounded labels
# ---------------------------------------------------------------------------


def _scope(path: str, template, params=None) -> dict:
    scope = {"path": path, "path_params": params or {}}
    if template is not None:
        scope["route"] = SimpleNamespace(path=template)
    return scope


@pytest.mark.parametrize(
    "scope, expected",
    [
        # No route matched: one shared label.
        (_scope("/wp-login.php", None), UNMATCHED_ROUTE),
        # Route path without the include prefix (newer FastAPI).
        (
            _scope("/api/v1/users/abc", "/users/{user_id}", {"user_id": "abc"}),
            "/api/v1/users/{user_id}",
        ),
        # Route path with the include prefix (older FastAPI).
        (
            _scope("/api/v1/users/abc", "/api/v1/users/{user_id}", {"user_id": "abc"}),
            "/api/v1/users/{user_id}",
        ),
        (_scope("/", "/"), "/"),
        (_scope("/api/v1/health/ready", "/health/ready"), "/api/v1/health/ready"),
        # Included router root route.
        (_scope("/api/v1/organizations", ""), "/api/v1/organizations"),
        # Same value in two parameters.
        (
            _scope("/orgs/x/users/x", "/users/{user_id}", {"org_id": "x", "user_id": "x"}),
            "/orgs/{org_id}/users/{user_id}",
        ),
        (
            _scope(
                "/api/v1/orgs/o1/members/m1",
                "/members/{member_id}",
                {"org_id": "o1", "member_id": "m1"},
            ),
            "/api/v1/orgs/{org_id}/members/{member_id}",
        ),
        # Alignment does not hold: fall back to the route's own template.
        (_scope("/a/b", "/x/y/z"), "/x/y/z"),
        (_scope("/api/v1/other/abc", "/users/{user_id}", {"user_id": "abc"}), "/users/{user_id}"),
        (_scope("/files/a/b", "/files/{rest:path}", {"rest": "a/b"}), "/files/{rest:path}"),
    ],
)
def test_route_label(scope, expected):
    assert route_label(scope) == expected


def test_method_label_is_bounded():
    assert method_label("get") == "GET"
    assert method_label("DELETE") == "DELETE"
    assert method_label("PROPFIND") == "OTHER"
    assert method_label("") == "OTHER"


# ---------------------------------------------------------------------------
# Middleware wiring (isolated app)
# ---------------------------------------------------------------------------


async def test_performance_middleware_records_templates_and_unhandled_500():
    from app.core.performance import PerformanceMonitoringMiddleware

    router = APIRouter()

    @router.get("/items/{item_id}")
    async def get_item(item_id: str):
        return {"item_id": item_id}

    @router.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    @router.get("/teapot")
    async def teapot():
        raise HTTPException(status_code=418)

    mini = FastAPI()
    mini.include_router(router, prefix="/lane-l/v1")
    mini.add_middleware(PerformanceMonitoringMiddleware)

    item_before = _requests_total("GET", "/lane-l/v1/items/{item_id}", "200")
    boom_before = _requests_total("GET", "/lane-l/v1/boom", "500")
    teapot_before = _requests_total("GET", "/lane-l/v1/teapot", "418")
    unmatched_before = _requests_total("GET", UNMATCHED_ROUTE, "404")

    async with AsyncClient(app=mini, base_url="http://testserver") as client:
        assert (await client.get("/lane-l/v1/items/one")).status_code == 200
        assert (await client.get("/lane-l/v1/items/two")).status_code == 200
        assert (await client.get("/lane-l/v1/teapot")).status_code == 418
        assert (await client.get("/lane-l/v1/nope")).status_code == 404
        with pytest.raises(RuntimeError):
            await client.get("/lane-l/v1/boom")

    assert _requests_total("GET", "/lane-l/v1/items/{item_id}", "200") == item_before + 2
    assert _requests_total("GET", "/lane-l/v1/teapot", "418") == teapot_before + 1
    assert _requests_total("GET", UNMATCHED_ROUTE, "404") == unmatched_before + 1
    assert _requests_total("GET", "/lane-l/v1/boom", "500") == boom_before + 1
    assert (
        REGISTRY.get_sample_value(
            "janua_requests_total",
            {"method": "GET", "path": "/lane-l/v1/items/one", "status": "200"},
        )
        is None
    )
