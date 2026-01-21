"""
Compliance service for GDPR, SOC 2, HIPAA, and other frameworks
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text

from app.models import User
from app.models.compliance import (
    ConsentRecord, ConsentType, ConsentStatus, LegalBasis,
    DataRetentionPolicy, DataSubjectRequest, DataSubjectRequestType, RequestStatus,
    PrivacySettings, DataBreachIncident, ComplianceReport, DataCategory,
    ComplianceFramework
)
from app.services.audit_logger import AuditLogger, AuditEventType
from app.core.logging import logger


class ConsentService:
    """GDPR consent management service"""

    def __init__(self, db: AsyncSession, audit_logger: AuditLogger):
        self.db = db
        self.audit_logger = audit_logger

    async def record_consent(
        self,
        user_id: UUID,
        consent_type: ConsentType,
        purpose: str,
        legal_basis: LegalBasis = LegalBasis.CONSENT,
        data_categories: List[DataCategory] = None,
        processing_purposes: List[str] = None,
        third_parties: List[str] = None,
        retention_period: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        consent_method: str = "api",
        consent_version: str = "1.0",
        tenant_id: Optional[UUID] = None
    ) -> ConsentRecord:
        """Record user consent"""

        # Check for existing consent
        existing = await self.db.execute(
            select(ConsentRecord).where(
                and_(
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.consent_type == consent_type,
                    ConsentRecord.purpose == purpose,
                    ConsentRecord.status.in_([ConsentStatus.GIVEN, ConsentStatus.PENDING])
                )
            )
        )
        existing_consent = existing.scalar_one_or_none()

        if existing_consent:
            # Update existing consent
            existing_consent.status = ConsentStatus.GIVEN
            existing_consent.given_at = datetime.utcnow()
            existing_consent.last_confirmed_at = datetime.utcnow()
            existing_consent.ip_address = ip_address
            existing_consent.user_agent = user_agent
            existing_consent.consent_method = consent_method
            existing_consent.consent_version = consent_version
            consent_record = existing_consent
        else:
            # Create new consent record
            consent_record = ConsentRecord(
                user_id=user_id,
                tenant_id=tenant_id,
                consent_type=consent_type,
                purpose=purpose,
                legal_basis=legal_basis,
                status=ConsentStatus.GIVEN,
                given_at=datetime.utcnow(),
                last_confirmed_at=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent,
                consent_method=consent_method,
                consent_version=consent_version,
                data_categories=[cat.value for cat in (data_categories or [])],
                processing_purposes=processing_purposes or [],
                third_parties=third_parties or [],
                retention_period=retention_period
            )
            self.db.add(consent_record)

        await self.db.commit()
        await self.db.refresh(consent_record)

        # Log consent
        await self.audit_logger.log(
            event_type=AuditEventType.GDPR_CONSENT_GIVEN,
            tenant_id=str(tenant_id) if tenant_id else "default",
            identity_id=str(user_id),
            data_subject_id=str(user_id),
            details={
                "consent_type": consent_type.value,
                "purpose": purpose,
                "legal_basis": legal_basis.value,
                "consent_method": consent_method,
                "consent_version": consent_version
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article 7",
                "lawful_basis": legal_basis.value
            },
            legal_basis=legal_basis.value,
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info"
        )

        return consent_record

    async def withdraw_consent(
        self,
        user_id: UUID,
        consent_type: ConsentType,
        purpose: str,
        withdrawal_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """Withdraw user consent"""

        # Find active consent
        result = await self.db.execute(
            select(ConsentRecord).where(
                and_(
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.consent_type == consent_type,
                    ConsentRecord.purpose == purpose,
                    ConsentRecord.status == ConsentStatus.GIVEN
                )
            )
        )
        consent_record = result.scalar_one_or_none()

        if not consent_record:
            return False

        # Update consent status
        consent_record.status = ConsentStatus.WITHDRAWN
        consent_record.withdrawn_at = datetime.utcnow()
        consent_record.withdrawal_reason = withdrawal_reason

        await self.db.commit()

        # Log withdrawal
        await self.audit_logger.log(
            event_type=AuditEventType.GDPR_CONSENT_WITHDRAWN,
            tenant_id=str(tenant_id) if tenant_id else "default",
            identity_id=str(user_id),
            data_subject_id=str(user_id),
            details={
                "consent_type": consent_type.value,
                "purpose": purpose,
                "withdrawal_reason": withdrawal_reason or "No reason provided"
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article 7(3)",
                "withdrawal_ease": "as_easy_as_giving"
            },
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info"
        )

        return True

    async def get_user_consents(
        self,
        user_id: UUID,
        include_withdrawn: bool = False
    ) -> List[ConsentRecord]:
        """Get all consents for a user"""

        query = select(ConsentRecord).where(ConsentRecord.user_id == user_id)

        if not include_withdrawn:
            query = query.where(ConsentRecord.status != ConsentStatus.WITHDRAWN)

        result = await self.db.execute(query.order_by(ConsentRecord.created_at.desc()))
        return result.scalars().all()

    async def check_consent(
        self,
        user_id: UUID,
        consent_type: ConsentType,
        purpose: str
    ) -> bool:
        """Check if user has given valid consent"""

        result = await self.db.execute(
            select(ConsentRecord).where(
                and_(
                    ConsentRecord.user_id == user_id,
                    ConsentRecord.consent_type == consent_type,
                    ConsentRecord.purpose == purpose,
                    ConsentRecord.status == ConsentStatus.GIVEN,
                    or_(
                        ConsentRecord.expires_at.is_(None),
                        ConsentRecord.expires_at > datetime.utcnow()
                    )
                )
            )
        )

        return result.scalar_one_or_none() is not None


class DataSubjectRightsService:
    """GDPR data subject rights service"""

    def __init__(self, db: AsyncSession, audit_logger: AuditLogger):
        self.db = db
        self.audit_logger = audit_logger

    async def create_request(
        self,
        user_id: UUID,
        request_type: DataSubjectRequestType,
        description: Optional[str] = None,
        data_categories: List[DataCategory] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
        specific_fields: List[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> DataSubjectRequest:
        """Create a data subject rights request"""

        # Generate unique request ID
        request_id = f"DSR-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Calculate response due date (30 days for GDPR)
        response_due_date = datetime.utcnow() + timedelta(days=30)

        # Create request
        request = DataSubjectRequest(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            request_type=request_type,
            status=RequestStatus.RECEIVED,
            description=description,
            data_categories=[cat.value for cat in (data_categories or [])],
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            specific_fields=specific_fields or [],
            received_at=datetime.utcnow(),
            response_due_date=response_due_date,
            identity_verified=False,
            ip_address=ip_address,
            user_agent=user_agent,
            request_source="api"
        )

        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)

        # Log request creation
        await self.audit_logger.log(
            event_type=getattr(AuditEventType, f"GDPR_DATA_{request_type.value.upper()}"),
            tenant_id=str(tenant_id) if tenant_id else "default",
            identity_id=str(user_id),
            data_subject_id=str(user_id),
            resource_type="data_subject_request",
            resource_id=request_id,
            details={
                "request_type": request_type.value,
                "description": description,
                "data_categories": [cat.value for cat in (data_categories or [])],
                "response_due_date": response_due_date.isoformat()
            },
            compliance_context={
                "framework": "GDPR",
                "article": {
                    "access": "Article 15",
                    "rectification": "Article 16",
                    "erasure": "Article 17",
                    "portability": "Article 20",
                    "restriction": "Article 18",
                    "objection": "Article 21"
                }.get(request_type.value, "Article 15"),
                "request_id": request_id,
                "response_deadline": response_due_date.isoformat()
            },
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info"
        )

        return request

    async def process_access_request(
        self,
        request_id: str,
        processor_id: UUID
    ) -> Dict[str, Any]:
        """Process a data access request (Article 15)"""

        # Get request
        result = await self.db.execute(
            select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request or request.request_type != DataSubjectRequestType.ACCESS:
            raise ValueError("Invalid access request")

        # Get user data
        user_result = await self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Compile user data export
        user_data = {
            "personal_information": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "metadata": user.user_metadata
            },
            "consent_records": [],
            "privacy_settings": {},
            "data_subject_requests": [],
            "audit_logs": []
        }

        # Get consent records
        consent_result = await self.db.execute(
            select(ConsentRecord).where(ConsentRecord.user_id == user.id)
        )
        consents = consent_result.scalars().all()

        user_data["consent_records"] = [
            {
                "consent_type": consent.consent_type.value,
                "purpose": consent.purpose,
                "status": consent.status.value,
                "given_at": consent.given_at.isoformat() if consent.given_at else None,
                "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                "legal_basis": consent.legal_basis.value,
                "data_categories": consent.data_categories,
                "processing_purposes": consent.processing_purposes
            }
            for consent in consents
        ]

        # Get privacy settings
        privacy_result = await self.db.execute(
            select(PrivacySettings).where(PrivacySettings.user_id == user.id)
        )
        privacy = privacy_result.scalar_one_or_none()

        if privacy:
            user_data["privacy_settings"] = {
                "email_marketing": privacy.email_marketing,
                "analytics_tracking": privacy.analytics_tracking,
                "personalization": privacy.personalization,
                "third_party_sharing": privacy.third_party_sharing,
                "profile_visibility": privacy.profile_visibility,
                "updated_at": privacy.updated_at.isoformat() if privacy.updated_at else None
            }

        # Update request status
        request.status = RequestStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        request.assigned_to = processor_id
        request.response_method = "api"

        await self.db.commit()

        return user_data

    async def process_erasure_request(
        self,
        request_id: str,
        processor_id: UUID,
        deletion_method: str = "anonymize"
    ) -> bool:
        """Process a data erasure request (Article 17 - Right to be forgotten)"""

        # Get request
        result = await self.db.execute(
            select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request or request.request_type != DataSubjectRequestType.ERASURE:
            raise ValueError("Invalid erasure request")

        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if deletion_method == "anonymize":
            # Anonymize user data
            user.email = f"deleted-{str(uuid.uuid4())[:8]}@anonymized.local"
            user.first_name = "Deleted"
            user.last_name = "User"
            user.phone = None
            user.avatar_url = None
            user.user_metadata = {"anonymized": True, "anonymized_at": datetime.utcnow().isoformat()}

            # Withdraw all consents
            await self.db.execute(
                text("""
                UPDATE consent_records
                SET status = 'withdrawn', withdrawn_at = :now
                WHERE user_id = :user_id
                """).bindparam(now=datetime.utcnow(), user_id=request.user_id)
            )

        elif deletion_method == "hard_delete":
            # Hard delete (be careful with foreign key constraints)
            # This is a simplified example - in production you'd need to handle cascading deletes carefully
            await self.db.delete(user)

        # Update request status
        request.status = RequestStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        request.assigned_to = processor_id
        request.response_notes = f"Data {deletion_method}d successfully"

        await self.db.commit()

        # Log erasure
        await self.audit_logger.log(
            event_type=AuditEventType.GDPR_DATA_DELETION,
            tenant_id=str(request.tenant_id) if request.tenant_id else "default",
            identity_id=str(request.user_id),
            data_subject_id=str(request.user_id),
            resource_type="user_data",
            resource_id=str(request.user_id),
            details={
                "request_id": request_id,
                "deletion_method": deletion_method,
                "processor_id": str(processor_id)
            },
            compliance_context={
                "framework": "GDPR",
                "article": "Article 17",
                "right": "right_to_be_forgotten"
            },
            severity="info",
            retention_period=2555  # Keep deletion logs for 7 years
        )

        return True


class DataRetentionService:
    """Data retention and lifecycle management"""

    def __init__(self, db: AsyncSession, audit_logger: AuditLogger):
        self.db = db
        self.audit_logger = audit_logger

    async def create_retention_policy(
        self,
        name: str,
        data_category: DataCategory,
        retention_period_days: int,
        compliance_framework: ComplianceFramework,
        description: Optional[str] = None,
        deletion_method: str = "soft_delete",
        auto_deletion_enabled: bool = True,
        organization_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        approved_by: Optional[UUID] = None
    ) -> DataRetentionPolicy:
        """Create a data retention policy"""

        policy = DataRetentionPolicy(
            name=name,
            description=description,
            compliance_framework=compliance_framework,
            data_category=data_category,
            retention_period_days=retention_period_days,
            deletion_method=deletion_method,
            auto_deletion_enabled=auto_deletion_enabled,
            organization_id=organization_id,
            tenant_id=tenant_id,
            approved_by=approved_by,
            effective_date=datetime.utcnow(),
            review_date=datetime.utcnow() + timedelta(days=365)  # Annual review
        )

        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)

        # Log policy creation
        await self.audit_logger.log(
            event_type=AuditEventType.DATA_RETENTION_EXPIRED,  # Using closest available event
            tenant_id=str(tenant_id) if tenant_id else "default",
            resource_type="retention_policy",
            resource_id=str(policy.id),
            details={
                "policy_name": name,
                "data_category": data_category.value,
                "retention_period_days": retention_period_days,
                "compliance_framework": compliance_framework.value,
                "auto_deletion_enabled": auto_deletion_enabled
            },
            compliance_context={
                "framework": compliance_framework.value,
                "policy_type": "data_retention",
                "effective_date": policy.effective_date.isoformat()
            },
            severity="info"
        )

        return policy

    async def check_expired_data(self) -> List[Dict[str, Any]]:
        """Check for data that has exceeded retention periods"""

        # Get active retention policies
        policies_result = await self.db.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.is_active == True)
        )
        policies = policies_result.scalars().all()

        expired_items = []

        for policy in policies:
            cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_period_days)

            # This is a simplified example - in practice you'd check specific tables based on data_category
            if policy.data_category == DataCategory.IDENTITY:
                # Check for old user records
                users_result = await self.db.execute(
                    select(User).where(
                        and_(
                            User.created_at < cutoff_date,
                            User.last_login < cutoff_date - timedelta(days=90)  # 90 days inactive
                        )
                    )
                )
                users = users_result.scalars().all()

                for user in users:
                    expired_items.append({
                        "policy_id": str(policy.id),
                        "policy_name": policy.name,
                        "data_type": "user",
                        "data_id": str(user.id),
                        "created_at": user.created_at,
                        "deletion_method": policy.deletion_method,
                        "requires_approval": policy.require_approval
                    })

        return expired_items

    async def execute_retention_policy(
        self,
        policy_id: UUID,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Execute data retention policy"""

        # Get policy
        policy_result = await self.db.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.id == policy_id)
        )
        policy = policy_result.scalar_one_or_none()

        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        expired_items = await self.check_expired_data()
        deleted_count = 0
        anonymized_count = 0
        errors = []

        for item in expired_items:
            if item['policy_id'] != str(policy_id):
                continue

            try:
                if dry_run:
                    logger.info(f"DRY RUN: Would delete/anonymize {item['data_type']} {item['data_id']}")
                else:
                    if policy.deletion_method == 'anonymize':
                        await self._anonymize_data(item['data_type'], item['data_id'])
                        anonymized_count += 1
                    else:
                        await self._delete_data(item['data_type'], item['data_id'])
                        deleted_count += 1
            except Exception as e:
                errors.append({"item": item['data_id'], "error": str(e)})

        return {
            "policy_id": str(policy_id),
            "dry_run": dry_run,
            "deleted": deleted_count,
            "anonymized": anonymized_count,
            "errors": errors,
            "execution_time": datetime.utcnow().isoformat()
        }

    async def _anonymize_data(self, data_type: str, data_id: str):
        """Anonymize sensitive data"""
        if data_type == "user":
            user_result = await self.db.execute(
                select(User).where(User.id == UUID(data_id))
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.email = f"anon_{uuid.uuid4().hex[:8]}@anonymized.local"
                user.first_name = "REDACTED"
                user.last_name = "REDACTED"
                user.phone = None
                await self.db.commit()

    async def _delete_data(self, data_type: str, data_id: str):
        """Delete data permanently"""
        if data_type == "user":
            await self.db.execute(
                text(f"DELETE FROM users WHERE id = :id"),
                {"id": data_id}
            )
            await self.db.commit()

        if not policy:
            raise ValueError("Policy not found")

        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_period_days)

        # Get expired data items
        expired_items = await self.check_expired_data()
        policy_items = [item for item in expired_items if item["policy_id"] == str(policy_id)]

        if dry_run:
            return {
                "policy_name": policy.name,
                "expired_items_count": len(policy_items),
                "expired_items": policy_items,
                "dry_run": True
            }

        # Execute deletions
        deleted_count = 0
        errors = []

        for item in policy_items:
            try:
                if item["data_type"] == "user" and policy.deletion_method == "anonymize":
                    # Anonymize user data
                    user_result = await self.db.execute(
                        select(User).where(User.id == UUID(item["data_id"]))
                    )
                    user = user_result.scalar_one_or_none()

                    if user:
                        user.email = f"anonymized-{str(uuid.uuid4())[:8]}@retention.local"
                        user.first_name = "Anonymized"
                        user.last_name = "User"
                        user.user_metadata = {
                            "anonymized": True,
                            "anonymized_at": datetime.utcnow().isoformat(),
                            "retention_policy_id": str(policy_id)
                        }
                        deleted_count += 1

                        # Log retention action
                        await self.audit_logger.log(
                            event_type=AuditEventType.DATA_RETENTION_EXPIRED,
                            tenant_id=str(policy.tenant_id) if policy.tenant_id else "default",
                            resource_type="user_data",
                            resource_id=item["data_id"],
                            details={
                                "policy_id": str(policy_id),
                                "policy_name": policy.name,
                                "retention_action": "anonymized",
                                "original_creation_date": item["created_at"].isoformat()
                            },
                            compliance_context={
                                "framework": policy.compliance_framework.value,
                                "retention_period_days": policy.retention_period_days,
                                "automatic_deletion": policy.auto_deletion_enabled
                            },
                            severity="info"
                        )

            except Exception as e:
                errors.append({
                    "item_id": item["data_id"],
                    "error": str(e)
                })

        await self.db.commit()

        return {
            "policy_name": policy.name,
            "processed_items": len(policy_items),
            "deleted_count": deleted_count,
            "errors": errors,
            "dry_run": False
        }


class ComplianceService:
    """Main compliance service orchestrator"""

    def __init__(self, db: AsyncSession, audit_logger: AuditLogger):
        self.db = db
        self.audit_logger = audit_logger
        self.consent_service = ConsentService(db, audit_logger)
        self.data_subject_rights_service = DataSubjectRightsService(db, audit_logger)
        self.data_retention_service = DataRetentionService(db, audit_logger)

    async def get_compliance_dashboard(
        self,
        tenant_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get compliance dashboard metrics"""

        # Get consent metrics
        consent_stats = await self.db.execute(
            select(
                ConsentRecord.status,
                func.count(ConsentRecord.id).label('count')
            ).where(
                ConsentRecord.tenant_id == tenant_id if tenant_id else True
            ).group_by(ConsentRecord.status)
        )

        consent_metrics = {status: count for status, count in consent_stats.fetchall()}

        # Get data subject request metrics
        dsr_stats = await self.db.execute(
            select(
                DataSubjectRequest.status,
                func.count(DataSubjectRequest.id).label('count')
            ).where(
                DataSubjectRequest.tenant_id == tenant_id if tenant_id else True
            ).group_by(DataSubjectRequest.status)
        )

        dsr_metrics = {status: count for status, count in dsr_stats.fetchall()}

        # Get breach incidents
        breach_stats = await self.db.execute(
            select(func.count(DataBreachIncident.id)).where(
                DataBreachIncident.tenant_id == tenant_id if tenant_id else True
            )
        )

        breach_count = breach_stats.scalar() or 0

        # Get overdue DSRs
        overdue_dsrs = await self.db.execute(
            select(func.count(DataSubjectRequest.id)).where(
                and_(
                    DataSubjectRequest.response_due_date < datetime.utcnow(),
                    DataSubjectRequest.status.in_([RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS]),
                    DataSubjectRequest.tenant_id == tenant_id if tenant_id else True
                )
            )
        )

        overdue_count = overdue_dsrs.scalar() or 0

        return {
            "consent_metrics": consent_metrics,
            "data_subject_request_metrics": dsr_metrics,
            "breach_incidents_total": breach_count,
            "overdue_requests": overdue_count,
            "compliance_score": self._calculate_compliance_score(
                consent_metrics, dsr_metrics, breach_count, overdue_count
            ),
            "last_updated": datetime.utcnow().isoformat()
        }

    def _calculate_compliance_score(
        self,
        consent_metrics: Dict,
        dsr_metrics: Dict,
        breach_count: int,
        overdue_count: int
    ) -> int:
        """Calculate a compliance score (0-100)"""

        score = 100

        # Deduct points for overdue requests
        score -= min(overdue_count * 10, 50)

        # Deduct points for breaches
        score -= min(breach_count * 5, 30)

        # Deduct points for high withdrawal rate
        total_consents = sum(consent_metrics.values())
        if total_consents > 0:
            withdrawn_rate = consent_metrics.get('withdrawn', 0) / total_consents
            if withdrawn_rate > 0.2:  # More than 20% withdrawn
                score -= 20

        return max(score, 0)

    async def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        period_start: datetime,
        period_end: datetime,
        tenant_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        generated_by: UUID = None
    ) -> ComplianceReport:
        """Generate a compliance report"""

        report_id = f"RPT-{framework.value.upper()}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Collect metrics for the period
        findings = []
        recommendations = []
        metrics = {}

        if framework == ComplianceFramework.GDPR:
            # GDPR-specific reporting
            consent_metrics = await self._get_consent_metrics(period_start, period_end, tenant_id)
            dsr_metrics = await self._get_dsr_metrics(period_start, period_end, tenant_id)

            metrics = {
                "consent_requests": consent_metrics,
                "data_subject_requests": dsr_metrics,
                "breach_notifications": await self._get_breach_metrics(period_start, period_end, tenant_id)
            }

            # Check for compliance issues
            if dsr_metrics.get("overdue_responses", 0) > 0:
                findings.append({
                    "type": "violation",
                    "severity": "high",
                    "description": f"{dsr_metrics['overdue_responses']} data subject requests exceeded 30-day response deadline",
                    "regulation": "GDPR Article 12(3)"
                })
                recommendations.append({
                    "priority": "high",
                    "action": "Implement automated DSR processing and monitoring",
                    "timeline": "30 days"
                })

        # Create report
        report = ComplianceReport(
            report_id=report_id,
            tenant_id=tenant_id,
            organization_id=organization_id,
            title=f"{framework.value.upper()} Compliance Report",
            report_type="periodic_assessment",
            compliance_framework=framework,
            period_start=period_start,
            period_end=period_end,
            findings=findings,
            recommendations=recommendations,
            metrics=metrics,
            compliance_score=self._calculate_compliance_score(
                consent_metrics, dsr_metrics,
                metrics.get("breach_notifications", {}).get("total", 0),
                dsr_metrics.get("overdue_responses", 0)
            ),
            generated_by=generated_by,
            status="draft"
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        return report

    async def _get_consent_metrics(self, start: datetime, end: datetime, tenant_id: Optional[UUID]) -> Dict:
        """Get consent metrics for reporting period"""

        result = await self.db.execute(
            select(
                ConsentRecord.status,
                func.count(ConsentRecord.id).label('count')
            ).where(
                and_(
                    ConsentRecord.created_at >= start,
                    ConsentRecord.created_at <= end,
                    ConsentRecord.tenant_id == tenant_id if tenant_id else True
                )
            ).group_by(ConsentRecord.status)
        )

        return {status: count for status, count in result.fetchall()}

    async def _get_dsr_metrics(self, start: datetime, end: datetime, tenant_id: Optional[UUID]) -> Dict:
        """Get data subject request metrics for reporting period"""

        # Total requests
        total_result = await self.db.execute(
            select(func.count(DataSubjectRequest.id)).where(
                and_(
                    DataSubjectRequest.received_at >= start,
                    DataSubjectRequest.received_at <= end,
                    DataSubjectRequest.tenant_id == tenant_id if tenant_id else True
                )
            )
        )

        # Overdue requests
        overdue_result = await self.db.execute(
            select(func.count(DataSubjectRequest.id)).where(
                and_(
                    DataSubjectRequest.received_at >= start,
                    DataSubjectRequest.received_at <= end,
                    DataSubjectRequest.response_due_date < datetime.utcnow(),
                    DataSubjectRequest.status.in_([RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS]),
                    DataSubjectRequest.tenant_id == tenant_id if tenant_id else True
                )
            )
        )

        return {
            "total_requests": total_result.scalar() or 0,
            "overdue_responses": overdue_result.scalar() or 0
        }

    async def _get_breach_metrics(self, start: datetime, end: datetime, tenant_id: Optional[UUID]) -> Dict:
        """Get breach metrics for reporting period"""

        result = await self.db.execute(
            select(func.count(DataBreachIncident.id)).where(
                and_(
                    DataBreachIncident.discovered_at >= start,
                    DataBreachIncident.discovered_at <= end,
                    DataBreachIncident.tenant_id == tenant_id if tenant_id else True
                )
            )
        )

        return {"total": result.scalar() or 0}