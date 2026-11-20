"""Account, password and session-helper methods of `AuthService`.

Split out of `app/services/auth_service.py` (2026-11-19) to keep every module
under the repository's 800-line pre-commit limit; no behaviour change.
`AuthService` inherits these, so every caller keeps calling
`AuthService.<method>(...)`. They are classmethods: `cls` is `AuthService`
when called through it, so `patch.object(AuthService, ...)` still reaches the
calls these methods make to each other and to `AuthService`'s own methods.

Methods that read the module globals tests patch on
`app.services.auth_service` (`get_redis`, `SessionStore`, `AuditLog`,
`token_revocation`, and `settings` for token minting) stay in
`auth_service.py`, so every existing patch target keeps reaching the code it
targets. `_decode_token` reads `settings` from this module; patch
`app.services.auth_account_methods.settings` (or an attribute of the shared
`settings` object) to change what it sees.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import jwt
import structlog
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.models import Session, User
from app.services.user_lookup import get_user_by_email

logger = structlog.get_logger()

# Password hashing - using bcrypt 2b to avoid passlib wrap bug detection issue
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


class AuthAccountMethods:
    """Mixin for `AuthService` (see the module docstring)."""

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def validate_password_strength(cls, password: str) -> Tuple[bool, Optional[str]]:
        """Validate password meets security requirements"""
        if len(password) < 12:  # Increased from 8 for better security
            return False, "Password must be at least 12 characters long"

        if len(password.encode("utf-8")) > 72:
            return False, "Password must not exceed 72 UTF-8 bytes"

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"

        return True, None

    @classmethod
    async def create_user(
        cls,
        db: AsyncSession,
        email: str,
        password: str,
        name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ) -> User:
        """Create a new user with hashed password"""
        # Validate password strength
        is_valid, error_msg = cls.validate_password_strength(password)
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
            password_hash=cls.hash_password(password),
            first_name=name,  # Use first_name field from User model
            tenant_id=tenant_id,
        )
        db.add(user)

        # Create audit log
        await cls.create_audit_log(
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

    @classmethod
    async def authenticate_user(cls, db: AsyncSession, email: str, password: str) -> Optional[User]:
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
        if not cls.verify_password(password, user.password_hash):
            logger.warning("Authentication failed - invalid password", user_id=str(user.id))

            # Log failed attempt
            await cls.create_audit_log(
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
        await cls.create_audit_log(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            event_type="login_success",
            event_data={},
        )

        await db.commit()

        logger.info("User authenticated", user_id=str(user.id))
        return user

    @classmethod
    async def invalidate_user_sessions(
        cls,
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

        revoked_count = await cls.revoke_sessions(sessions, reason=reason, strict=strict)

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

    @classmethod
    def _decode_token(cls, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
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

    @classmethod
    async def identify_token(
        cls, token: str, token_type: str = "access"
    ) -> Optional[Dict[str, Any]]:
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
            return await cls.verify_token(token, token_type)
        except RedisUnavailableError:
            logger.warning(
                "Revocation list unavailable; identifying the current session "
                "from signature-checked claims",
                token_type=token_type,
            )
            return cls._decode_token(token, token_type)

    @classmethod
    async def revoke_session(
        cls, db: AsyncSession, session_id: Any, *, reason: str = "user_revoked"
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
        await cls.revoke_sessions([session], reason=reason)
        return True

    @classmethod
    async def logout(cls, db: AsyncSession, session_id: UUID, user_id: UUID):
        """Logout user by revoking session"""
        # Get session
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return False

        await cls.revoke_sessions([session], reason="user_logout")

        # Create audit log
        await cls.create_audit_log(
            db=db,
            user_id=user_id,
            tenant_id=session.user.tenant_id,
            event_type="logout",
            event_data={"session_id": str(session_id)},
        )

        await db.commit()

        logger.info("User logged out", session_id=str(session_id), user_id=str(user_id))
        return True

    @classmethod
    def update_user(cls, db, user_id: str, user_data: dict) -> dict:
        """Update user information"""
        # Placeholder implementation for testing
        return {"updated": True}

    @classmethod
    def delete_user(cls, db, user_id: str) -> dict:
        """Delete a user account"""
        # Placeholder implementation for testing
        return {"deleted": True}

    @classmethod
    def get_user_sessions(cls, db, user_id: str) -> list:
        """Get all user sessions"""
        # Placeholder implementation for testing
        return [
            {"session_id": "session_1", "created_at": "2025-01-01T00:00:00"},
            {"session_id": "session_2", "created_at": "2025-01-01T01:00:00"},
        ]

    @classmethod
    def create_organization(cls, db, user_id: str, org_data: dict) -> dict:
        """Create a new organization"""
        # Placeholder implementation for testing
        return {
            "id": "org_123",
            "name": org_data.get("name", "Test Organization"),
            "slug": org_data.get("slug", "test-org"),
        }

    @classmethod
    def get_user_organizations(cls, db, user_id: str) -> list:
        """Get user's organizations"""
        # Placeholder implementation for testing
        return [
            {"id": "org_1", "name": "Org 1", "role": "admin"},
            {"id": "org_2", "name": "Org 2", "role": "member"},
        ]

    @classmethod
    def get_organization(cls, db, org_id: str) -> dict:
        """Get specific organization details"""
        # Placeholder implementation for testing
        return {"id": org_id, "name": "Test Organization", "members_count": 5}

    @classmethod
    def update_organization(cls, db, org_id: str, org_data: dict) -> dict:
        """Update organization details"""
        # Placeholder implementation for testing
        return {"updated": True}

    @classmethod
    def delete_organization(cls, db, org_id: str) -> dict:
        """Delete an organization"""
        # Placeholder implementation for testing
        return {"deleted": True}

    @classmethod
    def get_active_sessions(cls, db, user_id: str) -> list:
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

    @classmethod
    def revoke_all_sessions(cls, db, user_id: str) -> dict:
        """Revoke all user sessions except current"""
        # Placeholder implementation for testing
        return {"revoked_count": 3}

    @classmethod
    def extend_session(cls, db, session_id: str, extend_data: dict) -> dict:
        """Extend current session"""
        # Placeholder implementation for testing
        return {"extended": True, "new_expiry": "2025-01-02T00:00:00"}
