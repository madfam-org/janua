"""
Enterprise Audit Logging System
Tamper-proof audit logs with hash chain for compliance

Features:
- Hash-chain integrity verification
- File-based fallback for compliance (never lose logs)
- Multiple export formats (JSON, CSV, SIEM/CEF)
- Compliance-aware retention policies
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.enterprise import AuditLog, AuditEventType
from app.core.tenant_context import TenantContext

logger = structlog.get_logger()

# Fallback log directory for compliance
FALLBACK_LOG_DIR = os.environ.get("AUDIT_LOG_FALLBACK_DIR", "/var/log/janua/audit")


def _ensure_fallback_dir() -> Path:
    """Ensure fallback directory exists"""
    path = Path(FALLBACK_LOG_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_fallback_log(event_data: Dict[str, Any]) -> bool:
    """
    Write audit event to fallback file when database is unavailable.
    Uses append-only JSON Lines format for compliance.
    """
    try:
        fallback_dir = _ensure_fallback_dir()
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        fallback_file = fallback_dir / f"audit-fallback-{date_str}.jsonl"

        # Add fallback metadata
        event_data["_fallback"] = True
        event_data["_fallback_timestamp"] = datetime.utcnow().isoformat()

        with open(fallback_file, "a") as f:
            f.write(json.dumps(event_data, default=str) + "\n")

        logger.warning(
            "Audit event written to fallback file",
            fallback_file=str(fallback_file),
            event_name=event_data.get("event_name")
        )
        return True
    except Exception as e:
        logger.critical(
            "COMPLIANCE ALERT: Failed to write audit event to fallback",
            error=str(e),
            event_data=event_data
        )
        return False


class AuditLogger:
    """Enterprise audit logging with hash chain integrity"""

    def __init__(self):
        self._last_hash_cache: Dict[str, str] = {}

    async def log_event(
        self,
        session: AsyncSession,
        event_type: AuditEventType,
        event_name: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        service_account_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None
    ) -> AuditLog:
        """
        Create a tamper-proof audit log entry

        Args:
            session: Database session
            event_type: Category of event (AUTH, ACCESS, MODIFY, etc.)
            event_name: Specific event name (e.g., "user.login", "role.created")
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            event_data: Additional event context
            changes: Before/after values for modifications
            user_id: User who triggered the event
            service_account_id: Service account if applicable
            ip_address: Client IP address
            user_agent: Client user agent
            compliance_tags: Compliance frameworks (SOC2, HIPAA, etc.)

        Returns:
            Created audit log entry
        """

        # Prepare event data for fallback logging
        fallback_event_data = {
            "event_type": event_type.value,
            "event_name": event_name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "event_data": event_data,
            "changes": changes,
            "user_id": user_id,
            "service_account_id": service_account_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "compliance_tags": compliance_tags,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Get organization context
            org_id = TenantContext.get_organization_id()
            if not org_id:
                logger.warning("No organization context for audit log - using fallback")
                fallback_event_data["organization_id"] = None
                fallback_event_data["_reason"] = "no_organization_context"
                _write_fallback_log(fallback_event_data)
                return None

            # Get the previous hash for this organization
            previous_hash = await self._get_previous_hash(session, org_id)

            # Create the audit log entry
            audit_log = AuditLog(
                organization_id=UUID(org_id),
                user_id=UUID(user_id) if user_id else None,
                service_account_id=UUID(service_account_id) if service_account_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                event_type=event_type,
                event_name=event_name,
                resource_type=resource_type,
                resource_id=resource_id,
                event_data=event_data or {},
                changes=changes,
                compliance_tags=compliance_tags or [],
                previous_hash=previous_hash,
                retention_until=self._calculate_retention(compliance_tags)
            )

            # Calculate the hash for this entry
            audit_log.current_hash = self._calculate_hash(audit_log)

            # Add to session
            session.add(audit_log)
            await session.flush()

            # Update cache
            self._last_hash_cache[org_id] = audit_log.current_hash

            logger.info(
                "Audit event logged",
                event_type=event_type.value,
                event_name=event_name,
                resource_type=resource_type,
                resource_id=resource_id,
                organization_id=org_id
            )

            return audit_log

        except Exception as e:
            logger.error("Failed to create audit log - using fallback", error=str(e))
            # Use fallback to ensure compliance - never lose audit events
            fallback_event_data["organization_id"] = org_id if 'org_id' in dir() else None
            fallback_event_data["_reason"] = "database_error"
            fallback_event_data["_error"] = str(e)
            _write_fallback_log(fallback_event_data)
            # Audit logging failures should not break the application
            return None

    async def verify_integrity(
        self,
        session: AsyncSession,
        organization_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log hash chain

        Args:
            session: Database session
            organization_id: Organization to verify
            start_date: Start of verification period
            end_date: End of verification period

        Returns:
            Verification results including any broken links
        """

        try:
            # Build query
            query = select(AuditLog).where(
                AuditLog.organization_id == organization_id
            ).order_by(AuditLog.created_at)

            if start_date:
                query = query.where(AuditLog.created_at >= start_date)
            if end_date:
                query = query.where(AuditLog.created_at <= end_date)

            # Get all logs in order
            result = await session.execute(query)
            logs = result.scalars().all()

            if not logs:
                return {
                    "verified": True,
                    "total_entries": 0,
                    "message": "No audit logs to verify"
                }

            # Verify the chain
            broken_links = []
            previous_hash = None

            for i, log in enumerate(logs):
                # Check if previous hash matches
                if i > 0 and log.previous_hash != previous_hash:
                    broken_links.append({
                        "position": i,
                        "log_id": str(log.id),
                        "expected_previous": previous_hash,
                        "actual_previous": log.previous_hash,
                        "timestamp": log.created_at.isoformat()
                    })

                # Recalculate hash and verify
                calculated_hash = self._calculate_hash(log)
                if calculated_hash != log.current_hash:
                    broken_links.append({
                        "position": i,
                        "log_id": str(log.id),
                        "type": "hash_mismatch",
                        "expected_hash": calculated_hash,
                        "actual_hash": log.current_hash,
                        "timestamp": log.created_at.isoformat()
                    })

                previous_hash = log.current_hash

            return {
                "verified": len(broken_links) == 0,
                "total_entries": len(logs),
                "broken_links": broken_links,
                "first_entry": logs[0].created_at.isoformat(),
                "last_entry": logs[-1].created_at.isoformat(),
                "message": "Audit log integrity verified" if not broken_links else f"Found {len(broken_links)} integrity violations"
            }

        except Exception as e:
            logger.error("Audit log verification failed", error=str(e))
            return {
                "verified": False,
                "error": str(e),
                "message": "Verification failed due to error"
            }

    async def query_logs(
        self,
        session: AsyncSession,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        event_name: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        compliance_tag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Query audit logs with filtering

        Args:
            Various filter parameters

        Returns:
            List of matching audit logs
        """

        # Build query
        query = select(AuditLog)
        conditions = []

        # Apply filters
        if organization_id:
            conditions.append(AuditLog.organization_id == organization_id)
        else:
            # Use tenant context if not specified
            org_id = TenantContext.get_organization_id()
            if org_id:
                conditions.append(AuditLog.organization_id == org_id)

        if user_id:
            conditions.append(AuditLog.user_id == user_id)

        if event_type:
            conditions.append(AuditLog.event_type == event_type)

        if event_name:
            conditions.append(AuditLog.event_name == event_name)

        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)

        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)

        if start_date:
            conditions.append(AuditLog.created_at >= start_date)

        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        if compliance_tag:
            conditions.append(AuditLog.compliance_tags.contains([compliance_tag]))

        if conditions:
            query = query.where(and_(*conditions))

        # Order by creation time (newest first)
        query = query.order_by(desc(AuditLog.created_at))

        # Apply pagination
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await session.execute(query)
        return result.scalars().all()

    async def export_logs(
        self,
        session: AsyncSession,
        organization_id: str,
        format: str = "json",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        compliance_filter: Optional[str] = None
    ) -> str:
        """
        Export audit logs for compliance reporting

        Args:
            session: Database session
            organization_id: Organization to export
            format: Export format (json, csv, siem)
            start_date: Start of export period
            end_date: End of export period
            compliance_filter: Filter by compliance tag

        Returns:
            Exported data as string
        """

        # Query logs
        logs = await self.query_logs(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            compliance_tag=compliance_filter,
            limit=10000  # Reasonable limit for export
        )

        if format == "json":
            return self._export_json(logs)
        elif format == "csv":
            return self._export_csv(logs)
        elif format == "siem":
            return self._export_siem(logs)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    # Private helper methods

    async def _get_previous_hash(self, session: AsyncSession, organization_id: str) -> Optional[str]:
        """Get the hash of the most recent audit log for the organization"""

        # Check cache first
        if organization_id in self._last_hash_cache:
            return self._last_hash_cache[organization_id]

        # Query database for last entry
        result = await session.execute(
            select(AuditLog.current_hash)
            .where(AuditLog.organization_id == organization_id)
            .order_by(desc(AuditLog.created_at))
            .limit(1)
        )

        last_hash = result.scalar_one_or_none()

        if last_hash:
            self._last_hash_cache[organization_id] = last_hash

        return last_hash

    def _calculate_hash(self, audit_log: AuditLog) -> str:
        """Calculate SHA-256 hash for an audit log entry"""

        # Create a deterministic string representation
        hash_input = json.dumps({
            "organization_id": str(audit_log.organization_id),
            "user_id": str(audit_log.user_id) if audit_log.user_id else None,
            "event_type": audit_log.event_type.value,
            "event_name": audit_log.event_name,
            "resource_type": audit_log.resource_type,
            "resource_id": audit_log.resource_id,
            "event_data": audit_log.event_data,
            "changes": audit_log.changes,
            "ip_address": audit_log.ip_address,
            "previous_hash": audit_log.previous_hash,
            "timestamp": audit_log.created_at.isoformat() if audit_log.created_at else datetime.utcnow().isoformat()
        }, sort_keys=True)

        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _calculate_retention(self, compliance_tags: Optional[List[str]]) -> datetime:
        """Calculate retention period based on compliance requirements"""

        # Default retention: 2 years
        retention_days = 730

        if compliance_tags:
            # Compliance-specific retention requirements
            if "HIPAA" in compliance_tags:
                retention_days = 2190  # 6 years
            elif "SOC2" in compliance_tags:
                retention_days = 2555  # 7 years
            elif "GDPR" in compliance_tags:
                retention_days = 1095  # 3 years
            elif "PCI-DSS" in compliance_tags:
                retention_days = 365  # 1 year minimum

        return datetime.utcnow() + timedelta(days=retention_days)

    def _export_json(self, logs: List[AuditLog]) -> str:
        """Export logs as JSON"""

        export_data = []
        for log in logs:
            export_data.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "organization_id": str(log.organization_id),
                "user_id": str(log.user_id) if log.user_id else None,
                "event_type": log.event_type.value,
                "event_name": log.event_name,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "event_data": log.event_data,
                "changes": log.changes,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "compliance_tags": log.compliance_tags,
                "hash": log.current_hash
            })

        return json.dumps(export_data, indent=2)

    def _export_csv(self, logs: List[AuditLog]) -> str:
        """Export logs as CSV"""

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Timestamp", "Organization ID", "User ID", "Event Type",
            "Event Name", "Resource Type", "Resource ID", "IP Address",
            "Compliance Tags", "Hash"
        ])

        # Data rows
        for log in logs:
            writer.writerow([
                log.created_at.isoformat(),
                str(log.organization_id),
                str(log.user_id) if log.user_id else "",
                log.event_type.value,
                log.event_name,
                log.resource_type or "",
                log.resource_id or "",
                log.ip_address or "",
                ",".join(log.compliance_tags) if log.compliance_tags else "",
                log.current_hash
            ])

        return output.getvalue()

    def _export_siem(self, logs: List[AuditLog]) -> str:
        """Export logs in SIEM format (CEF - Common Event Format)"""

        siem_logs = []

        for log in logs:
            # CEF format: CEF:Version|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|[Extension]
            cef_log = (
                f"CEF:0|Janua|AuditLog|1.0|{log.event_type.value}|{log.event_name}|3|"
                f"duid={log.user_id if log.user_id else 'system'} "
                f"src={log.ip_address or 'unknown'} "
                f"act={log.event_name} "
                f"dvc={log.organization_id} "
                f"cs1Label=ResourceType cs1={log.resource_type or 'none'} "
                f"cs2Label=ResourceID cs2={log.resource_id or 'none'} "
                f"cs3Label=Hash cs3={log.current_hash}"
            )
            siem_logs.append(cef_log)

        return "\n".join(siem_logs)


# Audit event decorators for automatic logging

def audit_event(
    event_type: AuditEventType,
    event_name: str,
    resource_type: Optional[str] = None
):
    """Decorator to automatically log audit events for endpoints"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract necessary information from kwargs
            db = kwargs.get('db')
            current_user_id = kwargs.get('current_user_id')
            request = kwargs.get('request')

            # Get resource ID from path parameters if available
            resource_id = kwargs.get('id') or kwargs.get('resource_id')

            # Execute the function
            result = await func(*args, **kwargs)

            # Log the audit event
            if db:
                audit_logger = AuditLogger()
                await audit_logger.log_event(
                    session=db,
                    event_type=event_type,
                    event_name=event_name,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    user_id=current_user_id,
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get("user-agent") if request else None,
                    event_data={"result": "success"}
                )

            return result

        return wrapper
    return decorator


async def replay_fallback_logs(session: AsyncSession) -> Dict[str, Any]:
    """
    Replay fallback audit logs back into the database.
    Should be called when database connectivity is restored.

    Returns:
        Summary of replay operation with success/failure counts
    """
    fallback_dir = Path(FALLBACK_LOG_DIR)
    if not fallback_dir.exists():
        return {"message": "No fallback directory found", "replayed": 0, "failed": 0}

    results = {"replayed": 0, "failed": 0, "files_processed": [], "errors": []}
    audit = AuditLogger()

    # Find all fallback files
    fallback_files = sorted(fallback_dir.glob("audit-fallback-*.jsonl"))

    for fallback_file in fallback_files:
        try:
            with open(fallback_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        event_data = json.loads(line.strip())

                        # Skip already-replayed entries
                        if event_data.get("_replayed"):
                            continue

                        # Extract event data for replay
                        event_type_str = event_data.get("event_type")
                        if not event_type_str:
                            continue

                        event_type = AuditEventType(event_type_str)

                        # Set organization context if available
                        org_id = event_data.get("organization_id")
                        if org_id:
                            TenantContext.set_organization_id(org_id)

                        # Replay the event (will go to database this time)
                        await audit.log_event(
                            session=session,
                            event_type=event_type,
                            event_name=event_data.get("event_name", ""),
                            resource_type=event_data.get("resource_type"),
                            resource_id=event_data.get("resource_id"),
                            event_data=event_data.get("event_data"),
                            changes=event_data.get("changes"),
                            user_id=event_data.get("user_id"),
                            service_account_id=event_data.get("service_account_id"),
                            ip_address=event_data.get("ip_address"),
                            user_agent=event_data.get("user_agent"),
                            compliance_tags=event_data.get("compliance_tags")
                        )

                        results["replayed"] += 1

                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append({
                            "file": str(fallback_file),
                            "line": line_num,
                            "error": str(e)
                        })

            # Archive processed file
            archive_name = fallback_file.with_suffix(".jsonl.replayed")
            fallback_file.rename(archive_name)
            results["files_processed"].append(str(fallback_file))

            logger.info(
                "Processed fallback audit log file",
                file=str(fallback_file),
                replayed=results["replayed"],
                failed=results["failed"]
            )

        except Exception as e:
            logger.error("Failed to process fallback file", file=str(fallback_file), error=str(e))
            results["errors"].append({"file": str(fallback_file), "error": str(e)})

    await session.commit()
    return results


def get_fallback_log_stats() -> Dict[str, Any]:
    """
    Get statistics about pending fallback logs.
    Useful for monitoring and alerting.
    """
    fallback_dir = Path(FALLBACK_LOG_DIR)
    if not fallback_dir.exists():
        return {"pending_files": 0, "pending_events": 0, "oldest_file": None}

    stats = {"pending_files": 0, "pending_events": 0, "oldest_file": None, "newest_file": None}

    fallback_files = sorted(fallback_dir.glob("audit-fallback-*.jsonl"))
    stats["pending_files"] = len(fallback_files)

    for fallback_file in fallback_files:
        try:
            with open(fallback_file, "r") as f:
                stats["pending_events"] += sum(1 for _ in f)

            if stats["oldest_file"] is None:
                stats["oldest_file"] = str(fallback_file)
            stats["newest_file"] = str(fallback_file)
        except Exception:
            pass

    return stats


# Global audit logger instance
audit_logger = AuditLogger()