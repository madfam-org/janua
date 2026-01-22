"""
Compliance Audit Trail System for enterprise SOC2 requirements.
Automated evidence collection, retention, correlation, and integrity verification.
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
import aiofiles
import redis.asyncio as aioredis
from sqlalchemy import select, and_, text

from app.core.database import get_session
from app.models.audit import AuditLog
from app.models.compliance import ComplianceFramework
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuditEventType(str, Enum):
    """Types of auditable events for compliance tracking"""

    USER_ACCESS = "user_access"
    DATA_ACCESS = "data_access"
    SYSTEM_CHANGE = "system_change"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_CONTROL = "compliance_control"
    POLICY_CHANGE = "policy_change"
    INCIDENT_RESPONSE = "incident_response"
    BACKUP_OPERATION = "backup_operation"
    CONFIGURATION_CHANGE = "configuration_change"
    PRIVILEGED_ACCESS = "privileged_access"


class EvidenceType(str, Enum):
    """Types of compliance evidence for SOC2 requirements"""

    SYSTEM_LOG = "system_log"
    USER_ACTIVITY = "user_activity"
    ACCESS_REVIEW = "access_review"
    CONTROL_TEST = "control_test"
    VULNERABILITY_SCAN = "vulnerability_scan"
    BACKUP_VERIFICATION = "backup_verification"
    INCIDENT_DOCUMENTATION = "incident_documentation"
    POLICY_DOCUMENTATION = "policy_documentation"
    TRAINING_RECORD = "training_record"
    RISK_ASSESSMENT = "risk_assessment"


class RetentionPeriod(str, Enum):
    """Data retention periods for compliance requirements"""

    SEVEN_YEARS = "seven_years"  # SOC2 requirement
    THREE_YEARS = "three_years"  # Standard business records
    ONE_YEAR = "one_year"  # Operational logs
    SIX_MONTHS = "six_months"  # Performance metrics
    NINETY_DAYS = "ninety_days"  # Debug logs


@dataclass
class ComplianceEvent:
    """Auditable compliance event with evidence collection"""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    organization_id: str
    tenant_id: str

    # Event details
    resource_type: str
    resource_id: str
    action: str
    outcome: str

    # Context and metadata
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]

    # Evidence and correlation
    evidence_id: Optional[str]
    correlation_id: Optional[str]
    control_id: Optional[str]

    # Risk and compliance
    risk_level: str
    compliance_framework: List[ComplianceFramework]
    retention_period: RetentionPeriod

    # Metadata
    raw_data: Dict[str, Any]
    tags: List[str]


@dataclass
class AuditEvidence:
    """Compliance evidence with integrity verification"""

    evidence_id: str
    evidence_type: EvidenceType
    title: str
    description: str

    # Source information
    source_system: str
    collected_at: datetime
    collector_id: str

    # Content and integrity
    content_hash: str
    content_type: str
    file_path: Optional[str]
    content_size: int

    # Retention and lifecycle
    retention_period: RetentionPeriod
    retention_expires_at: datetime
    destruction_due_at: Optional[datetime]

    # Compliance mapping
    control_objectives: List[str]
    compliance_frameworks: List[ComplianceFramework]

    # Chain of custody
    custody_chain: List[Dict[str, Any]]
    integrity_verified: bool
    last_verification_at: datetime

    # Metadata
    metadata: Dict[str, Any]
    tags: List[str]


class AuditLogger:
    """High-performance audit logging with integrity verification"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self.evidence_store = Path(settings.EVIDENCE_STORAGE_PATH)
        self.evidence_store.mkdir(parents=True, exist_ok=True)

    async def log_compliance_event(
        self,
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        outcome: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        control_id: Optional[str] = None,
        risk_level: str = "low",
        compliance_frameworks: List[ComplianceFramework] = None,
        retention_period: RetentionPeriod = RetentionPeriod.SEVEN_YEARS,
        raw_data: Dict[str, Any] = None,
        tags: List[str] = None,
    ) -> str:
        """Log a compliance event with automatic evidence collection"""

        event_id = str(uuid.uuid4())
        correlation_id = request_id or str(uuid.uuid4())

        compliance_event = ComplianceEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            organization_id=organization_id or "default",
            tenant_id=tenant_id or "default",
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            evidence_id=None,
            correlation_id=correlation_id,
            control_id=control_id,
            risk_level=risk_level,
            compliance_framework=compliance_frameworks or [ComplianceFramework.SOC2],
            retention_period=retention_period,
            raw_data=raw_data or {},
            tags=tags or [],
        )

        # Store in database
        async with get_session() as session:
            audit_log = AuditLog(
                id=uuid.UUID(event_id),
                event_type=event_type.value,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                outcome=outcome,
                user_id=uuid.UUID(user_id) if user_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                metadata={
                    "compliance_event": asdict(compliance_event),
                    "retention_period": retention_period.value,
                    "compliance_frameworks": [f.value for f in compliance_frameworks]
                    if compliance_frameworks
                    else ["soc2"],
                },
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
            )
            session.add(audit_log)
            await session.commit()

        # Cache for real-time monitoring
        if self.redis:
            await self.redis.lpush(
                f"compliance:events:{organization_id}",
                json.dumps(asdict(compliance_event), default=str),
            )
            await self.redis.expire(f"compliance:events:{organization_id}", 86400)  # 24 hours

        logger.info(
            f"Compliance event logged: {event_id}",
            extra={
                "event_type": event_type.value,
                "resource_type": resource_type,
                "action": action,
                "outcome": outcome,
                "correlation_id": correlation_id,
            },
        )

        return event_id

    async def collect_evidence(
        self,
        evidence_type: EvidenceType,
        title: str,
        description: str,
        content: Union[str, bytes, Dict[str, Any]],
        source_system: str,
        collector_id: str,
        control_objectives: List[str] = None,
        compliance_frameworks: List[ComplianceFramework] = None,
        retention_period: RetentionPeriod = RetentionPeriod.SEVEN_YEARS,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
    ) -> str:
        """Collect and store compliance evidence with integrity verification"""

        evidence_id = str(uuid.uuid4())
        collected_at = datetime.utcnow()

        # Serialize content if needed
        if isinstance(content, dict):
            content_bytes = json.dumps(content, indent=2, default=str).encode("utf-8")
            content_type = "application/json"
        elif isinstance(content, str):
            content_bytes = content.encode("utf-8")
            content_type = "text/plain"
        else:
            content_bytes = content
            content_type = "application/octet-stream"

        # Calculate content hash for integrity
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        content_size = len(content_bytes)

        # Determine retention expiration
        retention_days = {
            RetentionPeriod.SEVEN_YEARS: 2555,  # 7 years
            RetentionPeriod.THREE_YEARS: 1095,  # 3 years
            RetentionPeriod.ONE_YEAR: 365,
            RetentionPeriod.SIX_MONTHS: 180,
            RetentionPeriod.NINETY_DAYS: 90,
        }

        retention_expires_at = collected_at + timedelta(days=retention_days[retention_period])

        # Store evidence file
        evidence_path = self.evidence_store / f"{evidence_id}.evidence"
        async with aiofiles.open(evidence_path, "wb") as f:
            await f.write(content_bytes)

        # Create evidence record
        evidence = AuditEvidence(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            title=title,
            description=description,
            source_system=source_system,
            collected_at=collected_at,
            collector_id=collector_id,
            content_hash=content_hash,
            content_type=content_type,
            file_path=str(evidence_path),
            content_size=content_size,
            retention_period=retention_period,
            retention_expires_at=retention_expires_at,
            destruction_due_at=None,
            control_objectives=control_objectives or [],
            compliance_frameworks=compliance_frameworks or [ComplianceFramework.SOC2],
            custody_chain=[
                {
                    "timestamp": collected_at.isoformat(),
                    "action": "collected",
                    "actor": collector_id,
                    "hash": content_hash,
                }
            ],
            integrity_verified=True,
            last_verification_at=collected_at,
            metadata=metadata or {},
            tags=tags or [],
        )

        # Store evidence metadata in database
        async with get_session() as session:
            # Store in audit log for searchability
            audit_log = AuditLog(
                event_type="evidence_collection",
                resource_type="compliance_evidence",
                resource_id=evidence_id,
                action="collect",
                outcome="success",
                user_id=uuid.UUID(collector_id) if collector_id else None,
                metadata={
                    "evidence": asdict(evidence),
                    "evidence_type": evidence_type.value,
                    "control_objectives": control_objectives or [],
                    "compliance_frameworks": [f.value for f in compliance_frameworks]
                    if compliance_frameworks
                    else ["soc2"],
                },
            )
            session.add(audit_log)
            await session.commit()

        logger.info(
            f"Evidence collected: {evidence_id}",
            extra={
                "evidence_type": evidence_type.value,
                "source_system": source_system,
                "content_size": content_size,
                "content_hash": content_hash,
            },
        )

        return evidence_id

    async def verify_evidence_integrity(self, evidence_id: str) -> bool:
        """Verify the integrity of stored evidence"""

        async with get_session() as session:
            # Get evidence metadata
            result = await session.execute(
                select(AuditLog).where(
                    and_(
                        AuditLog.resource_type == "compliance_evidence",
                        AuditLog.resource_id == evidence_id,
                        AuditLog.action == "collect",
                    )
                )
            )
            evidence_log = result.scalar_one_or_none()

            if not evidence_log:
                logger.warning(f"Evidence not found: {evidence_id}")
                return False

            evidence_data = evidence_log.metadata.get("evidence", {})
            stored_hash = evidence_data.get("content_hash")
            file_path = evidence_data.get("file_path")

            if not stored_hash or not file_path:
                logger.error(f"Evidence metadata incomplete: {evidence_id}")
                return False

            try:
                # Read file and calculate current hash
                async with aiofiles.open(file_path, "rb") as f:
                    content = await f.read()
                    current_hash = hashlib.sha256(content).hexdigest()

                # Compare hashes
                integrity_valid = current_hash == stored_hash

                if integrity_valid:
                    logger.info(f"Evidence integrity verified: {evidence_id}")
                else:
                    logger.error(f"Evidence integrity compromised: {evidence_id} - Hash mismatch")

                # Update verification timestamp
                evidence_data["last_verification_at"] = datetime.utcnow().isoformat()
                evidence_data["integrity_verified"] = integrity_valid
                evidence_log.metadata["evidence"] = evidence_data

                await session.commit()

                return integrity_valid

            except Exception as e:
                logger.error(f"Error verifying evidence integrity: {evidence_id} - {str(e)}")
                return False


class AuditTrail:
    """Comprehensive audit trail management for SOC2 compliance"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self.audit_logger = AuditLogger(redis_client)

    async def correlate_events(
        self, correlation_id: str, organization_id: str, time_window_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Correlate related audit events for incident analysis"""

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_window_hours)

        async with get_session() as session:
            result = await session.execute(
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.created_at >= start_time,
                        AuditLog.created_at <= end_time,
                        AuditLog.metadata.contains({"correlation_id": correlation_id}),
                    )
                )
                .order_by(AuditLog.created_at)
            )

            events = result.scalars().all()

            correlated_events = []
            for event in events:
                correlated_events.append(
                    {
                        "event_id": str(event.id),
                        "timestamp": event.created_at.isoformat(),
                        "event_type": event.event_type,
                        "resource_type": event.resource_type,
                        "resource_id": event.resource_id,
                        "action": event.action,
                        "outcome": event.outcome,
                        "user_id": str(event.user_id) if event.user_id else None,
                        "ip_address": event.ip_address,
                        "metadata": event.metadata,
                    }
                )

        logger.info(f"Correlated {len(correlated_events)} events for {correlation_id}")
        return correlated_events

    async def generate_audit_report(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        control_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive audit report for compliance requirements"""

        async with get_session() as session:
            # Base query for audit events in date range
            base_query = select(AuditLog).where(
                and_(AuditLog.created_at >= start_date, AuditLog.created_at <= end_date)
            )

            # Filter by control IDs if specified
            if control_ids:
                base_query = base_query.where(
                    AuditLog.metadata["compliance_event"]["control_id"].astext.in_(control_ids)
                )

            result = await session.execute(base_query.order_by(AuditLog.created_at))
            audit_events = result.scalars().all()

            # Event statistics
            event_stats = {
                "total_events": len(audit_events),
                "events_by_type": {},
                "events_by_outcome": {},
                "events_by_risk_level": {},
                "unique_users": set(),
                "unique_resources": set(),
            }

            # Security and compliance metrics
            security_metrics = {
                "failed_logins": 0,
                "privileged_access_events": 0,
                "policy_violations": 0,
                "security_incidents": 0,
                "control_failures": 0,
            }

            # Process events
            for event in audit_events:
                event_type = event.event_type
                outcome = event.outcome

                # Update statistics
                event_stats["events_by_type"][event_type] = (
                    event_stats["events_by_type"].get(event_type, 0) + 1
                )
                event_stats["events_by_outcome"][outcome] = (
                    event_stats["events_by_outcome"].get(outcome, 0) + 1
                )

                if event.user_id:
                    event_stats["unique_users"].add(str(event.user_id))

                event_stats["unique_resources"].add(f"{event.resource_type}:{event.resource_id}")

                # Security metrics
                if event_type == "user_access" and outcome == "failure":
                    security_metrics["failed_logins"] += 1
                elif event_type == "privileged_access":
                    security_metrics["privileged_access_events"] += 1
                elif event_type == "policy_violation" or "violation" in event.action.lower():
                    security_metrics["policy_violations"] += 1
                elif event_type == "security_event":
                    security_metrics["security_incidents"] += 1
                elif event_type == "compliance_control" and outcome == "failure":
                    security_metrics["control_failures"] += 1

                # Risk level tracking
                compliance_event = event.metadata.get("compliance_event", {})
                risk_level = compliance_event.get("risk_level", "unknown")
                event_stats["events_by_risk_level"][risk_level] = (
                    event_stats["events_by_risk_level"].get(risk_level, 0) + 1
                )

            # Convert sets to counts
            event_stats["unique_users"] = len(event_stats["unique_users"])
            event_stats["unique_resources"] = len(event_stats["unique_resources"])

            # Evidence collection summary
            evidence_query = select(AuditLog).where(
                and_(
                    AuditLog.created_at >= start_date,
                    AuditLog.created_at <= end_date,
                    AuditLog.resource_type == "compliance_evidence",
                )
            )

            evidence_result = await session.execute(evidence_query)
            evidence_events = evidence_result.scalars().all()

            evidence_summary = {
                "total_evidence_collected": len(evidence_events),
                "evidence_by_type": {},
                "evidence_by_framework": {},
            }

            for evidence in evidence_events:
                evidence_data = evidence.metadata.get("evidence", {})
                evidence_type = evidence_data.get("evidence_type", "unknown")
                frameworks = evidence.metadata.get("compliance_frameworks", [])

                evidence_summary["evidence_by_type"][evidence_type] = (
                    evidence_summary["evidence_by_type"].get(evidence_type, 0) + 1
                )

                for framework in frameworks:
                    evidence_summary["evidence_by_framework"][framework] = (
                        evidence_summary["evidence_by_framework"].get(framework, 0) + 1
                    )

        # Compile report
        audit_report = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "compliance_framework": compliance_framework.value,
                "organization_id": organization_id,
                "control_ids": control_ids,
            },
            "executive_summary": {
                "total_events": event_stats["total_events"],
                "unique_users": event_stats["unique_users"],
                "unique_resources": event_stats["unique_resources"],
                "security_incidents": security_metrics["security_incidents"],
                "control_failures": security_metrics["control_failures"],
                "evidence_collected": evidence_summary["total_evidence_collected"],
            },
            "event_statistics": event_stats,
            "security_metrics": security_metrics,
            "evidence_summary": evidence_summary,
            "compliance_assessment": {
                "framework": compliance_framework.value,
                "assessment_date": datetime.utcnow().isoformat(),
                "overall_status": "compliant"
                if security_metrics["control_failures"] == 0
                else "non_compliant",
                "risk_level": "high"
                if security_metrics["security_incidents"] > 0
                else "medium"
                if security_metrics["policy_violations"] > 5
                else "low",
            },
        }

        logger.info(
            f"Audit report generated for {organization_id}",
            extra={
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_events": event_stats["total_events"],
                "compliance_framework": compliance_framework.value,
            },
        )

        return audit_report

    async def schedule_evidence_retention_cleanup(self):
        """Schedule automatic cleanup of expired evidence"""

        current_time = datetime.utcnow()

        async with get_session() as session:
            # Find expired evidence
            expired_query = select(AuditLog).where(
                and_(
                    AuditLog.resource_type == "compliance_evidence",
                    AuditLog.action == "collect",
                    AuditLog.metadata["evidence"]["retention_expires_at"].astext.cast(
                        text("timestamp")
                    )
                    < current_time,
                )
            )

            result = await session.execute(expired_query)
            expired_evidence = result.scalars().all()

            cleanup_summary = {"processed": 0, "deleted": 0, "errors": 0, "total_size_freed": 0}

            for evidence_log in expired_evidence:
                try:
                    cleanup_summary["processed"] += 1
                    evidence_data = evidence_log.metadata.get("evidence", {})
                    file_path = evidence_data.get("file_path")
                    content_size = evidence_data.get("content_size", 0)

                    if file_path and Path(file_path).exists():
                        Path(file_path).unlink()  # Delete file
                        cleanup_summary["deleted"] += 1
                        cleanup_summary["total_size_freed"] += content_size

                    # Mark as destroyed in audit log
                    evidence_data["destruction_completed_at"] = current_time.isoformat()
                    evidence_data["destruction_method"] = "automated_retention_cleanup"
                    evidence_log.metadata["evidence"] = evidence_data

                except Exception as e:
                    cleanup_summary["errors"] += 1
                    logger.error(f"Error cleaning up evidence {evidence_log.resource_id}: {str(e)}")

            await session.commit()

        logger.info("Evidence retention cleanup completed", extra=cleanup_summary)
        return cleanup_summary
