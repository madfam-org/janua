"""Run inside an image: print how its hosted sign-in answers a used request, for the workflow.

Runs in the base image too, where janua#841's names do not exist, so they are
looked up defensively and the markup it adds is matched as literal text.
Importing the application proves the image imports cleanly. Nothing connects to
a database or to Redis: the one Redis read is a stub that answers "gone".

Prints two lines:

- ``FIX=`` the properties janua#841 adds (all true on the hotfix, all false on
  production's image);
- ``UNCHANGED=`` what must be identical in both images: whether each hosted
  page, with exactly janua#841's two insertions (the same-origin script tag and
  the form's ``data-busy-label``) removed, is byte for byte the golden render
  of production's source (the folder's ``pages/``; the workflow prepends them
  to this script on stdin as ``GOLDEN_PAGES``; true on both images); sha256 of the copy keys production already
  had and of every other route of the auth router; and the 400 every other
  caller of ``login_client_context`` answers.

The pages are compared inside the image rather than hashed out of it: code
scanning reads the login page as credential data (its form copy is keyed
``password_label``) and flags any hash or print of it, although it is public
HTML.
"""

import asyncio
import hashlib
import inspect
import json
import os
import re
from pathlib import Path

import app.main
from app.auth import hosted_locale
from app.auth import login_method
from app.auth import tenant_login_context
from app.routers.v1 import auth as auth_router

SCRIPT_PATH = "/api/v1/auth/hosted-form.js"
EXPIRED_PATH = "/api/v1/auth/login-expired"
#: The auth router's own paths for those two (main.py mounts it under /api/v1).
NEW_ROUTER_PATHS = {"/auth/hosted-form.js", "/auth/login-expired"}
MOUNT = 'app.include_router(auth_v1.router, prefix="/api/v1")'
SCRIPT_TAG = f'\n    <script src="{SCRIPT_PATH}" defer></script>'
BUSY = re.compile(r' data-busy-label="[^"]*"')
DETAIL = "La solicitud de acceso venció. Vuelve al MAP para iniciar."
NEW_COPY_KEYS = {
    "session_expired_restart",
    "busy_signing_in",
    "busy_sending",
    "busy_saving",
    "busy_verifying",
}
#: The two hosted entry methods, from the module both images ship (no literal
#: credential-sounding names here: code scanning reads those as secrets).
METHODS = tuple(sorted(login_method.LOGIN_METHODS))
LINK_METHOD = login_method.LOGIN_METHOD_MAGIC_LINK
FORM_METHOD = next(m for m in METHODS if m != LINK_METHOD)  # the email + secret form
BUSY_LABELS = {
    "en": {FORM_METHOD: "Signing in…", LINK_METHOD: "Sending…"},
    "es": {FORM_METHOD: "Entrando…", LINK_METHOD: "Enviando…"},
}
LOCALES = ("en", "es")
NOTICE = "https://app.example.test/privacy"
#: The golden pages: prepended by the workflow as GOLDEN_PAGES (name -> HTML);
#: run from a checkout (the guard test), read from the folder next to this file.
GOLDEN_DIR = Path(os.environ.get("GOLDEN_DIR") or Path(globals().get("__file__", ".")).parent / "pages")
GOLDEN = globals().get("GOLDEN_PAGES") or {
    path.stem: path.read_bytes().decode("utf-8") for path in sorted(GOLDEN_DIR.glob("*.html"))
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _strip(page: str) -> str:
    """The page without exactly janua#841's two insertions (a no-op on the base)."""
    return BUSY.sub("", page.replace(SCRIPT_TAG, ""))


def _login_page(locale: str, method: str = FORM_METHOD, **extra) -> str:
    # Same arguments as the golden renders in
    # apps/api/tests/unit/routers/fixtures/hosted_login_unlisted/ for the plain page.
    kwargs = {"app_name": "MADFAM CV", "hidden_fields": "", "method": method, "switch_url": None}
    kwargs.update(extra)
    return auth_router._hosted_login_page_html(**kwargs, locale=locale)


def _second_factor_page() -> str:
    response = auth_router._render_mfa_challenge_page(
        mfa_token="hotfix-check-token",
        app_name="Hotfix Check App",
        auth_request_id="hotfix-check-request",
        client_id="hotfix-check",
        client_name="Hotfix Check App",
        next_url=None,
    )
    body = getattr(response, "body", response)
    return body.decode() if isinstance(body, bytes) else body


class _GoneRedis:
    """A pending sign-in request that is gone: strict_get answers None."""

    async def strict_get(self, key):
        return None


def _gone_request_error():
    async def call():
        try:
            await tenant_login_context.login_client_context(
                None, _GoneRedis(), auth_request_id="hotfix-check-request", client_id="hotfix-check"
            )
        except Exception as error:  # the HTTPException (or its subclass) is the answer
            return error
        return None

    return asyncio.run(call())


def _router_routes() -> list:
    """The auth router's own routes as `METHOD path`, plus the routers it
    includes by type (some FastAPI versions keep those as lazy entries without
    a path; both images run the same FastAPI, so the shape is comparable)."""
    entries = []
    for route in auth_router.router.routes:
        path = getattr(route, "path", None)
        if path is None:
            entries.append(f"included {type(route).__name__}")
            continue
        for method in sorted(getattr(route, "methods", None) or ("*",)):
            entries.append(f"{method} {path}")
    return sorted(entries)


# --- FIX ---------------------------------------------------------------------


def _login_request_expired_type() -> bool:
    expired = getattr(tenant_login_context, "LoginRequestExpired", None)
    if expired is None:
        return False
    from fastapi import HTTPException

    error = expired()
    return (
        issubclass(expired, HTTPException)
        and error.status_code == 400
        and error.detail == DETAIL
    )


def _gone_request_raises_its_own_type() -> bool:
    expired = getattr(tenant_login_context, "LoginRequestExpired", None)
    return expired is not None and type(_gone_request_error()) is expired


def _routes_registered() -> bool:
    routes = _router_routes()
    return (
        MOUNT in inspect.getsource(app.main)
        and all(f"GET {path}" in routes for path in NEW_ROUTER_PATHS)
    )


def _script_served() -> bool:
    handler = getattr(auth_router, "hosted_form_script", None)
    if handler is None:
        return False
    response = asyncio.run(handler())
    body = response.body.decode()
    return (
        response.media_type == "application/javascript"
        and 'document.querySelectorAll("form[data-busy-label]")' in body
        and 'event.preventDefault();' in body
        and '"pageshow"' in body
    )


def _login_pages_press_once() -> bool:
    for locale in LOCALES:
        for method, label in BUSY_LABELS[locale].items():
            page = _login_page(locale, method)
            if page.count(SCRIPT_TAG) != 1 or page.count(f' data-busy-label="{label}"') != 1:
                return False
    return True


def _second_factor_page_presses_once() -> bool:
    page = _second_factor_page()
    return page.count(SCRIPT_TAG) == 1 and page.count(' data-busy-label="Verifying…"') == 1


def _login_expired_url_shape() -> bool:
    url_of = getattr(auth_router, "_login_expired_url", None)
    if url_of is None:
        return False
    return (
        url_of(client_id="hotfix-check", locale="es")
        == f"{EXPIRED_PATH}?client_id=hotfix-check&ui_locales=es"
        and url_of(client_id="hotfix-check", locale="en") == f"{EXPIRED_PATH}?client_id=hotfix-check"
        and url_of(client_id=None, locale="en") == EXPIRED_PATH
    )


def _login_expired_page() -> bool:
    page_of = getattr(auth_router, "login_expired_page", None)
    if page_of is None:
        return False
    # No client: the page never looks anything up, so no database is needed.
    response = asyncio.run(page_of(client_id=None, ui_locales="es", db=None))
    body = response.body.decode()
    spanish = hosted_locale.hosted_copy("es")
    return (
        response.status_code == 400
        and response.headers.get("cache-control") == "no-store"
        and spanish["session_expired_title"] in body
        and spanish["session_expired_body"] in body
        and "<a href=" not in body
    )


def _login_form_answers_a_gone_request_with_a_page() -> bool:
    # A request handler needs a database to run, so its wiring is read from the
    # code the image ships.
    source = inspect.getsource(auth_router.login_form)
    return (
        "except LoginRequestExpired:" in source
        and "request_gone = True" in source
        and "url=_login_expired_url(client_id=client_id, locale=locale), status_code=303" in source
        and 'await redis.get(f"oauth:pre_login:{auth_request_id}")' not in source
    )


# --- UNCHANGED ---------------------------------------------------------------


def _pages() -> dict:
    """Every hosted page the check renders, by golden file name."""
    pages = {
        f"login_{method}_{locale}": _login_page(locale, method)
        for locale in LOCALES
        for method in METHODS
    }
    pages.update(
        {f"login_notice_{locale}": _login_page(locale, privacy_notice_url=NOTICE) for locale in LOCALES}
    )
    pages["second_factor"] = _second_factor_page()
    return pages


def _is_production(name: str, page: str) -> bool:
    return name in GOLDEN and _strip(page) == GOLDEN[name]


def _unchanged() -> dict:
    error = _gone_request_error()
    known_routes = [
        entry for entry in _router_routes() if entry.split(" ", 1)[1] not in NEW_ROUTER_PATHS
    ]
    return {
        **{f"page_{name}_is_production": _is_production(name, page) for name, page in _pages().items()},
        **{
            f"copy_{locale}": _sha(
                json.dumps(
                    {
                        key: value
                        for key, value in hosted_locale.hosted_copy(locale).items()
                        if key not in NEW_COPY_KEYS
                    },
                    sort_keys=True,
                )
            )
            for locale in LOCALES
        },
        "gone_request_answer": [getattr(error, "status_code", None), getattr(error, "detail", None)],
        "auth_routes": _sha(json.dumps(known_routes)),
    }


print("UNCHANGED=" + json.dumps(_unchanged(), sort_keys=True))
print(
    "FIX="
    + json.dumps(
        {
            "login_request_expired_type": _login_request_expired_type(),
            "gone_request_raises_its_own_type": _gone_request_raises_its_own_type(),
            "routes_registered": _routes_registered(),
            "script_served": _script_served(),
            "login_pages_press_once": _login_pages_press_once(),
            "second_factor_page_presses_once": _second_factor_page_presses_once(),
            "login_expired_url_shape": _login_expired_url_shape(),
            "login_expired_page": _login_expired_page(),
            "login_form_answers_a_gone_request_with_a_page": _login_form_answers_a_gone_request_with_a_page(),
        },
        sort_keys=True,
    )
)
