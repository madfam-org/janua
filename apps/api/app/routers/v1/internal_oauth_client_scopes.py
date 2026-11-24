"""Internal OAuth-client scope grants — grant / revoke / list.

For a SERVICE client, ``OAuthClient.allowed_scopes`` IS the grant record. A
person's application roles (``hcm:hr`` and friends) hang off a membership row
and are administered through ``internal_app_roles.py``; a machine principal has
no membership, so the operator-controlled column that already decides what the
client may ask for is where its authority lives. Since the token path emits an
org-bound client's namespaced scopes verbatim into the ``roles`` claim
(``routers/v1/oauth_provider._service_client_app_roles``), editing that column
is now an AUTHORIZATION change — and an authorization change should not require
`psql` against production.

Why not the existing surfaces
-----------------------------
``POST /oauth/clients/register`` REPLACES ``allowed_scopes`` wholesale on the
converge path. A consumer's checked-in bootstrap manifest re-running would
therefore silently WIPE a scope an operator granted by hand — the grant would
work until the next deploy of an unrelated service. ``PATCH /oauth/clients/{id}``
requires a human session (``get_current_user``) and also takes a whole list.
This surface is additive, single-scope, and idempotent, so a grant survives
every convergent re-registration and a retry is never destructive.

Auth
----
``verify_internal_api_key`` — the same ``X-Internal-API-Key`` dependency as
``internal_users.py``, ``internal_capability_links.py`` and
``internal_app_roles.py``, and the same swappable seam: declared once per route,
with no handler body depending on the shared key, so the ratified move to
janua-issued service tokens is a dependency swap rather than a rewrite.

What janua deliberately does NOT know
-------------------------------------
The scope string is OPAQUE. Janua stores it, matches it against the request, and
emits it verbatim when it has the namespaced shape. It holds no table of valid
apps and no vocabulary of role names — a new HCM role must not require a janua
deploy. What janua validates is SHAPE (``schemas/oauth_client_scope.py``).

Scope guarantee
---------------
There is no endpoint here that touches, reads, or returns a client SECRET, and
none that deletes a client. Revoking a scope removes one string from the list;
the client, its credential, and its audit history are untouched.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.device_clients import DEVICE_ONLY_SCOPE_DETAIL, device_only_scopes_in
from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.models import AuditLog, OAuthClient
from app.routers.v1.oauth_clients import (
    INTERNAL_API_KEY_PRINCIPAL,
    _safe_oauth_client_name,
)
from app.schemas.oauth_client_scope import (
    OAuthClientScopeListResponse,
    OAuthClientScopeRequest,
    OAuthClientScopeResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/oauth-clients", tags=["internal"])

#: THE refusal text for "no such client". Deliberately one message, so a caller
#: cannot use this surface to probe which client_ids exist.
NO_CLIENT_DETAIL = "OAuth client not found"


async def _get_client(db: AsyncSession, client_id: str) -> OAuthClient:
    """Resolve a client by its PUBLIC client_id, or 404.

    Matched on ``client_id``, never on the database primary key: ``client_id``
    is the identifier an operator has in front of them (it is what the consumer
    puts in its config) and it is public by construction.

    Deliberately NOT filtered on ``is_active``, unlike
    ``OAuthClientService.get_client_by_client_id``. Editing the scopes of a
    deactivated client must keep working: an operator preparing a client for
    re-activation, or revoking an authority from one that was switched off
    rather than deleted, has a legitimate reason to reach it — and a 404 there
    would read as "no such client" and send them looking for a typo. The
    deactivated client mints no tokens either way (``is_active`` is checked on
    the token path), so nothing is authorized by this.
    """
    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalars().first()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_CLIENT_DETAIL)
    return client


def _emits_app_role(client: OAuthClient, scope: str) -> bool:
    """Whether this scope will reach the token's ``roles`` claim.

    Imported from the token path rather than re-derived, so this surface and the
    minting seam can never disagree about what a grant does. An operator who
    grants ``hcm_hr`` by mistake, or grants ``hcm:hr`` to a client with no
    organization, is told in the response instead of discovering it as a 403
    from HCM days later.
    """
    from app.routers.v1.oauth_provider import _service_client_app_roles

    return bool(_service_client_app_roles(client, {scope}))


def _record_audit(
    db: AsyncSession,
    *,
    action: str,
    client: OAuthClient,
    scope: str,
) -> None:
    """Stage an audit_logs row for a scope grant/revoke.

    Same direct-``AuditLog`` construction as
    ``oauth_clients._record_internal_registration_audit``, staged on the session
    so the audit row and the scope write land in ONE transaction: an
    authorization change that committed without its record would be exactly the
    gap this endpoint exists to close.

    Never records secret material — only the client name, public ``client_id``,
    the organization, and the scope string.
    """
    db.add(
        AuditLog(
            user_id=None,
            action=action,
            resource_type="oauth_client",
            resource_id=client.id,
            details={
                "actor": INTERNAL_API_KEY_PRINCIPAL,
                "actor_type": "service",
                "client_id": client.client_id,
                "name": _safe_oauth_client_name(client.name),
                "organization_id": (
                    str(client.organization_id) if client.organization_id else None
                ),
                "scope": scope,
                "emits_app_role": _emits_app_role(client, scope),
            },
        )
    )


def _response(
    client: OAuthClient,
    scope: str,
    *,
    changed: bool,
) -> OAuthClientScopeResponse:
    return OAuthClientScopeResponse(
        client_id=client.client_id,
        organization_id=str(client.organization_id) if client.organization_id else None,
        scope=scope,
        allowed_scopes=list(client.allowed_scopes or []),
        emits_app_role=_emits_app_role(client, scope),
        changed=changed,
    )


# -------------------------------------------------------------------- grant


@router.post(
    "/{client_id}/scopes",
    response_model=OAuthClientScopeResponse,
    # 201 is the DECLARED default (the create case, what OpenAPI advertises).
    # The handler downgrades to 200 on the already-granted path by writing
    # `response.status_code` — a per-call status cannot be expressed statically.
    # Same shape as internal_app_roles.grant and internal_users.provision.
    status_code=status.HTTP_201_CREATED,
)
async def grant_client_scope(
    client_id: str,
    body: OAuthClientScopeRequest,
    response: Response,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> OAuthClientScopeResponse:
    """Add one scope to a client's ``allowed_scopes``. Idempotent, additive.

    Returns 201 when this call added the scope, 200 when it was already there.
    ADDITIVE by construction: every other scope on the client is left exactly as
    it was, so this can never be the call that removes an authority — the
    failure mode ``/oauth/clients/register`` has, where a whole-list write
    silently drops a hand-granted scope on the next convergent bootstrap.

    404 for an unknown client. A grant that could never feed a token is an
    operator error worth surfacing, not a row written into nowhere.
    """
    if device_only_scopes_in([body.scope]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{body.scope} {DEVICE_ONLY_SCOPE_DETAIL}",
        )
    client = await _get_client(db, client_id)

    current = list(client.allowed_scopes or [])
    if body.scope in current:
        response.status_code = status.HTTP_200_OK
        return _response(client, body.scope, changed=False)

    # Rebound rather than mutated in place: `allowed_scopes` is a JSONB column,
    # and SQLAlchemy does not track in-place mutation of a plain JSON list, so
    # `current.append(...)` alone would COMMIT NOTHING and report success.
    client.allowed_scopes = current + [body.scope]
    client.updated_at = datetime.utcnow()

    _record_audit(
        db,
        action="oauth_client_scope_granted",
        client=client,
        scope=body.scope,
    )

    await db.commit()
    await db.refresh(client)

    logger.info(
        "Granted OAuth client scope via internal API",
        client_id=client.client_id,
        organization_id=str(client.organization_id) if client.organization_id else None,
        scope=body.scope,
    )

    return _response(client, body.scope, changed=True)


# ------------------------------------------------------------------- revoke


@router.post(
    "/{client_id}/scopes/revoke",
    response_model=OAuthClientScopeResponse,
)
async def revoke_client_scope(
    client_id: str,
    body: OAuthClientScopeRequest,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> OAuthClientScopeResponse:
    """Remove one scope from a client's ``allowed_scopes``. Idempotent.

    Always 200 when the client exists: ``changed`` reports whether THIS call was
    the one that removed it, matching ``internal_app_roles.revoke`` and
    ``internal_users.suspend``. A scope that was never granted is the caller's
    desired end state, so it is success with ``changed: false`` rather than a
    404.

    POST, not DELETE, because the scope travels in the BODY: a scope is a
    colon-bearing string and putting it in the path would make routing depend on
    URL-encoding an authorization value correctly.

    Revocation reaches a live caller at its next mint — service tokens are
    short-lived (``SERVICE_TOKEN_TTL_SECONDS``) and every mint re-reads
    ``allowed_scopes`` — but it does NOT invalidate a token already issued. To
    stop an in-flight token, rotate the client secret or deactivate the client.
    """
    client = await _get_client(db, client_id)

    current = list(client.allowed_scopes or [])
    if body.scope not in current:
        return _response(client, body.scope, changed=False)

    # Rebound, not mutated: see the note in `grant_client_scope`. Removes EVERY
    # occurrence, so a list that already carried a duplicate (written by an
    # older path) is left genuinely without the scope rather than one short.
    client.allowed_scopes = [s for s in current if s != body.scope]
    client.updated_at = datetime.utcnow()

    _record_audit(
        db,
        action="oauth_client_scope_revoked",
        client=client,
        scope=body.scope,
    )

    await db.commit()
    await db.refresh(client)

    logger.info(
        "Revoked OAuth client scope via internal API",
        client_id=client.client_id,
        organization_id=str(client.organization_id) if client.organization_id else None,
        scope=body.scope,
    )

    return _response(client, body.scope, changed=True)


# --------------------------------------------------------------------- list


@router.get(
    "/{client_id}/scopes",
    response_model=OAuthClientScopeListResponse,
)
async def list_client_scopes(
    client_id: str,
    _auth: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db),
) -> OAuthClientScopeListResponse:
    """Everything a client may ask for, and which of those become app roles.

    ``app_role_scopes`` is the resolved set — exactly the strings this client's
    next token will carry under ``roles`` if it requests them — so an operator
    can answer "why does HCM still refuse this service?" without decoding a JWT.
    Empty for a client with no ``organization_id``, which is itself the answer
    in the most common case.

    Returns no secret material.
    """
    from app.routers.v1.oauth_provider import _service_client_app_roles

    client = await _get_client(db, client_id)
    allowed = list(client.allowed_scopes or [])

    return OAuthClientScopeListResponse(
        client_id=client.client_id,
        organization_id=str(client.organization_id) if client.organization_id else None,
        allowed_scopes=allowed,
        app_role_scopes=_service_client_app_roles(client, set(allowed)),
    )


__all__ = ["router"]
