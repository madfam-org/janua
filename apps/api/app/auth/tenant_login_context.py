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
    from app.services.user_lookup import get_user_by_email

    # With a bound client there is exactly one pool: never fall back to a
    # same-email identity in the platform or another organization.
    user = await get_user_by_email(
        db, email, tenant_id=getattr(client, "organization_id", None), active_only=active_only
    )
    if user is not None and getattr(client, "organization_id", None):
        await require_client_membership(db, user, client)
    return user


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
