import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Tuple
from uuid import UUID

import jwt
import structlog
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import SessionStore, get_redis
from app.core.redis_circuit_breaker import RedisUnavailableError, ResilientRedisClient
from app.models import AuditLog, Session, User
from app.services import token_revocation
from app.services.user_lookup import get_user_by_email

logger = structlog.get_logger()

# Password hashing - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


async def _blacklist_jti(redis: ResilientRedisClient, jti: Any, ttl: int, *, reason: str) -> None:
    """Add a JTI to the revocation list that `AuthService.verify_token` reads.

    Best-effort (see `token_revocation`): the database row (`sessions`) is the
    durable record these flows also update, and a write Redis did not take is
    logged as an error instead of passing silently.
    """
    await token_revocation.revoke_jti(redis, jti, ttl, reason=reason)


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
    async def revoke_sessions(
        sessions: Iterable[Session], *, reason: str, strict: bool = False
    ) -> int:
        """Revoke `sessions` rows: the one implementation every revocation path uses.

        For each row:

        - the row is marked revoked with every flag Janua reads (`revoked`,
          `is_active = False`, `revoked_at`, `revoked_reason`), so
          `/auth/refresh`, the sessions list, `janua_sso` resolution, account
          switching and the account chooser all stop accepting it;
        - its refresh-token family is revoked (`revoked_family:<family>`) and
          its current refresh JTI is blacklisted, until the row's own expiry;
        - its current access-token JTI is blacklisted for the access-token
          lifetime, so routes that read the revocation list refuse it;
        - its fast-lookup entry in the Redis session store is dropped.

        Redis writes are best-effort (logged on failure) by default: the row
        is the durable record and `/auth/refresh` checks it. With
        `strict=True` (password reset) the revocation-list writes raise
        `RedisUnavailableError` when Redis cannot take them, so the caller can
        refuse the whole operation (503) before committing anything. The
        session-store eviction stays best-effort either way: it is a cache.
        The caller commits. Returns the number of rows passed in.
        """
        redis = await get_redis()
        session_store = SessionStore(redis)
        now = datetime.utcnow()
        count = 0
        for session in sessions:
            session.revoked = True
            session.is_active = False
            session.revoked_at = now
            session.revoked_reason = reason

            refresh_ttl = token_revocation.seconds_until(
                getattr(session, "expires_at", None), token_revocation.refresh_token_ttl()
            )
            await token_revocation.revoke_family(
                redis,
                getattr(session, "refresh_token_family", None),
                refresh_ttl,
                reason=reason,
                strict=strict,
            )
            await token_revocation.revoke_jti(
                redis,
                getattr(session, "refresh_token_jti", None),
                refresh_ttl,
                reason=reason,
                strict=strict,
            )
            await token_revocation.revoke_jti(
                redis,
                getattr(session, "access_token_jti", None),
                token_revocation.access_token_ttl(),
                reason=reason,
                strict=strict,
            )
            if getattr(session, "id", None) is not None:
                await session_store.delete(str(session.id))
            count += 1
        if count:
            logger.info("Sessions revoked", count=count, reason=reason)
        return count

    @staticmethod
    async def revoke_access_token(
        payload: Dict[str, Any], *, reason: str, strict: bool = False
    ) -> None:
        """Blacklist one access token's JTI until the token's own expiry."""
        await token_revocation.revoke_jti(
            await get_redis(),
            payload.get("jti"),
            token_revocation.seconds_until(payload.get("exp"), token_revocation.access_token_ttl()),
            reason=reason,
            strict=strict,
        )

    @staticmethod
    async def invalidate_user_sessions(
        db: AsyncSession,
        user_id: UUID,
        exclude_session_id: Optional[UUID] = None,
        reason: str = "sessions_invalidated",
        *,
        strict: bool = False,
        commit: bool = True,
    ) -> int:
        """Revoke every live session of a user, optionally keeping one.

        Used by password change (keeping the session that changed it), by
        password reset (keeping none) and by security events that sign a user
        out everywhere. Each revoked row's refresh-token family stops
        refreshing (see `revoke_sessions`).

        Args:
            db: Database session
            user_id: User whose sessions to invalidate
            exclude_session_id: Optional session ID to keep valid (for current session)
            reason: Recorded in `sessions.revoked_reason`
            strict: Raise `RedisUnavailableError` when a revocation-list write
                cannot be stored (see `revoke_sessions`)
            commit: Commit the revoked rows here. Pass False to commit them
                in the caller's own transaction (password reset commits the
                revoked rows and the new password together)

        Returns:
            Number of sessions revoked
        """
        query = select(Session).where(
            and_(
                Session.user_id == user_id,
                Session.revoked == False,  # noqa: E712 - SQL expression
            )
        )

        if exclude_session_id:
            query = query.where(Session.id != exclude_session_id)

        result = await db.execute(query)
        sessions = result.scalars().all()

        revoked_count = await AuthService.revoke_sessions(sessions, reason=reason, strict=strict)

        if revoked_count > 0:
            if commit:
                await db.commit()
            logger.info(
                "Invalidated user sessions",
                user_id=str(user_id),
                sessions_revoked=revoked_count,
                reason=reason,
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
                # Evicted sessions are revoked like any other: their refresh
                # families stop refreshing (the device signs in again).
                await AuthService.revoke_sessions(
                    existing_sessions[:sessions_to_remove], reason="session_limit"
                )

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
    def _decode_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Signature, issuer, expiry, audience and type checks only. No Redis.

        Answers whether Janua minted this token and it has not expired. It does
        NOT answer whether the token was revoked; `verify_token` does that.
        """
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

            return payload

        except (
            jwt.exceptions.DecodeError,
            jwt.exceptions.ExpiredSignatureError,
            InvalidTokenError,
        ) as e:
            logger.warning("Token verification failed", error=str(e))
            return None

    @staticmethod
    async def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token, including the revocation list.

        Returns None for a token that is invalid, expired or revoked.

        Fails closed: the revocation list (`blacklist:<jti>`) is read with a
        strict Redis operation. When Redis cannot answer, this raises
        `RedisUnavailableError` (answered as 503 + Retry-After by
        `redis_unavailable_handler`) instead of treating the token as not
        revoked. Until 2026-10 the read went through the circuit breaker's
        fallback, whose answer while Redis was unreachable was "not revoked",
        so a logged-out or rotated-away token was accepted during an outage.
        """
        payload = AuthService._decode_token(token, token_type)
        if payload is None:
            return None

        # Revocation list: the JTI under both spellings Janua writes, and for a
        # refresh token its rotation family (sign-out, password change, session
        # deletion, family revocation, POST /oauth/revoke). See token_revocation.
        redis = await get_redis()
        if await token_revocation.is_revoked(redis, payload, token_type):
            logger.warning("Token is revoked", jti=payload.get("jti"), token_type=token_type)
            return None

        return payload

    @staticmethod
    async def identify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Claims of a token the request has ALREADY been authenticated with.

        For bookkeeping only (which session is "this" one: sign-out, password
        change, the sessions list), never to decide whether to accept a
        request. With a healthy Redis it is exactly `verify_token`. When Redis
        cannot answer it falls back to the signature-checked claims, because
        failing these callers would not protect anything: sign-out must still
        revoke the session row and clear cookies, and the sessions list must
        still render. Revoking an already-revoked session again is harmless.
        """
        try:
            return await AuthService.verify_token(token, token_type)
        except RedisUnavailableError:
            logger.warning(
                "Revocation list unavailable; identifying the current session "
                "from signature-checked claims",
                token_type=token_type,
            )
            return AuthService._decode_token(token, token_type)

    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token: str) -> Optional[Tuple[str, str]]:
        """Refresh access and refresh tokens with rotation.

        Refused (None) when the token is invalid or expired, on the revocation
        list (its JTI or its family; strict read, 503 when Redis is down), or
        when its `sessions` row is not live: signed out, revoked by password
        change, session-limit eviction, `DELETE /sessions/{id}` or an admin,
        or deactivated by family revocation. The row check is what makes a
        revocation stick even when the Redis write behind it was lost.
        """
        # Verify refresh token
        payload = await AuthService.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None

        # The row this refresh token is the current token of. Looked up by JTI
        # alone: a revoked row must be told apart from a JTI no row holds.
        result = await db.execute(
            select(Session).where(Session.refresh_token_jti == payload.get("jti"))
        )
        session = result.scalar_one_or_none()

        if not session:
            logger.warning(
                "Refresh token is not the current token of any session", jti=payload.get("jti")
            )

            # A rotated-away token presented again: possible theft. Revoke the
            # entire family.
            await AuthService.revoke_token_family(db, payload.get("family"))
            return None

        if not token_revocation.session_is_live(session):
            logger.warning(
                "Refresh refused: session revoked or expired",
                session_id=str(session.id),
                reason=session.revoked_reason,
            )
            return None

        # Get user
        user = await db.get(User, UUID(payload.get("sub")))
        if not user or not user.is_active:
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

        # Update session
        session.access_token_jti = access_jti
        session.refresh_token_jti = refresh_jti
        session.last_activity = datetime.utcnow()
        session.expires_at = refresh_expires

        # Blacklist old refresh token
        redis = await get_redis()
        await _blacklist_jti(
            redis,
            payload.get("jti"),
            int((refresh_expires - datetime.utcnow()).total_seconds()),
            reason="refresh_rotation",
        )

        await db.commit()

        logger.info("Tokens refreshed", session_id=str(session.id), user_id=str(user.id))
        return access_token, refresh_token

    @staticmethod
    async def revoke_token_family(db: AsyncSession, family: str):
        """Revoke all tokens in a family (for security)"""
        sessions: list[Session] = []
        if family:
            result = await db.execute(select(Session).where(Session.refresh_token_family == family))
            sessions = list(result.scalars().all())

        await AuthService.revoke_sessions(sessions, reason="family_revoked_security")
        # The family key also covers a family whose row is already gone.
        await token_revocation.revoke_family(
            await get_redis(), family, reason="family_revoked_security"
        )

        await db.commit()
        logger.warning("Token family revoked", family=family, count=len(sessions))

    @staticmethod
    async def revoke_session(
        db: AsyncSession, session_id: Any, *, reason: str = "user_revoked"
    ) -> bool:
        """Revoke one `sessions` row by id. Returns whether a row was found.

        The caller decides who may revoke it (owner or admin) and commits.
        """
        try:
            session_uuid = session_id if isinstance(session_id, UUID) else UUID(str(session_id))
        except (ValueError, AttributeError, TypeError):
            return False
        result = await db.execute(select(Session).where(Session.id == session_uuid))
        session = result.scalar_one_or_none()
        if session is None:
            return False
        await AuthService.revoke_sessions([session], reason=reason)
        return True

    @staticmethod
    async def logout(db: AsyncSession, session_id: UUID, user_id: UUID):
        """Logout user by revoking session"""
        # Get session
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return False

        await AuthService.revoke_sessions([session], reason="user_logout")

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
