"""
Audit logging service with Cloudflare R2 integration
"""

import asyncio
import hashlib
import json
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import and_, select, text
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import logger
from app.models import AuditLog


class AuditEventType(str, Enum):
    """Audit event types"""

    # Authentication events
    AUTH_SIGNIN = "auth.signin"
    AUTH_SIGNOUT = "auth.signout"
    AUTH_SIGNUP = "auth.signup"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    AUTH_PASSWORD_CHANGE = "auth.password_change"
    AUTH_MFA_ENABLE = "auth.mfa_enable"
    AUTH_MFA_DISABLE = "auth.mfa_disable"
    AUTH_PASSKEY_ADD = "auth.passkey_add"
    AUTH_PASSKEY_REMOVE = "auth.passkey_remove"

    # Session events
    SESSION_CREATE = "session.create"
    SESSION_REFRESH = "session.refresh"
    SESSION_REVOKE = "session.revoke"
    SESSION_EXPIRE = "session.expire"

    # User management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_SUSPEND = "user.suspend"
    USER_REACTIVATE = "user.reactivate"

    # Organization events
    ORG_CREATE = "org.create"
    ORG_UPDATE = "org.update"
    ORG_DELETE = "org.delete"
    ORG_MEMBER_ADD = "org.member_add"
    ORG_MEMBER_REMOVE = "org.member_remove"
    ORG_ROLE_CHANGE = "org.role_change"

    # Invitation events. The invitation service has referenced all four of
    # these since it was written; none of them existed, so every invitation
    # operation raised AttributeError at its audit call.
    INVITATION_CREATE = "invitation.create"
    INVITATION_ACCEPT = "invitation.accept"
    INVITATION_REVOKE = "invitation.revoke"
    INVITATION_RESEND = "invitation.resend"

    # API events
    API_KEY_CREATE = "api.key_create"
    API_KEY_ROTATE = "api.key_rotate"
    API_KEY_REVOKE = "api.key_revoke"
    API_RATE_LIMIT = "api.rate_limit"

    # Security events
    SECURITY_THREAT_DETECTED = "security.threat_detected"
    SECURITY_BRUTE_FORCE = "security.brute_force"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious"
    SECURITY_ACCESS_DENIED = "security.access_denied"

    # Policy / RBAC events
    # `app/routers/v1/policies.py` and `app/services/policy_engine.py` referenced
    # these seven members before they were defined, so each handler raised
    # AttributeError on the audit call even when the query above it succeeded.
    POLICY_CREATE = "policy.create"
    POLICY_UPDATE = "policy.update"
    POLICY_DELETE = "policy.delete"
    POLICY_EVALUATE = "policy.evaluate"
    ROLE_CREATE = "role.create"
    ROLE_ASSIGN = "role.assign"
    ROLE_UNASSIGN = "role.unassign"

    # Billing events
    BILLING_SUBSCRIPTION_CREATE = "billing.subscription_create"
    BILLING_SUBSCRIPTION_UPDATE = "billing.subscription_update"
    BILLING_SUBSCRIPTION_CANCEL = "billing.subscription_cancel"
    BILLING_PAYMENT_SUCCESS = "billing.payment_success"
    BILLING_PAYMENT_FAILED = "billing.payment_failed"

    # Entitlement events. Admin grant/revoke of product entitlements for a user
    # or an org (POST/DELETE /api/v1/admin/entitlements/{user,org}). Every
    # mutation of the entitlement surface is audited — it is an auth-system write.
    ENTITLEMENT_GRANT = "entitlement.grant"
    ENTITLEMENT_REVOKE = "entitlement.revoke"

    # Application-role events. Grant/revoke of a per-organization-member
    # application role (`hcm:hr` and friends) via the internal app-roles API.
    # Distinct from ROLE_ASSIGN/ROLE_UNASSIGN, which are janua's own RBAC:
    # these grant authority INSIDE ANOTHER PRODUCT — payroll and labour files
    # in symbiosis-hcm's case — so they get their own event names rather than
    # being indistinguishable from an account-role change in the trail.
    APP_ROLE_GRANT = "app_role.grant"
    APP_ROLE_REVOKE = "app_role.revoke"

    # A machine token was minted CARRYING application roles — authority inside
    # another product, held by a service client rather than a person. Logged
    # separately from the human grant events because the grant record is
    # different (`oauth_clients.allowed_scopes`, not a membership row) and
    # because "which service read payroll, when" is a question an auditor asks
    # in its own right. Only emitted when the token actually carries app roles:
    # an ordinary service token writes nothing and its cost is unchanged.
    SERVICE_TOKEN_APP_ROLES = "service_token.app_roles"

    # Compliance events - GDPR
    GDPR_CONSENT_GIVEN = "gdpr.consent_given"
    GDPR_CONSENT_WITHDRAWN = "gdpr.consent_withdrawn"
    GDPR_CONSENT_UPDATED = "gdpr.consent_updated"
    GDPR_DATA_EXPORT = "gdpr.data_export"
    GDPR_DATA_DELETION = "gdpr.data_deletion"
    GDPR_DATA_RECTIFICATION = "gdpr.data_rectification"
    GDPR_DATA_PORTABILITY = "gdpr.data_portability"
    GDPR_PROCESSING_RESTRICTION = "gdpr.processing_restriction"
    GDPR_OBJECTION_PROCESSING = "gdpr.objection_processing"
    GDPR_BREACH_NOTIFICATION = "gdpr.breach_notification"

    # Compliance events - SOC 2
    SOC2_ACCESS_GRANTED = "soc2.access_granted"
    SOC2_ACCESS_DENIED = "soc2.access_denied"
    SOC2_ACCESS_REVOKED = "soc2.access_revoked"
    SOC2_PRIVILEGE_ESCALATION = "soc2.privilege_escalation"
    SOC2_ADMIN_ACTION = "soc2.admin_action"
    SOC2_CONFIG_CHANGE = "soc2.config_change"
    SOC2_BACKUP_CREATED = "soc2.backup_created"
    SOC2_BACKUP_RESTORED = "soc2.backup_restored"
    SOC2_INCIDENT_REPORTED = "soc2.incident_reported"
    SOC2_VULNERABILITY_DETECTED = "soc2.vulnerability_detected"

    # Compliance events - HIPAA
    HIPAA_PHI_ACCESS = "hipaa.phi_access"
    HIPAA_PHI_EXPORT = "hipaa.phi_export"
    HIPAA_PHI_MODIFICATION = "hipaa.phi_modification"
    HIPAA_PHI_DELETION = "hipaa.phi_deletion"
    HIPAA_BREACH_DETECTED = "hipaa.breach_detected"
    HIPAA_AUDIT_ACCESS = "hipaa.audit_access"
    HIPAA_EMERGENCY_ACCESS = "hipaa.emergency_access"

    # Data governance events
    DATA_RETENTION_EXPIRED = "data.retention_expired"
    DATA_ARCHIVAL = "data.archival"
    DATA_CLASSIFICATION = "data.classification"
    DATA_ANONYMIZATION = "data.anonymization"
    DATA_PSEUDONYMIZATION = "data.pseudonymization"

    # Privacy events
    PRIVACY_SETTINGS_UPDATED = "privacy.settings_updated"
    PRIVACY_PREFERENCE_CHANGED = "privacy.preference_changed"
    PRIVACY_POLICY_ACCEPTED = "privacy.policy_accepted"
    PRIVACY_NOTICE_SENT = "privacy.notice_sent"

    # Compliance reporting
    COMPLIANCE_REPORT_GENERATED = "compliance.report_generated"
    COMPLIANCE_AUDIT_STARTED = "compliance.audit_started"
    COMPLIANCE_AUDIT_COMPLETED = "compliance.audit_completed"
    COMPLIANCE_VIOLATION_DETECTED = "compliance.violation_detected"


# Alias for backward compatibility
AuditAction = AuditEventType


# One R2 client per process, keyed by the settings it was built from.
# boto3 clients are thread-safe (sessions are not), so every AuditLogger can
# share one. Building a client is expensive: without explicit credentials
# botocore walks the default credential chain, which probes the instance
# metadata endpoint over the network, and routers build an AuditLogger per
# request.
_R2ClientConfig = Tuple[str, Optional[str], Optional[str]]
_shared_r2_client: Optional[Tuple[_R2ClientConfig, Any]] = None
_shared_r2_client_lock = threading.Lock()


def get_shared_r2_client() -> Optional[Any]:
    """Return the process-wide Cloudflare R2 client, building it on first use.

    Returns None, and builds nothing, when ``R2_ENDPOINT`` is not configured.
    The client is rebuilt only when the R2 settings change.
    """
    global _shared_r2_client

    endpoint = settings.R2_ENDPOINT
    if not endpoint:
        return None
    config: _R2ClientConfig = (
        endpoint,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
    )

    cached = _shared_r2_client
    if cached is not None and cached[0] == config:
        return cached[1]

    with _shared_r2_client_lock:
        cached = _shared_r2_client
        if cached is None or cached[0] != config:
            client = boto3.client(
                "s3",
                endpoint_url=config[0],
                aws_access_key_id=config[1],
                aws_secret_access_key=config[2],
                region_name="auto",
            )
            cached = (config, client)
            _shared_r2_client = cached
        return cached[1]


# Stable codes for the audit logger's log lines, so operators can alert on them.
AUDIT_ARCHIVE_BUCKET_REFUSED = "AUDIT_ARCHIVE_BUCKET_REFUSED"
AUDIT_ARCHIVE_FAILED = "AUDIT_ARCHIVE_FAILED"
AUDIT_STORE_FAILED = "AUDIT_STORE_FAILED"

# Keys in `details` that hold an identity or resource reference that is not a
# UUID, so it cannot go in the `user_id` / `resource_id` columns.
IDENTITY_REF_KEY = "identity_ref"
RESOURCE_REF_KEY = "resource_ref"

# Shape of encrypted details: {"encrypted": true, "ciphertext": "<Fernet token>"}.
ENCRYPTED_DETAILS_FLAG = "encrypted"
ENCRYPTED_DETAILS_CIPHERTEXT = "ciphertext"

# Namespace of the PostgreSQL advisory lock taken per tenant chain.
CHAIN_LOCK_NAMESPACE = "janua.audit_logs.chain"


def _event_type_value(event_type: Any) -> str:
    """The event name as stored: an ``AuditEventType`` member's value, else ``str()``."""
    if isinstance(event_type, Enum):
        return str(event_type.value)
    return str(event_type)


def _split_reference(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Split a reference into ``(uuid, other)``: exactly one is set, or neither.

    A UUID (object or string, any case) comes back in canonical form as the
    first item. Anything else non-empty comes back as a string in the second.
    """
    if value is None or value == "":
        return None, None
    if isinstance(value, uuid.UUID):
        return str(value), None
    try:
        return str(uuid.UUID(str(value))), None
    except (ValueError, TypeError, AttributeError):
        return None, str(value)


def _as_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    return uuid.UUID(value) if value else None


def _json_safe(value: Any) -> Any:
    """``value`` as plain JSON data; values JSON cannot hold become strings."""
    return json.loads(json.dumps(value, default=str))


def decode_details(value: Any) -> Any:
    """Return stored audit ``details`` as written, decrypting them if encrypted.

    Values that are not in the encrypted shape are returned unchanged. If the
    ciphertext cannot be decrypted (for example after a key change), the stored
    value is returned unchanged and a warning is logged.
    """
    if not (
        isinstance(value, dict)
        and set(value) == {ENCRYPTED_DETAILS_FLAG, ENCRYPTED_DETAILS_CIPHERTEXT}
        and value[ENCRYPTED_DETAILS_FLAG] is True
    ):
        return value
    try:
        from app.core.encryption import FieldEncryptor

        plaintext = FieldEncryptor.get_instance().decrypt_field(value[ENCRYPTED_DETAILS_CIPHERTEXT])
        return json.loads(plaintext)
    except Exception as e:
        logger.warning(f"Could not decrypt audit details: {type(e).__name__}")
        return value


# The refused bucket name already reported, so the error is logged once per
# process rather than on every flush.
_refused_audit_bucket_reported: Optional[str] = None


def get_audit_archive_bucket() -> Optional[str]:
    """Return the bucket audit archives and exports are written to, or None.

    Archiving is off (None) when ``R2_AUDIT_BUCKET`` is unset or blank, and when
    it names ``CLOUDFLARE_R2_BUCKET``: that is the general upload bucket, whose
    objects are served at public URLs, so audit data is never written there.
    The refusal is logged once per process with a stable code and never raises.
    """
    global _refused_audit_bucket_reported

    bucket = (settings.R2_AUDIT_BUCKET or "").strip()
    if not bucket:
        return None

    upload_bucket = (settings.CLOUDFLARE_R2_BUCKET or "").strip()
    if upload_bucket and bucket.lower() == upload_bucket.lower():
        if _refused_audit_bucket_reported != bucket:
            _refused_audit_bucket_reported = bucket
            logger.error(
                f"[{AUDIT_ARCHIVE_BUCKET_REFUSED}] R2_AUDIT_BUCKET is the same bucket as "
                "CLOUDFLARE_R2_BUCKET, the general upload bucket. Audit archiving is off "
                "until R2_AUDIT_BUCKET names a dedicated private bucket.",
                code=AUDIT_ARCHIVE_BUCKET_REFUSED,
            )
        return None

    return bucket


class AuditLogger:
    """
    Comprehensive audit logging with hash chain integrity
    and Cloudflare R2 archival

    Every entry is written to ``audit_logs`` when it is logged, linked to the
    previous entry of the same tenant: ``previous_hash`` is that entry's
    ``current_hash``, and ``current_hash`` is the SHA-256 of the entry's stable
    fields (``_calculate_hash``). ``created_at`` is the entry's timestamp and
    increases strictly along each tenant's chain, so ``(tenant_id, created_at,
    id)`` orders it.

    Session ownership is explicit:

    - ``AuditLogger(db)``: the caller owns ``db``. ``log()`` inserts the row in
      a SAVEPOINT and flushes it; it never commits. The row commits or rolls
      back with the caller's transaction, so a caller that logs after its own
      last commit must commit again.
    - ``AuditLogger.with_own_session()``: the logger opens, owns and closes its
      session, and ``log()`` commits each entry.

    When archiving is enabled (see ``get_audit_archive_bucket``), committed
    entries are also buffered and archived to R2 in batches. Archiving never
    writes to the database.
    """

    def __init__(
        self,
        db: AsyncSession,
        r2_client: Optional[Any] = None,
        *,
        owns_session: bool = False,
    ):
        self.db = db
        # True only when this logger opened ``db`` itself (``with_own_session``).
        # Then, and only then, ``log()`` commits.
        self.owns_session = owns_session
        self.r2_client = r2_client or self._create_r2_client()
        # Committed entries waiting to be archived. Only filled while archiving
        # is enabled; flushed at ``buffer_size`` entries or every
        # ``flush_interval`` seconds.
        self.buffer: List[Dict[str, Any]] = []
        # Entries flushed into the caller's transaction, archived only once
        # that transaction commits and dropped if it rolls back.
        self._awaiting_commit: List[Dict[str, Any]] = []
        self._watching_caller_transaction = False
        self.buffer_size = 100
        self.flush_interval = 60  # seconds
        self._flush_task: Optional[asyncio.Task[None]] = None

    @classmethod
    @asynccontextmanager
    async def with_own_session(
        cls,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        r2_client: Optional[Any] = None,
    ) -> AsyncIterator["AuditLogger"]:
        """Yield a logger over a session it opens, owns and closes.

        Its ``log()`` commits each entry in its own transaction, independent of
        any request session. For background work, or for code whose business
        transaction has already committed and must not be reopened.
        ``session_factory`` defaults to ``app.database.AsyncSessionLocal``.
        """
        if session_factory is None:
            from app.database import AsyncSessionLocal

            session_factory = AsyncSessionLocal
        async with session_factory() as session:
            yield cls(session, r2_client=r2_client, owns_session=True)

    def _create_r2_client(self) -> Optional[Any]:
        """Return the shared Cloudflare R2 client, or None when R2 is not configured."""
        return get_shared_r2_client()

    def _archiving_enabled(self) -> bool:
        return self.r2_client is not None and get_audit_archive_bucket() is not None

    async def log(
        self,
        event_type: AuditEventType,
        tenant_id: str,
        identity_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info",
        compliance_context: Optional[Dict[str, Any]] = None,
        data_subject_id: Optional[str] = None,
        legal_basis: Optional[str] = None,
        retention_period: Optional[int] = None,
    ) -> str:
        """
        Create an audit log entry with hash chain integrity

        The row is written before this returns: flushed into the caller's
        transaction, or committed when the logger owns its session. A database
        failure is logged with the stable code ``AUDIT_STORE_FAILED`` and raised;
        in a caller's transaction only the SAVEPOINT is rolled back.

        ``identity_id`` and ``resource_id`` are stored in their UUID columns
        only when they are UUIDs. Any other value is kept in ``details`` under
        ``IDENTITY_REF_KEY`` / ``RESOURCE_REF_KEY``.
        """

        # Generate unique event ID
        event_id = str(uuid.uuid4())
        tenant = "" if tenant_id is None else str(tenant_id)
        event_name = _event_type_value(event_type)

        identity_uuid, identity_ref = _split_reference(identity_id)
        resource_uuid, resource_ref = _split_reference(resource_id)
        stored_details = _json_safe(details or {})
        if not isinstance(stored_details, dict):
            stored_details = {"value": stored_details}
        if identity_ref is not None:
            stored_details[IDENTITY_REF_KEY] = identity_ref
        if resource_ref is not None:
            stored_details[RESOURCE_REF_KEY] = resource_ref

        # Serialize writers of this tenant's chain until the entry is committed.
        await self._lock_chain(tenant)
        previous_hash, previous_at = await self._chain_tail(tenant)
        timestamp = datetime.utcnow()
        if previous_at is not None and timestamp <= previous_at:
            timestamp = previous_at + timedelta(microseconds=1)

        # Create audit entry
        audit_entry = {
            "event_id": event_id,
            "event_type": event_name,
            "tenant_id": tenant,
            "identity_id": identity_uuid,
            "organization_id": organization_id,
            "resource_type": resource_type,
            "resource_id": resource_uuid,
            "details": stored_details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "severity": severity,
            "timestamp": timestamp.isoformat(),
            "previous_hash": previous_hash,
            "compliance_context": _json_safe(compliance_context or {}),
            "data_subject_id": data_subject_id,
            "legal_basis": legal_basis,
            "retention_period": retention_period,
        }

        # Calculate hash for this entry
        entry_hash = self._calculate_hash(audit_entry)
        audit_entry["hash"] = entry_hash

        await self._store_entry(audit_entry)

        if self._archiving_enabled():
            if self.owns_session:
                self.buffer.append(audit_entry)
            else:
                self._awaiting_commit.append(audit_entry)
                self._watch_caller_transaction()
            if len(self.buffer) >= self.buffer_size:
                await self._flush_buffer()
            if (self.buffer or self._awaiting_commit) and not self._flush_task:
                self._flush_task = asyncio.create_task(self._periodic_flush())

        logger.info(f"Audit logged: {event_name} for tenant {tenant}", extra={"event_id": event_id})

        return event_id

    async def _store_entry(self, entry: Dict[str, Any]) -> None:
        """Store audit entry in database, optionally encrypting details (CF-11).

        The row is inserted and flushed inside a SAVEPOINT, so a failed insert
        rolls back only the SAVEPOINT and the caller's own work stays in its
        transaction. The row is committed only when the logger owns its session
        (``owns_session``); otherwise it commits with the caller. Encrypted details are
        stored as ``{"encrypted": true, "ciphertext": ...}`` so the column always
        holds a JSON object; ``decode_details`` reverses it.
        """

        details = entry.get("details", {})

        # SOC 2 CF-11: Encrypt audit log details payload if configured
        if settings.AUDIT_LOG_ENCRYPTION and getattr(settings, "FIELD_ENCRYPTION_KEY", None):
            try:
                from app.core.encryption import FieldEncryptor

                encryptor = FieldEncryptor.get_instance()
                details = {
                    ENCRYPTED_DETAILS_FLAG: True,
                    ENCRYPTED_DETAILS_CIPHERTEXT: encryptor.encrypt_field(json.dumps(details)),
                }
            except Exception as e:
                logger.warning(f"Failed to encrypt audit details, storing plaintext: {e}")

        audit_log = AuditLog(
            id=uuid.UUID(entry["event_id"]),
            action=entry["event_type"],
            event_type=entry["event_type"],
            tenant_id=entry["tenant_id"],
            user_id=_as_uuid(entry.get("identity_id")),
            resource_type=entry.get("resource_type"),
            resource_id=_as_uuid(entry.get("resource_id")),
            details=details,
            ip_address=entry.get("ip_address"),
            user_agent=entry.get("user_agent"),
            current_hash=entry["hash"],
            previous_hash=entry["previous_hash"],
            created_at=datetime.fromisoformat(entry["timestamp"]),
        )

        try:
            async with self.db.begin_nested():
                self.db.add(audit_log)
        except Exception as e:
            self._log_store_failure(entry, e)
            raise

        if not self.owns_session:
            return

        try:
            await self.db.commit()
        except Exception as e:
            self._log_store_failure(entry, e)
            try:
                await self.db.rollback()
            except Exception:  # pragma: no cover - the session is unusable either way
                pass
            raise

    def _watch_caller_transaction(self) -> None:
        """Move entries to the archive buffer when the caller's transaction
        commits, and drop them when it rolls back.

        SQLAlchemy fires ``after_commit`` / ``after_rollback`` for SAVEPOINTs too;
        only the outermost transaction (no nested transaction open while the
        event fires) decides.
        """
        if self._watching_caller_transaction:
            return
        target = getattr(self.db, "sync_session", self.db)
        sa_event.listen(target, "after_commit", self._on_caller_commit)
        sa_event.listen(target, "after_rollback", self._on_caller_rollback)
        self._watching_caller_transaction = True

    def _on_caller_commit(self, session: Any) -> None:
        if session.in_nested_transaction():
            return
        self.buffer.extend(self._awaiting_commit)
        self._awaiting_commit.clear()

    def _on_caller_rollback(self, session: Any) -> None:
        if session.in_nested_transaction():
            return
        self._awaiting_commit.clear()

    def _log_store_failure(self, entry: Dict[str, Any], error: BaseException) -> None:
        logger.error(
            f"[{AUDIT_STORE_FAILED}] Audit entry {entry.get('event_id')} "
            f"({entry.get('event_type')}) was not stored: {type(error).__name__}",
            code=AUDIT_STORE_FAILED,
            event_type=entry.get("event_type"),
            error_type=type(error).__name__,
        )

    async def _flush_buffer(self) -> None:
        """Archive the buffered entries to R2.

        Every buffered entry is already stored: a flush never writes to the
        database. An archive failure is logged once, with a stable code, and
        changes nothing else: entries are never put back in the buffer.
        """

        if not self.buffer:
            return

        entries_to_flush = self.buffer.copy()
        self.buffer.clear()

        if self.r2_client is not None and get_audit_archive_bucket():
            try:
                await self._archive_to_r2(entries_to_flush)
            except Exception as e:
                self._log_archive_failure(len(entries_to_flush), e)

    def _log_archive_failure(self, entry_count: int, error: BaseException) -> None:
        logger.warning(
            f"[{AUDIT_ARCHIVE_FAILED}] {entry_count} audit entries were stored in the "
            f"database but not archived to R2 ({type(error).__name__}). They are not "
            "retried.",
            code=AUDIT_ARCHIVE_FAILED,
            entries=entry_count,
            error_type=type(error).__name__,
        )

    async def _periodic_flush(self) -> None:
        """Flush the buffer every ``flush_interval`` seconds while entries wait.

        Ends once nothing is buffered or waiting for the caller's commit; the
        next logged entry starts it again.
        """

        try:
            while True:
                await asyncio.sleep(self.flush_interval)
                await self._flush_buffer()
                if not self.buffer and not self._awaiting_commit:
                    return
        finally:
            self._flush_task = None

    async def _archive_to_r2(self, entries: List[Dict[str, Any]]) -> None:
        """Archive stored audit entries to the dedicated R2 audit bucket.

        Writes one object per tenant and day. Does nothing when there is no
        client or archiving is off (see ``get_audit_archive_bucket``). A failed
        upload does not stop the other groups; failures are logged once, with a
        stable code, and are not retried.
        """

        if not entries or self.r2_client is None:
            return
        bucket = get_audit_archive_bucket()
        if not bucket:
            return

        # Group by tenant and date
        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for entry in entries:
            date = entry["timestamp"][:10]  # YYYY-MM-DD
            grouped.setdefault((entry["tenant_id"], date), []).append(entry)

        unarchived = 0
        last_error: Optional[BaseException] = None

        # Upload each group
        for (tenant_id, date), group_entries in grouped.items():
            filename = f"audit/{tenant_id}/{date}/{uuid.uuid4()}.json"
            data = {
                "tenant_id": tenant_id,
                "date": date,
                "count": len(group_entries),
                "entries": group_entries,
                "uploaded_at": datetime.utcnow().isoformat(),
            }

            try:
                self.r2_client.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=json.dumps(data, indent=2),
                    ContentType="application/json",
                    Metadata={
                        "tenant_id": tenant_id,
                        "date": date,
                        "count": str(len(group_entries)),
                    },
                )
            except Exception as e:
                unarchived += len(group_entries)
                last_error = e
                continue

            logger.info(f"Archived {len(group_entries)} audit logs to R2: {filename}")

        if last_error is not None:
            self._log_archive_failure(unarchived, last_error)

    def _is_postgresql(self) -> bool:
        if not isinstance(self.db, AsyncSession):
            return False
        try:
            return self.db.get_bind().dialect.name == "postgresql"
        except Exception:
            return False

    async def _lock_chain(self, tenant_id: str) -> None:
        """Hold a transaction-scoped lock on this tenant's chain (PostgreSQL only).

        Two writers of one tenant would otherwise read the same tail and both
        link to it. The lock is released when ``_store_entry`` commits, or when
        the caller's transaction ends.
        """

        if self._is_postgresql():
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"{CHAIN_LOCK_NAMESPACE}:{tenant_id}"},
            )

    async def _chain_tail(self, tenant_id: str) -> Tuple[Optional[str], Optional[datetime]]:
        """Return ``(current_hash, created_at)`` of the tenant's latest entry."""

        result = await self.db.execute(
            select(AuditLog.current_hash, AuditLog.created_at)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.current_hash.is_not(None))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None, None
        return row[0], row[1]

    async def _get_previous_hash(self, tenant_id: str) -> Optional[str]:
        """Get the hash of the previous audit entry for this tenant"""

        previous_hash, _ = await self._chain_tail(tenant_id)
        return previous_hash

    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of audit entry

        Covers the fields stored in their own columns, with the values the
        columns hold, so ``verify_integrity`` recomputes it from the row alone.
        ``details`` is not covered: it may be stored encrypted.
        """

        # Create deterministic string representation
        hash_input = json.dumps(
            {
                "event_id": entry["event_id"],
                "event_type": _event_type_value(entry["event_type"]),
                "tenant_id": entry["tenant_id"],
                "identity_id": entry.get("identity_id"),
                "resource_type": entry.get("resource_type"),
                "resource_id": entry.get("resource_id"),
                "timestamp": entry["timestamp"],
                "previous_hash": entry.get("previous_hash"),
            },
            sort_keys=True,
        )

        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _row_hash(self, log: Any) -> str:
        return self._calculate_hash(
            {
                "event_id": str(log.id),
                "event_type": log.event_type,
                "tenant_id": log.tenant_id,
                "identity_id": str(log.user_id) if log.user_id else None,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "timestamp": log.created_at.isoformat(),
                "previous_hash": log.previous_hash,
            }
        )

    async def verify_integrity(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log hash chain

        Walks the tenant's entries in chain order and recomputes each hash.
        Without ``start_date`` the first entry must start the chain (no
        ``previous_hash``); with it, the first entry's link is not checked.
        """

        # Build query
        query = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.current_hash.is_not(None))
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )

        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        if not logs:
            return {"valid": True, "message": "No logs found for verification", "count": 0}

        # Verify hash chain
        valid = True
        broken_at = None
        previous_hash = None

        for i, log in enumerate(logs):
            # Check if previous hash matches
            if i > 0 or start_date is None:
                if log.previous_hash != previous_hash:
                    valid = False
                    broken_at = i
                    break

            # Recalculate hash and verify
            if self._row_hash(log) != log.current_hash:
                valid = False
                broken_at = i
                break

            previous_hash = log.current_hash

        return {
            "valid": valid,
            "message": (
                "Hash chain is valid" if valid else f"Hash chain broken at index {broken_at}"
            ),
            "count": len(logs),
            "broken_at": broken_at,
            "first_log": logs[0].created_at.isoformat() if logs else None,
            "last_log": logs[-1].created_at.isoformat() if logs else None,
        }

    async def export_logs(
        self, tenant_id: str, start_date: datetime, end_date: datetime, format: str = "json"
    ) -> str:
        """
        Export audit logs for a tenant
        """

        # Query logs
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.created_at >= start_date,
                    AuditLog.created_at <= end_date,
                )
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )

        logs = result.scalars().all()

        # Prepare export data
        export_data = {
            "tenant_id": tenant_id,
            "export_date": datetime.utcnow().isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "count": len(logs),
            "logs": [
                {
                    "event_id": str(log.id),
                    "event_type": log.event_type,
                    "identity_id": str(log.user_id) if log.user_id else None,
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id) if log.resource_id else None,
                    "details": decode_details(log.details),
                    "ip_address": str(log.ip_address) if log.ip_address else None,
                    "user_agent": log.user_agent,
                    "timestamp": log.created_at.isoformat(),
                    "hash": log.current_hash,
                    "previous_hash": log.previous_hash,
                }
                for log in logs
            ],
        }

        # Generate export file
        export_id = str(uuid.uuid4())
        filename = f"exports/{tenant_id}/{export_id}.{format}"

        if format == "json":
            content = json.dumps(export_data, indent=2)
        else:
            # Add CSV support if needed
            content = json.dumps(export_data, indent=2)

        # Upload to the dedicated audit bucket. With no client, or with
        # archiving off, the export id is returned instead of a download URL.
        bucket = get_audit_archive_bucket() if self.r2_client is not None else None
        if bucket:
            try:
                self.r2_client.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=content,
                    ContentType="application/json" if format == "json" else "text/csv",
                    Metadata={
                        "tenant_id": tenant_id,
                        "export_id": export_id,
                        "count": str(len(logs)),
                    },
                )

                # Generate presigned URL for download
                url = self.r2_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": filename},
                    ExpiresIn=3600,  # 1 hour
                )

                return url

            except ClientError as e:
                logger.error(f"Failed to export audit logs: {e}")
                raise

        return export_id

    async def log_authentication(
        self,
        user_id: str,
        event_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs,
    ):
        """Log authentication events"""
        await self.log(
            event_type=AuditEventType.AUTH_SIGNIN,
            tenant_id="default",
            identity_id=user_id,
            details={"auth_event_type": event_type},
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info",
        )

    async def log_authorization(
        self, user_id: str, resource: str, action: str, ip_address: Optional[str] = None, **kwargs
    ):
        """Log authorization events"""
        await self.log(
            event_type=AuditEventType.SECURITY_ACCESS_DENIED,
            tenant_id="default",
            identity_id=user_id,
            resource_type="api_resource",
            details={"resource": resource, "action": action},
            ip_address=ip_address,
            severity="info",
        )

    async def log_data_access(
        self, user_id: str, resource_type: str, resource_id: str, action: str, **kwargs
    ):
        """Log data access events"""
        await self.log(
            event_type=AuditEventType.USER_UPDATE,
            tenant_id="default",
            identity_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details={"action": action},
            severity="info",
        )

    async def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "medium",
        **kwargs,
    ):
        """Log security events"""
        await self.log(
            event_type=AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY,
            tenant_id="default",
            identity_id=user_id,
            details={"security_event_type": event_type, **(details or {})},
            severity=severity,
        )


class AuditMiddleware:
    """
    Middleware to automatically log API requests
    """

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.excluded_paths = [
            "/health",
            "/ready",
            "/.well-known/jwks.json",
            "/docs",
            "/openapi.json",
        ]

    async def __call__(self, request, call_next):
        """Log API requests automatically"""

        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Extract request details
        tenant_id = request.headers.get("X-Tenant-ID")
        identity_id = getattr(request.state, "identity_id", None)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Log the request
        await self.audit_logger.log(
            event_type="api.request",
            tenant_id=tenant_id or "unknown",
            identity_id=identity_id,
            details={
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info",
        )

        return await call_next(request)

    # Compliance-specific logging methods
    async def log_gdpr_consent(
        self,
        user_id: str,
        consent_type: str,
        purpose: str,
        action: str,  # given, withdrawn, updated
        consent_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: str = "default",
    ):
        """Log GDPR consent events"""
        event_type_map = {
            "given": AuditEventType.GDPR_CONSENT_GIVEN,
            "withdrawn": AuditEventType.GDPR_CONSENT_WITHDRAWN,
            "updated": AuditEventType.GDPR_CONSENT_UPDATED,
        }

        await self.audit_logger.log(
            event_type=event_type_map.get(action, AuditEventType.GDPR_CONSENT_UPDATED),
            tenant_id=tenant_id,
            identity_id=user_id,
            data_subject_id=user_id,
            details={
                "consent_type": consent_type,
                "purpose": purpose,
                "consent_data": consent_data or {},
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article 7",
                "lawful_basis": "consent",
            },
            legal_basis="consent",
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info",
        )

    async def log_data_subject_request(
        self,
        user_id: str,
        request_type: str,  # access, rectification, erasure, portability, restriction, objection
        data_categories: List[str],
        status: str,  # received, processing, completed, denied
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        tenant_id: str = "default",
    ):
        """Log GDPR data subject rights requests"""
        event_type_map = {
            "access": AuditEventType.GDPR_DATA_EXPORT,
            "rectification": AuditEventType.GDPR_DATA_RECTIFICATION,
            "erasure": AuditEventType.GDPR_DATA_DELETION,
            "portability": AuditEventType.GDPR_DATA_PORTABILITY,
            "restriction": AuditEventType.GDPR_PROCESSING_RESTRICTION,
            "objection": AuditEventType.GDPR_OBJECTION_PROCESSING,
        }

        await self.audit_logger.log(
            event_type=event_type_map.get(request_type, AuditEventType.GDPR_DATA_EXPORT),
            tenant_id=tenant_id,
            identity_id=user_id,
            data_subject_id=user_id,
            details={
                "request_type": request_type,
                "data_categories": data_categories,
                "status": status,
                "reason": reason,
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article "
                + {
                    "access": "15",
                    "rectification": "16",
                    "erasure": "17",
                    "portability": "20",
                    "restriction": "18",
                    "objection": "21",
                }.get(request_type, "15"),
                "request_id": f"dsr_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            },
            ip_address=ip_address,
            severity="info",
        )

    async def log_data_breach(
        self,
        breach_id: str,
        breach_type: str,
        affected_records: int,
        data_categories: List[str],
        severity: str,
        containment_status: str,
        notification_required: bool,
        details: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default",
    ):
        """Log data breach incidents"""
        await self.audit_logger.log(
            event_type=AuditEventType.GDPR_BREACH_NOTIFICATION,
            tenant_id=tenant_id,
            resource_type="data_breach",
            resource_id=breach_id,
            details={
                "breach_type": breach_type,
                "affected_records": affected_records,
                "data_categories": data_categories,
                "containment_status": containment_status,
                "notification_required": notification_required,
                "additional_details": details or {},
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article 33, Article 34",
                "notification_deadline": (datetime.utcnow() + timedelta(hours=72)).isoformat(),
                "breach_id": breach_id,
            },
            severity=severity,
            retention_period=2555,  # 7 years in days for breach records
        )

    async def log_soc2_access_control(
        self,
        user_id: str,
        action: str,  # granted, revoked, escalated
        resource: str,
        privilege_level: str,
        justification: str,
        approved_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        tenant_id: str = "default",
    ):
        """Log SOC 2 access control events"""
        event_type_map = {
            "granted": AuditEventType.SOC2_ACCESS_GRANTED,
            "revoked": AuditEventType.SOC2_ACCESS_REVOKED,
            "escalated": AuditEventType.SOC2_PRIVILEGE_ESCALATION,
        }

        await self.audit_logger.log(
            event_type=event_type_map.get(action, AuditEventType.SOC2_ACCESS_GRANTED),
            tenant_id=tenant_id,
            identity_id=user_id,
            resource_type="access_control",
            resource_id=resource,
            details={
                "action": action,
                "privilege_level": privilege_level,
                "justification": justification,
                "approved_by": approved_by,
            },
            compliance_context={
                "framework": "SOC2",
                "control_type": "access_control",
                "control_id": "CC6.1",
                "approval_required": approved_by is not None,
            },
            ip_address=ip_address,
            severity="info" if action != "escalated" else "medium",
        )

    async def log_hipaa_phi_access(
        self,
        user_id: str,
        patient_id: str,
        phi_type: str,
        action: str,  # access, export, modify, delete
        purpose: str,
        emergency_access: bool = False,
        ip_address: Optional[str] = None,
        tenant_id: str = "default",
    ):
        """Log HIPAA PHI access events"""
        event_type_map = {
            "access": AuditEventType.HIPAA_PHI_ACCESS,
            "export": AuditEventType.HIPAA_PHI_EXPORT,
            "modify": AuditEventType.HIPAA_PHI_MODIFICATION,
            "delete": AuditEventType.HIPAA_PHI_DELETION,
        }

        if emergency_access:
            event_type = AuditEventType.HIPAA_EMERGENCY_ACCESS
        else:
            event_type = event_type_map.get(action, AuditEventType.HIPAA_PHI_ACCESS)

        await self.audit_logger.log(
            event_type=event_type,
            tenant_id=tenant_id,
            identity_id=user_id,
            data_subject_id=patient_id,
            resource_type="phi",
            resource_id=f"{patient_id}_{phi_type}",
            details={
                "phi_type": phi_type,
                "action": action,
                "purpose": purpose,
                "emergency_access": emergency_access,
            },
            compliance_context={
                "framework": "HIPAA",
                "regulation": "45 CFR 164.312(a)(2)(i)",
                "minimum_necessary": True,
                "emergency_override": emergency_access,
            },
            ip_address=ip_address,
            severity="high" if emergency_access else "info",
            retention_period=2190,  # 6 years in days for HIPAA records
        )
