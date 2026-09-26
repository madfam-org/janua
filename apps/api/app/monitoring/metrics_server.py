"""
Internal-only Prometheus metrics listener.

janua-api serves Prometheus text on a dedicated port (``METRICS_PORT``,
default 9464) instead of on the public FastAPI app (8080). The listener is a
plain ``http.server`` running in a daemon thread, outside FastAPI, so none of
the public app's middleware applies to it:

- TrustedHostMiddleware would answer 400 to the pod-IP ``Host`` header that
  Prometheus sends.
- The janua namespace is default-deny ingress, and the only NetworkPolicy
  that admits 9464 (enclii ``janua-api-ingress-monitoring``) admits only the
  ``monitoring`` namespace. The tunnel namespace is admitted on 8080 only, so
  even a misrouted tunnel hostname cannot reach this port.

The listener answers ``GET /metrics`` with the process-wide default registry
(``prometheus_client.REGISTRY``). That registry holds the process/platform/GC
collectors plus the ``janua_*`` metrics defined in ``app.monitoring.metrics``.
Every other path returns 404, and any other method on ``/metrics`` returns
405.

Single-process only. The API runs one uvicorn process per pod (Dockerfile.api
CMD, no ``--workers``). With several worker processes each one would hold its
own registry and only one could bind the port, so ``resolve_metrics_port``
refuses to start when ``WEB_CONCURRENCY`` asks for more than one worker.
Switching to multiple workers needs prometheus_client multiprocess mode
(``PROMETHEUS_MULTIPROC_DIR`` plus a ``MultiProcessCollector`` served from the
parent process).
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, generate_latest

METRICS_PATH = "/metrics"
DEFAULT_METRICS_PORT = 9464


def resolve_metrics_port(env: Optional[Mapping[str, str]] = None) -> int:
    """Return the metrics port from ``METRICS_PORT``, or raise ``ValueError``.

    Invalid configuration fails loudly at boot. A listener that silently did
    not start would look exactly like a dead API to every ``up`` alert.
    """
    env = os.environ if env is None else env

    raw = (env.get("METRICS_PORT") or "").strip()
    if not raw:
        port = DEFAULT_METRICS_PORT
    else:
        try:
            port = int(raw)
        except ValueError:
            raise ValueError(f"METRICS_PORT must be an integer, got {raw!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"METRICS_PORT must be between 1 and 65535, got {port}")

    app_port = (env.get("PORT") or "").strip()
    if app_port and app_port == str(port):
        raise ValueError(
            f"METRICS_PORT ({port}) must differ from PORT ({app_port}): the metrics "
            "listener must not share the public API port"
        )

    workers = (env.get("WEB_CONCURRENCY") or "").strip()
    if workers and workers.isdigit() and int(workers) > 1:
        raise ValueError(
            f"WEB_CONCURRENCY={workers}: the metrics listener serves one process's "
            "registry and cannot run under multiple uvicorn workers; use "
            "prometheus_client multiprocess mode before raising the worker count"
        )
    return port


def _make_handler(registry: CollectorRegistry) -> type[BaseHTTPRequestHandler]:
    class MetricsHandler(BaseHTTPRequestHandler):
        server_version = "janua-metrics"
        sys_version = ""

        def _send(self, status: int, body: bytes, content_type: str, allow: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if allow:
                self.send_header("Allow", "GET")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _is_metrics_path(self) -> bool:
            return urlsplit(self.path).path == METRICS_PATH

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            if not self._is_metrics_path():
                self._send(404, b"Not Found\n", "text/plain; charset=utf-8")
                return
            try:
                body = generate_latest(registry)
            except Exception:  # pragma: no cover - collector failure
                self._send(500, b"metrics collection failed\n", "text/plain; charset=utf-8")
                raise
            self._send(200, body, CONTENT_TYPE_LATEST)

        def _method_not_allowed(self) -> None:
            if not self._is_metrics_path():
                self._send(404, b"Not Found\n", "text/plain; charset=utf-8")
                return
            self._send(405, b"Method Not Allowed\n", "text/plain; charset=utf-8", allow=True)

        do_HEAD = _method_not_allowed  # noqa: N815
        do_POST = _method_not_allowed  # noqa: N815
        do_PUT = _method_not_allowed  # noqa: N815
        do_PATCH = _method_not_allowed  # noqa: N815
        do_DELETE = _method_not_allowed  # noqa: N815
        do_OPTIONS = _method_not_allowed  # noqa: N815

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # One line per scrape every 15-30s from two Prometheus instances is
            # noise; failures surface as `up == 0` on the scrape side.
            return

    return MetricsHandler


class MetricsServer:
    """A running metrics listener. ``close()`` stops it and frees the port."""

    def __init__(self, httpd: ThreadingHTTPServer, thread: threading.Thread):
        self._httpd = httpd
        self._thread = thread

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def start_metrics_server(
    port: int,
    addr: str = "0.0.0.0",  # nosec B104 - pod-internal; NetworkPolicy admits only monitoring
    registry: CollectorRegistry = REGISTRY,
) -> MetricsServer:
    """Bind the metrics listener and serve it from a daemon thread.

    Raises ``OSError`` when the port cannot be bound. ``port=0`` binds an
    ephemeral port (tests).
    """
    httpd = ThreadingHTTPServer((addr, port), _make_handler(registry))
    httpd.daemon_threads = True
    thread = threading.Thread(
        target=httpd.serve_forever, name="janua-metrics-listener", daemon=True
    )
    thread.start()
    return MetricsServer(httpd, thread)
