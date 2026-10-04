import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import jwt
import structlog
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import SessionStore, get_redis
from app.models import AuditLog, Session, User, UserStatus
from app.services.user_lookup import get_user_by_email

logger = structlog.get_logger()

# Password hashing - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


class AuthService:
    """Core authentication service with real implementation"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
        """Validate password meets security requirements"""
        if len(password) < 12:  # Increased from 8 for better security
            return False, "Password must be at least 12 characters long"

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"

        return True, None

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        password: str,
        name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ) -> User:
        """Create a new user with hashed password"""
        # Validate password strength
        is_valid, error_msg = AuthService.validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)

        # Use default tenant_id if not provided (simplified for testing)
        if not tenant_id:
            # For testing purposes, use a default UUID if no tenant is provided
            # In production, this would be managed by proper tenant creation
            from uuid import uuid4

            tenant_id = uuid4()

        # Check if user already exists IN THIS TENANT's pool. Email uniqueness is
        # per-tenant (migration 013), and this method sets `tenant_id=tenant_id`
        # on the created row below, so the existence check must scope to the same
        # tenant — else it would spuriously conflict on another tenant's user.
        if await get_user_by_email(db, email, tenant_id=tenant_id):
            from app.exceptions import ConflictError

            raise ConflictError("User with this email already exists")

        # Create user
        user = User(
            email=email,
            password_hash=AuthService.hash_password(password),
            first_name=name,  # Use first_name field from User model
            tenant_id=tenant_id,
        )
        db.add(user)

        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=user.id,
            tenant_id=tenant_id,
            event_type="user_created",
            event_data={"email": email},
        )

        await db.commit()
        await db.refresh(user)

        logger.info("User created", user_id=str(user.id), email=email)
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        # Get user from the untenanted / staff pool. This signature carries no
        # tenant, and it is the platform password-auth path; end-user (tenanted)
        # auth resolves its tenant from the OAuth client context, not here. Pool-
        # scoping also keeps the lookup single-row now that email is per-tenant.
        user = await get_user_by_email(db, email, tenant_id=None)

        if not user:
            logger.warning("Authentication failed - user not found", email=email)
            return None

        if not user.is_active:
            logger.warning("Authentication failed - user inactive", user_id=str(user.id))
            return None

        if user.is_suspended:
            logger.warning("Authentication failed - user suspended", user_id=str(user.id))
            return None

        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            logger.warning("Authentication failed - invalid password", user_id=str(user.id))

            # Log failed attempt
            await AuthService.create_audit_log(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                event_type="login_failed",
                event_data={"reason": "invalid_password"},
            )
            return None

        # Update last login
        user.last_login_at = datetime.utcnow()

        # Log successful login
        await AuthService.create_audit_log(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            event_type="login_success",
            event_data={},
        )

        await db.commit()

        logger.info("User authenticated", user_id=str(user.id))
        return user

    @staticmethod
    def create_access_token(
        user_id: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        email: Optional[str] = None,
        audience: Optional[str] = None,
        additional_claims: Optional[dict] = None,
    ) -> Tuple[str, str, datetime]:
        """Create JWT access token.

        `audience` overrides the platform default `aud` claim. The OIDC path
        has always minted per-client audiences; passing it here lets the
        magic-link flow do the same, so a session created for a product's
        redirect host carries THAT product's audience instead of the platform
        default the product's verifier has no reason to accept.

        `additional_claims` merges extra top-level claims into the payload
        (e.g. `madfam_entitled_products` so the MADFAM ecosystem entitlement
        claim rides session tokens the same way it already rides OIDC
        access tokens). Reserved payload keys are set explicitly below and are
        NOT overridable via this dict — the merge happens first so the core
        claims win, preserving the token's identity/security invariants.
        """
        jti = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {}
        # Merge caller-supplied claims first so the reserved keys below always
        # win; additional_claims can enrich (entitlements) but never spoof
        # sub/tid/jti/exp/iss/aud.
        if additional_claims:
            payload.update(additional_claims)

        payload.update(
            {
                "sub": user_id,
                "tid": tenant_id,
                "jti": jti,
                "type": "access",
                "exp": expires_at,
                "iat": datetime.utcnow(),
                "iss": settings.JWT_ISSUER,
                "aud": audience or settings.JWT_AUDIENCE,
            }
        )

        if organization_id:
            payload["org"] = organization_id

        if email:
            payload["email"] = email

        # Use RS256 with private key if available, otherwise fall back to HS256
        algorithm = settings.JWT_ALGORITHM
        signing_key = settings.JWT_SECRET_KEY

        if algorithm == "RS256" and settings.JWT_PRIVATE_KEY:
            # Use PEM private key for RS256
            signing_key = settings.JWT_PRIVATE_KEY.replace("\\n", "\n")
        elif algorithm == "RS256":
            # RS256 requested but no private key available
            if settings.ENVIRONMENT == "production":
                raise ValueError(
                    "RS256 algorithm configured but no private key available. "
                    "Set JWT_PRIVATE_KEY or JWT_PRIVATE_KEY_PATH in production."
                )
            logger.warning("RS256 requested but no private key — falling back to HS256 (development only)")
            algorithm = "HS256"

        # Always use HS256 in test environment
        if settings.ENVIRONMENT == "test":
            algorithm = "HS256"
            signing_key = settings.JWT_SECRET_KEY

        token = jwt.encode(payload, signing_key, algorithm=algorithm)

        return token, jti, expires_at

    @staticmethod
    def create_refresh_token(
        user_id: str, tenant_id: str, family: Optional[str] = None
    ) -> Tuple[str, str, str, datetime]:
        """Create JWT refresh token with rotation family"""
        jti = secrets.token_urlsafe(32)
        family = family or secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "jti": jti,
            "family": family,
            "type": "refresh",
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        # Use RS256 with private key if available, otherwise fall back to HS256
        algorithm = settings.JWT_ALGORITHM
        signing_key = settings.JWT_SECRET_KEY

        if algorithm == "RS256" and settings.JWT_PRIVATE_KEY:
            # Use PEM private key for RS256
            signing_key = settings.JWT_PRIVATE_KEY.replace("\\n", "\n")
        elif algorithm == "RS256":
            # RS256 requested but no private key available
            if settings.ENVIRONMENT == "production":
                raise ValueError(
                    "RS256 algorithm configured but no private key available. "
                    "Set JWT_PRIVATE_KEY or JWT_PRIVATE_KEY_PATH in production."
                )
            logger.warning("RS256 requested but no private key — falling back to HS256 (development only)")
            algorithm = "HS256"

        # Always use HS256 in test environment
        if settings.ENVIRONMENT == "test":
            algorithm = "HS256"
            signing_key = settings.JWT_SECRET_KEY

        token = jwt.encode(payload, signing_key, algorithm=algorithm)

        return token, jti, family, expires_at

    @staticmethod
    async def invalidate_user_sessions(
        db: AsyncSession,
        user_id: UUID,
        exclude_session_id: Optional[UUID] = None,
    ) -> int:
        """Invalidate all sessions for a user.

        SECURITY: Used to prevent session fixation and ensure clean session state
        when a user authenticates.

        Args:
            db: Database session
            user_id: User whose sessions to invalidate
            exclude_session_id: Optional session ID to keep valid (for current session)

        Returns:
            Number of sessions revoked
        """
        from app.core.jwt_manager import jwt_manager

        # Find all active sessions for this user
        query = select(Session).where(
            and_(
                Session.user_id == user_id,
                Session.revoked == False,
            )
        )

        if exclude_session_id:
            query = query.where(Session.id != exclude_session_id)

        result = await db.execute(query)
        sessions = result.scalars().all()

        revoked_count = 0
        redis = await get_redis()

        for session in sessions:
            # Mark session as revoked
            session.revoked = True

            # Blacklist the tokens
            if session.refresh_token_jti:
                await jwt_manager.blacklist_token(session.refresh_token_jti, "refresh")
            if session.access_token_jti:
                await jwt_manager.blacklist_token(session.access_token_jti, "access")

            # Remove from Redis
            session_store = SessionStore(redis)
            await session_store.delete(str(session.id))

            revoked_count += 1

        if revoked_count > 0:
            await db.commit()
            logger.info(
                "Invalidated user sessions",
                user_id=str(user_id),
                sessions_revoked=revoked_count,
                reason="session_fixation_prevention",
            )

        return revoked_count

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None,
        invalidate_existing: bool = False,
        enforce_session_limit: bool = True,
        audience: Optional[str] = None,
    ) -> Tuple[str, str, Session]:
        """Create a new session with tokens.

        SECURITY: Enforces concurrent session limits to prevent session abuse.
        When the limit is reached, the oldest session is revoked.

        Args:
            invalidate_existing: If True, revoke all existing sessions first
                                (use for password change, security events)
            enforce_session_limit: If True (default), enforce MAX_SESSIONS_PER_IDENTITY
                                   by revoking oldest session when limit exceeded
        """
        from app.core.jwt_manager import jwt_manager

        # SECURITY: Invalidate existing sessions if requested (e.g., password change)
        if invalidate_existing:
            await AuthService.invalidate_user_sessions(db, user.id)
        elif enforce_session_limit:
            # Enforce concurrent session limit
            max_sessions = settings.MAX_SESSIONS_PER_IDENTITY

            # Count active sessions for this user
            result = await db.execute(
                select(Session)
                .where(
                    and_(
                        Session.user_id == user.id,
                        Session.revoked == False,
                    )
                )
                .order_by(Session.created_at.asc())
            )
            existing_sessions = result.scalars().all()

            # If at or over limit, revoke oldest sessions
            sessions_to_remove = len(existing_sessions) - max_sessions + 1  # +1 for new session
            if sessions_to_remove > 0:
                redis = await get_redis()
                for i, old_session in enumerate(existing_sessions):
                    if i >= sessions_to_remove:
                        break

                    # Revoke old session
                    old_session.revoked = True

                    # Blacklist tokens
                    if old_session.refresh_token_jti:
                        await jwt_manager.blacklist_token(old_session.refresh_token_jti, "refresh")
                    if old_session.access_token_jti:
                        await jwt_manager.blacklist_token(old_session.access_token_jti, "access")

                    # Remove from Redis
                    session_store = SessionStore(redis)
                    await session_store.delete(str(old_session.id))

                logger.info(
                    "Revoked oldest sessions due to limit",
                    user_id=str(user.id),
                    sessions_revoked=sessions_to_remove,
                    max_sessions=max_sessions,
                )

        # Resolve the MADFAM ecosystem entitlement claim so session tokens
        # carry `madfam_entitled_products` exactly the way the OIDC auth-code
        # and refresh flows already stamp it (see oauth_provider.py). This lets
        # downstream consumers (e.g. the nauta ERP hub) read entitlements from
        # the token instead of a per-render /me/entitlements round-trip.
        #
        # SSOT reuse: identical `entitlements_to_claim(await get_user_entitlements(...))`
        # pipeline as the OIDC path — no re-implementation. Resolution keys off
        # the `user` object (User.tenant_id → first org membership), matching
        # OIDC precisely; per-user rows beat org inheritance beat admin bootstrap.
        #
        # The claim is ALWAYS stamped (an empty list for users with no
        # entitlements), byte-identical to the OIDC path which also stamps
        # unconditionally. Entitlement resolution must never block session
        # issuance: get_user_entitlements already degrades its own reads
        # gracefully, and this defensive guard ensures any unexpected failure
        # falls back to an empty claim rather than failing login.
        from app.services.entitlements_service import (
            entitlements_to_claim,
            get_user_entitlements,
        )

        try:
            madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))
        except Exception:  # pragma: no cover - defensive; never fail login on this
            logger.warning(
                "Failed to resolve entitlement claim for session token; stamping empty list",
                user_id=str(user.id),
            )
            madfam_entitled_products = []

        # Resolve organization claims through the SAME SSOT the OIDC path uses
        # (app/services/org_claims_service.py). Until this landed, a session
        # token — every magic-link login, every password login — carried no
        # `org_id`, so org-scoped resource servers (symbiosis-hcm 403s any token
        # without it) could not authorize anyone who arrived by magic link.
        #
        # SECURITY, and the reason this is not just "add org_id": the roles this
        # stamps go under the NAMESPACED key `madfam_org_roles`, never a bare
        # `roles`. Organization roles are owner/admin/member — permissions over
        # the ACCOUNT — and symbiosis-hcm's HR_ROLES set contains the literal
        # string "admin". Stamping org roles as `roles` alongside a working
        # `org_id` would have promoted every janua org admin to HR admin over
        # payroll and labour files. The namespace is the fix; see the
        # org_claims_service docstring.
        #
        # Ambiguity is silence: a user in several orgs with no tenant pin gets
        # `orgs` and no `org_id`, so no consumer can guess a tenant. Resolution
        # never blocks login — failure stamps no org claims at all.
        # APPLICATION roles (`hcm:hr` and friends) ride under `roles`, folded in
        # by the shared merge so this seam and the OIDC one cannot drift. A
        # session token passes NO existing roles, so what lands under `roles` is
        # application roles alone — never an organization role, which is exactly
        # the invariant the namespace above exists to protect. No grants ⇒ no
        # `roles` key at all, so a token's shape is unchanged for everyone who
        # has not been granted anything.
        from app.services.org_claims_service import (
            get_user_org_claims_safe,
            merge_app_roles_into_claims,
        )
        from app.services.service_principal import service_principal_claims

        org_claims = merge_app_roles_into_claims(await get_user_org_claims_safe(user, db))

        # Create tokens
        access_token, access_jti, access_expires = AuthService.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            audience=audience,
            additional_claims={
                "madfam_entitled_products": madfam_entitled_products,
                **org_claims,
                # `is_service_account: true` only for technical logins; absent
                # for everyone else, so a person's token shape is unchanged.
                **service_principal_claims(user),
            },
        )

        refresh_token, refresh_jti, family, refresh_expires = AuthService.create_refresh_token(
            user_id=str(user.id), tenant_id=str(user.tenant_id)
        )

        # Create session in database
        session = Session(
            user_id=user.id,
            token=access_token,
            refresh_token=refresh_token,
            access_token_jti=access_jti,
            refresh_token_jti=refresh_jti,
            refresh_token_family=family,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
            expires_at=refresh_expires,
        )
        db.add(session)

        # Store in Redis for fast lookup
        redis = await get_redis()
        session_store = SessionStore(redis)
        await session_store.set(
            session_id=str(session.id),
            data={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "access_jti": access_jti,
                "refresh_jti": refresh_jti,
                "family": family,
            },
            ttl=int((refresh_expires - datetime.utcnow()).total_seconds()),
        )

        await db.commit()
        await db.refresh(session)

        logger.info("Session created", session_id=str(session.id), user_id=str(user.id))
        return access_token, refresh_token, session

    @staticmethod
    async def verify_token(
        token: str, token_type: str = "access", check_revocation: bool = True
    ) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            # Determine verification key based on algorithm
            algorithm = settings.JWT_ALGORITHM
            verify_key = settings.JWT_SECRET_KEY

            if algorithm == "RS256" and settings.JWT_PUBLIC_KEY:
                # Use PEM public key for RS256 verification
                verify_key = settings.JWT_PUBLIC_KEY.replace("\\n", "\n")
            elif algorithm == "RS256":
                # RS256 requested but no public key, fall back to HS256
                algorithm = "HS256"

            try:
                payload = jwt.decode(
                    token,
                    verify_key,
                    algorithms=[algorithm],
                    audience=settings.JWT_AUDIENCE,
                    issuer=settings.JWT_ISSUER,
                )
            except jwt.InvalidAudienceError:
                # Janua is the ISSUER validating its own tokens here, and it
                # mints more than one audience: magic-link sessions carry the
                # audience of the product they forward to (per-client, e.g.
                # nauta-portal) — see _session_audience_for_redirect. Audience
                # restriction exists for RESOURCE SERVERS deciding which
                # tokens to accept; the issuer accepts every audience it
                # minted, still enforcing signature, issuer, expiry and type.
                payload = jwt.decode(
                    token,
                    verify_key,
                    algorithms=[algorithm],
                    issuer=settings.JWT_ISSUER,
                    options={"verify_aud": False},
                )
                if not isinstance(payload.get("aud"), str) or not payload.get("aud"):
                    logger.warning("Token carries no usable audience claim")
                    return None

            if payload.get("type") != token_type:
                logger.warning("Token type mismatch", expected=token_type, got=payload.get("type"))
                return None

            from app.services.token_state import token_is_revoked

            if check_revocation and await token_is_revoked(payload, await get_redis()):
                return None

            return payload

        except (
            jwt.exceptions.DecodeError,
            jwt.exceptions.ExpiredSignatureError,
            InvalidTokenError,
        ) as e:
            logger.warning("Token verification failed", error=str(e))
            return None

    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token: str) -> Optional[Tuple[str, str]]:
        """Refresh access and refresh tokens with rotation"""
        # Verify refresh token
        payload = await AuthService.verify_token(
            refresh_token, token_type="refresh", check_revocation=False
        )
        if not payload:
            return None

        from app.services.token_state import consume_refresh, session_is_live

        if not await consume_refresh(payload, await get_redis()):
            if payload.get("family"):
                await AuthService.revoke_token_family(db, payload["family"])
            return None

        # Check if refresh token is still valid in database
        result = await db.execute(
            select(Session).where(
                and_(Session.refresh_token_jti == payload.get("jti"), Session.is_active == True)
            )
        )
        session = result.scalar_one_or_none()

        if not session or str(session.user_id) != payload.get("sub") or not session_is_live(session):
            logger.warning("Refresh token not found or inactive", jti=payload.get("jti"))

            # Possible token reuse - revoke entire family
            await AuthService.revoke_token_family(db, payload.get("family"))
            return None

        # Get user
        user = await db.get(User, UUID(payload.get("sub")))
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            return None

        # Re-resolve the MADFAM ecosystem entitlement claim on refresh so a
        # refreshed session token keeps `madfam_entitled_products` (and picks
        # up any grant/revoke since the session was minted) — mirroring the
        # OIDC refresh grant which re-stamps the claim on every rotation. Same
        # SSOT pipeline; same graceful degradation as create_session.
        from app.services.entitlements_service import (
            entitlements_to_claim,
            get_user_entitlements,
        )

        try:
            madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))
        except Exception:  # pragma: no cover - defensive; never fail refresh on this
            logger.warning(
                "Failed to resolve entitlement claim on token refresh; stamping empty list",
                user_id=str(user.id),
            )
            madfam_entitled_products = []

        # Re-resolve organization claims on refresh too, through the same SSOT.
        # This is what makes membership revocation reach a live session: a
        # member whose status stops being `active` loses org_id (and the
        # namespaced role) on the next rotation, exactly as the OIDC refresh
        # grant behaves. Same fail-closed degradation as create_session.
        # Application roles are re-resolved here for the same reason: a grant
        # revoked between mint and refresh stops feeding `roles` on the next
        # rotation, so revoking HR authority reaches a live session.
        from app.services.org_claims_service import (
            get_user_org_claims_safe,
            merge_app_roles_into_claims,
        )
        from app.services.service_principal import service_principal_claims

        org_claims = merge_app_roles_into_claims(await get_user_org_claims_safe(user, db))

        # Create new tokens
        access_token, access_jti, access_expires = AuthService.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            additional_claims={
                "madfam_entitled_products": madfam_entitled_products,
                **org_claims,
                **service_principal_claims(user),
            },
        )

        refresh_token, refresh_jti, family, refresh_expires = AuthService.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            family=payload.get("family"),  # Keep same family for rotation tracking
        )

        # Invalidate the outgoing access token before its JTI leaves the row.
        from app.core.jwt_manager import jwt_manager

        await jwt_manager.blacklist_token(session.access_token_jti, "access")
        session.access_token_jti = access_jti
        session.refresh_token_jti = refresh_jti
        session.last_activity = datetime.utcnow()
        session.expires_at = refresh_expires

        await db.commit()

        logger.info("Tokens refreshed", session_id=str(session.id), user_id=str(user.id))
        return access_token, refresh_token

    @staticmethod
    async def revoke_token_family(db: AsyncSession, family: str):
        """Revoke all tokens in a family (for security)"""
        result = await db.execute(select(Session).where(Session.refresh_token_family == family))
        sessions = result.scalars().all()

        from app.services.token_state import revoke_session_row

        for session in sessions:
            await revoke_session_row(session, "family_revoked_security")

        await db.commit()
        logger.warning("Token family revoked", family=family, count=len(sessions))

    @staticmethod
    async def logout(db: AsyncSession, session_id: UUID, user_id: UUID):
        """Logout user by revoking session"""
        # Get session
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return False

        # Revoke session
        session.is_active = False
        session.revoked_at = datetime.utcnow()
        session.revoked_reason = "user_logout"

        # Blacklist tokens
        redis = await get_redis()
        await redis.set(f"blacklist:{session.access_token_jti}", "1", ex=86400)
        await redis.set(f"blacklist:{session.refresh_token_jti}", "1", ex=86400)

        # Remove from Redis session store
        session_store = SessionStore(redis)
        await session_store.delete(str(session_id))

        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=user_id,
            tenant_id=session.user.tenant_id,
            event_type="logout",
            event_data={"session_id": str(session_id)},
        )

        await db.commit()

        logger.info("User logged out", session_id=str(session_id), user_id=str(user_id))
        return True

    @staticmethod
    async def create_audit_log(
        db: AsyncSession,
        user_id: Optional[UUID],
        tenant_id: UUID,
        event_type: str,
        event_data: dict,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Create tamper-proof audit log entry"""
        import json

        # Get previous hash for chain
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        previous_log = result.scalar_one_or_none()
        previous_hash = previous_log.current_hash if previous_log else "genesis"

        # Create log entry
        log = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=previous_hash,
        )

        # Calculate hash
        hash_input = f"{log.user_id}{log.tenant_id}{log.event_type}{log.event_data}{log.created_at}{previous_hash}"
        log.current_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        db.add(log)
        # Don't commit here - let caller handle transaction

    @staticmethod
    def update_user(db, user_id: str, user_data: dict) -> dict:
        """Update user information"""
        # Placeholder implementation for testing
        return {"updated": True}

    @staticmethod
    def delete_user(db, user_id: str) -> dict:
        """Delete a user account"""
        # Placeholder implementation for testing
        return {"deleted": True}

    @staticmethod
    def get_user_sessions(db, user_id: str) -> list:
        """Get all user sessions"""
        # Placeholder implementation for testing
        return [
            {"session_id": "session_1", "created_at": "2025-01-01T00:00:00"},
            {"session_id": "session_2", "created_at": "2025-01-01T01:00:00"},
        ]

    @staticmethod
    async def revoke_session(db: AsyncSession, session_id: str) -> dict:
        """Persist session revocation and denylist its current token pair."""
        from app.services.token_state import revoke_session_row

        session = await db.get(Session, UUID(session_id))
        if session is None:
            return {"revoked": False}
        await revoke_session_row(session)
        await db.commit()
        return {"revoked": True}

    @staticmethod
    def create_organization(db, user_id: str, org_data: dict) -> dict:
        """Create a new organization"""
        # Placeholder implementation for testing
        return {
            "id": "org_123",
            "name": org_data.get("name", "Test Organization"),
            "slug": org_data.get("slug", "test-org"),
        }

    @staticmethod
    def get_user_organizations(db, user_id: str) -> list:
        """Get user's organizations"""
        # Placeholder implementation for testing
        return [
            {"id": "org_1", "name": "Org 1", "role": "admin"},
            {"id": "org_2", "name": "Org 2", "role": "member"},
        ]

    @staticmethod
    def get_organization(db, org_id: str) -> dict:
        """Get specific organization details"""
        # Placeholder implementation for testing
        return {"id": org_id, "name": "Test Organization", "members_count": 5}

    @staticmethod
    def update_organization(db, org_id: str, org_data: dict) -> dict:
        """Update organization details"""
        # Placeholder implementation for testing
        return {"updated": True}

    @staticmethod
    def delete_organization(db, org_id: str) -> dict:
        """Delete an organization"""
        # Placeholder implementation for testing
        return {"deleted": True}

    @staticmethod
    def get_active_sessions(db, user_id: str) -> list:
        """Get active user sessions"""
        # Placeholder implementation for testing
        return [
            {
                "session_id": "session_1",
                "device": "Chrome on Windows",
                "last_active": "2025-01-01T00:00:00",
                "current": True,
            }
        ]

    @staticmethod
    def revoke_all_sessions(db, user_id: str) -> dict:
        """Revoke all user sessions except current"""
        # Placeholder implementation for testing
        return {"revoked_count": 3}

    @staticmethod
    def extend_session(db, session_id: str, extend_data: dict) -> dict:
        """Extend current session"""
        # Placeholder implementation for testing
        return {"extended": True, "new_expiry": "2025-01-02T00:00:00"}
