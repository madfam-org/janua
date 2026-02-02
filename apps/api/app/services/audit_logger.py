"""
Audit logging service with Cloudflare R2 integration
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import and_, select
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

    # Billing events
    BILLING_SUBSCRIPTION_CREATE = "billing.subscription_create"
    BILLING_SUBSCRIPTION_UPDATE = "billing.subscription_update"
    BILLING_SUBSCRIPTION_CANCEL = "billing.subscription_cancel"
    BILLING_PAYMENT_SUCCESS = "billing.payment_success"
    BILLING_PAYMENT_FAILED = "billing.payment_failed"

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


class AuditLogger:
    """
    Comprehensive audit logging with hash chain integrity
    and Cloudflare R2 archival
    """

    def __init__(self, db: AsyncSession, r2_client: Optional[boto3.client] = None):
        self.db = db
        self.r2_client = r2_client or self._create_r2_client()
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100
        self.flush_interval = 60  # seconds
        self._flush_task = None

    def _create_r2_client(self) -> boto3.client:
        """Create Cloudflare R2 client"""
        return boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

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
        """

        # Generate unique event ID
        event_id = str(uuid.uuid4())

        # Get previous hash for chain
        previous_hash = await self._get_previous_hash(tenant_id)

        # Create audit entry
        audit_entry = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "identity_id": identity_id,
            "organization_id": organization_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "previous_hash": previous_hash,
            "compliance_context": compliance_context or {},
            "data_subject_id": data_subject_id,
            "legal_basis": legal_basis,
            "retention_period": retention_period,
        }

        # Calculate hash for this entry
        entry_hash = self._calculate_hash(audit_entry)
        audit_entry["hash"] = entry_hash

        # Add to buffer for batch processing
        self.buffer.append(audit_entry)

        # Store in database immediately for critical events
        if severity in ["critical", "high"]:
            await self._store_entry(audit_entry)

        # Check if buffer needs flushing
        if len(self.buffer) >= self.buffer_size:
            await self._flush_buffer()

        # Start flush timer if not running
        if not self._flush_task:
            self._flush_task = asyncio.create_task(self._periodic_flush())

        logger.info(
            f"Audit logged: {event_type} for tenant {tenant_id}", extra={"event_id": event_id}
        )

        return event_id

    async def _store_entry(self, entry: Dict[str, Any]) -> None:
        """Store audit entry in database, optionally encrypting details (CF-11)."""

        details = entry.get("details", {})

        # SOC 2 CF-11: Encrypt audit log details payload if configured
        if settings.AUDIT_LOG_ENCRYPTION and getattr(settings, "FIELD_ENCRYPTION_KEY", None):
            try:
                from app.core.encryption import FieldEncryptor

                encryptor = FieldEncryptor.get_instance()
                details = encryptor.encrypt_field(json.dumps(details))
            except Exception as e:
                logger.warning(f"Failed to encrypt audit details, storing plaintext: {e}")

        audit_log = AuditLog(
            id=entry["event_id"],
            event_type=entry["event_type"],
            tenant_id=entry["tenant_id"],
            user_id=entry.get("identity_id"),
            resource_type=entry.get("resource_type"),
            resource_id=entry.get("resource_id"),
            details=details,
            ip_address=entry.get("ip_address"),
            user_agent=entry.get("user_agent"),
            current_hash=entry["hash"],
            previous_hash=entry["previous_hash"],
            timestamp=datetime.fromisoformat(entry["timestamp"]),
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def _flush_buffer(self) -> None:
        """Flush buffer to database and R2"""

        if not self.buffer:
            return

        entries_to_flush = self.buffer.copy()
        self.buffer.clear()

        try:
            # Batch insert to database
            for entry in entries_to_flush:
                await self._store_entry(entry)

            # Archive to R2 if configured
            if self.r2_client and settings.R2_AUDIT_BUCKET:
                await self._archive_to_r2(entries_to_flush)

        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {e}")
            # Re-add to buffer for retry
            self.buffer.extend(entries_to_flush)

    async def _periodic_flush(self) -> None:
        """Periodically flush buffer"""

        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_buffer()

    async def _archive_to_r2(self, entries: List[Dict[str, Any]]) -> None:
        """Archive audit logs to Cloudflare R2"""

        if not entries:
            return

        # Group by tenant and date
        grouped = {}
        for entry in entries:
            tenant_id = entry["tenant_id"]
            date = entry["timestamp"][:10]  # YYYY-MM-DD
            key = f"{tenant_id}/{date}"

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(entry)

        # Upload each group
        for key, group_entries in grouped.items():
            tenant_id, date = key.split("/")

            # Create filename
            filename = f"audit/{tenant_id}/{date}/{uuid.uuid4()}.json"

            # Prepare data
            data = {
                "tenant_id": tenant_id,
                "date": date,
                "count": len(group_entries),
                "entries": group_entries,
                "uploaded_at": datetime.utcnow().isoformat(),
            }

            try:
                # Upload to R2
                self.r2_client.put_object(
                    Bucket=settings.R2_AUDIT_BUCKET,
                    Key=filename,
                    Body=json.dumps(data, indent=2),
                    ContentType="application/json",
                    Metadata={
                        "tenant_id": tenant_id,
                        "date": date,
                        "count": str(len(group_entries)),
                    },
                )

                logger.info(f"Archived {len(group_entries)} audit logs to R2: {filename}")

            except ClientError as e:
                logger.error(f"Failed to archive to R2: {e}")

    async def _get_previous_hash(self, tenant_id: str) -> Optional[str]:
        """Get the hash of the previous audit entry for this tenant"""

        result = await self.db.execute(
            select(AuditLog.current_hash)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )

        row = result.scalar_one_or_none()
        return row if row else None

    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of audit entry"""

        # Create deterministic string representation
        hash_input = json.dumps(
            {
                "event_id": entry["event_id"],
                "event_type": entry["event_type"],
                "tenant_id": entry["tenant_id"],
                "identity_id": entry.get("identity_id"),
                "timestamp": entry["timestamp"],
                "previous_hash": entry.get("previous_hash"),
            },
            sort_keys=True,
        )

        return hashlib.sha256(hash_input.encode()).hexdigest()

    async def verify_integrity(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log hash chain
        """

        # Build query
        query = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.asc())
        )

        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)

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
            if i > 0 and log.previous_hash != previous_hash:
                valid = False
                broken_at = i
                break

            # Recalculate hash and verify
            entry = {
                "event_id": str(log.id),
                "event_type": log.event_type,
                "tenant_id": str(log.tenant_id),
                "identity_id": str(log.user_id) if log.user_id else None,
                "timestamp": log.timestamp.isoformat(),
                "previous_hash": log.previous_hash,
            }

            calculated_hash = self._calculate_hash(entry)

            if calculated_hash != log.current_hash:
                valid = False
                broken_at = i
                break

            previous_hash = log.current_hash

        return {
            "valid": valid,
            "message": "Hash chain is valid"
            if valid
            else f"Hash chain broken at index {broken_at}",
            "count": len(logs),
            "broken_at": broken_at,
            "first_log": logs[0].timestamp.isoformat() if logs else None,
            "last_log": logs[-1].timestamp.isoformat() if logs else None,
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
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                )
            )
            .order_by(AuditLog.timestamp.asc())
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
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "timestamp": log.timestamp.isoformat(),
                    "hash": log.current_hash,
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

        # Upload to R2
        if self.r2_client and settings.R2_AUDIT_BUCKET:
            try:
                self.r2_client.put_object(
                    Bucket=settings.R2_AUDIT_BUCKET,
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
                    Params={"Bucket": settings.R2_AUDIT_BUCKET, "Key": filename},
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
