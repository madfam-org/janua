"""Operator invitations to an invite-only client — invite / revoke — and its entry route.

An invite-only client (``settings.INVITE_ONLY_CLIENTS``, see
``services/invite_only_clients.py``) admits only people entitled to its product.
These endpoints are how an operator lets one person in, and out:

``POST /api/v1/internal/product-invites``
    Ensures the person's platform identity (passwordless, created if absent),
    grants the client's product as an ADMIN_GRANT entitlement, and mails ONE
    message naming the client with a single-use sign-in link
    (``PRODUCT_INVITE_LINK_TTL_HOURS``, default 72). Idempotent: calling it
    again mails a fresh link — that is the "resend".

``POST /api/v1/internal/product-invites/revoke``
    Cancels the entitlement (``expires_at = now``; the row and its audit history
    stay) and spends any invitation link not yet used. The person keeps their
    Janua identity; they lose the client at their next authorize or refresh.

``GET /api/v1/auth/app-entry``
    Where the invitation link lands after Janua's callback has set the session:
    a 302 to the client's front door (the origin of its registered redirect
    URI). The callback appends ``?token=`` to its destination by contract; this
    route drops it, so an access token never reaches a product URL, a browser
    history entry on the product's host, or a product's request log.

Auth: ``verify_internal_api_key`` on the internal routes, the same seam as
``internal_users.py``. The public edge answers 403 for ``/api/v1/internal/*``;
operators call these from inside the janua-api pod.

PRIVACY: the address is never logged, never written into an audit ``details``
blob, never returned except as the caller sent it, and the link token is never
returned at all.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Literal, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.hosted_locale import UI_LOCALES_PARAM
from app.config import settings
from app.core.url_security import validate_redirect_url
from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.models import EntitlementSource, MagicLink, OAuthClient, User, UserStatus
from app.routers.v1.oauth_clients import INTERNAL_API_KEY_PRINCIPAL
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.email_service import send_product_invite_email_task
from app.services.entitlements_service import (
    cancel_entitlement,
    get_active_user_grant_tiers,
    upsert_entitlement,
)
from app.services.invite_only_clients import DEFAULT_INVITE_TIER, invite_only_product
from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    get_user_by_email,
    log_ambiguous_email,
    resolve_user_by_email_across_pools,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/product-invites", tags=["internal"])
entry_router = APIRouter(prefix="/auth", tags=["auth"])

#: The public path the invitation link lands on (after Janua's callback).
APP_ENTRY_PATH = "/api/v1/auth/app-entry"

NO_USER_DETAIL = "No janua user for that address"


class ProductInviteRequest(BaseModel):
    email: EmailStr
    client_id: str = Field(min_length=1, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=255)
    tier: str = Field(default=DEFAULT_INVITE_TIER, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    #: The invitation's language; also stored as a NEW account's locale.
    locale: Literal["es", "en"] = "es"
    #: Spanish register of the mail (es only). Absent = `usted`.
    formality: Optional[Literal["tu", "usted"]] = None


class ProductInviteResponse(BaseModel):
    user_id: str
    user_created: bool
    client_id: str
    product: str
    tier: str
    #: False when the person already held an active entitlement (a resend).
    entitlement_granted: bool
    link_expires_at: datetime
    email_queued: bool


class ProductInviteRevokeRequest(BaseModel):
    email: EmailStr
    client_id: str = Field(min_length=1, max_length=255)


class ProductInviteRevokeResponse(BaseModel):
    user_id: str
    client_id: str
    product: str
    #: False when there was no active entitlement to cancel.
    changed: bool
    links_spent: int


def _normalize_email(email: str) -> str:
    """Same fold as internal_users: one address, one identity."""
    return email.strip().lower()


def _redacted(user_id: object) -> str:
    return f"{str(user_id)[:8]}…"


def _entry_url(client_id: str, locale: str) -> str:
    query = urlencode({"client_id": client_id, UI_LOCALES_PARAM: locale})
    return f"{settings.public_base_url.rstrip('/')}{APP_ENTRY_PATH}?{query}"


async def _invite_only_client(db: AsyncSession, client_id: str) -> tuple[OAuthClient, str]:
    """The active client and its product, or the operator-facing refusal."""
    product = invite_only_product(client_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Client is not invite-only: list it in INVITE_ONLY_CLIENTS "
                "(client_id=product) before inviting anyone to it"
            ),
        )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="INVITE_ONLY_CLIENTS names this client without a valid product",
        )
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active == True,  # noqa: E712 — SQLAlchemy comparator
        )
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active OAuth client")
    return client, product


async def _find_person(db: AsyncSession, email: str) -> Optional[User]:
    """The one identity holding ``email``: platform pool first, then any pool."""
    user = await get_user_by_email(db, email, tenant_id=None)
    if user is not None:
        return user
    try:
        return await resolve_user_by_email_across_pools(db, email, active_only=False)
    except AmbiguousEmailAcrossPools as exc:
        log_ambiguous_email(exc, entry_point="internal_product_invite")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That address exists in more than one identity pool; reconcile it first",
        ) from exc


async def _audit(db: AsyncSession, event_type: AuditEventType, *, user_id: str, details: dict) -> None:
    """Best-effort hash-chain audit row (never the address, never the token)."""
    try:
        await AuditLogger(db).log(
            event_type=event_type,
            tenant_id=user_id,
            identity_id=None,
            resource_type="user_entitlement",
            resource_id=user_id,
            details={"actor": INTERNAL_API_KEY_PRINCIPAL, **details},
            severity="info",
        )
    except Exception:
        pass


@router.post("", response_model=ProductInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_to_product(
    body: ProductInviteRequest,
    background_tasks: BackgroundTasks,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductInviteResponse:
    """Let one person into an invite-only client and mail them ONE sign-in link."""
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email is not enabled: the invitation could not be delivered",
        )
    client, product = await _invite_only_client(db, body.client_id)
    entry_url = _entry_url(client.client_id, body.locale)
    if validate_redirect_url(entry_url, default_url=None) is None:
        # Fail visible: a link whose destination the callback will refuse is a
        # dead invitation the person cannot fix.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Janua's public origin is not on its own redirect allow-list",
        )

    email = _normalize_email(str(body.email))
    user = await _find_person(db, email)
    user_created = False
    if user is not None and user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That account is not active; reactivate it before inviting it",
        )
    if user is None:
        user = User(
            email=email,
            # Passwordless by construction, like internal provisioning: the
            # invitee signs in by link and may set a password later.
            password_hash=None,
            first_name=body.first_name,
            status=UserStatus.ACTIVE,
            email_verified=False,
            email_verified_at=None,
            is_admin=False,
            user_metadata={},
            tenant_id=None,
            locale=body.locale,
        )
        db.add(user)
        await db.flush()
        user_created = True

    active_before = await get_active_user_grant_tiers(user.id, db)
    await upsert_entitlement(
        db,
        user_id=user.id,
        product=product,
        tier=body.tier,
        source=EntitlementSource.ADMIN_GRANT,
        expires_at=None,
    )

    expires_at = datetime.utcnow() + timedelta(hours=settings.PRODUCT_INVITE_LINK_TTL_HOURS)
    token = secrets.token_urlsafe(32)
    db.add(
        MagicLink(
            user_id=user.id,
            email=user.email,
            token=token,
            redirect_url=entry_url,
            expires_at=expires_at,
        )
    )
    user_id = str(user.id)
    await _audit(
        db,
        AuditEventType.ENTITLEMENT_GRANT,
        user_id=user_id,
        details={
            "via": "internal.product_invites.invite",
            "client_id": client.client_id,
            "product": product,
            "tier": body.tier,
            "user_created": user_created,
            "source": EntitlementSource.ADMIN_GRANT.value,
        },
    )
    await db.commit()

    background_tasks.add_task(
        send_product_invite_email_task,
        user.email,
        token,
        app_name=client.name or client.client_id,
        expires_hours=settings.PRODUCT_INVITE_LINK_TTL_HOURS,
        locale=body.locale,
        formality=body.formality,
        first_name=body.first_name,
    )
    logger.info(
        "product_invite.queued",
        user=_redacted(user_id),
        client_id=client.client_id,
        product=product,
        user_created=user_created,
    )
    return ProductInviteResponse(
        user_id=user_id,
        user_created=user_created,
        client_id=client.client_id,
        product=product,
        tier=body.tier,
        entitlement_granted=product not in active_before,
        link_expires_at=expires_at,
        email_queued=True,
    )


@router.post("/revoke", response_model=ProductInviteRevokeResponse)
async def revoke_product_invite(
    body: ProductInviteRevokeRequest,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductInviteRevokeResponse:
    """Take one person out of an invite-only client. Idempotent."""
    client, product = await _invite_only_client(db, body.client_id)
    user = await _find_person(db, _normalize_email(str(body.email)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_USER_DETAIL)

    active_before = await get_active_user_grant_tiers(user.id, db)
    changed = product in active_before
    if changed:
        await cancel_entitlement(db, user_id=user.id, product=product)

    # Spend every unused invitation link for THIS client, so a link still in
    # the person's inbox cannot open a session meant for an access they no
    # longer have.
    entry_prefix = f"{settings.public_base_url.rstrip('/')}{APP_ENTRY_PATH}?"
    pending = (
        await db.execute(
            select(MagicLink).where(
                MagicLink.user_id == user.id,
                MagicLink.used_at.is_(None),
                MagicLink.redirect_url.like(f"{entry_prefix}%"),
            )
        )
    ).scalars().all()
    spent = [
        link
        for link in pending
        if parse_qs(urlparse(link.redirect_url or "").query).get("client_id") == [client.client_id]
    ]
    if spent:
        await db.execute(
            update(MagicLink)
            .where(MagicLink.id.in_([link.id for link in spent]))
            .values(used_at=datetime.utcnow())
        )

    user_id = str(user.id)
    if changed or spent:
        await _audit(
            db,
            AuditEventType.ENTITLEMENT_REVOKE,
            user_id=user_id,
            details={
                "via": "internal.product_invites.revoke",
                "client_id": client.client_id,
                "product": product,
                "entitlement_cancelled": changed,
                "links_spent": len(spent),
            },
        )
    await db.commit()
    logger.info(
        "product_invite.revoked",
        user=_redacted(user_id),
        client_id=client.client_id,
        product=product,
        changed=changed,
        links_spent=len(spent),
    )
    return ProductInviteRevokeResponse(
        user_id=user_id,
        client_id=client.client_id,
        product=product,
        changed=changed,
        links_spent=len(spent),
    )


def _front_door(client: OAuthClient) -> Optional[str]:
    """The origin of the client's first registered https redirect URI, with a slash."""
    uris = client.redirect_uris or []
    if isinstance(uris, str):
        import json

        try:
            uris = json.loads(uris)
        except json.JSONDecodeError:
            uris = []
    for uri in uris:
        if not isinstance(uri, str):
            continue
        parsed = urlparse(uri)
        local = parsed.hostname in ("localhost", "127.0.0.1")
        if parsed.netloc and (parsed.scheme == "https" or (local and parsed.scheme == "http")):
            return f"{parsed.scheme}://{parsed.netloc}/"
    return None


@entry_router.get("/app-entry")
async def app_entry(
    client_id: str = Query(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """302 to the client's front door; any ``token`` query parameter is dropped.

    Only active clients with a registered https redirect URI have a front door;
    anything else is a 404, never an open redirect. The URL's ``ui_locales``
    served the interstitial before it; the product picks its own language.
    """
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active == True,  # noqa: E712 — SQLAlchemy comparator
        )
    )
    client = result.scalar_one_or_none()
    destination = _front_door(client) if client is not None else None
    if destination is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown application")
    return RedirectResponse(
        url=destination,
        status_code=302,
        # The security-headers middleware sets Referrer-Policy
        # strict-origin-when-cross-origin, so the product sees only Janua's
        # origin as referrer, never this URL's query.
        headers={"cache-control": "no-store"},
    )
