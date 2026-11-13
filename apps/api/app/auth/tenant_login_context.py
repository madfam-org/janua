"""Resolve identity pools only from a validated registered-client transaction."""

import json
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select


async def login_client_context(db, redis, *, auth_request_id=None, client_id=None, return_url=None):
    from app.models import OAuthClient
    from app.routers.v1.oauth_provider import _validate_redirect_uri

    context = {}
    if auth_request_id:
        raw = await redis.strict_get(f"oauth:pre_login:{auth_request_id}")
        if not raw:
            raise HTTPException(400, "La solicitud de acceso venció. Vuelve al MAP para iniciar.")
        try:
            context = json.loads(raw)
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid authentication context")
        if client_id and context.get("client_id") != client_id:
            raise HTTPException(400, "Authentication client does not match")
        client_id = context.get("client_id")
    if not client_id:
        return None, context
    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalar_one_or_none()
    if client is None and context.get("resource"):
        from types import SimpleNamespace

        from app.core.protected_resources import PROTECTED_RESOURCES, redirect_uri_matches
        from app.routers.v1.oauth_provider import _resolve_resource_client, _resource_policy_error

        resource = PROTECTED_RESOURCES.get(context["resource"])
        resolved, refusal = (
            await _resolve_resource_client(client_id, resource, db)
            if resource
            else (None, "invalid resource")
        )
        if (
            resolved is None
            or not redirect_uri_matches(context.get("redirect_uri", ""), resolved.redirect_uris)
            or _resource_policy_error(resource, resolved, context.get("redirect_uri", ""))
        ):
            raise HTTPException(400, "Invalid protected-resource authentication client")
        client = SimpleNamespace(
            client_id=client_id,
            organization_id=None,
            redirect_uris=resolved.redirect_uris,
            is_active=True,
            audience=None,
        )
    if client is None or not client.is_active:
        raise HTTPException(400, "Invalid authentication client")
    if auth_request_id and not _validate_redirect_uri(
        context.get("redirect_uri", ""), client.redirect_uris
    ):
        raise HTTPException(400, "Invalid authentication redirect")
    if return_url:
        if "\\" in return_url or any(ord(char) < 32 or ord(char) == 127 for char in return_url):
            raise HTTPException(400, "Invalid return URL")
        target = urlsplit(return_url)
        if target.scheme != "https" or target.username or target.password or target.fragment:
            raise HTTPException(400, "Invalid return URL")
        allowed = {
            urlsplit(uri).scheme + "://" + urlsplit(uri).netloc for uri in client.redirect_uris
        }
        if target.scheme + "://" + target.netloc not in allowed or target.path.startswith("//"):
            raise HTTPException(400, "Return URL is not registered for this client")
    return client, context


async def login_user(db, email, client=None, *, active_only=False):
    """Resolve the identity a hosted login for ``client`` may authenticate.

    Unbound client (or none): the platform pool only, exactly as before.

    Org-bound client: the organization's own tenant pool wins whenever it holds
    the email, and that identity must still be an active member (403
    otherwise). Only when the tenant pool has no match may a PLATFORM-pool
    identity (``tenant_id IS NULL``, how staff are provisioned) be used, and
    only if it holds an ACTIVE membership in the client's organization: the
    same rule the token exchange enforces with ``require_client_membership``.
    Identities in OTHER tenant pools are never considered.

    A platform identity without that membership is reported as not found, the
    same ``None`` an unknown email produces, through the same single query, so
    the refusal does not reveal that the address exists elsewhere.
    """
    from app.services.user_lookup import get_user_by_email

    org_id = getattr(client, "organization_id", None)
    user = await get_user_by_email(db, email, tenant_id=org_id, active_only=active_only)
    if org_id is None:
        return user
    if user is not None:
        await require_client_membership(db, user, client)
        return user
    return await _platform_member_by_email(db, email, org_id, active_only=active_only)


def _active_membership(user_id, org_id):
    from app.models import OrganizationMember

    return select(OrganizationMember.id).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id == org_id,
        OrganizationMember.status == "active",
    )


async def _platform_member_by_email(db, email, org_id, *, active_only=False):
    """The platform-pool user with ``email`` iff actively a member of ``org_id``.

    One statement: the pool scope and the membership requirement are evaluated
    together, so "no such user" and "user without membership" are the same
    query and the same ``None``. The platform pool is unique per email (partial
    index ``uq_users_email_global``), so at most one row can match.
    """
    from app.models import User, UserStatus

    stmt = select(User).where(
        User.email == email,
        User.tenant_id.is_(None),
        _active_membership(User.id, org_id).exists(),
    )
    if active_only:
        stmt = stmt.where(User.status == UserStatus.ACTIVE)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def user_in_client_pool(db, user, client):
    """Whether ``user`` is an identity ``client``'s hosted login may resolve.

    Mirrors :func:`login_user`: the client's own pool (its organization's
    tenant pool, or the platform pool for an unbound client), or, for an
    org-bound client, a platform-pool identity with an active membership in
    that organization.
    """
    org_id = getattr(client, "organization_id", None)
    if str(user.tenant_id) == str(org_id):
        return True
    if user.tenant_id is not None or org_id is None:
        return False
    result = await db.execute(_active_membership(user.id, org_id))
    return result.first() is not None


async def require_client_membership(db, user, client):
    from app.models import OrganizationMember

    org_id = getattr(client, "organization_id", None)
    if org_id is None:
        return
    membership = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(403, "La cuenta no pertenece a esta organización activa")
