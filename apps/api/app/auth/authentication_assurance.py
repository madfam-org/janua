"""Authentication evidence belongs to a session, never to a refresh event."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select


def _epoch(value):
    if isinstance(value, datetime):
        return int(
            (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            ).timestamp()
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def assurance_claims(methods=None, authenticated_at=None, mfa_verified_at=None, sid=None):
    claims = {"amr": list(methods or [])}
    for name, value in (("auth_time", authenticated_at), ("mfa_time", mfa_verified_at)):
        stamp = _epoch(value)
        if stamp is not None:
            claims[name] = stamp
    if sid is not None:
        claims["sid"] = str(sid)
    return claims


def session_assurance(session):
    return assurance_claims(
        getattr(session, "authentication_methods", None),
        getattr(session, "authenticated_at", None),
        getattr(session, "mfa_verified_at", None),
        getattr(session, "id", None),
    )


def has_mfa_assurance(claims):
    methods = claims.get("amr", [])
    stamp = _epoch(claims.get("mfa_time"))
    now = int(datetime.now(timezone.utc).timestamp())
    return isinstance(methods, list) and "otp" in methods and stamp is not None and 0 <= now - stamp


async def require_recent_authentication(
    request, db, user, *, max_age_seconds=300, require_mfa=False
):
    """Strictly validate the caller's credential; refresh never supplies freshness."""
    from app.models import Session
    from app.services.auth_service import AuthService
    from app.services.token_revocation import session_is_live

    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else None
    token = token or request.cookies.get("janua_access_token")
    claims = await AuthService.verify_token(token) if token else None
    if not claims or claims.get("sub") != str(user.id):
        raise HTTPException(401, "Invalid or expired authentication")
    sid = claims.get("sid")
    if not sid:
        raise HTTPException(428, "A fresh session with authentication evidence is required")
    if sid:
        result = await db.execute(
            select(Session).where(Session.id == sid, Session.user_id == user.id)
        )
        session = result.scalar_one_or_none()
        if session is None or not session_is_live(session):
            raise HTTPException(401, "Authentication session is no longer active")
        stored = session_assurance(session)
        if any(claims.get(key) != stored.get(key) for key in ("amr", "auth_time", "mfa_time")):
            raise HTTPException(401, "Authentication evidence does not match the session")
        claims = {**claims, **stored}
    now = int(datetime.now(timezone.utc).timestamp())
    auth_time = _epoch(claims.get("auth_time"))
    factor_time = _epoch(claims.get("mfa_time")) if require_mfa else auth_time
    if (
        auth_time is None
        or factor_time is None
        or not 0 <= now - auth_time <= max_age_seconds
        or not 0 <= now - factor_time <= max_age_seconds
        or (require_mfa and not has_mfa_assurance(claims))
    ):
        raise HTTPException(
            428,
            (
                "Recent multi-factor authentication required"
                if require_mfa
                else "Recent authentication required"
            ),
        )
    return claims


async def user_requires_mfa(db, user, organization_id=None):
    from app.auth.mfa_enforcement import mfa_enrolled

    if mfa_enrolled(user):
        return True
    return await user_policy_requires_mfa(db, user, organization_id)


async def user_policy_requires_mfa(db, user, organization_id=None):
    """Mandatory policy only; voluntary enrollment must remain removable."""
    from app.services.organization_authentication_policy import member_requires_mfa

    if organization_id is not None:
        return await member_requires_mfa(db, user.id, organization_id)
    from app.models import OrganizationMember

    organizations = set()
    if getattr(user, "tenant_id", None):
        organizations.add(user.tenant_id)
    result = await db.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id, OrganizationMember.status == "active"
        )
    )
    organizations.update(result.scalars().all())
    for org_id in organizations:
        if await member_requires_mfa(db, user.id, org_id):
            return True
    return False


async def assurance_for_request(request, db, user):
    """Return evidence for the identity selected by the issuer's cookie resolver."""
    selected = getattr(request.state, "authentication_assurance", None)
    if isinstance(selected, dict):
        return await validate_live_assurance(db, user, selected)
    from app.auth.sso_cookie import SSO_COOKIE_NAME, resolve_sso_cookie_session
    from app.services.auth_service import AuthService

    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        claims = await AuthService.verify_token(header[7:])
        return (
            await validate_live_assurance(db, user, claims)
            if claims and claims.get("sub") == str(user.id)
            else {}
        )
    cookie = request.cookies.get(SSO_COOKIE_NAME)
    if cookie:
        cookie_user, session = await resolve_sso_cookie_session(cookie, db)
        if cookie_user is not None and str(cookie_user.id) == str(user.id):
            return session_assurance(session)
    token = request.cookies.get("janua_access_token")
    claims = await AuthService.verify_token(token) if token else None
    return (
        await validate_live_assurance(db, user, claims)
        if claims and claims.get("sub") == str(user.id)
        else {}
    )


async def validate_live_assurance(db, user, claims):
    """Resolve signed/code-bound evidence against its live session row."""
    from app.models import Session
    from app.services.token_revocation import session_is_live

    if not claims.get("sid"):
        return {}  # Legacy sessions never acquire stronger evidence by refresh.
    result = await db.execute(
        select(Session).where(Session.id == claims["sid"], Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None or not session_is_live(session):
        raise HTTPException(401, "Authentication session is no longer active")
    stored = session_assurance(session)
    if any(claims.get(key) != stored.get(key) for key in ("amr", "auth_time", "mfa_time")):
        raise HTTPException(401, "Authentication evidence does not match the session")
    return stored
