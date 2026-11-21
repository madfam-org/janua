"""Run inside an image: print what this row changes and what it must not, for the workflow.

Runs in the base image too, where the new names do not exist, so every probe is
wrapped and answers a value instead of raising. Importing the application proves
the image imports cleanly. Nothing connects to a database or to Redis: the
exception handlers and the hosted error page are called directly with a
constructed request, and the error page is asked without a client, so it never
looks one up.

Prints three lines:

- ``ROUTES=`` every route the application registers, as ``METHOD path`` (the
  workflow requires the new image's set to be the base's plus exactly the
  routes the nine merges add);
- ``FIX=`` the properties this row adds (all true on the hotfix, all false on
  production's image): a browser navigation refused on a hosted route (an
  ``HTTPException``, a validation error, slowapi's 429) gets ``303`` to
  ``/api/v1/auth/error`` with a reason code; the error page renders in Spanish
  with fixed copy and never echoes a reason it does not know; the refresh grace
  window is 30 s;
- ``UNCHANGED=`` what must be identical in both images: the JSON an API or
  ``fetch`` caller gets for the same refusals on a hosted route, and the JSON a
  browser navigation gets on a route that is not hosted (``request_id`` is
  fixed and ``timestamp`` dropped, the only values that vary per request).
"""

import asyncio
import json
import types
from urllib.parse import parse_qs, urlsplit

import app.main
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

APP = app.main.app
REQUEST_ID = "edge-hardening-check"
ERROR_PATH = "/api/v1/auth/error"
NAVIGATE = {"accept": "text/html,application/xhtml+xml", "sec-fetch-mode": "navigate"}
API = {"accept": "application/json", "sec-fetch-mode": "cors"}
#: A hosted form POST and a hosted GET page (app/auth/hosted_errors.py's list),
#: and an API route that is not hosted.
HOSTED_POST = ("POST", "/api/v1/auth/login-form")
HOSTED_GET = ("GET", "/api/v1/oauth/authorize")
NOT_HOSTED = ("GET", "/api/v1/users/me")


def _request(method: str, path: str, headers: dict, query: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "server": ("auth.example.test", 443),
            "client": ("203.0.113.9", 50000),
            "root_path": "",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            "app": APP,
            "state": {"request_id": REQUEST_ID, "view_rate_limit": None},
        }
    )


def _validation_error() -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("query", "client_id"),
                "msg": "Field required",
                "input": None,
            }
        ]
    )


def _rate_limited() -> RateLimitExceeded:
    return RateLimitExceeded(
        types.SimpleNamespace(error_message=None, limit="5 per 1 minute")
    )


#: (name, exception type the handler is registered for, factory, route)
CASES = (
    (
        "http_400",
        StarletteHTTPException,
        lambda: StarletteHTTPException(400, "refused"),
        HOSTED_POST,
    ),
    ("validation_422", RequestValidationError, _validation_error, HOSTED_GET),
    ("rate_limited_429", RateLimitExceeded, _rate_limited, HOSTED_POST),
)


def _answer(handler_type, exc, method: str, path: str, headers: dict) -> dict:
    """What the application's registered handler answers, normalized."""
    try:
        handler = APP.exception_handlers[handler_type]
        response = handler(_request(method, path, headers), exc)
        if asyncio.iscoroutine(response):
            response = asyncio.run(response)
    except Exception as error:  # noqa: BLE001 - an answer either way, so both images compare
        return {"raised": type(error).__name__}
    body = response.body.decode()
    try:
        content = json.loads(body)
    except ValueError:
        content = {"non_json_bytes": len(body)}
    if isinstance(content, dict) and isinstance(content.get("error"), dict):
        content["error"].pop("timestamp", None)
    return {
        "status": response.status_code,
        "media_type": response.media_type,
        "location": response.headers.get("location"),
        "content": content,
    }


def _routes() -> list:
    """Every registered route as `METHOD path`. FastAPI 0.16x keeps included
    routers as lazy entries without a path; older versions flatten them."""
    routes = set()

    def walk(entries, prefix=""):
        for route in entries:
            path = getattr(route, "path", None)
            context = getattr(route, "include_context", None)
            if path is None and context is not None:
                walk(context.included_router.routes, prefix + context.prefix)
                continue
            if path is None:
                routes.add(f"? {type(route).__name__}")
                continue
            for method in sorted(getattr(route, "methods", None) or ()) or (
                type(route).__name__,
            ):
                routes.add(f"{method} {prefix}{path}")

    walk(APP.routes)
    return sorted(routes)


# --- FIX ---------------------------------------------------------------------


def _navigation_gets_the_page(
    name: str, handler_type, factory, route, reason: str, status: int
) -> bool:
    answer = _answer(handler_type, factory(), *route, NAVIGATE)
    location = answer.get("location") or ""
    parts = urlsplit(location)
    query = parse_qs(parts.query)
    return (
        answer.get("status") == 303
        and parts.path == ERROR_PATH
        and query.get("reason") == [reason]
        and query.get("status") == [str(status)]
        and query.get("ref") == [REQUEST_ID]
    )


def _error_page(query: str):
    try:
        from app.auth.hosted_errors import hosted_error_page
    except ImportError:
        return None
    request = _request("GET", ERROR_PATH, NAVIGATE, query)
    # No client_id: the page never looks a client up, so db is never touched.
    return asyncio.run(hosted_error_page(request, db=None))


def _error_page_renders() -> bool:
    response = _error_page(
        "reason=rate_limited&status=429&ui_locales=es&ref=" + REQUEST_ID
    )
    if response is None:
        return False
    body = response.body.decode()
    return (
        response.status_code == 429
        and response.headers.get("cache-control") == "no-store"
        and "default-src" in (response.headers.get("content-security-policy") or "")
        and '<html lang="es-MX"' in body
        and "Demasiados intentos" in body
        and f"rate_limited · {REQUEST_ID}" in body
        and "<a href=" not in body
    )


def _error_page_never_echoes() -> bool:
    response = _error_page("reason=%3Cscript%3E&status=999&ref=%3Cb%3E")
    if response is None:
        return False
    body = response.body.decode()
    return (
        response.status_code == 400
        and "<script>" not in body
        and "<b>" not in body
        and "<code>bad_request</code>" in body
    )


def _refresh_grace_is_30_seconds() -> bool:
    try:
        from app.services.refresh_grace import REFRESH_REUSE_GRACE_SECONDS
    except ImportError:
        return False
    return REFRESH_REUSE_GRACE_SECONDS == 30


def _fix() -> dict:
    return {
        "navigation_http_400_gets_the_page": _navigation_gets_the_page(
            *CASES[0], reason="bad_request", status=400
        ),
        "navigation_validation_422_gets_the_page": _navigation_gets_the_page(
            *CASES[1], reason="invalid_request", status=422
        ),
        "navigation_rate_limited_429_gets_the_page": _navigation_gets_the_page(
            *CASES[2], reason="rate_limited", status=429
        ),
        "error_page_renders": _error_page_renders(),
        "error_page_never_echoes": _error_page_never_echoes(),
        "refresh_grace_is_30_seconds": _refresh_grace_is_30_seconds(),
    }


# --- UNCHANGED ---------------------------------------------------------------


def _unchanged() -> dict:
    answers = {}
    for name, handler_type, factory, route in CASES:
        answers[f"api_caller_{name}"] = _answer(handler_type, factory(), *route, API)
        answers[f"not_hosted_navigation_{name}"] = _answer(
            handler_type, factory(), *NOT_HOSTED, NAVIGATE
        )
    return answers


print("ROUTES=" + json.dumps(_routes()))
print("UNCHANGED=" + json.dumps(_unchanged(), sort_keys=True))
print("FIX=" + json.dumps(_fix(), sort_keys=True))
