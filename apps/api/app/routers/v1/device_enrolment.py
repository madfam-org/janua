"""Enrolling a shared device, and its organization administrators' controls.

A shared device (a shop-floor terminal that several people use) becomes a
confidential OAuth client of kind ``device`` in four steps
(`core/device_clients.py`, `models/device_client.py`):

1. **Register** — ``POST /api/v1/device-enrolments`` (public; the device has
   no credential yet). The device sends the organization's slug, a label, and
   a secret of 32 random bytes it generated itself. Janua stores only a bcrypt
   hash in a pending enrolment that lasts ``DEVICE_ENROLMENT_TTL_SECONDS`` and
   answers with an eight-letter code for the device to show on its screen.
2. **Approve** — ``POST /api/v1/organizations/{org_id}/devices/enrolments/approve``.
   An administrator of that organization, signed in as a person, types the
   code shown on the device in hand. Janua creates the device's client from
   the template: fixed audience, fixed scopes, client credentials only. Nobody
   chooses a scope. The pending row keeps no hash.
3. **Poll** — ``GET /api/v1/device-enrolments/{enrolment_id}`` (public). The
   device learns "pending", "approved" (with its ``client_id``) or "expired".
   Never credential material.
4. **Use** — the device asks ``POST /api/v1/oauth/token`` for a
   client_credentials token with its ``client_id``, its own secret and its
   boot identifier. The token lives fifteen minutes.

Enrolling again with ``device_client_id`` set names the device being replaced
(a re-flashed card, say): approving it rotates that device's credential and
makes it active again, under the same ``client_id``.

The administrators' routes also list pending enrolments, list devices, and
disable a device in one action: it then gets no new token, and the token it
holds expires within fifteen minutes.

Who may call what
-----------------
* Register and poll are public, like any route a device calls before it has a
  credential. They are limited per client address and (register) per
  organization in Redis, read strictly: when the counter cannot be read the
  request is refused with 503, never let through. Every limit and the cap on
  pending enrolments apply BEFORE any hash is computed.
* Which organizations may enrol devices is configuration
  (``DEVICE_ENROLMENT_ORGANIZATIONS``). A slug outside it gets the same answer
  as one that does not exist.
* The administrators' routes are for PEOPLE: a Janua access token whose subject
  is an active user who is not a service account, carrying no machine marker
  (``token_use``, ``actor_type``, ``client_kind``, a ``service-account:``
  subject). API keys, service tokens and device tokens are refused. The person
  must own the organization or hold an active ``owner``/``admin`` membership in
  it; a person who is not a member gets the same 404 as an organization that
  does not exist.

Every enrolment, approval and disabling writes an audit row on the same
transaction as the change (`services/device_audit.py`).
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.device_admin import require_org_admin, require_person
from app.auth.magic_link_limits import _ip_bucket_key, trusted_client_ip
from app.config import settings
from app.core.database import get_db
from app.core.device_clients import (
    DEFAULT_DEVICE_TEMPLATE,
    DEVICE_TEMPLATES,
    device_secret_is_valid,
    generate_device_client_id,
    generate_user_code,
    get_device_template,
    normalize_user_code,
)
from app.core.redis import ResilientRedisClient, get_redis
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.models import OAuthClient, Organization, User
from app.models.device_client import (
    DEVICE_STATUS_ACTIVE,
    DEVICE_STATUS_DISABLED,
    ENROLMENT_STATUS_APPROVED,
    ENROLMENT_STATUS_PENDING,
    DeviceClient,
    DeviceEnrolment,
)
from app.schemas.device_enrolment import (
    ApproveRequest,
    ApproveResponse,
    DeviceList,
    DeviceView,
    DisableRequest,
    DisableResponse,
    EnrolmentCreated,
    EnrolmentRequest,
    EnrolmentStatus,
    PendingEnrolment,
    PendingEnrolmentList,
    ReplacedDevice,
)
from app.services.device_audit import (
    DEVICE_DISABLED,
    DEVICE_ENROLMENT_APPROVED,
    DEVICE_ENROLMENT_REQUESTED,
    RESOURCE_DEVICE,
    RESOURCE_ENROLMENT,
    stage_device_audit,
)

logger = structlog.get_logger()

public_router = APIRouter(prefix="/device-enrolments", tags=["Device Enrolment"])
admin_router = APIRouter(prefix="/organizations/{org_id}/devices", tags=["Devices"])

#: Seconds a device should wait between polls.
POLL_INTERVAL_SECONDS = 5
#: Shown in place of a secret prefix on a device client: Janua never had the
#: secret in a form it could show.
DEVICE_SECRET_PREFIX_PLACEHOLDER = "(device)"
#: How many times a fresh code is drawn when one collides.
USER_CODE_ATTEMPTS = 5

UNKNOWN_ORGANIZATION_DETAIL = "This organization does not enrol devices"


# --------------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.utcnow()


def enrolable_organization_slugs() -> set[str]:
    return {
        slug.strip().lower()
        for slug in (settings.DEVICE_ENROLMENT_ORGANIZATIONS or "").split(",")
        if slug.strip()
    }


def _request_origin(request: Request) -> tuple[Optional[str], str]:
    """(address to record, or None when it is not an IP; rate-limit bucket)."""
    address = trusted_client_ip(request)
    try:
        recorded = str(ipaddress.ip_address(address))
    except ValueError:
        recorded = None
    return recorded, _ip_bucket_key(address)


def _user_agent(request: Request) -> Optional[str]:
    value = request.headers.get("user-agent")
    return value[:255] if value else None


async def _enforce_limit(
    redis: ResilientRedisClient, name: str, subject: str, limit: int, window_seconds: int
) -> None:
    """Fixed-window counter shared by every replica; refuses (raises) when Redis cannot count."""
    if redis is None:
        raise RedisUnavailableError("rate-limit store unavailable")
    if not hasattr(redis, "strict_incr_window"):
        # A raw client (what get_redis hands out before the breaker wraps it)
        # gets the same strict operation through the breaker.
        redis = ResilientRedisClient(redis)
    window = int(time.time()) // window_seconds
    key = f"device-enrolment:{name}:{subject}:{window}"
    count = await redis.strict_incr_window(key, window_seconds)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests; try again later",
        )


def _device_view(device: DeviceClient, client_id: Optional[str]) -> DeviceView:
    return DeviceView(
        id=device.id,
        client_id=client_id,
        label=device.label,
        template=device.template,
        status=device.status,
        approved_by=device.approved_by,
        approved_at=device.approved_at,
        disabled_by=device.disabled_by,
        disabled_at=device.disabled_at,
        disabled_reason=device.disabled_reason,
        last_token_at=device.last_token_at,
        clone_suspected_at=device.clone_suspected_at,
        boot_alternations=device.boot_alternations or 0,
        created_at=device.created_at,
    )


async def _client_id_of(db: AsyncSession, device: DeviceClient) -> Optional[str]:
    return (
        await db.execute(
            select(OAuthClient.client_id).where(OAuthClient.id == device.oauth_client_id)
        )
    ).scalar_one_or_none()


def _hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt(settings.BCRYPT_ROUNDS)).decode()


def _is_expired(enrolment: DeviceEnrolment, now: datetime) -> bool:
    return enrolment.expires_at <= now


async def _pending_count(db: AsyncSession, organization_id: uuid.UUID, now: datetime) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(DeviceEnrolment)
                .where(
                    DeviceEnrolment.organization_id == organization_id,
                    DeviceEnrolment.status == ENROLMENT_STATUS_PENDING,
                    DeviceEnrolment.expires_at > now,
                )
            )
        ).scalar_one()
    )


# ---------------------------------------------------------------- public routes


@public_router.post("", response_model=EnrolmentCreated, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: EnrolmentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> EnrolmentCreated:
    """A device asks to be enrolled. Public; limited before any hash is computed."""
    recorded_ip, ip_bucket = _request_origin(request)
    await _enforce_limit(
        redis,
        "register-address",
        ip_bucket,
        settings.DEVICE_ENROLMENT_REGISTER_PER_ADDRESS_PER_HOUR,
        3600,
    )

    slug = body.organization.strip().lower()
    if slug not in enrolable_organization_slugs():
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_ORGANIZATION_DETAIL)
    await _enforce_limit(
        redis,
        "register-organization",
        slug,
        settings.DEVICE_ENROLMENT_REGISTER_PER_ORGANIZATION_PER_HOUR,
        3600,
    )

    template = get_device_template(body.template or DEFAULT_DEVICE_TEMPLATE)
    if template is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown template; known: {', '.join(sorted(DEVICE_TEMPLATES))}",
        )
    if not device_secret_is_valid(body.secret):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "secret must be 32 random bytes as 64 hex characters or 43 base64url characters",
        )

    organization = (
        await db.execute(select(Organization).where(func.lower(Organization.slug) == slug))
    ).scalar_one_or_none()
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_ORGANIZATION_DETAIL)

    now = _now()
    if await _pending_count(db, organization.id, now) >= settings.DEVICE_ENROLMENT_MAX_PENDING:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many enrolments are waiting for approval in this organization",
        )

    # A re-enrolment names a device of THIS organization. Anything else is
    # treated as a new device, so the route says nothing about other clients.
    replaces: Optional[DeviceClient] = None
    if body.device_client_id:
        replaces = (
            await db.execute(
                select(DeviceClient)
                .join(OAuthClient, OAuthClient.id == DeviceClient.oauth_client_id)
                .where(
                    OAuthClient.client_id == body.device_client_id,
                    DeviceClient.organization_id == organization.id,
                )
            )
        ).scalar_one_or_none()

    secret_hash = await asyncio.to_thread(_hash_secret, body.secret)

    # Exact under concurrency: lock the organization row, count again, insert.
    await db.execute(
        select(Organization.id).where(Organization.id == organization.id).with_for_update()
    )
    now = _now()
    if await _pending_count(db, organization.id, now) >= settings.DEVICE_ENROLMENT_MAX_PENDING:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many enrolments are waiting for approval in this organization",
        )
    user_code = None
    for _ in range(USER_CODE_ATTEMPTS):
        candidate = generate_user_code()
        taken = (
            await db.execute(
                select(DeviceEnrolment.id).where(DeviceEnrolment.user_code == candidate)
            )
        ).first()
        if taken is None:
            user_code = candidate
            break
    if user_code is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Try again")

    enrolment = DeviceEnrolment(
        id=uuid.uuid4(),
        organization_id=organization.id,
        template=template.name,
        label=body.label,
        user_code=user_code,
        secret_hash=secret_hash,
        status=ENROLMENT_STATUS_PENDING,
        replaces_device_id=replaces.id if replaces else None,
        requested_ip=recorded_ip,
        requested_user_agent=_user_agent(request),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.DEVICE_ENROLMENT_TTL_SECONDS),
    )
    db.add(enrolment)
    stage_device_audit(
        db,
        action=DEVICE_ENROLMENT_REQUESTED,
        resource_type=RESOURCE_ENROLMENT,
        resource_id=enrolment.id,
        actor_id=None,
        details={
            "org_id": str(organization.id),
            "template": template.name,
            "label": body.label,
            "re_enrolment": replaces is not None,
        },
        ip_address=recorded_ip,
        user_agent=_user_agent(request),
    )
    await db.commit()
    logger.info(
        "Device enrolment pending approval",
        enrolment_id=str(enrolment.id),
        org_id=str(organization.id),
        template=template.name,
    )
    return EnrolmentCreated(
        enrolment_id=enrolment.id,
        status="pending",
        user_code=user_code,
        expires_at=enrolment.expires_at,
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
    )


@public_router.get("/{enrolment_id}", response_model=EnrolmentStatus)
async def poll_enrolment(
    enrolment_id: uuid.UUID,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
) -> EnrolmentStatus:
    """The device polls its enrolment. Status and, once approved, its client_id; nothing else."""
    _, ip_bucket = _request_origin(request)
    await _enforce_limit(
        redis, "poll-address", ip_bucket, settings.DEVICE_ENROLMENT_POLL_PER_ADDRESS_PER_MINUTE, 60
    )
    response.headers["Cache-Control"] = "no-store"
    enrolment = (
        await db.execute(select(DeviceEnrolment).where(DeviceEnrolment.id == enrolment_id))
    ).scalar_one_or_none()
    if enrolment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enrolment not found")

    if enrolment.status == ENROLMENT_STATUS_APPROVED and enrolment.device_id is not None:
        device = (
            await db.execute(select(DeviceClient).where(DeviceClient.id == enrolment.device_id))
        ).scalar_one_or_none()
        client_id = await _client_id_of(db, device) if device else None
        return EnrolmentStatus(
            enrolment_id=enrolment.id,
            status="approved",
            expires_at=enrolment.expires_at,
            client_id=client_id,
        )

    now = _now()
    if _is_expired(enrolment, now):
        if enrolment.secret_hash is not None:
            enrolment.secret_hash = None
            await db.commit()
        return EnrolmentStatus(
            enrolment_id=enrolment.id, status="expired", expires_at=enrolment.expires_at
        )
    return EnrolmentStatus(
        enrolment_id=enrolment.id, status="pending", expires_at=enrolment.expires_at
    )


# ----------------------------------------------------------------- admin routes


@admin_router.get("/enrolments", response_model=PendingEnrolmentList)
async def list_pending_enrolments(
    org_id: uuid.UUID,
    current_user: User = Depends(require_person),
    db: AsyncSession = Depends(get_db),
) -> PendingEnrolmentList:
    """Enrolments of this organization waiting for approval (not yet expired)."""
    await require_org_admin(db, org_id, current_user)
    now = _now()
    enrolments = (
        (
            await db.execute(
                select(DeviceEnrolment)
                .where(
                    DeviceEnrolment.organization_id == org_id,
                    DeviceEnrolment.status == ENROLMENT_STATUS_PENDING,
                    DeviceEnrolment.expires_at > now,
                )
                .order_by(DeviceEnrolment.created_at)
            )
        )
        .scalars()
        .all()
    )
    data = []
    for enrolment in enrolments:
        replaced = None
        if enrolment.replaces_device_id is not None:
            device = (
                await db.execute(
                    select(DeviceClient).where(DeviceClient.id == enrolment.replaces_device_id)
                )
            ).scalar_one_or_none()
            if device is not None:
                replaced = ReplacedDevice(
                    id=device.id, client_id=await _client_id_of(db, device), label=device.label
                )
        data.append(
            PendingEnrolment(
                id=enrolment.id,
                user_code=enrolment.user_code,
                label=enrolment.label,
                template=enrolment.template,
                requested_at=enrolment.created_at,
                expires_at=enrolment.expires_at,
                requested_from=enrolment.requested_ip,
                requested_user_agent=enrolment.requested_user_agent,
                replaces_device=replaced,
            )
        )
    return PendingEnrolmentList(data=data)


@admin_router.post("/enrolments/approve", response_model=ApproveResponse)
async def approve_enrolment(
    org_id: uuid.UUID,
    body: ApproveRequest,
    request: Request,
    current_user: User = Depends(require_person),
    db: AsyncSession = Depends(get_db),
) -> ApproveResponse:
    """Approve the code a device of this organization shows. Creates or rotates its client."""
    organization = await require_org_admin(db, org_id, current_user)
    code = normalize_user_code(body.user_code)
    if code is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending enrolment with this code")

    enrolment = (
        await db.execute(
            select(DeviceEnrolment)
            .where(
                DeviceEnrolment.organization_id == organization.id,
                DeviceEnrolment.user_code == code,
                DeviceEnrolment.status == ENROLMENT_STATUS_PENDING,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if enrolment is None or enrolment.secret_hash is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending enrolment with this code")
    now = _now()
    if _is_expired(enrolment, now):
        enrolment.secret_hash = None
        await db.commit()
        raise HTTPException(
            status.HTTP_410_GONE, "This code expired; restart enrolment on the device"
        )
    template = get_device_template(enrolment.template)
    if template is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This enrolment's template no longer exists")

    device: Optional[DeviceClient] = None
    client: Optional[OAuthClient] = None
    if enrolment.replaces_device_id is not None:
        device = (
            await db.execute(
                select(DeviceClient)
                .where(
                    DeviceClient.id == enrolment.replaces_device_id,
                    DeviceClient.organization_id == organization.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if device is not None:
            client = (
                await db.execute(
                    select(OAuthClient).where(OAuthClient.id == device.oauth_client_id)
                )
            ).scalar_one_or_none()
            if client is None:
                device = None

    re_enrolment = device is not None
    if re_enrolment:
        # Same client_id, new credential, active again. The clone signal starts
        # over: the old boots belong to the credential that was replaced.
        client.client_secret_hash = enrolment.secret_hash
        client.is_active = True
        client.updated_at = now
        device.status = DEVICE_STATUS_ACTIVE
        device.label = enrolment.label
        device.template = template.name
        device.approved_by = current_user.id
        device.approved_at = now
        device.disabled_by = None
        device.disabled_at = None
        device.disabled_reason = None
        device.recent_boot_ids = None
        device.boot_alternations = 0
        device.clone_suspected_at = None
        device.updated_at = now
    else:
        client = OAuthClient(
            id=uuid.uuid4(),
            organization_id=organization.id,
            created_by=current_user.id,
            client_id=generate_device_client_id(),
            client_secret_hash=enrolment.secret_hash,
            client_secret_prefix=DEVICE_SECRET_PREFIX_PLACEHOLDER,
            name=f"{template.name}-{uuid.uuid4().hex[:8]}",
            description=template.description,
            redirect_uris=[],
            allowed_scopes=sorted(template.scopes),
            grant_types=sorted(template.grant_types),
            audience=template.audience,
            is_active=True,
            is_confidential=True,
            created_at=now,
            updated_at=now,
        )
        db.add(client)
        await db.flush()
        device = DeviceClient(
            id=uuid.uuid4(),
            oauth_client_id=client.id,
            organization_id=organization.id,
            template=template.name,
            label=enrolment.label,
            status=DEVICE_STATUS_ACTIVE,
            approved_by=current_user.id,
            approved_at=now,
            boot_alternations=0,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
        await db.flush()

    enrolment.status = ENROLMENT_STATUS_APPROVED
    enrolment.secret_hash = None
    enrolment.approved_by = current_user.id
    enrolment.approved_at = now
    enrolment.device_id = device.id

    recorded_ip, _ = _request_origin(request)
    stage_device_audit(
        db,
        action=DEVICE_ENROLMENT_APPROVED,
        resource_type=RESOURCE_DEVICE,
        resource_id=device.id,
        actor_id=current_user.id,
        details={
            "org_id": str(organization.id),
            "client_id": client.client_id,
            "enrolment_id": str(enrolment.id),
            "template": template.name,
            "label": enrolment.label,
            "re_enrolment": re_enrolment,
        },
        ip_address=recorded_ip,
        user_agent=_user_agent(request),
    )
    await db.commit()
    logger.info(
        "Device enrolment approved",
        org_id=str(organization.id),
        client_id=client.client_id,
        re_enrolment=re_enrolment,
    )
    return ApproveResponse(re_enrolment=re_enrolment, device=_device_view(device, client.client_id))


@admin_router.get("", response_model=DeviceList)
async def list_devices(
    org_id: uuid.UUID,
    current_user: User = Depends(require_person),
    db: AsyncSession = Depends(get_db),
) -> DeviceList:
    """Every device of this organization, active and disabled, with its clone flag."""
    await require_org_admin(db, org_id, current_user)
    rows = (
        await db.execute(
            select(DeviceClient, OAuthClient.client_id)
            .join(OAuthClient, OAuthClient.id == DeviceClient.oauth_client_id, isouter=True)
            .where(DeviceClient.organization_id == org_id)
            .order_by(DeviceClient.created_at)
        )
    ).all()
    return DeviceList(data=[_device_view(device, client_id) for device, client_id in rows])


@admin_router.post("/{device_id}/disable", response_model=DisableResponse)
async def disable_device(
    org_id: uuid.UUID,
    device_id: uuid.UUID,
    request: Request,
    body: Optional[DisableRequest] = None,
    current_user: User = Depends(require_person),
    db: AsyncSession = Depends(get_db),
) -> DisableResponse:
    """Disable a device in one action. Idempotent: disabling a disabled device changes nothing."""
    organization = await require_org_admin(db, org_id, current_user)
    device = (
        await db.execute(
            select(DeviceClient)
            .where(DeviceClient.id == device_id, DeviceClient.organization_id == organization.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    client = (
        await db.execute(select(OAuthClient).where(OAuthClient.id == device.oauth_client_id))
    ).scalar_one_or_none()
    client_id = client.client_id if client else None

    if device.status == DEVICE_STATUS_DISABLED and (client is None or not client.is_active):
        return DisableResponse(changed=False, device=_device_view(device, client_id))

    now = _now()
    reason = (body.reason or "").strip() or None if body else None
    device.status = DEVICE_STATUS_DISABLED
    device.disabled_by = current_user.id
    device.disabled_at = now
    device.disabled_reason = reason
    device.updated_at = now
    if client is not None:
        client.is_active = False
        client.updated_at = now

    recorded_ip, _ = _request_origin(request)
    stage_device_audit(
        db,
        action=DEVICE_DISABLED,
        resource_type=RESOURCE_DEVICE,
        resource_id=device.id,
        actor_id=current_user.id,
        details={
            "org_id": str(organization.id),
            "client_id": client_id,
            "label": device.label,
            "reason": reason,
        },
        ip_address=recorded_ip,
        user_agent=_user_agent(request),
    )
    await db.commit()
    logger.info("Device disabled", org_id=str(organization.id), client_id=client_id)
    return DisableResponse(changed=True, device=_device_view(device, client_id))


__all__ = ["admin_router", "public_router", "require_person"]
