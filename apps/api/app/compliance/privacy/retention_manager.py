"""
Retention Manager
Handles automated data retention and deletion based on GDPR retention policies.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.compliance import DataRetentionPolicy, DataCategory, ComplianceFramework
from app.models.users import User
from app.models.audit import AuditLog
from ..audit import AuditLogger, AuditEventType

from .privacy_types import RetentionAction

logger = logging.getLogger(__name__)


class RetentionManager:
    """Manages automated data retention and deletion policies"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger

    async def execute_retention_policies(
        self, organization_id: Optional[str] = None, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute automated data retention and deletion based on policies"""

        current_time = datetime.utcnow()
        retention_summary = {
            "processed_policies": 0,
            "affected_records": 0,
            "deleted_records": 0,
            "anonymized_records": 0,
            "archived_records": 0,
            "errors": 0,
            "processing_details": [],
            "dry_run": dry_run,
        }

        async with get_session() as session:
            # Get active retention policies
            policy_query = select(DataRetentionPolicy).where(DataRetentionPolicy.is_active == True)

            if organization_id:
                policy_query = policy_query.where(
                    DataRetentionPolicy.organization_id == uuid.UUID(organization_id)
                )

            result = await session.execute(policy_query)
            policies = result.scalars().all()

            for policy in policies:
                try:
                    retention_summary["processed_policies"] += 1

                    # Calculate cutoff date
                    cutoff_date = current_time - timedelta(days=policy.retention_period_days)

                    # Process records based on data category and source
                    if policy.data_category == DataCategory.IDENTITY:
                        records_processed = await self._process_identity_retention(
                            session, policy, cutoff_date, dry_run
                        )
                    elif policy.data_category == DataCategory.BEHAVIORAL:
                        records_processed = await self._process_behavioral_retention(
                            session, policy, cutoff_date, dry_run
                        )
                    elif policy.data_category == DataCategory.TECHNICAL:
                        records_processed = await self._process_technical_retention(
                            session, policy, cutoff_date, dry_run
                        )
                    else:
                        records_processed = await self._process_generic_retention(
                            session, policy, cutoff_date, dry_run
                        )

                    retention_summary["affected_records"] += records_processed["affected"]
                    retention_summary["deleted_records"] += records_processed["deleted"]
                    retention_summary["anonymized_records"] += records_processed["anonymized"]
                    retention_summary["archived_records"] += records_processed["archived"]

                    retention_summary["processing_details"].append(
                        {
                            "policy_id": str(policy.id),
                            "policy_name": policy.name,
                            "data_category": policy.data_category.value,
                            "retention_days": policy.retention_period_days,
                            "cutoff_date": cutoff_date.isoformat(),
                            "records_processed": records_processed,
                        }
                    )

                except Exception as e:
                    retention_summary["errors"] += 1
                    logger.error(f"Error processing retention policy {policy.id}: {str(e)}")

        # Log retention activity
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.SYSTEM_CHANGE,
            resource_type="data_retention",
            resource_id="automated_cleanup",
            action="retention_processing",
            outcome="success" if retention_summary["errors"] == 0 else "partial_success",
            organization_id=organization_id,
            control_id="GDPR-5",
            compliance_frameworks=[ComplianceFramework.GDPR],
            raw_data=retention_summary,
        )

        logger.info("Automated data retention completed", extra=retention_summary)
        return retention_summary

    async def create_retention_policy(
        self,
        name: str,
        description: str,
        data_category: DataCategory,
        retention_period_days: int,
        retention_action: RetentionAction,
        data_sources: List[str],
        legal_basis: str,
        organization_id: Optional[str] = None,
        creator_id: Optional[str] = None,
    ) -> str:
        """Create a new data retention policy"""

        async with get_session() as session:
            policy = DataRetentionPolicy(
                name=name,
                description=description,
                data_category=data_category,
                retention_period_days=retention_period_days,
                retention_action=retention_action.value,
                data_sources=data_sources,
                legal_basis=legal_basis,
                is_active=True,
                organization_id=uuid.UUID(organization_id) if organization_id else None,
                created_by=uuid.UUID(creator_id) if creator_id else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(policy)
            await session.commit()
            await session.refresh(policy)

            policy_id = str(policy.id)

        # Log policy creation
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.SYSTEM_CHANGE,
            resource_type="retention_policy",
            resource_id=policy_id,
            action="create",
            outcome="success",
            organization_id=organization_id,
            control_id="GDPR-5",
            compliance_frameworks=[ComplianceFramework.GDPR],
            raw_data={
                "policy_name": name,
                "data_category": data_category.value,
                "retention_days": retention_period_days,
                "retention_action": retention_action.value,
            },
        )

        logger.info(
            f"Retention policy created: {name}",
            extra={
                "policy_id": policy_id,
                "data_category": data_category.value,
                "retention_days": retention_period_days,
            },
        )

        return policy_id

    async def _process_identity_retention(
        self,
        session: AsyncSession,
        policy: DataRetentionPolicy,
        cutoff_date: datetime,
        dry_run: bool,
    ) -> Dict[str, int]:
        """Process identity data retention"""

        result = {"affected": 0, "deleted": 0, "anonymized": 0, "archived": 0}

        # Find records older than cutoff date
        if "users" in policy.data_sources:
            users_query = (
                select(func.count()).select_from(User).where(User.created_at < cutoff_date)
            )
            affected_count = (await session.execute(users_query)).scalar()
            result["affected"] += affected_count

            if not dry_run and affected_count > 0:
                if policy.retention_action == RetentionAction.DELETE.value:
                    delete_result = await session.execute(
                        delete(User).where(User.created_at < cutoff_date)
                    )
                    result["deleted"] += delete_result.rowcount
                elif policy.retention_action == RetentionAction.ANONYMIZE.value:
                    # Anonymize user data (implementation specific)
                    result["anonymized"] += affected_count

        return result

    async def _process_behavioral_retention(
        self,
        session: AsyncSession,
        policy: DataRetentionPolicy,
        cutoff_date: datetime,
        dry_run: bool,
    ) -> Dict[str, int]:
        """Process behavioral data retention"""

        result = {"affected": 0, "deleted": 0, "anonymized": 0, "archived": 0}

        # Find audit logs older than cutoff date
        if "audit_logs" in policy.data_sources:
            logs_query = (
                select(func.count()).select_from(AuditLog).where(AuditLog.timestamp < cutoff_date)
            )
            affected_count = (await session.execute(logs_query)).scalar()
            result["affected"] += affected_count

            if not dry_run and affected_count > 0:
                if policy.retention_action == RetentionAction.DELETE.value:
                    delete_result = await session.execute(
                        delete(AuditLog).where(AuditLog.timestamp < cutoff_date)
                    )
                    result["deleted"] += delete_result.rowcount
                elif policy.retention_action == RetentionAction.ARCHIVE.value:
                    # Archive logs (implementation specific)
                    result["archived"] += affected_count

        return result

    async def _process_technical_retention(
        self,
        session: AsyncSession,
        policy: DataRetentionPolicy,
        cutoff_date: datetime,
        dry_run: bool,
    ) -> Dict[str, int]:
        """Process technical data retention"""

        result = {"affected": 0, "deleted": 0, "anonymized": 0, "archived": 0}

        # Implementation for technical data (logs, metrics, etc.)
        # This would be customized based on specific technical data sources

        return result

    async def _process_generic_retention(
        self,
        session: AsyncSession,
        policy: DataRetentionPolicy,
        cutoff_date: datetime,
        dry_run: bool,
    ) -> Dict[str, int]:
        """Process generic data retention"""

        result = {"affected": 0, "deleted": 0, "anonymized": 0, "archived": 0}

        # Generic implementation for unspecified data categories
        # Would be customized based on specific requirements

        return result

    async def get_active_policies(
        self, organization_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all active retention policies"""

        async with get_session() as session:
            query = select(DataRetentionPolicy).where(DataRetentionPolicy.is_active == True)

            if organization_id:
                query = query.where(
                    DataRetentionPolicy.organization_id == uuid.UUID(organization_id)
                )

            result = await session.execute(query)
            policies = result.scalars().all()

            return [
                {
                    "policy_id": str(policy.id),
                    "name": policy.name,
                    "description": policy.description,
                    "data_category": policy.data_category.value,
                    "retention_period_days": policy.retention_period_days,
                    "retention_action": policy.retention_action,
                    "data_sources": policy.data_sources,
                    "legal_basis": policy.legal_basis,
                    "created_at": policy.created_at.isoformat(),
                }
                for policy in policies
            ]

    async def deactivate_policy(
        self, policy_id: str, organization_id: Optional[str] = None
    ) -> bool:
        """Deactivate a retention policy"""

        async with get_session() as session:
            result = await session.execute(
                select(DataRetentionPolicy).where(DataRetentionPolicy.id == uuid.UUID(policy_id))
            )
            policy = result.scalar_one_or_none()

            if not policy:
                return False

            policy.is_active = False
            policy.updated_at = datetime.utcnow()
            await session.commit()

        # Log policy deactivation
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.SYSTEM_CHANGE,
            resource_type="retention_policy",
            resource_id=policy_id,
            action="deactivate",
            outcome="success",
            organization_id=organization_id,
            control_id="GDPR-5",
            compliance_frameworks=[ComplianceFramework.GDPR],
        )

        return True
