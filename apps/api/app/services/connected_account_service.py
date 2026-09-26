"""ConnectedAccount service — vault CRUD and OAuthAccount bridge."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.consent_purposes import (
    PURPOSE_STATUS_GRANTED,
    PURPOSE_STATUS_REVOKED,
    PURPOSES_METADATA_KEY,
    ConsentPurpose,
)
from app.models import ActivityLog, OAuthAccount, OAuthProvider, User
from app.models.connected_account import ConnectedAccount, ConnectedAccountStatus
from app.services.oauth import (
    OAuthService,
    ProviderRefreshRejected,
    ProviderRefreshUnavailable,
)

logger = logging.getLogger(__name__)

_PROVIDER_MAP = {
    "github": OAuthProvider.GITHUB,
    "slack": OAuthProvider.SLACK,
    "google": OAuthProvider.GOOGLE,
}

#: Providers whose stored access token expires and is refreshed before
#: delegation. A token from one of these with an unknown expiry is treated as
#: expired: Janua never hands out a provider token it cannot vouch for.
_REFRESHABLE_PROVIDERS = {"google"}

#: Refresh when the stored access token has less than this left.
TOKEN_REFRESH_SKEW = timedelta(seconds=120)


#: Statuses a connection can be revoked from (REVOKED is terminal history).
_LIVE_STATUSES = [ConnectedAccountStatus.ACTIVE.value, ConnectedAccountStatus.EXPIRED.value]

#: Providers whose tokens Janua revokes at the provider on connection revoke/unlink.
_PROVIDER_REVOCATION = {"google"}


@dataclass(frozen=True)
class ProviderTokenRef:
    """One provider credential to revoke at the provider, and where it came from."""

    provider_type: str
    token: Optional[str]
    token_kind: str  # "refresh" | "access"
    resource_type: str  # "connected_account" | "oauth_account"
    resource_id: str
    connection: Optional[ConnectedAccount] = None


class ReauthorizationRequired(Exception):
    """The stored credential cannot be made fresh; the user must re-consent."""


class ProviderTemporarilyUnavailable(Exception):
    """The provider could not refresh the credential right now (transient)."""


def purpose_grants(connection: ConnectedAccount) -> dict[str, Any]:
    metadata = connection.account_metadata or {}
    grants = metadata.get(PURPOSES_METADATA_KEY) or {}
    return grants if isinstance(grants, dict) else {}


def has_active_purpose_grant(connection: ConnectedAccount, purpose: ConsentPurpose) -> bool:
    """True only when the purpose is granted AND its scopes are still held."""
    grant = purpose_grants(connection).get(purpose.id)
    if not isinstance(grant, dict) or grant.get("status") != PURPOSE_STATUS_GRANTED:
        return False
    held = set(connection.oauth_scopes or [])
    return set(purpose.additional_scopes).issubset(held)


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class ConnectedAccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user: User, *, sync_oauth: bool = True) -> list[ConnectedAccount]:
        if sync_oauth:
            await self._sync_from_oauth_accounts(user)
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return list(result.scalars().all())

    async def get_for_user(
        self, user: User, connection_id: uuid.UUID
    ) -> Optional[ConnectedAccount]:
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == connection_id,
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, connection_id: uuid.UUID) -> Optional[ConnectedAccount]:
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == connection_id,
                ConnectedAccount.status == ConnectedAccountStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_live_for_provider(
        self, user_id: uuid.UUID, provider_type: str
    ) -> list[ConnectedAccount]:
        """The user's active or expired connections for one provider."""
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider_type == provider_type,
                ConnectedAccount.status.in_(_LIVE_STATUSES),
            )
        )
        return list(result.scalars().all())

    async def get_by_id_any_status(self, connection_id: uuid.UUID) -> Optional[ConnectedAccount]:
        """Load a connection whatever its status, so callers can refuse specifically."""
        result = await self.db.execute(
            select(ConnectedAccount).where(ConnectedAccount.id == connection_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _end_purposes(connection: ConnectedAccount, reason: str) -> list[str]:
        """Mark every granted purpose on the row revoked. Returns the ended ids."""
        metadata = dict(connection.account_metadata or {})
        grants = dict(purpose_grants(connection))
        ended: list[str] = []
        now = _utcnow_iso()
        for purpose_id, grant in grants.items():
            if isinstance(grant, dict) and grant.get("status") == PURPOSE_STATUS_GRANTED:
                grants[purpose_id] = {
                    **grant,
                    "status": PURPOSE_STATUS_REVOKED,
                    "revoked_at": now,
                    "revoked_reason": reason,
                }
                ended.append(purpose_id)
        if ended:
            metadata[PURPOSES_METADATA_KEY] = grants
            # Reassign (not mutate) so SQLAlchemy sees the JSON change.
            connection.account_metadata = metadata
        return ended

    async def revoke(
        self, user: User, connection_id: uuid.UUID
    ) -> Optional[tuple[ConnectedAccount, list[str]]]:
        """Revoke a connection locally and end every purpose granted on it.

        Commits. Returns ``(connection, ended_purpose_ids)``, or None when the
        user has no live (active or expired) connection with that id. The
        provider-side revocation is a separate step (`revoke_at_provider`)
        so that it can never block or undo this one.
        """
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == connection_id,
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.status.in_(_LIVE_STATUSES),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return None
        ended = self._end_purposes(account, "connection_revoked")
        account.status = ConnectedAccountStatus.REVOKED.value
        account.updated_at = datetime.utcnow()
        await self.db.commit()
        return account, ended

    async def revoke_for_provider(
        self, user_id: uuid.UUID, provider_type: str
    ) -> tuple[list[ConnectedAccount], list[str]]:
        """Revoke every live connection for a provider (used when it is unlinked).

        Does not commit; the caller owns the transaction. Returns the revoked
        rows and the ended purpose ids.
        """
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider_type == provider_type,
                ConnectedAccount.status.in_(_LIVE_STATUSES),
            )
        )
        accounts = list(result.scalars().all())
        ended: list[str] = []
        for account in accounts:
            ended.extend(self._end_purposes(account, "provider_unlinked"))
            account.status = ConnectedAccountStatus.REVOKED.value
            account.updated_at = datetime.utcnow()
        return accounts, ended

    async def revoke_at_provider(
        self,
        *,
        user_id: uuid.UUID,
        connections: Iterable[ConnectedAccount] = (),
        oauth_account_tokens: Iterable[ProviderTokenRef] = (),
    ) -> list[dict[str, Any]]:
        """Revoke already-locally-revoked credentials at the provider.

        Run AFTER the local revocation is committed. Prefers the refresh
        token (revoking it ends the whole provider grant), else the access
        token. Each attempt set is audited as ``consent.provider.revoked``
        with its outcome. On success the vault copy of the tokens is wiped;
        on failure the tokens are kept on the (already REVOKED, never
        delegable) row and ``account_metadata.provider_revocation`` records
        the failure so an operator can retry. Never raises.
        """
        refs: list[ProviderTokenRef] = []
        for conn in connections:
            token = conn.refresh_token_encrypted or conn.access_token_encrypted
            refs.append(
                ProviderTokenRef(
                    provider_type=conn.provider_type,
                    token=token,
                    token_kind="refresh" if conn.refresh_token_encrypted else "access",
                    resource_type="connected_account",
                    resource_id=str(conn.id),
                    connection=conn,
                )
            )
        refs.extend(oauth_account_tokens)

        outcomes: list[dict[str, Any]] = []
        seen_tokens: dict[str, dict[str, Any]] = {}
        try:
            for ref in refs:
                provider = _PROVIDER_MAP.get(ref.provider_type)
                if provider is None or ref.provider_type not in _PROVIDER_REVOCATION:
                    continue  # no provider-side revocation implemented (e.g. GitHub/Slack)
                if not ref.token:
                    result = {"outcome": "no_token", "attempts": 0}
                elif ref.token in seen_tokens:
                    result = {**seen_tokens[ref.token], "deduplicated": True}
                else:
                    result = await OAuthService.revoke_provider_token(provider, ref.token)
                    seen_tokens[ref.token] = result
                outcome = {
                    "provider": ref.provider_type,
                    "resource_type": ref.resource_type,
                    "resource_id": ref.resource_id,
                    "token_kind": ref.token_kind,
                    **result,
                }
                outcomes.append(outcome)
                self._apply_provider_revocation(ref.connection, outcome)
                self.db.add(
                    ActivityLog(
                        user_id=user_id,
                        action="consent.provider.revoked",
                        resource_type=ref.resource_type,
                        resource_id=ref.resource_id,
                        activity_metadata=outcome,
                    )
                )
                if outcome["outcome"] in ("failed", "no_token"):
                    logger.error(
                        "Provider revocation not confirmed for %s %s: %s",
                        ref.resource_type,
                        ref.resource_id,
                        outcome,
                    )
            await self.db.commit()
        except Exception:  # noqa: BLE001 - must never undo the local revocation
            logger.exception("Provider revocation bookkeeping failed for user %s", user_id)
            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                logger.exception("Rollback after provider revocation failure failed")
            outcomes.append({"outcome": "failed", "error": "internal_error"})
        return outcomes

    @staticmethod
    def _apply_provider_revocation(
        connection: Optional[ConnectedAccount], outcome: dict[str, Any]
    ) -> None:
        if connection is None:
            return
        metadata = dict(connection.account_metadata or {})
        metadata["provider_revocation"] = {
            "status": outcome["outcome"],
            "attempts": outcome.get("attempts", 0),
            "error": outcome.get("error"),
            "at": _utcnow_iso(),
        }
        connection.account_metadata = metadata
        if outcome["outcome"] in ("revoked", "already_invalid"):
            # Nothing left at the provider; drop the vault copy too.
            connection.access_token_encrypted = None
            connection.refresh_token_encrypted = None

    async def record_purpose_grant(
        self,
        *,
        user_id: uuid.UUID,
        oauth_account: OAuthAccount,
        purpose: ConsentPurpose,
        granted_scopes: Iterable[str],
    ) -> ConnectedAccount:
        """Upsert the provider connection with fresh tokens and record the grant.

        The live (ACTIVE or EXPIRED) row for this user+provider is updated in
        place — re-consent is how an EXPIRED connection becomes ACTIVE again.
        REVOKED rows are history and are never resurrected; a new row is made.
        Does not commit; the caller owns the transaction.
        """
        provider_type = purpose.provider
        scopes = list(dict.fromkeys(granted_scopes))
        result = await self.db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider_type == provider_type,
                ConnectedAccount.status.in_(
                    [ConnectedAccountStatus.ACTIVE.value, ConnectedAccountStatus.EXPIRED.value]
                ),
            )
        )
        account = result.scalars().first()
        if account is None:
            account = ConnectedAccount(
                id=uuid.uuid4(),
                user_id=user_id,
                provider_type=provider_type,
                provider_name=f"{provider_type.capitalize()} connection",
                account_metadata={"source": "purpose_consent"},
                created_by=user_id,
            )
            self.db.add(account)

        account.provider_id = oauth_account.provider_user_id
        account.access_token_encrypted = oauth_account.access_token
        if oauth_account.refresh_token:
            account.refresh_token_encrypted = oauth_account.refresh_token
        account.oauth_expires_at = oauth_account.token_expires_at
        account.oauth_scopes = scopes
        account.status = ConnectedAccountStatus.ACTIVE.value
        account.updated_at = datetime.utcnow()

        metadata = dict(account.account_metadata or {})
        grants = dict(purpose_grants(account))
        grants[purpose.id] = {
            "status": PURPOSE_STATUS_GRANTED,
            "scopes": list(purpose.additional_scopes),
            "granted_at": _utcnow_iso(),
        }
        metadata[PURPOSES_METADATA_KEY] = grants
        account.account_metadata = metadata
        return account

    async def ensure_fresh_access_token(self, connection: ConnectedAccount) -> None:
        """Refresh the stored provider access token if it is expired or close to it.

        Raises `ReauthorizationRequired` (connection is marked EXPIRED and
        committed) when the provider rejects the refresh token or there is
        none, and `ProviderTemporarilyUnavailable` when the provider cannot
        be reached. Never leaves a stale token looking usable.
        """
        now = datetime.utcnow()
        expires_at = connection.oauth_expires_at
        refreshable = connection.provider_type in _REFRESHABLE_PROVIDERS
        if expires_at is not None and expires_at > now + TOKEN_REFRESH_SKEW:
            return
        if expires_at is None and not refreshable:
            return  # provider issues non-expiring tokens (e.g. GitHub OAuth apps)

        provider = _PROVIDER_MAP.get(connection.provider_type)
        if not refreshable or provider is None or not connection.refresh_token_encrypted:
            await self._mark_expired(connection, "no_refresh_path")
            raise ReauthorizationRequired("no_refresh_path")

        try:
            tokens = await OAuthService.refresh_access_token(
                provider, connection.refresh_token_encrypted
            )
        except ProviderRefreshRejected as e:
            await self._mark_expired(connection, f"refresh_rejected:{e}")
            raise ReauthorizationRequired(str(e)) from e
        except ProviderRefreshUnavailable as e:
            logger.warning("Provider refresh unavailable for connection %s: %s", connection.id, e)
            raise ProviderTemporarilyUnavailable(str(e)) from e

        connection.access_token_encrypted = tokens["access_token"]
        if tokens.get("refresh_token"):
            connection.refresh_token_encrypted = tokens["refresh_token"]
        try:
            ttl = int(tokens.get("expires_in") or 3600)
        except (TypeError, ValueError):
            ttl = 3600
        connection.oauth_expires_at = now + timedelta(seconds=ttl)
        if tokens.get("scope"):
            connection.oauth_scopes = OAuthService._parse_scopes_from_tokens(tokens, provider)
        connection.updated_at = now
        await self.db.commit()

    async def _mark_expired(self, connection: ConnectedAccount, reason: str) -> None:
        connection.status = ConnectedAccountStatus.EXPIRED.value
        connection.updated_at = datetime.utcnow()
        metadata = dict(connection.account_metadata or {})
        metadata["expired_reason"] = reason
        metadata["expired_at"] = _utcnow_iso()
        connection.account_metadata = metadata
        await self.db.commit()
        logger.warning("Connection %s marked expired: %s", connection.id, reason)

    async def delegate_token(
        self,
        connection: ConnectedAccount,
        *,
        acting_user_id: uuid.UUID,
        purpose: str = "tool_execute",
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        if connection.user_id != acting_user_id:
            raise PermissionError("acting_user_mismatch")
        if not connection.access_token_encrypted:
            raise ValueError("no_access_token")

        connection.last_used_at = datetime.utcnow()
        await self.db.commit()

        expires_at = datetime.utcnow() + timedelta(seconds=min(ttl_seconds, 900))
        # Never advertise a lifetime longer than the provider token actually has.
        if connection.oauth_expires_at is not None and connection.oauth_expires_at < expires_at:
            expires_at = connection.oauth_expires_at
        return {
            "access_token": connection.access_token_encrypted,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat() + "Z",
            "purpose": purpose,
            "provider_type": connection.provider_type,
            "scopes": connection.oauth_scopes or [],
        }

    async def _sync_from_oauth_accounts(self, user: User) -> None:
        """Bootstrap ConnectedAccount rows from legacy OAuthAccount linkages."""
        result = await self.db.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
        oauth_accounts = result.scalars().all()
        if not oauth_accounts:
            return

        existing = await self.db.execute(
            select(ConnectedAccount.provider_type).where(ConnectedAccount.user_id == user.id)
        )
        existing_types = {row[0] for row in existing.all()}

        for oauth in oauth_accounts:
            provider_type = oauth.provider.value
            if provider_type not in _PROVIDER_MAP or provider_type in existing_types:
                continue
            if not oauth.access_token:
                continue

            provider_data = oauth.provider_data if isinstance(oauth.provider_data, dict) else {}
            scopes = provider_data.get("scopes") or []
            account = ConnectedAccount(
                id=uuid.uuid4(),
                user_id=user.id,
                provider_type=provider_type,
                provider_name=f"{provider_type.capitalize()} connection",
                provider_id=oauth.provider_user_id,
                access_token_encrypted=oauth.access_token,
                refresh_token_encrypted=oauth.refresh_token,
                oauth_scopes=list(scopes) if isinstance(scopes, list) else [],
                oauth_expires_at=oauth.token_expires_at,
                status=ConnectedAccountStatus.ACTIVE.value,
                account_metadata={"source": "oauth_account_sync"},
                created_by=user.id,
            )
            self.db.add(account)
            existing_types.add(provider_type)

        await self.db.commit()
