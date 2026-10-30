"""Hosted, cookie-bound factor enrollment/challenge continuations."""

import base64
import hashlib
import html
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import pyotp
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.auth.authentication_assurance import (
    assurance_for_request,
    user_requires_mfa,
)
from app.auth.tenant_login_context import login_client_context
from app.core.redis import get_redis
from app.database import get_db
from app.models import User, UserStatus
from app.services.account_lockout_service import AccountLockoutService
from app.services.auth_service import AuthService

router = APIRouter()
COOKIE = "__Host-janua_factor_flow"
TTL = 600

# Fixed issuer-owned CSS. Its CSP hash allows this exact style block without
# permitting arbitrary inline styles, scripts, remote fonts, or trackers.
SECURITY_CSS = """
:root{color-scheme:light;--paper:#fff;--ground:#f4f5f7;--ink:#1b1c2e;--line:#d8dbe3;--control-line:#6d7386;--accent:#4338a6}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--paper:#1e2030;--ground:#14151f;--ink:#ece6f5;--line:#53586f;--control-line:#8b92ad;--accent:#c1baff}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;padding:1rem;background:var(--ground);color:var(--ink);font:1rem/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{width:100%;max-width:32rem;margin:1rem auto;padding:1.5rem;background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow-wrap:anywhere}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 1rem}h2{font-size:1.2rem;line-height:1.4}
img{display:block;max-width:100%;height:auto;margin:1rem auto}
form,label{display:grid;gap:.5rem}form{gap:1rem;margin-top:1.5rem}
input,button{font:inherit;min-height:44px;width:100%;padding:.65rem .8rem;border:1px solid var(--control-line);border-radius:8px}
input{background:var(--paper);color:var(--ink)}
button{cursor:pointer;font-weight:600;background:var(--paper);color:var(--ink)}
button:hover{border-color:var(--accent)}a{color:var(--accent);text-underline-offset:.2em}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}code{overflow-wrap:anywhere}
"""
SECURITY_STYLE_HASH = base64.b64encode(hashlib.sha256(SECURITY_CSS.encode()).digest()).decode()
SECURITY_CSP = (
    f"default-src 'none'; style-src 'sha256-{SECURITY_STYLE_HASH}'; "
    "img-src data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


def _page(body, status=200):
    return HTMLResponse(
        '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        "<title>Seguridad de tu cuenta</title><style>"
        + SECURITY_CSS
        + "</style><body><main><h1>Seguridad de tu cuenta</h1>"
        + body
        + "</main></body></html>",
        status_code=status,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": SECURITY_CSP,
        },
    )


def _form(flow_id, secret=None, error=None, account=None):
    from app.routers.v1.mfa import generate_qr_code

    identity = "<p>Cuenta: <strong>" + html.escape(account or "Tu cuenta") + "</strong></p>"
    body = "<p>Confirma tu segundo factor para continuar.</p>"
    if secret:
        uri = pyotp.TOTP(secret).provisioning_uri(name=account or "Tu cuenta", issuer_name="Janua")
        body = (
            "<p>Agrega esta cuenta a tu aplicación de autenticación y guarda los códigos de recuperación que se mostrarán al confirmar.</p>"
            f'<img alt="Código para tu aplicación de autenticación" src="{generate_qr_code(uri)}">'
            f"<p>Clave manual: <code>{html.escape(secret)}</code></p>"
        )
    if error:
        body += f'<p role="alert">{html.escape(error)}</p>'
    return (
        identity
        + body
        + (
            '<form method="post" action="/api/v1/auth/factor/complete">'
            f'<input type="hidden" name="flow_id" value="{html.escape(flow_id)}">'
            '<label>Código de tu aplicación o de recuperación <input name="code" required autocomplete="one-time-code"></label>'
            "<button>Confirmar y continuar</button></form>"
        )
    )


async def start_factor_flow(
    request,
    db,
    user,
    *,
    methods,
    authenticated_at,
    auth_request_id=None,
    client_id=None,
    next_url="/",
    organization_id=None,
):
    if user.status != UserStatus.ACTIVE or not user.is_active:
        raise HTTPException(403, "Esta cuenta no está activa")
    redis = await get_redis()
    client, _ = await login_client_context(
        db,
        redis,
        auth_request_id=auth_request_id,
        client_id=client_id,
        return_url=next_url if next_url.startswith("https://") else None,
    )
    org_id = getattr(client, "organization_id", None) or organization_id or user.tenant_id
    # If the caller selected a client pool, the identity must belong to it.
    if client is not None and str(user.tenant_id) != str(client.organization_id):
        raise HTTPException(403, "La cuenta no pertenece a esta organización")
    flow_id, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    setup_secret = None if user.mfa_enabled and user.mfa_secret else pyotp.random_base32()
    data = {
        "user_id": str(user.id),
        "binding": hashlib.sha256(binding.encode()).hexdigest(),
        "methods": methods,
        "auth_time": int(authenticated_at),
        "auth_request_id": auth_request_id,
        "client_id": client_id,
        "next": next_url,
        "organization_id": str(org_id) if org_id else None,
        "setup_secret": setup_secret,
    }
    await redis.strict_set("auth:factor:" + flow_id, json.dumps(data), ex=TTL)
    recovery_url = "/api/v1/auth/forgot-password?" + urlencode(
        {
            "client_id": client_id or "",
            "auth_request_id": auth_request_id or "",
            "return_url": next_url if next_url.startswith("https://") else "",
            "ui_locales": "es",
        }
    )
    response = _page(
        '<p><a href="'
        + html.escape(recovery_url, quote=True)
        + '">Crear o recuperar mi contraseña</a></p>'
        + _form(flow_id, setup_secret, account=user.email)
    )
    response.set_cookie(
        COOKIE, binding, secure=True, httponly=True, samesite="lax", path="/", max_age=TTL
    )
    return response


@router.post("/factor/complete")
async def complete_factor(
    request: Request, flow_id: str = Form(...), code: str = Form(...), db=Depends(get_db)
):
    from app.routers.v1.auth import _resolve_oauth_redirect_target, _set_session_cookies
    from app.routers.v1.mfa import (
        consume_backup_code,
        consume_totp,
        generate_backup_codes,
        hash_backup_code,
    )

    redis = await get_redis()
    raw = await redis.strict_get("auth:factor:" + flow_id)
    if not raw:
        raise HTTPException(400, "La verificación venció. Vuelve a iniciar sesión.")
    data = json.loads(raw)
    binding = request.cookies.get(COOKIE, "")
    if not binding or not secrets.compare_digest(
        data["binding"], hashlib.sha256(binding.encode()).hexdigest()
    ):
        raise HTTPException(403, "La verificación pertenece a otro navegador")
    if await redis.strict_exists("auth:factor:used:" + flow_id):
        raise HTTPException(400, "La verificación ya se utilizó")
    # A bounded, atomic attempt budget independent of IP and token reminting.
    admitted = False
    for attempt in range(5):
        if await redis.strict_set_nx(f"auth:factor:attempt:{flow_id}:{attempt}", "1", ex=TTL):
            admitted = True
            break
    if not admitted:
        raise HTTPException(429, "Demasiados intentos. Vuelve a iniciar sesión.")
    client, _ = await login_client_context(
        db,
        redis,
        auth_request_id=data["auth_request_id"],
        client_id=data["client_id"],
        return_url=data["next"] if data["next"].startswith("https://") else None,
    )
    result = await db.execute(
        select(User)
        .where(User.id == data["user_id"])
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE or not user.is_active:
        raise HTTPException(403, "Esta cuenta no está activa")
    org_id = getattr(client, "organization_id", None) or user.tenant_id
    if str(org_id) != str(data["organization_id"]) or (
        client and str(user.tenant_id) != str(client.organization_id)
    ):
        raise HTTPException(403, "La organización cambió")
    if client is not None:
        from app.auth.tenant_login_context import require_client_membership

        await require_client_membership(db, user, client)
    # Re-read policy before issuing anything; failures propagate closed.
    await user_requires_mfa(db, user, org_id)
    locked, _ = AccountLockoutService.is_account_locked(user)
    if locked:
        raise HTTPException(429, "La cuenta está temporalmente bloqueada")
    secret = data["setup_secret"] or user.mfa_secret
    if not secret or (not data["setup_secret"] and not user.mfa_enabled):
        raise HTTPException(400, "La configuración del segundo factor cambió")
    # Never overwrite a factor enabled in another concurrent continuation.
    if data["setup_secret"] and user.mfa_enabled:
        raise HTTPException(409, "El segundo factor ya se configuró. Vuelve a iniciar sesión.")
    valid = await consume_totp(user, secret, code, redis)
    if not valid and not data["setup_secret"]:
        valid = consume_backup_code(user, code)
    if not valid:
        await AccountLockoutService.record_failed_attempt(
            db,
            user,
            ip_address=request.client.host if request.client else None,
        )
        return _page(
            _form(flow_id, data["setup_secret"], "El código no es válido.", account=user.email), 401
        )
    if not await redis.strict_set_nx("auth:factor:used:" + flow_id, "1", ex=TTL):
        raise HTTPException(400, "La verificación ya se utilizó")
    backup_codes = []
    if data["setup_secret"]:
        backup_codes = generate_backup_codes()
        user.mfa_secret, user.mfa_enabled = secret, True
        user.mfa_backup_codes = [
            {
                "hash": hash_backup_code(value),
                "used": False,
                "created_at": datetime.utcnow().isoformat(),
            }
            for value in backup_codes
        ]
    now = datetime.utcnow()
    methods = list(dict.fromkeys([*data["methods"], "otp"]))
    access, refresh, session = await AuthService.create_session(
        db,
        user,
        authentication_methods=methods,
        authenticated_at=datetime.utcfromtimestamp(data["auth_time"]),
        mfa_verified_at=now,
        audience=getattr(client, "audience", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await AccountLockoutService.reset_failed_attempts(db, user)
    target = await _resolve_oauth_redirect_target(
        auth_request_id=data["auth_request_id"],
        client_id=data["client_id"],
        next_url=data["next"],
        redis=redis,
        db=db,
    )
    if data["auth_request_id"]:
        await redis.strict_delete("oauth:pre_login:" + data["auth_request_id"])
    await redis.strict_delete("auth:factor:" + flow_id)
    if backup_codes:
        # Render exactly once with a safe issuer/local or registered return URL.
        response = _page(
            "<p>Cuenta: <strong>"
            + html.escape(user.email)
            + "</strong></p><h2>Guarda tus códigos de recuperación</h2><p>Se muestran una sola vez.</p><pre>"
            + html.escape("\n".join(backup_codes))
            + '</pre><a href="'
            + html.escape(target, quote=True)
            + '">Continuar</a>'
        )
    else:
        response = RedirectResponse(target, 303)
    _set_session_cookies(response, access, refresh, user=user, session=session, request=request)
    response.delete_cookie(COOKIE, path="/")
    return response


@router.get("/security")
async def security_page(request: Request, client_id: str, return_url: str, db=Depends(get_db)):
    from app.routers.v1.oauth_provider import get_user_from_cookie_or_header

    redis = await get_redis()
    client, _ = await login_client_context(db, redis, client_id=client_id, return_url=return_url)
    user = await get_user_from_cookie_or_header(request, db)
    local_url = "/api/v1/auth/security?" + urlencode(
        {"client_id": client_id, "return_url": return_url}
    )
    if user is None:
        return RedirectResponse(
            "/api/v1/auth/login?"
            + urlencode({"client_id": client_id, "next": local_url, "ui_locales": "es"}),
            303,
        )
    if user.status != UserStatus.ACTIVE or not user.is_active:
        raise HTTPException(403, "Esta cuenta no está activa")
    if str(user.tenant_id) != str(client.organization_id):
        raise HTTPException(403, "La cuenta no pertenece a esta organización")
    evidence = await assurance_for_request(request, db, user)
    now = int(datetime.now(timezone.utc).timestamp())
    if (
        not isinstance(evidence.get("auth_time"), int)
        or not 0 <= now - evidence["auth_time"] <= 300
    ):
        return RedirectResponse(
            "/api/v1/auth/login?"
            + urlencode({"client_id": client_id, "next": local_url, "ui_locales": "es"}),
            303,
        )
    # Enrollment / reauthentication starts from a proven recent primary factor.
    return await start_factor_flow(
        request,
        db,
        user,
        methods=evidence.get("amr", []),
        authenticated_at=evidence["auth_time"],
        client_id=client_id,
        next_url=return_url,
        organization_id=client.organization_id,
    )
