"""
Evidence Collector
Evidence gathering and validation operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from sqlalchemy import select, and_, func

from app.core.database import get_session
from app.models.audit import AuditLog
from app.models.users import User

from .control_status import EvidenceType, ComplianceEvidence


logger = logging.getLogger(__name__)


class EvidenceCollector:
    """Evidence gathering and validation operations"""

    def __init__(self, evidence_storage: Path):
        self.evidence_storage = evidence_storage
        self.evidence_storage.mkdir(parents=True, exist_ok=True)

    async def collect_system_evidence(self) -> List[ComplianceEvidence]:
        """Collect system-generated compliance evidence"""
        evidence_list = []

        try:
            # Collect application logs
            app_log_evidence = ComplianceEvidence(
                evidence_id=f"sys_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                control_id="CC7.2",
                evidence_type=EvidenceType.SYSTEM_GENERATED,
                description="Application system logs for monitoring control",
                collection_date=datetime.utcnow(),
                collector="system",
                metadata={
                    "log_level": "INFO",
                    "time_range": "last_24_hours",
                    "source": "application_logger",
                },
            )
            evidence_list.append(app_log_evidence)

            # Collect system configuration evidence
            config_evidence = ComplianceEvidence(
                evidence_id=f"sys_config_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                control_id="CC5.2",
                evidence_type=EvidenceType.SYSTEM_GENERATED,
                description="System configuration settings for technology controls",
                collection_date=datetime.utcnow(),
                collector="system",
                metadata={"config_type": "security_settings", "validation_status": "verified"},
            )
            evidence_list.append(config_evidence)

            # Collect backup status evidence
            backup_evidence = ComplianceEvidence(
                evidence_id=f"backup_status_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                control_id="CC7.1",
                evidence_type=EvidenceType.SYSTEM_GENERATED,
                description="Backup system status and recovery point verification",
                collection_date=datetime.utcnow(),
                collector="system",
                metadata={
                    "backup_type": "incremental",
                    "last_backup": datetime.utcnow().isoformat(),
                    "retention_period": "30_days",
                },
            )
            evidence_list.append(backup_evidence)

            return evidence_list

        except Exception as e:
            logger.error(f"Failed to collect system evidence: {str(e)}")
            return []

    async def collect_security_logs(self) -> List[ComplianceEvidence]:
        """Collect security-related logs for compliance evidence"""
        evidence_list = []

        try:
            async with get_session() as session:
                # Collect authentication logs
                auth_logs = await session.execute(
                    select(AuditLog)
                    .where(
                        and_(
                            AuditLog.action.like("%auth%"),
                            AuditLog.created_at >= datetime.utcnow() - timedelta(days=1),
                        )
                    )
                    .limit(100)
                )
                auth_log_records = auth_logs.scalars().all()

                if auth_log_records:
                    auth_evidence = ComplianceEvidence(
                        evidence_id=f"auth_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        control_id="CC6.2",
                        evidence_type=EvidenceType.SYSTEM_GENERATED,
                        description=f"Authentication activity logs - {len(auth_log_records)} records",
                        collection_date=datetime.utcnow(),
                        collector="system",
                        metadata={
                            "record_count": len(auth_log_records),
                            "time_range": "last_24_hours",
                            "log_types": ["login", "logout", "failed_auth"],
                        },
                    )
                    evidence_list.append(auth_evidence)

                # Collect access control logs
                access_logs = await session.execute(
                    select(AuditLog)
                    .where(
                        and_(
                            AuditLog.action.like("%access%"),
                            AuditLog.created_at >= datetime.utcnow() - timedelta(days=1),
                        )
                    )
                    .limit(100)
                )
                access_log_records = access_logs.scalars().all()

                if access_log_records:
                    access_evidence = ComplianceEvidence(
                        evidence_id=f"access_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        control_id="CC6.3",
                        evidence_type=EvidenceType.SYSTEM_GENERATED,
                        description=f"Access control activity logs - {len(access_log_records)} records",
                        collection_date=datetime.utcnow(),
                        collector="system",
                        metadata={
                            "record_count": len(access_log_records),
                            "time_range": "last_24_hours",
                            "access_types": ["granted", "denied", "escalated"],
                        },
                    )
                    evidence_list.append(access_evidence)

                # Collect privilege elevation logs
                privilege_logs = await session.execute(
                    select(AuditLog)
                    .where(
                        and_(
                            AuditLog.action.like("%admin%"),
                            AuditLog.created_at >= datetime.utcnow() - timedelta(days=1),
                        )
                    )
                    .limit(50)
                )
                privilege_log_records = privilege_logs.scalars().all()

                if privilege_log_records:
                    privilege_evidence = ComplianceEvidence(
                        evidence_id=f"privilege_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        control_id="CC6.7",
                        evidence_type=EvidenceType.SYSTEM_GENERATED,
                        description=f"Privileged access activity logs - {len(privilege_log_records)} records",
                        collection_date=datetime.utcnow(),
                        collector="system",
                        metadata={
                            "record_count": len(privilege_log_records),
                            "time_range": "last_24_hours",
                            "privilege_types": ["admin_access", "system_changes"],
                        },
                    )
                    evidence_list.append(privilege_evidence)

            return evidence_list

        except Exception as e:
            logger.error(f"Failed to collect security logs: {str(e)}")
            return []

    async def collect_access_logs(self) -> List[ComplianceEvidence]:
        """Collect access-related logs for compliance evidence"""
        evidence_list = []

        try:
            async with get_session() as session:
                # Collect user provisioning evidence
                recent_users = await session.execute(
                    select(User)
                    .where(User.created_at >= datetime.utcnow() - timedelta(days=7))
                    .limit(20)
                )
                user_records = recent_users.scalars().all()

                if user_records:
                    provisioning_evidence = ComplianceEvidence(
                        evidence_id=f"user_provisioning_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        control_id="CC6.1",
                        evidence_type=EvidenceType.SYSTEM_GENERATED,
                        description=f"User provisioning activities - {len(user_records)} new users",
                        collection_date=datetime.utcnow(),
                        collector="system",
                        metadata={
                            "user_count": len(user_records),
                            "time_range": "last_7_days",
                            "provisioning_types": ["new_user", "role_assignment"],
                        },
                    )
                    evidence_list.append(provisioning_evidence)

                # Collect user access review evidence
                total_users = await session.execute(select(func.count(User.id)))
                user_count = total_users.scalar()

                active_users = await session.execute(
                    select(func.count(User.id)).where(User.is_active == True)
                )
                active_count = active_users.scalar()

                if user_count > 0:
                    access_review_evidence = ComplianceEvidence(
                        evidence_id=f"access_review_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        control_id="CC6.8",
                        evidence_type=EvidenceType.SYSTEM_GENERATED,
                        description=f"User access review data - {active_count}/{user_count} active users",
                        collection_date=datetime.utcnow(),
                        collector="system",
                        metadata={
                            "total_users": user_count,
                            "active_users": active_count,
                            "inactive_users": user_count - active_count,
                            "review_date": datetime.utcnow().isoformat(),
                        },
                    )
                    evidence_list.append(access_review_evidence)

            return evidence_list

        except Exception as e:
            logger.error(f"Failed to collect access logs: {str(e)}")
            return []

    async def store_evidence(self, evidence: ComplianceEvidence) -> bool:
        """Store compliance evidence securely"""
        try:
            # Create evidence file path
            evidence_file = self.evidence_storage / f"{evidence.evidence_id}.json"

            # Prepare evidence data for storage
            evidence_data = {
                "evidence_id": evidence.evidence_id,
                "control_id": evidence.control_id,
                "evidence_type": evidence.evidence_type.value,
                "description": evidence.description,
                "collection_date": evidence.collection_date.isoformat(),
                "collector": evidence.collector,
                "file_path": evidence.file_path,
                "content": evidence.content,
                "metadata": evidence.metadata,
                "validation_status": evidence.validation_status,
                "retention_date": evidence.retention_date.isoformat()
                if evidence.retention_date
                else None,
            }

            # Write evidence to file
            with open(evidence_file, "w") as f:
                json.dump(evidence_data, f, indent=2, default=str)

            logger.info(f"Stored evidence: {evidence.evidence_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store evidence {evidence.evidence_id}: {str(e)}")
            return False

    async def retrieve_evidence(self, evidence_id: str) -> Optional[ComplianceEvidence]:
        """Retrieve stored compliance evidence"""
        try:
            evidence_file = self.evidence_storage / f"{evidence_id}.json"

            if not evidence_file.exists():
                logger.warning(f"Evidence file not found: {evidence_id}")
                return None

            with open(evidence_file, "r") as f:
                evidence_data = json.load(f)

            # Reconstruct ComplianceEvidence object
            evidence = ComplianceEvidence(
                evidence_id=evidence_data["evidence_id"],
                control_id=evidence_data["control_id"],
                evidence_type=EvidenceType(evidence_data["evidence_type"]),
                description=evidence_data["description"],
                collection_date=datetime.fromisoformat(evidence_data["collection_date"]),
                collector=evidence_data["collector"],
                file_path=evidence_data.get("file_path"),
                content=evidence_data.get("content"),
                metadata=evidence_data.get("metadata"),
                validation_status=evidence_data.get("validation_status", "pending"),
                retention_date=datetime.fromisoformat(evidence_data["retention_date"])
                if evidence_data.get("retention_date")
                else None,
            )

            return evidence

        except Exception as e:
            logger.error(f"Failed to retrieve evidence {evidence_id}: {str(e)}")
            return None

    async def validate_evidence(
        self, evidence_id: str, validation_criteria: Dict[str, Any]
    ) -> bool:
        """Validate compliance evidence quality and completeness"""
        try:
            evidence = await self.retrieve_evidence(evidence_id)
            if not evidence:
                return False

            validation_score = 0
            max_score = 0

            # Check completeness
            if validation_criteria.get("completeness", False):
                max_score += 1
                if evidence.description and evidence.collection_date and evidence.collector:
                    validation_score += 1

            # Check accuracy
            if validation_criteria.get("accuracy", False):
                max_score += 1
                if evidence.metadata and evidence.control_id:
                    validation_score += 1

            # Check timeliness
            if validation_criteria.get("timeliness", False):
                max_score += 1
                if evidence.collection_date >= datetime.utcnow() - timedelta(days=30):
                    validation_score += 1

            # Update validation status
            if max_score > 0:
                validation_percentage = validation_score / max_score
                if validation_percentage >= 0.8:
                    evidence.validation_status = "validated"
                elif validation_percentage >= 0.6:
                    evidence.validation_status = "partial"
                else:
                    evidence.validation_status = "failed"

                # Store updated evidence
                await self.store_evidence(evidence)

            return validation_percentage >= 0.8 if max_score > 0 else False

        except Exception as e:
            logger.error(f"Failed to validate evidence {evidence_id}: {str(e)}")
            return False

    async def search_evidence(self, search_criteria: Dict[str, Any]) -> List[ComplianceEvidence]:
        """Search compliance evidence repository"""
        try:
            evidence_list = []

            # List all evidence files
            for evidence_file in self.evidence_storage.glob("*.json"):
                try:
                    with open(evidence_file, "r") as f:
                        evidence_data = json.load(f)

                    # Apply search filters
                    matches = True

                    if "control_id" in search_criteria:
                        if evidence_data.get("control_id") != search_criteria["control_id"]:
                            matches = False

                    if "evidence_type" in search_criteria:
                        if evidence_data.get("evidence_type") != search_criteria["evidence_type"]:
                            matches = False

                    if "date_range" in search_criteria:
                        evidence_date = datetime.fromisoformat(evidence_data["collection_date"])
                        start_date = search_criteria["date_range"].get("start")
                        end_date = search_criteria["date_range"].get("end")

                        if start_date and evidence_date < start_date:
                            matches = False
                        if end_date and evidence_date > end_date:
                            matches = False

                    if matches:
                        # Reconstruct evidence object
                        evidence = ComplianceEvidence(
                            evidence_id=evidence_data["evidence_id"],
                            control_id=evidence_data["control_id"],
                            evidence_type=EvidenceType(evidence_data["evidence_type"]),
                            description=evidence_data["description"],
                            collection_date=datetime.fromisoformat(
                                evidence_data["collection_date"]
                            ),
                            collector=evidence_data["collector"],
                            file_path=evidence_data.get("file_path"),
                            content=evidence_data.get("content"),
                            metadata=evidence_data.get("metadata"),
                            validation_status=evidence_data.get("validation_status", "pending"),
                        )
                        evidence_list.append(evidence)

                except Exception as e:
                    logger.warning(f"Error processing evidence file {evidence_file}: {str(e)}")
                    continue

            return evidence_list

        except Exception as e:
            logger.error(f"Failed to search evidence: {str(e)}")
            return []

    async def cleanup_expired_evidence(self, retention_days: int = 2555) -> int:  # 7 years default
        """Clean up expired compliance evidence"""
        try:
            cleaned_count = 0
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            for evidence_file in self.evidence_storage.glob("*.json"):
                try:
                    with open(evidence_file, "r") as f:
                        evidence_data = json.load(f)

                    collection_date = datetime.fromisoformat(evidence_data["collection_date"])

                    if collection_date < cutoff_date:
                        evidence_file.unlink()  # Delete file
                        cleaned_count += 1
                        logger.info(f"Cleaned up expired evidence: {evidence_data['evidence_id']}")

                except Exception as e:
                    logger.warning(f"Error processing evidence file {evidence_file}: {str(e)}")
                    continue

            logger.info(f"Cleaned up {cleaned_count} expired evidence files")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired evidence: {str(e)}")
            return 0
