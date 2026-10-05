"""
Passkeys/WebAuthn authentication endpoints
"""

import json
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.routers.v1.auth import get_current_user
from app.services.auth_service import AuthService

from ...models import ActivityLog, Passkey, User
from ...services.user_lookup import get_user_by_email

router = APIRouter(prefix="/passkeys", tags=["passkeys"])


class PasskeyRegisterOptionsRequest(BaseModel):
    """Passkey registration options request"""

    authenticator_attachment: Optional[str] = Field(None, pattern="^(platform|cross-platform)$")


class PasskeyRegisterRequest(BaseModel):
    """Passkey registration verification request"""

    credential: Dict[str, Any]
    name: Optional[str] = Field(None, max_length=100)


class PasskeyAuthOptionsRequest(BaseModel):
    """Passkey authentication options request"""

    email: Optional[str] = None  # For passwordless login


class PasskeyAuthRequest(BaseModel):
    """Passkey authentication verification request"""

    email: Optional[str] = None  # For passwordless login
    credential: Dict[str, Any]


class PasskeyResponse(BaseModel):
    """Passkey response model"""

    id: str
    name: Optional[str]
    authenticator_attachment: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    sign_count: int


class PasskeyUpdateRequest(BaseModel):
    """Passkey update request"""

    name: str = Field(..., min_length=1, max_length=100)


def get_rp_id() -> str:
    """Get Relying Party ID.

    Must be the registrable domain the passkey is scoped to (e.g. `janua.dev`),
    NOT `settings.DOMAIN` (which defaults to `localhost` and would make every
    prod passkey scoped to localhost — 2026-08-23 fix). Prefer the dedicated
    WEBAUTHN_RP_ID; fall back to DOMAIN only if it is unset.
    """
    return getattr(settings, "WEBAUTHN_RP_ID", None) or settings.DOMAIN or "localhost"


def get_rp_name() -> str:
    """Get Relying Party Name"""
    return getattr(settings, "WEBAUTHN_RP_NAME", None) or settings.APP_NAME or "Janua"


def get_origin() -> str:
    """Get expected origin.

    The RP origin the browser reports in the WebAuthn ceremony (scheme + host,
    e.g. `https://janua.dev`). Prefer the dedicated WEBAUTHN_ORIGIN so it matches
    the RP ID; fall back to FRONTEND_URL / a derived origin (2026-08-23 fix — was
    FRONTEND_URL only, which need not match get_rp_id()).
    """
    configured = getattr(settings, "WEBAUTHN_ORIGIN", None)
    if configured:
        return configured
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL
    return (
        f"https://{get_rp_id()}"
        if settings.ENVIRONMENT == "production"
        else f"http://{get_rp_id()}:3000"
    )


# Redis key builders + TTLs for one-time WebAuthn challenges (server-side only —
# a challenge must NEVER be supplied by the client, or replay protection is void).
async def _consume_challenge(
    redis_client: ResilientRedisClient, key: str, missing_detail: str
) -> str:
    """Read and consume a one-time WebAuthn challenge, strictly.

    Strict operations (no breaker fallback, no pod-local cache): Redis being
    unreachable raises RedisUnavailableError (503 + Retry-After) instead of
    reading as "no challenge", and a challenge consumed on another replica can
    never come back from this one's memory. The DEL count makes the challenge
    single-use across replicas: of two concurrent verifies, exactly one wins.
    """
    stored = await redis_client.strict_get(key)
    if not stored:
        raise HTTPException(status_code=400, detail=missing_detail)
    if isinstance(stored, bytes):
        stored = stored.decode()
    if await redis_client.strict_delete(key) != 1:
        raise HTTPException(status_code=400, detail=missing_detail)
    return str(stored)


def _credential_descriptors(passkeys: Iterable[Passkey]) -> List[PublicKeyCredentialDescriptor]:
    """Stored passkeys as the descriptors webauthn's option builders take.

    `credential_id` is stored base64url (see /register/verify), so it is decoded
    with `base64url_to_bytes`. webauthn 2.x and 3.x both take descriptor
    objects here; a plain dict raises AttributeError in 3.x.
    """
    return [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(str(passkey.credential_id)))
        for passkey in passkeys
    ]


def _authenticator_selection(attachment: Optional[str]) -> AuthenticatorSelectionCriteria:
    """The registration ceremony's authenticator requirements.

    No attachment preference unless the client asks for one (owner decision
    2026-10-04, J3-006): `authenticatorAttachment` is omitted, so both
    platform authenticators (Touch ID, Windows Hello, Android) and roaming
    ones (security keys, a phone via hybrid) can register. Defaulting to
    `cross-platform` used to exclude every built-in authenticator; the
    dashboard sends no preference. A client that asks for `platform` or
    `cross-platform` still gets it. No resident key required and user
    verification preferred, as before. Built as the library's struct:
    webauthn 3.x reads `.resident_key` from it and crashed on the dict this
    used to pass.
    """
    return AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment(attachment) if attachment else None,
        resident_key=ResidentKeyRequirement.DISCOURAGED,
        require_resident_key=False,
        user_verification=UserVerificationRequirement.PREFERRED,
    )


def _reg_challenge_key(user_id) -> str:
    return f"passkey_challenge:{user_id}"


def _auth_challenge_key(session_id: str) -> str:
    return f"passkey_auth_challenge:{session_id}"


@router.post("/register/options")
async def get_registration_options(
    request: PasskeyRegisterOptionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get WebAuthn registration options"""
    # Get existing passkeys to exclude
    result = await db.execute(select(Passkey).where(Passkey.user_id == current_user.id))
    existing_passkeys = result.scalars().all()

    # Enforce the per-identity passkey cap (2026-08-23 fix — MAX_PASSKEYS_PER_IDENTITY
    # existed in config but was enforced nowhere). Checked here so the ceremony is
    # refused before the user touches their authenticator; re-checked at verify.
    max_passkeys = getattr(settings, "MAX_PASSKEYS_PER_IDENTITY", 10)
    if len(existing_passkeys) >= max_passkeys:
        raise HTTPException(
            status_code=400,
            detail=f"Passkey limit reached ({max_passkeys}). Remove one before adding another.",
        )

    # Generate registration options
    options = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name=get_rp_name(),
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.display_name or current_user.email,
        exclude_credentials=_credential_descriptors(existing_passkeys),
        authenticator_selection=_authenticator_selection(request.authenticator_attachment),
        timeout=60000,  # 60 seconds
    )

    # Store challenge in Redis with 5-minute expiry
    from app.core.redis import get_redis

    challenge = bytes_to_base64url(options.challenge)

    redis_client = await get_redis()
    # Strict write: the verify call may land on another replica. A challenge
    # Redis did not take answers 503 here, not "challenge expired" later.
    await redis_client.strict_set(
        _reg_challenge_key(current_user.id),
        challenge,
        ex=300,  # 5 minutes
    )

    # The library's own WebAuthn JSON (PublicKeyCredentialCreationOptionsJSON):
    # challenge, rp, user, pubKeyCredParams, timeout, excludeCredentials,
    # authenticatorSelection, attestation, all base64url where binary.
    # pubKeyCredParams is what verify_registration_response accepts, so the two
    # can no longer disagree.
    return json.loads(options_to_json(options))


@router.post("/register/verify")
async def verify_registration(
    request: PasskeyRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify WebAuthn registration"""
    # Read the one-time challenge from Redis, where /register/options stored it
    # (2026-08-23 fix — verify previously read user_metadata["webauthn_challenge"],
    # which options never wrote, so registration ALWAYS failed). Deleted after
    # read so a challenge can be used exactly once.
    from app.core.redis import get_redis

    redis_client = await get_redis()
    stored_challenge = await _consume_challenge(
        redis_client,
        _reg_challenge_key(current_user.id),
        "No registration in progress or challenge expired",
    )

    expected_challenge = base64url_to_bytes(stored_challenge)

    # Verify registration
    try:
        verification = verify_registration_response(
            credential=request.credential,
            expected_challenge=expected_challenge,
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {str(e)}")

    # webauthn 2.x and 3.x raise on every failed check (handled above); the
    # result object has no `verified` flag, and reading one raised
    # AttributeError (500) after a successful ceremony.

    # Store passkey
    credential_id = bytes_to_base64url(verification.credential_id)
    public_key = bytes_to_base64url(verification.credential_public_key)

    # Check if credential already exists
    existing_result = await db.execute(
        select(Passkey).where(Passkey.credential_id == credential_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="This passkey is already registered")

    # Re-check the cap at verify (defense in depth; the options step also checks).
    count_result = await db.execute(select(Passkey).where(Passkey.user_id == current_user.id))
    max_passkeys = getattr(settings, "MAX_PASSKEYS_PER_IDENTITY", 10)
    if len(count_result.scalars().all()) >= max_passkeys:
        raise HTTPException(status_code=400, detail=f"Passkey limit reached ({max_passkeys}).")

    # Create passkey
    passkey = Passkey(
        user_id=current_user.id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=verification.sign_count,
        name=request.name or f"Passkey {datetime.utcnow().strftime('%Y-%m-%d')}",
        authenticator_attachment=request.credential.get("authenticatorAttachment"),
    )

    db.add(passkey)

    # (Challenge already deleted from Redis above — one-time use.)

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="passkey_registered",
        activity_metadata={"passkey_id": str(passkey.id), "name": passkey.name},
    )
    db.add(activity)

    await db.commit()

    return {
        "verified": True,
        "passkey_id": str(passkey.id),
        "message": "Passkey successfully registered",
    }


@router.post("/authenticate/options")
async def get_authentication_options(
    request: PasskeyAuthOptionsRequest, db: Session = Depends(get_db)
):
    """Get WebAuthn authentication options"""
    allow_credentials: List[PublicKeyCredentialDescriptor] = []

    if request.email:
        # Passwordless login - get user's passkeys. Untenanted / staff pool
        # (platform passkey login; per-tenant email since 013 → scope to
        # single-row). End-user passkey auth would resolve its tenant separately.
        user = await get_user_by_email(db, request.email, tenant_id=None)
        if user:
            passkeys_result = await db.execute(select(Passkey).where(Passkey.user_id == user.id))
            passkeys = passkeys_result.scalars().all()
            allow_credentials = _credential_descriptors(passkeys)

    # Generate authentication options
    options = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement.PREFERRED,
        timeout=60000,
    )

    # Store challenge in Redis with 10-minute expiry
    from app.core.redis import get_redis

    challenge = bytes_to_base64url(options.challenge)

    # Generate session ID for this authentication attempt
    session_id = secrets.token_urlsafe(32)

    redis_client = await get_redis()
    # Strict write (see register/options).
    await redis_client.strict_set(
        _auth_challenge_key(session_id),
        challenge,
        ex=600,  # 10 minutes
    )

    return {
        "sessionId": session_id,  # Return session ID to client
        "challenge": challenge,
        "rpId": options.rp_id,
        "timeout": options.timeout,
        "allowCredentials": [
            {"id": bytes_to_base64url(cred.id), "type": "public-key"} for cred in allow_credentials
        ],
        "userVerification": options.user_verification,
    }


@router.post("/authenticate/verify")
async def verify_authentication(
    auth_request: PasskeyAuthRequest,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify WebAuthn authentication.

    2026-08-23 security fix: the challenge is read SERVER-SIDE from Redis keyed by
    the `session_id` returned by /authenticate/options — it is NOT accepted from
    the client. The prior version took `challenge` as a caller-supplied query
    param, which let a client present its own challenge and defeated replay
    protection entirely. The challenge is deleted after read (one-time use).
    """
    # Resolve the one-time challenge from the server side.
    from app.core.redis import get_redis

    redis_client = await get_redis()
    stored_challenge = await _consume_challenge(
        redis_client,
        _auth_challenge_key(session_id),
        "No authentication in progress or challenge expired",
    )

    # Get credential ID from response
    credential_id = auth_request.credential.get("id")
    if not credential_id:
        raise HTTPException(status_code=400, detail="Missing credential ID")

    # Find passkey
    passkey_result = await db.execute(select(Passkey).where(Passkey.credential_id == credential_id))
    passkey = passkey_result.scalar_one_or_none()

    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")

    # Get user
    user_result = await db.execute(select(User).where(User.id == passkey.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify authentication against the SERVER-STORED challenge.
    try:
        verification = verify_authentication_response(
            credential=auth_request.credential,
            expected_challenge=base64url_to_bytes(stored_challenge),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication verification failed: {str(e)}")

    # webauthn 2.x and 3.x raise on every failed check (handled above); the
    # result object has no `verified` flag, and reading one raised
    # AttributeError (500) after a successful ceremony.

    # Cloned-authenticator detection (2026-08-23): a non-increasing signature
    # counter means either a cloned credential or a replay. Authenticators that
    # don't implement a counter report 0/0 (allowed). Otherwise the new count must
    # strictly exceed the stored one. The library also guards this, but we refuse
    # explicitly and audit it rather than relying on library internals.
    if not (verification.new_sign_count == 0 and passkey.sign_count == 0):
        if verification.new_sign_count <= passkey.sign_count:
            db.add(
                ActivityLog(
                    user_id=user.id,
                    action="passkey_clone_suspected",
                    activity_metadata={
                        "passkey_id": str(passkey.id),
                        "stored_sign_count": passkey.sign_count,
                        "presented_sign_count": verification.new_sign_count,
                    },
                )
            )
            await db.commit()
            raise HTTPException(
                status_code=400,
                detail="Authentication refused: signature counter did not advance (possible cloned credential).",
            )

    # Update sign count
    passkey.sign_count = verification.new_sign_count
    passkey.last_used_at = datetime.utcnow()

    # Create the session the same way every other sign-in does, so it carries
    # a refresh-token family and is revocable like any other session. (This
    # called `AuthService.create_tokens`, which does not exist, and built a
    # `sessions` row without its required `token`: a verified passkey sign-in
    # ended in a 500.)
    client_ip = (
        request.client.host
        if request.client
        else request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
    )
    access_token, refresh_token, user_session = await AuthService.create_session(
        db,
        user,
        ip_address=client_ip,
        user_agent="Passkey Authentication",
    )
    tokens = {"access_token": access_token, "refresh_token": refresh_token}

    # Update user last sign in
    user.last_sign_in_at = datetime.utcnow()

    # Log activity
    activity = ActivityLog(
        user_id=user.id,
        action="passkey_authentication",
        activity_metadata={"passkey_id": str(passkey.id), "session_id": str(user_session.id)},
    )
    db.add(activity)

    await db.commit()

    return {
        "verified": True,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    }


@router.get("/", response_model=List[PasskeyResponse])
async def list_passkeys(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List user's passkeys"""
    result = await db.execute(
        select(Passkey)
        .where(Passkey.user_id == current_user.id)
        .order_by(Passkey.created_at.desc())
    )
    passkeys = result.scalars().all()

    return [
        PasskeyResponse(
            id=str(passkey.id),
            name=passkey.name,
            authenticator_attachment=passkey.authenticator_attachment,
            created_at=passkey.created_at,
            last_used_at=passkey.last_used_at,
            sign_count=passkey.sign_count,
        )
        for passkey in passkeys
    ]


@router.patch("/{passkey_id}", response_model=PasskeyResponse)
async def update_passkey(
    passkey_id: str,
    request: PasskeyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update passkey name"""
    try:
        passkey_uuid = uuid.UUID(passkey_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid passkey ID")

    result = await db.execute(
        select(Passkey).where(Passkey.id == passkey_uuid, Passkey.user_id == current_user.id)
    )
    passkey = result.scalar_one_or_none()

    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")

    passkey.name = request.name
    await db.commit()
    await db.refresh(passkey)

    return PasskeyResponse(
        id=str(passkey.id),
        name=passkey.name,
        authenticator_attachment=passkey.authenticator_attachment,
        created_at=passkey.created_at,
        last_used_at=passkey.last_used_at,
        sign_count=passkey.sign_count,
    )


@router.delete("/{passkey_id}")
async def delete_passkey(
    passkey_id: str,
    password: str,  # Require password for security
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a passkey"""
    # Verify password
    if not AuthService.verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")

    try:
        passkey_uuid = uuid.UUID(passkey_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid passkey ID")

    result = await db.execute(
        select(Passkey).where(Passkey.id == passkey_uuid, Passkey.user_id == current_user.id)
    )
    passkey = result.scalar_one_or_none()

    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="passkey_deleted",
        activity_metadata={"passkey_name": passkey.name},
    )
    db.add(activity)

    db.delete(passkey)
    await db.commit()

    return {"message": "Passkey deleted successfully"}


@router.get("/availability")
async def check_webauthn_availability():
    """Check if WebAuthn is available/supported"""
    return {
        "available": True,
        "platform_authenticator": True,  # Platform authenticator (Touch ID, Face ID, Windows Hello)
        "roaming_authenticator": True,  # USB security keys
        "conditional_mediation": True,  # Autofill UI for passkeys
        "user_verifying_platform_authenticator": True,
    }
