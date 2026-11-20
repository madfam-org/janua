import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Tuple
from uuid import UUID, uuid4

import jwt
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import SessionStore, get_redis
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import AuditLog, Session, User
from app.services import token_revocation
from app.services.auth_account_methods import AuthAccountMethods, pwd_context  # noqa: F401

logger = structlog.get_logger()


async def _blacklist_jti(redis: ResilientRedisClient, jti: Any, ttl: int, *, reason: str) -> None:
    """Add a JTI to the revocation list that `AuthService.verify_token` reads.

    Best-effort (see `token_revocation`): the database row (`sessions`) is the
    durable record these flows also update, and a write Redis did not take is
    logged as an error instead of passing silently.
    """
    await token_revocation.revoke_jti(redis, jti, ttl, reason=reason)


class AuthService(AuthAccountMethods):
    """Core authentication service with real implementation"""


    @staticmethod
    def create_access_token(
        user_id: str,
        tenant_id: str,
        organization_id: Optional[str] = None,
        email: Optional[str] = None,
        audience: Optional[str] = None,
        additional_claims: Optional[dict] = None,
        family: Optional[str] = None,
    ) -> Tuple[str, str, datetime]:
        """Create JWT access token.

        `family` is the refresh-token family of the session this token belongs
        to. It is stamped as the `family` claim so that revoking the session
        (`revoked_family:<family>`) also refuses access tokens minted before
        the session's latest refresh, not only its current one.

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
        if family:
            payload["family"] = family

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
            logger.warning(
                "RS256 requested but no private key — falling back to HS256 (development only)"
            )
            algorithm = "HS256"

        # Always use HS256 in test environment
        if settings.ENVIRONMENT == "test":
            algorithm = "HS256"
            signing_key = settings.JWT_SECRET_KEY

        token = jwt.encode(payload, signing_key, algorithm=algorithm)

        return token, jti, expires_at

    @staticmethod
    def create_refresh_token(
        user_id: str,
        tenant_id: str,
        family: Optional[str] = None,
        authentication_assurance: Optional[dict] = None,
        audience: Optional[str] = None,
    ) -> Tuple[str, str, str, datetime]:
        """Create JWT refresh token with rotation family"""
        jti = secrets.token_urlsafe(32)
        family = family or secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        payload = {
            **(authentication_assurance or {}),
            "session_audience": audience,
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
            logger.warning(
                "RS256 requested but no private key — falling back to HS256 (development only)"
            )
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
    async def create_session(
        db: AsyncSession,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None,
        invalidate_existing: bool = False,
        enforce_session_limit: bool = True,
        audience: Optional[str] = None,
        authentication_methods: Optional[list[str]] = None,
        authenticated_at: Optional[datetime] = None,
        mfa_verified_at: Optional[datetime] = None,
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
        from app.services.spanish_formality import spanish_formality_claims

        org_claims = merge_app_roles_into_claims(await get_user_org_claims_safe(user, db))

        # `{product}_tier` claims (G1-1): the primary org's product tiers merged
        # with the user's own active grants. Spread FIRST so no other claim can
        # be overridden by a product slug; never blocks login.
        from app.services.entitlements_service import get_product_tier_claims

        tier_claims = await get_product_tier_claims(user, db, org_id=org_claims.get("org_id"))

        from app.auth.authentication_assurance import assurance_claims

        session_id = uuid4()
        evidence = assurance_claims(
            authentication_methods, authenticated_at, mfa_verified_at, session_id
        )

        # Create tokens
        # Bind access and refresh to the same revocable token family.
        family = secrets.token_urlsafe(32)
        access_token, access_jti, access_expires = AuthService.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            audience=audience,
            family=family,
            additional_claims={
                **tier_claims,
                **evidence,
                "madfam_entitled_products": madfam_entitled_products,
                **org_claims,
                # `is_service_account: true` only for technical logins; absent
                # for everyone else, so a person's token shape is unchanged.
                **service_principal_claims(user),
                # `spanish_formality` ("tu" | "usted") only once the person has
                # answered; absent otherwise. Re-read at every refresh.
                **spanish_formality_claims(user),
            },
        )

        refresh_token, refresh_jti, family, refresh_expires = AuthService.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            authentication_assurance=evidence,
            audience=audience,
            family=family,
        )

        # Create session in database
        session = Session(
            id=session_id,
            authentication_methods=list(authentication_methods or []),
            authenticated_at=authenticated_at,
            mfa_verified_at=mfa_verified_at,
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

        from app.auth.authentication_assurance import (
            has_mfa_assurance,
            session_assurance,
            user_requires_mfa,
        )

        evidence = session_assurance(session)
        if await user_requires_mfa(db, user) and not has_mfa_assurance(evidence):
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
        from app.services.spanish_formality import spanish_formality_claims

        org_claims = merge_app_roles_into_claims(await get_user_org_claims_safe(user, db))

        # `{product}_tier` re-resolved on refresh, so a grant or a cancel since
        # the last mint reaches the live session (G1-1).
        from app.services.entitlements_service import get_product_tier_claims

        tier_claims = await get_product_tier_claims(user, db, org_id=org_claims.get("org_id"))

        # Create new tokens
        access_token, access_jti, access_expires = AuthService.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            audience=payload.get("session_audience"),
            family=payload.get("family"),
            additional_claims={
                **tier_claims,
                **evidence,
                "madfam_entitled_products": madfam_entitled_products,
                **org_claims,
                **service_principal_claims(user),
                **spanish_formality_claims(user),
            },
        )

        refresh_token, refresh_jti, family, refresh_expires = AuthService.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            family=payload.get("family"),  # Keep same family for rotation tracking
            authentication_assurance=evidence,
            audience=payload.get("session_audience"),
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


