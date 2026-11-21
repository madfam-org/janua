"""client_credentials for a shared device (client kind ``device``).

`oauth_provider_token.token` sends a client_credentials request here when the
client's ``client_id`` carries the device prefix (`core/device_clients.py`);
every other client keeps `oauth_provider_grants._handle_client_credentials_grant`.
The device's record and its enrolment live in `models/device_client.py` and
`routers/v1/device_enrolment.py`.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.device_clients import (
    CLIENT_KIND_DEVICE,
    boot_id_is_valid,
    get_device_template,
    observe_boot_id,
    parse_recent_boot_ids,
    serialize_recent_boot_ids,
)
from app.core.jwt_manager import jwt_manager
from app.models import OAuthClient, Organization
from app.models.device_client import DEVICE_STATUS_ACTIVE, DeviceClient
from app.routers.v1.oauth_provider_schemas import TokenResponse
from app.routers.v1.oauth_provider_scopes import (
    _get_client_credentials_claims,
    _parse_requested_scopes,
)
from app.routers.v1.oauth_provider_shared import DEVICE_TOKEN_TTL_SECONDS
from app.services.device_audit import DEVICE_CLONE_SUSPECTED, RESOURCE_DEVICE, stage_device_audit
from app.services.device_notifications import (
    build_clone_suspicion_notice,
    organization_admin_emails,
    send_clone_suspicion_notice,
)

logger = structlog.get_logger()


def _device_token_refused(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid_client: {detail}"
    )


async def _handle_device_client_credentials_grant(
    client: OAuthClient,
    requested_scope: Optional[str],
    boot_id: Optional[str],
    db: AsyncSession,
    background_tasks: Optional[BackgroundTasks],
) -> TokenResponse:
    """client_credentials for a shared device (client kind ``device``).

    The same grant and the same machine claims as a service client, so every
    verifier classifies the token as a machine and holds it to its scope, plus
    ``client_kind: "device"``. The differences:

    - the device's record must exist and be active; it is read under a row lock,
      and a device client is never served without it;
    - scope and audience come from the device's template, whatever else the
      client row holds;
    - the token lives ``DEVICE_TOKEN_TTL_SECONDS`` and carries no email;
    - ``boot_id`` is required. When an earlier boot identifier comes back (two
      holders of one credential taking turns), Janua flags the device, records
      it, and notifies the organization's administrators once. The token is
      still issued: a person decides whether to disable the device.
    """
    if not getattr(client, "is_confidential", False):
        raise _device_token_refused("client_credentials requires a confidential client")

    device = (
        await db.execute(
            select(DeviceClient).where(DeviceClient.oauth_client_id == client.id).with_for_update()
        )
    ).scalar_one_or_none()
    if device is None or device.status != DEVICE_STATUS_ACTIVE:
        raise _device_token_refused("Client disabled")
    template = get_device_template(device.template)
    if template is None:
        raise _device_token_refused("Client disabled")
    if not boot_id_is_valid(boot_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: a device must send boot_id (16-128 URL-safe characters)",
        )

    scope = _parse_requested_scopes(requested_scope, client)
    outside_template = set(scope.split()) - template.scopes
    if outside_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_scope: {', '.join(sorted(outside_template))}",
        )

    now = datetime.utcnow()
    observation = observe_boot_id(parse_recent_boot_ids(device.recent_boot_ids), boot_id)
    device.recent_boot_ids = serialize_recent_boot_ids(observation.recent)
    device.last_token_at = now
    client.last_used_at = now

    newly_flagged = False
    if observation.alternated:
        device.boot_alternations = (device.boot_alternations or 0) + 1
        if device.clone_suspected_at is None:
            device.clone_suspected_at = now
            newly_flagged = True

    claims = await _get_client_credentials_claims(client, scope, db)
    issued_at = int(now.replace(tzinfo=timezone.utc).timestamp())
    claims.update(
        {
            "sub": f"service-account:{client.client_id}",
            "jti": secrets.token_urlsafe(32),
            "iat": issued_at,
            "exp": issued_at + DEVICE_TOKEN_TTL_SECONDS,
            "type": "access",
            "iss": jwt_manager.issuer,
            "aud": template.audience,
            "client_kind": CLIENT_KIND_DEVICE,
        }
    )
    access_token = jwt_manager.encode_token(claims)

    notice = None
    if newly_flagged:
        stage_device_audit(
            db,
            action=DEVICE_CLONE_SUSPECTED,
            resource_type=RESOURCE_DEVICE,
            resource_id=device.id,
            actor_id=None,
            details={
                "org_id": str(device.organization_id),
                "client_id": client.client_id,
                "label": device.label,
                "boot_alternations": device.boot_alternations,
                "disabled": False,
            },
        )
        organization_name = (
            await db.execute(
                select(Organization.name).where(Organization.id == device.organization_id)
            )
        ).scalar_one_or_none()
        notice = build_clone_suspicion_notice(
            recipients=await organization_admin_emails(db, device.organization_id),
            organization_name=organization_name,
            device_label=device.label,
            client_id=client.client_id,
        )
        logger.warning(
            "Device flagged: boot identifiers alternate",
            client_id=client.client_id,
            org_id=str(device.organization_id),
            boot_alternations=device.boot_alternations,
        )

    await db.commit()

    if notice is not None:
        if background_tasks is not None:
            background_tasks.add_task(send_clone_suspicion_notice, notice)
        else:
            await send_clone_suspicion_notice(notice)

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=DEVICE_TOKEN_TTL_SECONDS,
        refresh_token=None,
        id_token=None,
        scope=scope,
    )
