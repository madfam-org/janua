"""Issuing sign-in links: POST /auth/magic-link and the shared issuing path.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.locale import locale_from_request
from app.database import get_db
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_schemas import MagicLinkRequest
from app.routers.v1.auth_shared import (
    _invite_only_destination,
    _map_mail_organization,
    _preferred_pool_for_redirect,
    logger,
    router,
)
from app.services.email_send_audit import CORRELATION_HEADER, attach_issuance, uuid_metadata
from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    log_ambiguous_email,
    resolve_user_by_email_across_pools,
)

from ...models import MagicLink, User, UserStatus


@router.post("/magic-link")
# Rate limits live in `_issue_magic_link` (app/auth/magic_link_limits.py): per
# ADDRESS (MAGIC_LINK_EMAIL_RATE_LIMIT) plus a per-caller ceiling (trusted
# service key, or client IP via TRUSTED_PROXIES). Until 2026-10-07 this was a
# slowapi decorator at MAGIC_LINK_RATE_LIMIT keyed on `request.client.host` —
# the tunnel pod's address for every public request, so one 5/hour bucket was
# shared by every person signing in to the MAP through its server.
async def send_magic_link(
    request: Request,
    magic_link_data: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Send magic link for passwordless signin; response never enumerates accounts."""
    correlation = uuid.uuid4()
    request.state.mail_correlation_id = correlation
    # Always present on the neutral 2xx response, including unknown/invite-only
    # users. Presence is never a signal that an account or a send exists.
    if response is not None:
        response.headers[CORRELATION_HEADER] = str(correlation)
    await _issue_magic_link(request, magic_link_data, background_tasks, db)
    return {"message": "Magic link sent to email"}


async def _issue_magic_link(
    request: Request,
    magic_link_data: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db,
    *,
    client_id: Optional[str] = None,
    email_locale: Optional[str] = None,
) -> Optional[User]:
    """Find-or-create the user, mint the link, queue the email.

    This is the body of POST /magic-link, lifted so the hosted login page
    (POST /login-form/magic-link, 2026-09-17) issues links through the very
    same pool resolution, allow-list check and mailer. Raises HTTPException
    exactly as the endpoint does; the caller decides how to render it.

    INVITE-ONLY CLIENTS (2026-10-22): when the link is for an invite-only
    client (`client_id`, or the destination's client) and no account exists,
    NOTHING is created, minted or sent, and this returns None. The callers
    answer exactly as for a sent link, so the response never tells a stranger
    whether an address is invited. `email_locale` is the language of the page
    the person asked from; it outranks the stored profile for this one mail.
    """
    if not settings.ENABLE_MAGIC_LINKS:
        raise HTTPException(status_code=403, detail="Magic links are disabled")

    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Rate limits FIRST: before any lookup or write, so a 429 depends only on
    # request counts — never on whether the address has an account — and an
    # over-limit caller costs no database work. Per address, plus a per-caller
    # ceiling (see app/auth/magic_link_limits.py).
    await _auth_shared.enforce_magic_link_limits(request, magic_link_data.email)

    # Find or create user. The untenanted / staff pool is still the primary
    # meaning of this bare-email platform entry (see /signin note), but a MISS
    # there may not mean "no such user":
    #
    #   The internal provisioning API writes users WITH a tenant_id — CTM
    #   staff, provisioned by crea-map. Those rows are invisible to the
    #   untenanted lookup, so this handler fell through to the create branch
    #   and, under the then-global unique index ix_users_email, the INSERT hit
    #   it → IntegrityError → 503. The requesting product showed «revisa tu
    #   correo» and no link was ever sent (2026-09-03, 21 users).
    #
    # So on a miss, resolve across pools before considering a create. Migration
    # 013 is APPLIED in production now (2026-09-06; the ledger is
    # apps/api/alembic/PROD_ALEMBIC_STATE.json, converged at
    # 016_org_member_app_roles), so ix_users_email is gone and that resolution
    # is no longer exact: one address may legitimately hold a row in the
    # platform pool and in N tenant pools. The redirect host's OAuth client
    # supplies the preferred pool; when it cannot decide, the resolver raises
    # and this handler answers 400 rather than signing anyone into an arbitrary
    # tenant. That 400 is REACHABLE in production — it was not, before 013.
    safe_redirect_url = magic_link_data.redirect_url
    # The audit store is checked BEFORE account lookup. An outage must not
    # distinguish an existing identity from an unknown invite-only address.
    mail_audit_id = None
    map_client = await _auth_shared._map_mail_client(db, safe_redirect_url, client_id)
    if map_client is not None:
        safe_redirect_url = _auth_shared.validate_redirect_url(magic_link_data.redirect_url, default_url=None)
        if safe_redirect_url is None:
            raise HTTPException(status_code=400, detail="MAP login redirect is not allowed")
        correlation = (
            uuid_metadata(getattr(request.state, "mail_correlation_id", None)) or uuid.uuid4()
        )
        try:
            mail_audit_id = await _auth_shared.add_intent(
                db,
                audit_id=correlation,
                source_app="crea-map",
                message_kind="magic_login",
                trigger_kind="map_login_request",
                provenance="registered_map_login",
                org_id=_map_mail_organization(map_client, safe_redirect_url),
            )
            await db.commit()
        except Exception as error:
            await db.rollback()
            raise HTTPException(status_code=503, detail="Login mail audit unavailable") from error

    user = await _auth_shared.get_user_by_email(db, magic_link_data.email, tenant_id=None, active_only=True)

    if not user:
        # Hoisted out of the call below only so the log line can say WHICH pool
        # was preferred — the single most useful field when asking why the
        # preference failed to resolve. Same call, same arguments, same order.
        preferred_tenant_id = await _preferred_pool_for_redirect(db, magic_link_data.redirect_url)
        try:
            user = await resolve_user_by_email_across_pools(
                db,
                magic_link_data.email,
                preferred_tenant_id=preferred_tenant_id,
                active_only=True,
            )
        except AmbiguousEmailAcrossPools as exc:
            # Refuse rather than sign someone into an arbitrary tenant.
            log_ambiguous_email(
                exc,
                entry_point="magic_link",
                redirect_host=urlparse(magic_link_data.redirect_url or "").hostname,
                preferred_tenant_id=(str(preferred_tenant_id) if preferred_tenant_id else None),
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "This email exists in more than one tenant pool; "
                    "request the link from the product that owns the account"
                ),
            ) from exc

    if not user and await _invite_only_destination(db, magic_link_data.redirect_url, client_id):
        if mail_audit_id is not None:
            await attach_issuance(db, mail_audit_id, not_issued=True)
            await db.commit()
        logger.info("magic_link.not_created_invite_only", client_id=client_id)
        return None

    if not user:
        # Create user without password for magic link only.
        # This branch is a signup in everything but name — it is the first and
        # only chance to record the requester's language, and the very next
        # thing this endpoint does is mail them.
        user = User(
            email=magic_link_data.email,
            email_verified=True,  # Auto-verify for magic link users
            status=UserStatus.ACTIVE,
            locale=locale_from_request(request),
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            # Lost a race, or the row exists in a state the lookups above do
            # not see (a non-ACTIVE row still occupies its pool's unique
            # index — uq_users_email_global for platform rows,
            # uq_users_tenant_email for tenant-pooled ones).
            # Re-select instead of 503ing: the address is taken, so the user
            # exists — find them rather than telling the product the service is
            # down.
            await db.rollback()
            user = await _auth_shared.get_user_by_email(
                db, magic_link_data.email, tenant_id=None, active_only=True
            )
            if not user:
                try:
                    user = await resolve_user_by_email_across_pools(
                        db, magic_link_data.email, active_only=True
                    )
                except AmbiguousEmailAcrossPools as exc:
                    log_ambiguous_email(
                        exc,
                        entry_point="magic_link_create_race",
                        redirect_host=urlparse(magic_link_data.redirect_url or "").hostname,
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "This email exists in more than one tenant pool; "
                            "request the link from the product that owns the account"
                        ),
                    ) from exc
            if not user:
                # The colliding row is not ACTIVE — a disabled or pending
                # account. Say so; do not retry the insert forever.
                raise HTTPException(
                    status_code=400,
                    detail="An account with this email exists but is not active",
                )

    if mail_audit_id is None:
        # SECURITY: Validate the redirect URL to prevent open redirect attacks.
        # A supplied-but-disallowed destination is a 400 HERE, not a silent None:
        # the emailed link is built ON the destination host, so nulling it would
        # mail a link that signs the user in and then dead-ends — a failure the
        # requesting product cannot see and the recipient cannot fix. (Found live
        # 2026-08-15: the rehearsal host was missing from CORS_ORIGINS and the
        # first client-ceremony walkthrough ended on the recovery page.)
        safe_redirect_url = None
        if magic_link_data.redirect_url:
            safe_redirect_url = _auth_shared.validate_redirect_url(
                magic_link_data.redirect_url, default_url=None
            )
            if safe_redirect_url is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "redirect_url host is not on the allowed list; "
                        "add it to CORS_ORIGINS before requesting links for it"
                    ),
                )

    # Create magic link token
    magic_token = secrets.token_urlsafe(32)
    magic_link = MagicLink(
        id=uuid.uuid4(),
        user_id=user.id,
        # The model declares email NOT NULL and this constructor never set it,
        # so the moment migration backlog 003-011 landed in production
        # (2026-08-15) every plain magic-link send 503'd with a
        # NotNullViolation — found live, mid-rehearsal, on the first send of
        # the CTM ceremony walkthrough. The stored, verified address is the
        # right value: the request's raw input may differ in case or alias
        # form, and the row is an audit record of who was actually mailed.
        # (Prod's NOT NULL was dropped as the same-day unblock; restore it in
        # a later migration once this code is promoted and NULLs backfilled.)
        email=user.email,
        token=magic_token,
        redirect_url=safe_redirect_url,  # Use validated URL
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    db.add(magic_link)
    try:
        if mail_audit_id is not None:
            await db.flush()
            await attach_issuance(db, mail_audit_id, magic_link.id)
        await db.commit()
    except Exception as error:
        await db.rollback()
        if mail_audit_id is not None:
            raise HTTPException(
                status_code=503, detail="Login mail issuance audit unavailable"
            ) from error
        raise

    # Send email in background.
    #
    # Both `locale` and `formality` are read off the User row HERE, while the
    # request still holds a DB session — a BackgroundTask has none, so anything
    # stored about the recipient has to be resolved before the task is queued.
    # `magic_link_data.formality` is the requesting product's own register and
    # outranks the stored value; when both are absent the mailer falls back to
    # the redirect host's registered default rather than to a global `usted`
    # (app/services/email_branding.py::default_formality_for).
    background_tasks.add_task(
        _auth_shared.send_magic_link_email_task,
        user.email,
        magic_token,
        safe_redirect_url,
        locale=email_locale or getattr(user, "locale", None),
        formality=magic_link_data.formality,
        user_formality=getattr(user, "spanish_formality", None),
        hosted_hop=magic_link_data.hosted_hop,
        **({"mail_audit_id": str(mail_audit_id)} if mail_audit_id is not None else {}),
    )

    return user
