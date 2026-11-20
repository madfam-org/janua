"""No raw JSON on a browser-navigated hosted route (roadmap 0.2, rule R1).

Production incident 2026-11-19: a second press on the hosted password form was
answered with the error envelope as raw JSON, because every ``HTTPException``
goes through the global handler, which only speaks JSON. janua#841 fixed that one
path. This module removes the class at the surface:

- When a request on a HOSTED route (the pages and form POSTs a browser
  navigates to: login, second factor, recovery, magic-link callback, authorize,
  consent, logout) is a NAVIGATION (``Sec-Fetch-Mode: navigate``, or no
  ``Sec-Fetch-Mode`` and an ``Accept`` that names ``text/html``), the error
  handlers answer ``303`` to ``GET /api/v1/auth/error`` instead of JSON. The page
  is reachable by GET, so a refresh never re-posts a form (rule R2), it speaks
  the person's language, and when the request named a registered client it
  offers one button to that client's registered origin, which starts a fresh
  sign-in (the same restart as ``/login-expired``).
- slowapi's 429 is not covered yet: its handler is registered in
  ``app/main.py`` and is deferred (see docs/authentication-policy.md).
- API and JSON clients (``Accept: application/json``, ``fetch`` with
  ``Sec-Fetch-Mode: cors``, server-side callers) get exactly the envelope they
  got before, from the same handlers.
- Every refusal on a hosted route logs ONE structured line,
  ``auth.hosted_refusal``, with a stable ``reason`` code, the route, the client
  id and the request id (rule R4). No email, no person id, no token.

The page never prints the exception's message: it shows fixed copy chosen by
status class plus the reason code and request id as a reference, so nothing a
request carries is ever echoed as prose on Janua's origin.
"""

from __future__ import annotations

import html
import re
import uuid
from typing import Any, Optional
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth.hosted_locale import (
    DEFAULT_HOSTED_LOCALE,
    HOSTED_LOCALES,
    UI_LOCALES_PARAM,
    hosted_locale,
    html_lang,
)
from app.database import get_db

logger = structlog.get_logger()

#: Included by app/auth/hosted_security.py's router, which the /auth router
#: includes, so "/error" here is GET /api/v1/auth/error.
router = APIRouter()


class HostedRefusal(HTTPException):
    """An HTTPException with a stable `reason` code for the refusal log line.

    Same status and detail as before for API callers (the JSON envelope is
    unchanged); a browser navigation gets the hosted error page.
    """

    def __init__(self, status_code: int, detail: str, *, reason: str):
        super().__init__(status_code, detail)
        self.reason = reason


#: The GET page every refused navigation on a hosted route lands on.
HOSTED_ERROR_PATH = "/api/v1/auth/error"

# The routes a browser navigates to (GET pages and form POSTs). Exact paths, so a
# JSON API route that shares a prefix (``/auth/login-form`` vs ``/auth/logout``)
# is never swept in by accident. ``POST /api/v1/auth/login`` is the JSON sign-in
# API: its callers send ``Accept: application/json`` and keep the envelope; a
# plain HTML form posting there is a navigation and gets the page.
_HOSTED_ROUTE = re.compile(
    r"^(?:"
    r"/api/v1/auth/(?:"
    r"login|login-form|login-form/mfa|login-form/magic-link|login-expired"
    r"|factor/[A-Za-z0-9_-]+|security"
    r"|forgot-password|forgot-password-form|reset-password|reset-password-form"
    r"|magic-link/callback|switch-session/form|error"
    r")"
    r"|/api/v1/oauth/(?:authorize|authorize/resume|consent)"
    r"|/logout"
    r")/?$"
)

_REASON = re.compile(r"[a-z][a-z0-9_]{0,47}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
_CLIENT_ID = re.compile(r"[A-Za-z0-9._:~-]{1,255}")

_STATUS_REASONS = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "too_large",
    422: "invalid_request",
    428: "mfa_required",
    429: "rate_limited",
}


def is_hosted_route(path: str) -> bool:
    return bool(_HOSTED_ROUTE.match(path or ""))


def is_navigation(request: Request) -> bool:
    """A browser navigation (address bar, link, form POST), not a fetch/API call.

    ``Sec-Fetch-Mode`` is authoritative when the browser sends it; without it
    (older browsers, test clients) an ``Accept`` that names ``text/html`` is the
    signal. ``Accept: application/json`` is never a navigation.
    """
    mode = request.headers.get("sec-fetch-mode")
    if mode:
        return mode.strip().lower() == "navigate"
    return "text/html" in request.headers.get("accept", "").lower()


def refusal_reason(exc: Any, status_code: int) -> str:
    """A stable, log-safe reason code: the exception's own ``reason`` when it
    declares one (e.g. ``LoginRequestExpired``), else one derived from the status."""
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and _REASON.fullmatch(reason):
        return reason
    if status_code in _STATUS_REASONS:
        return _STATUS_REASONS[status_code]
    return "server_error" if status_code >= 500 else f"http_{int(status_code)}"


def _cached_form(request: Request):
    # FastAPI parses a form route's body on this same Request object before the
    # route runs, and Starlette caches the result; an exception handler for that
    # route receives the same object. Reading the cache never consumes a body.
    return getattr(request, "_form", None)


def _request_value(request: Request, name: str) -> Optional[str]:
    value = request.query_params.get(name)
    if value is None:
        form = _cached_form(request)
        if form is not None:
            try:
                value = form.get(name)
            except Exception:  # pragma: no cover - defensive
                value = None
    return value if isinstance(value, str) else None


def _client_id(request: Request) -> Optional[str]:
    value = _request_value(request, "client_id")
    if value and _CLIENT_ID.fullmatch(value):
        return value
    return None


def _accept_language_locale(header: str) -> Optional[str]:
    for part in (header or "")[:256].split(",")[:16]:
        tag = part.split(";")[0].strip().lower()
        primary = tag.split("-")[0]
        for supported in HOSTED_LOCALES:
            if primary == supported:
                return supported
    return None


def _locale(request: Request) -> str:
    return (
        hosted_locale(_request_value(request, UI_LOCALES_PARAM))
        or _accept_language_locale(request.headers.get("accept-language", ""))
        or DEFAULT_HOSTED_LOCALE
    )


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        # Pin one id so the log line and the answer (page or envelope) agree.
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    return request_id


def hosted_refusal_response(request: Request, exc: Any, status_code: int) -> Optional[Response]:
    """Log a refusal on a hosted route; for a navigation, return the page redirect.

    Returns None when the route is not hosted (nothing logged) or the request is
    not a navigation (logged; the caller answers its usual JSON envelope).
    """
    path = request.url.path
    if not is_hosted_route(path):
        return None
    reason = refusal_reason(exc, status_code)
    navigation = is_navigation(request)
    request_id = _request_id(request)
    client_id = _client_id(request)
    logger.info(
        "auth.hosted_refusal",
        reason=reason,
        route=path,
        method=request.method,
        status_code=status_code,
        client_id=client_id,
        request_id=request_id,
        answer="html" if navigation else "json",
    )
    if not navigation:
        return None
    locale = _locale(request)
    if path.rstrip("/") == HOSTED_ERROR_PATH:
        # The error page itself failed (e.g. a POST to it): render, never loop.
        return _error_page(
            status_code=status_code,
            reason=reason,
            request_id=request_id,
            locale=locale,
            restart=None,
        )
    params = {"reason": reason, "status": str(int(status_code))}
    if client_id:
        params["client_id"] = client_id
    if locale != DEFAULT_HOSTED_LOCALE:
        params[UI_LOCALES_PARAM] = locale
    if _REQUEST_ID.fullmatch(request_id):
        params["ref"] = request_id
    return RedirectResponse(
        f"{HOSTED_ERROR_PATH}?{urlencode(params)}",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


# Fixed copy by status class. The exception's own message is never printed.
_COPY = {
    "en": {
        "title": "Sign-in",
        "request_title": "This sign-in can't continue",
        "request_body": (
            "The sign-in request expired, was already used, or belongs to another "
            "browser window. Nothing was changed. Start again from the app you "
            "were signing in to."
        ),
        "rate_title": "Too many attempts",
        "rate_body": "Please wait a minute, then start again. Nothing was changed.",
        "error_title": "Something went wrong",
        "error_body": "Nothing was changed. Please try again in a moment.",
        "restart": "Start again",
        "reference": "Reference",
    },
    "es": {
        "title": "Inicio de sesión",
        "request_title": "Este inicio de sesión no puede continuar",
        "request_body": (
            "La solicitud venció, ya se utilizó o pertenece a otra ventana del "
            "navegador. No se cambió nada. Vuelve a empezar desde la aplicación "
            "en la que estabas entrando."
        ),
        "rate_title": "Demasiados intentos",
        "rate_body": "Espera un minuto y vuelve a empezar. No se cambió nada.",
        "error_title": "Algo salió mal",
        "error_body": "No se cambió nada. Inténtalo de nuevo en un momento.",
        "restart": "Volver a empezar",
        "reference": "Referencia",
    },
}


def _error_page(
    *,
    status_code: int,
    reason: str,
    request_id: Optional[str],
    locale: str,
    restart: Optional[str],
) -> HTMLResponse:
    from app.auth.hosted_page_style import SECURITY_CSP, SECURITY_CSS

    copy = _COPY.get(locale, _COPY[DEFAULT_HOSTED_LOCALE])
    if status_code == 429:
        heading, body = copy["rate_title"], copy["rate_body"]
    elif status_code >= 500:
        heading, body = copy["error_title"], copy["error_body"]
    else:
        heading, body = copy["request_title"], copy["request_body"]
    button = ""
    if restart:
        button = f'<p><a href="{html.escape(restart, quote=True)}">{copy["restart"]}</a></p>'
    reference = html.escape(reason)
    if request_id:
        reference += " · " + html.escape(request_id)
    page = (
        f'<!doctype html><html lang="{html_lang(locale)}"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        f"<title>{copy['title']} - Janua</title><style>{SECURITY_CSS}</style>"
        f"<body><main><h1>{heading}</h1><p>{body}</p>{button}"
        f"<p><small>{copy['reference']}: <code>{reference}</code></small></p>"
        "</main></body></html>"
    )
    return HTMLResponse(
        page,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": SECURITY_CSP,
        },
    )


@router.get("/error", include_in_schema=False)
async def hosted_error_page(request: Request, db=Depends(get_db)):
    """The hosted error page a refused navigation lands on (see module doc).

    Reads its query by hand so that nothing here can itself fail validation.
    The restart button is the client's REGISTERED origin, looked up from the
    registered client, never taken from the request.
    """
    query = request.query_params
    reason = query.get("reason") or "bad_request"
    if not _REASON.fullmatch(reason):
        reason = "bad_request"
    try:
        status_code = int(query.get("status") or 400)
    except ValueError:
        status_code = 400
    if not 400 <= status_code <= 599:
        status_code = 400
    request_id = query.get("ref")
    if request_id and not _REQUEST_ID.fullmatch(request_id):
        request_id = None
    restart = None
    client_id = query.get("client_id")
    if client_id and _CLIENT_ID.fullmatch(client_id):
        from app.routers.v1.auth import _recover_authorize_url_from_client

        try:
            restart = await _recover_authorize_url_from_client(client_id, db)
        except Exception as exc:  # the page must render even if the lookup fails
            logger.warning(
                "auth.hosted_error_page.restart_lookup_failed", error_type=type(exc).__name__
            )
            restart = None
    return _error_page(
        status_code=status_code,
        reason=reason,
        request_id=request_id,
        locale=_locale(request),
        restart=restart,
    )
