"""
Data Privacy and GDPR Automation for enterprise compliance.
Automated data subject request handling, retention management, and privacy compliance.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import uuid
import aiofiles
import redis.asyncio as aioredis
from sqlalchemy import select, and_, desc, delete

from app.core.database import get_session
from app.models.compliance import (
    DataSubjectRequest, ConsentRecord, PrivacySettings, DataRetentionPolicy,
    DataSubjectRequestType, RequestStatus, ConsentType, ConsentStatus,
    DataCategory, LegalBasis, ComplianceFramework
)
from app.models.users import User
from app.core.config import get_settings
from .audit import AuditLogger, AuditEventType, EvidenceType

logger = logging.getLogger(__name__)
settings = get_settings()


class PrivacyRightType(str, Enum):
    """GDPR privacy rights under Articles 15-22"""
    ACCESS = "access"                    # Article 15 - Right of access
    RECTIFICATION = "rectification"      # Article 16 - Right to rectification
    ERASURE = "erasure"                  # Article 17 - Right to be forgotten
    PORTABILITY = "portability"          # Article 20 - Right to data portability
    RESTRICTION = "restriction"          # Article 18 - Right to restriction
    OBJECTION = "objection"             # Article 21 - Right to object
    AUTOMATED_DECISION = "automated_decision"  # Article 22 - Automated decision-making


class DataExportFormat(str, Enum):
    """Supported formats for data export"""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    PDF = "pdf"


class RetentionAction(str, Enum):
    """Actions to take when retention period expires"""
    DELETE = "delete"
    ANONYMIZE = "anonymize"
    ARCHIVE = "archive"
    REVIEW = "review"


@dataclass
class DataSubjectRequestResponse:
    """Response to a data subject request"""
    request_id: str
    response_type: str
    data: Optional[Dict[str, Any]]
    export_url: Optional[str]
    completion_time: datetime
    notes: Optional[str]


@dataclass
class PrivacyImpactAssessment:
    """Privacy Impact Assessment (PIA) for GDPR compliance"""
    pia_id: str
    title: str
    description: str
    project_name: str
    data_processing_purpose: str

    # Data categories and processing
    data_categories: List[DataCategory]
    processing_activities: List[str]
    legal_basis: List[LegalBasis]
    data_subjects: List[str]

    # Risk assessment
    privacy_risks: List[Dict[str, Any]]
    risk_level: str  # low, medium, high, very_high
    mitigation_measures: List[str]

    # Consultation and approval
    stakeholder_consultation: bool
    dpo_consultation: bool
    approved_by: Optional[str]
    approval_date: Optional[datetime]

    # Review and monitoring
    review_date: datetime
    monitoring_measures: List[str]

    created_at: datetime
    updated_at: datetime


class PrivacyManager:
    """Comprehensive privacy management for GDPR compliance"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self.audit_logger = AuditLogger(redis_client)

    async def create_data_subject_request(
        self,
        user_id: str,
        request_type: DataSubjectRequestType,
        description: str = "",
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create a new data subject request with automated processing"""

        request_id = f"DSR-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Calculate response deadline (30 days for GDPR)
        response_due_date = datetime.utcnow() + timedelta(days=30)

        async with get_session() as session:
            # Create request record
            request = DataSubjectRequest(
                request_id=request_id,
                user_id=uuid.UUID(user_id),
                request_type=request_type,
                description=description,
                data_categories=data_categories or [],
                specific_fields=specific_fields or [],
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                response_due_date=response_due_date,
                organization_id=uuid.UUID(organization_id) if organization_id else None,
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                request_source="api"
            )

            session.add(request)
            await session.commit()
            await session.refresh(request)

        # Log compliance event
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.DATA_ACCESS,
            resource_type="data_subject_request",
            resource_id=request_id,
            action="create",
            outcome="success",
            user_id=user_id,
            organization_id=organization_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            control_id="GDPR-15-22",
            compliance_frameworks=[ComplianceFramework.GDPR],
            raw_data={
                "request_type": request_type.value,
                "data_categories": data_categories,
                "specific_fields": specific_fields
            }
        )

        # Schedule automated processing
        await self._schedule_request_processing(request_id, request_type)

        logger.info(f"Data subject request created: {request_id}", extra={
            "user_id": user_id,
            "request_type": request_type.value,
            "response_due_date": response_due_date.isoformat()
        })

        return request_id

    async def process_access_request(
        self,
        request_id: str,
        include_metadata: bool = True
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 15 access request"""

        async with get_session() as session:
            # Get request details
            result = await session.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
            )
            request = result.scalar_one_or_none()

            if not request:
                raise ValueError(f"Request not found: {request_id}")

            # Collect all user data
            user_data = await self._collect_user_data(
                str(request.user_id),
                request.data_categories,
                request.specific_fields,
                request.date_range_start,
                request.date_range_end,
                include_metadata
            )

            # Generate export file
            export_url = await self._generate_data_export(
                request_id,
                user_data,
                DataExportFormat.JSON
            )

            # Update request status
            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            request.response_data_url = export_url
            request.response_method = "secure_download"

            await session.commit()

        # Log completion
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.DATA_ACCESS,
            resource_type="data_subject_request",
            resource_id=request_id,
            action="complete",
            outcome="success",
            user_id=str(request.user_id),
            control_id="GDPR-15",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        # Collect evidence
        await self.audit_logger.collect_evidence(
            evidence_type=EvidenceType.USER_ACTIVITY,
            title=f"GDPR Access Request Completion - {request_id}",
            description=f"Completed data access request for user {request.user_id}",
            content=user_data,
            source_system="privacy_manager",
            collector_id="system",
            control_objectives=["GDPR-15"],
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="access",
            data=user_data,
            export_url=export_url,
            completion_time=datetime.utcnow(),
            notes="Data access request completed successfully"
        )

    async def process_erasure_request(
        self,
        request_id: str,
        verify_identity: bool = True,
        backup_before_deletion: bool = True
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 17 right to be forgotten request"""

        async with get_session() as session:
            # Get request details
            result = await session.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
            )
            request = result.scalar_one_or_none()

            if not request:
                raise ValueError(f"Request not found: {request_id}")

            if verify_identity and not request.identity_verified:
                raise ValueError("Identity verification required for erasure request")

            user_id = str(request.user_id)

            # Create backup if requested
            backup_ref = None
            if backup_before_deletion:
                user_data = await self._collect_user_data(user_id)
                backup_ref = await self._create_erasure_backup(request_id, user_data)

            # Perform erasure according to data categories
            erasure_summary = await self._perform_data_erasure(
                user_id,
                request.data_categories,
                request.specific_fields
            )

            # Update request status
            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            request.response_notes = f"Data erasure completed. Backup reference: {backup_ref}"

            await session.commit()

        # Log erasure completion
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.DATA_ACCESS,
            resource_type="data_subject_request",
            resource_id=request_id,
            action="erasure_complete",
            outcome="success",
            user_id=user_id,
            control_id="GDPR-17",
            compliance_frameworks=[ComplianceFramework.GDPR],
            raw_data=erasure_summary
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="erasure",
            data=erasure_summary,
            export_url=None,
            completion_time=datetime.utcnow(),
            notes=f"Data erasure completed. Items processed: {erasure_summary.get('total_items', 0)}"
        )

    async def process_portability_request(
        self,
        request_id: str,
        export_format: DataExportFormat = DataExportFormat.JSON
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 20 data portability request"""

        async with get_session() as session:
            # Get request details
            result = await session.execute(
                select(DataSubjectRequest).where(DataSubjectRequest.request_id == request_id)
            )
            request = result.scalar_one_or_none()

            if not request:
                raise ValueError(f"Request not found: {request_id}")

            # Collect portable data (only data provided by user with consent)
            portable_data = await self._collect_portable_data(
                str(request.user_id),
                request.data_categories
            )

            # Generate structured export
            export_url = await self._generate_data_export(
                request_id,
                portable_data,
                export_format,
                structured_format=True
            )

            # Update request status
            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            request.response_data_url = export_url
            request.response_method = "structured_download"

            await session.commit()

        # Log completion
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.DATA_ACCESS,
            resource_type="data_subject_request",
            resource_id=request_id,
            action="portability_complete",
            outcome="success",
            user_id=str(request.user_id),
            control_id="GDPR-20",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="portability",
            data=portable_data,
            export_url=export_url,
            completion_time=datetime.utcnow(),
            notes=f"Data portability export generated in {export_format.value} format"
        )

    async def manage_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        action: str,  # "grant", "withdraw", "update"
        purpose: str,
        legal_basis: LegalBasis = LegalBasis.CONSENT,
        data_categories: List[DataCategory] = None,
        third_parties: List[str] = None,
        retention_period_days: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        consent_method: str = "api",
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Manage user consent with comprehensive audit trail"""

        async with get_session() as session:
            if action == "grant":
                # Create new consent record
                consent = ConsentRecord(
                    user_id=uuid.UUID(user_id),
                    consent_type=consent_type,
                    purpose=purpose,
                    legal_basis=legal_basis,
                    status=ConsentStatus.GIVEN,
                    given_at=datetime.utcnow(),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    consent_method=consent_method,
                    data_categories=data_categories or [],
                    third_parties=third_parties or [],
                    retention_period=retention_period_days,
                    organization_id=uuid.UUID(organization_id) if organization_id else None,
                    tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    consent_evidence={
                        "timestamp": datetime.utcnow().isoformat(),
                        "method": consent_method,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "purpose": purpose
                    }
                )

                session.add(consent)
                await session.commit()
                await session.refresh(consent)

                consent_id = str(consent.id)

            elif action == "withdraw":
                # Find and update existing consent
                result = await session.execute(
                    select(ConsentRecord).where(
                        and_(
                            ConsentRecord.user_id == uuid.UUID(user_id),
                            ConsentRecord.consent_type == consent_type,
                            ConsentRecord.status == ConsentStatus.GIVEN
                        )
                    ).order_by(desc(ConsentRecord.given_at))
                )
                consent = result.scalar_one_or_none()

                if not consent:
                    raise ValueError(f"No active consent found for {consent_type.value}")

                consent.status = ConsentStatus.WITHDRAWN
                consent.withdrawn_at = datetime.utcnow()
                consent.withdrawal_reason = f"User requested withdrawal via {consent_method}"

                await session.commit()
                consent_id = str(consent.id)

            else:
                raise ValueError(f"Unsupported consent action: {action}")

        # Log consent event
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.USER_ACCESS,
            resource_type="user_consent",
            resource_id=consent_id,
            action=f"consent_{action}",
            outcome="success",
            user_id=user_id,
            organization_id=organization_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            control_id="GDPR-7",
            compliance_frameworks=[ComplianceFramework.GDPR],
            raw_data={
                "consent_type": consent_type.value,
                "purpose": purpose,
                "legal_basis": legal_basis.value,
                "consent_method": consent_method
            }
        )

        logger.info(f"Consent {action} processed", extra={
            "user_id": user_id,
            "consent_type": consent_type.value,
            "consent_id": consent_id,
            "action": action
        })

        return consent_id

    async def automated_data_retention(
        self,
        organization_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Automated data retention and deletion based on policies"""

        current_time = datetime.utcnow()
        retention_summary = {
            "processed_policies": 0,
            "affected_records": 0,
            "deleted_records": 0,
            "anonymized_records": 0,
            "archived_records": 0,
            "errors": 0,
            "processing_details": []
        }

        async with get_session() as session:
            # Get active retention policies
            policy_query = select(DataRetentionPolicy).where(
                DataRetentionPolicy.is_active == True
            )

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
                            policy, cutoff_date, dry_run
                        )
                    elif policy.data_category == DataCategory.BEHAVIORAL:
                        records_processed = await self._process_behavioral_retention(
                            policy, cutoff_date, dry_run
                        )
                    elif policy.data_category == DataCategory.TECHNICAL:
                        records_processed = await self._process_technical_retention(
                            policy, cutoff_date, dry_run
                        )
                    else:
                        records_processed = await self._process_generic_retention(
                            policy, cutoff_date, dry_run
                        )

                    retention_summary["affected_records"] += records_processed["affected"]
                    retention_summary["deleted_records"] += records_processed["deleted"]
                    retention_summary["anonymized_records"] += records_processed["anonymized"]
                    retention_summary["archived_records"] += records_processed["archived"]

                    retention_summary["processing_details"].append({
                        "policy_id": str(policy.id),
                        "policy_name": policy.name,
                        "data_category": policy.data_category.value,
                        "retention_days": policy.retention_period_days,
                        "cutoff_date": cutoff_date.isoformat(),
                        "records_processed": records_processed
                    })

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
            raw_data=retention_summary
        )

        logger.info("Automated data retention completed", extra=retention_summary)
        return retention_summary

    async def create_privacy_impact_assessment(
        self,
        title: str,
        description: str,
        project_name: str,
        data_processing_purpose: str,
        data_categories: List[DataCategory],
        processing_activities: List[str],
        legal_basis: List[LegalBasis],
        data_subjects: List[str],
        privacy_risks: List[Dict[str, Any]],
        mitigation_measures: List[str],
        creator_id: str,
        organization_id: Optional[str] = None
    ) -> str:
        """Create a Privacy Impact Assessment (PIA) for GDPR compliance"""

        pia_id = str(uuid.uuid4())

        # Calculate risk level based on privacy risks
        risk_scores = [risk.get("score", 0) for risk in privacy_risks]
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        if avg_risk_score >= 8:
            risk_level = "very_high"
        elif avg_risk_score >= 6:
            risk_level = "high"
        elif avg_risk_score >= 4:
            risk_level = "medium"
        else:
            risk_level = "low"

        pia = PrivacyImpactAssessment(
            pia_id=pia_id,
            title=title,
            description=description,
            project_name=project_name,
            data_processing_purpose=data_processing_purpose,
            data_categories=data_categories,
            processing_activities=processing_activities,
            legal_basis=legal_basis,
            data_subjects=data_subjects,
            privacy_risks=privacy_risks,
            risk_level=risk_level,
            mitigation_measures=mitigation_measures,
            stakeholder_consultation=False,
            dpo_consultation=risk_level in ["high", "very_high"],
            approved_by=None,
            approval_date=None,
            review_date=datetime.utcnow() + timedelta(days=365),  # Annual review
            monitoring_measures=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Store PIA as evidence
        await self.audit_logger.collect_evidence(
            evidence_type=EvidenceType.RISK_ASSESSMENT,
            title=f"Privacy Impact Assessment - {title}",
            description=f"PIA for project: {project_name}",
            content=asdict(pia),
            source_system="privacy_manager",
            collector_id=creator_id,
            control_objectives=["GDPR-35"],
            compliance_frameworks=[ComplianceFramework.GDPR],
            metadata={
                "project_name": project_name,
                "risk_level": risk_level,
                "data_categories": [cat.value for cat in data_categories]
            }
        )

        logger.info(f"Privacy Impact Assessment created: {pia_id}", extra={
            "project_name": project_name,
            "risk_level": risk_level,
            "creator_id": creator_id
        })

        return pia_id

    # Helper methods

    async def _collect_user_data(
        self,
        user_id: str,
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Collect all user data for access requests"""

        user_data = {
            "user_id": user_id,
            "collection_timestamp": datetime.utcnow().isoformat(),
            "data_categories": data_categories or [],
            "data": {}
        }

        async with get_session() as session:
            # Basic user profile data
            if not data_categories or DataCategory.IDENTITY in data_categories:
                user_result = await session.execute(
                    select(User).where(User.id == uuid.UUID(user_id))
                )
                user = user_result.scalar_one_or_none()

                if user:
                    user_data["data"]["profile"] = {
                        "email": user.email,
                        "name": user.name,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                        "last_login": user.last_login_at.isoformat() if user.last_login_at else None,
                        "is_active": user.is_active
                    }

            # Consent records
            if not data_categories or DataCategory.BEHAVIORAL in data_categories:
                consent_result = await session.execute(
                    select(ConsentRecord).where(ConsentRecord.user_id == uuid.UUID(user_id))
                )
                consents = consent_result.scalars().all()

                user_data["data"]["consents"] = [
                    {
                        "consent_type": consent.consent_type.value,
                        "purpose": consent.purpose,
                        "status": consent.status.value,
                        "given_at": consent.given_at.isoformat() if consent.given_at else None,
                        "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None
                    }
                    for consent in consents
                ]

            # Privacy settings
            privacy_result = await session.execute(
                select(PrivacySettings).where(PrivacySettings.user_id == uuid.UUID(user_id))
            )
            privacy_settings = privacy_result.scalar_one_or_none()

            if privacy_settings:
                user_data["data"]["privacy_settings"] = {
                    "email_marketing": privacy_settings.email_marketing,
                    "analytics_tracking": privacy_settings.analytics_tracking,
                    "personalization": privacy_settings.personalization,
                    "third_party_sharing": privacy_settings.third_party_sharing
                }

        return user_data

    async def _collect_portable_data(
        self,
        user_id: str,
        data_categories: List[DataCategory] = None
    ) -> Dict[str, Any]:
        """Collect data provided by user with consent (Article 20)"""

        portable_data = {
            "user_id": user_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "format_version": "1.0",
            "data": {}
        }

        # Only include data that user provided and based on consent
        async with get_session() as session:
            # User-provided profile data
            user_result = await session.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            user = user_result.scalar_one_or_none()

            if user:
                portable_data["data"]["profile"] = {
                    "email": user.email,
                    "name": user.name,
                    "preferences": {}  # Only user-set preferences
                }

            # User-controlled privacy settings
            privacy_result = await session.execute(
                select(PrivacySettings).where(PrivacySettings.user_id == uuid.UUID(user_id))
            )
            privacy_settings = privacy_result.scalar_one_or_none()

            if privacy_settings:
                portable_data["data"]["preferences"] = {
                    "communication": {
                        "email_marketing": privacy_settings.email_marketing,
                        "email_product_updates": privacy_settings.email_product_updates
                    },
                    "privacy": {
                        "analytics_tracking": privacy_settings.analytics_tracking,
                        "personalization": privacy_settings.personalization
                    }
                }

        return portable_data

    async def _perform_data_erasure(
        self,
        user_id: str,
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None
    ) -> Dict[str, Any]:
        """Perform data erasure while respecting legal requirements"""

        erasure_summary = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "items_processed": 0,
            "items_deleted": 0,
            "items_anonymized": 0,
            "items_retained": 0,
            "retention_reasons": [],
            "details": []
        }

        async with get_session() as session:
            # User profile data
            if not data_categories or DataCategory.IDENTITY in data_categories:
                # Anonymize rather than delete for audit trail
                user_result = await session.execute(
                    select(User).where(User.id == uuid.UUID(user_id))
                )
                user = user_result.scalar_one_or_none()

                if user:
                    user.email = f"anonymized_{user_id}@deleted.local"
                    user.name = "DELETED_USER"
                    user.is_active = False
                    erasure_summary["items_anonymized"] += 1
                    erasure_summary["details"].append("User profile anonymized")

            # Delete consent records
            if not data_categories or DataCategory.BEHAVIORAL in data_categories:
                consent_result = await session.execute(
                    delete(ConsentRecord).where(ConsentRecord.user_id == uuid.UUID(user_id))
                )
                deleted_consents = consent_result.rowcount
                erasure_summary["items_deleted"] += deleted_consents
                erasure_summary["details"].append(f"Deleted {deleted_consents} consent records")

            # Privacy settings
            privacy_result = await session.execute(
                delete(PrivacySettings).where(PrivacySettings.user_id == uuid.UUID(user_id))
            )
            deleted_privacy = privacy_result.rowcount
            erasure_summary["items_deleted"] += deleted_privacy
            erasure_summary["details"].append(f"Deleted {deleted_privacy} privacy settings")

            await session.commit()

        erasure_summary["items_processed"] = (
            erasure_summary["items_deleted"] +
            erasure_summary["items_anonymized"] +
            erasure_summary["items_retained"]
        )

        return erasure_summary

    async def _generate_data_export(
        self,
        request_id: str,
        data: Dict[str, Any],
        format_type: DataExportFormat,
        structured_format: bool = False
    ) -> str:
        """Generate secure data export file"""

        export_filename = f"{request_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        export_path = Path(settings.DATA_EXPORT_PATH) / export_filename
        export_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type == DataExportFormat.JSON:
            content = json.dumps(data, indent=2, default=str)
        elif format_type == DataExportFormat.CSV:
            # Convert to CSV format (simplified)
            content = self._convert_to_csv(data)
        else:
            content = json.dumps(data, default=str)

        async with aiofiles.open(export_path, 'w') as f:
            await f.write(content)

        # Generate secure download URL (implementation depends on file serving setup)
        export_url = f"{settings.BASE_URL}/api/v1/privacy/download/{export_filename}"

        return export_url

    async def _schedule_request_processing(
        self,
        request_id: str,
        request_type: DataSubjectRequestType
    ):
        """Schedule automated processing of data subject requests"""

        # Add to processing queue (Redis-based queue)
        if self.redis:
            queue_item = {
                "request_id": request_id,
                "request_type": request_type.value,
                "scheduled_at": datetime.utcnow().isoformat(),
                "priority": "high" if request_type == DataSubjectRequestType.ERASURE else "normal"
            }

            await self.redis.lpush(
                "privacy:request_queue",
                json.dumps(queue_item)
            )

    def _convert_to_csv(self, data: Dict[str, Any]) -> str:
        """Simple CSV conversion for data export"""
        # Simplified CSV generation - in production, use proper CSV library
        lines = ["Category,Field,Value"]

        for category, fields in data.get("data", {}).items():
            if isinstance(fields, dict):
                for field, value in fields.items():
                    lines.append(f"{category},{field},{value}")
            else:
                lines.append(f"{category},value,{fields}")

        return "\n".join(lines)


class GDPRCompliance:
    """GDPR compliance orchestrator"""

    def __init__(self, privacy_manager: PrivacyManager):
        self.privacy_manager = privacy_manager

    async def assess_compliance_status(
        self,
        organization_id: str
    ) -> Dict[str, Any]:
        """Assess overall GDPR compliance status"""

        assessment = {
            "organization_id": organization_id,
            "assessment_date": datetime.utcnow().isoformat(),
            "compliance_score": 0,
            "areas": {
                "lawfulness": {"score": 0, "details": []},
                "data_minimization": {"score": 0, "details": []},
                "accuracy": {"score": 0, "details": []},
                "storage_limitation": {"score": 0, "details": []},
                "integrity_confidentiality": {"score": 0, "details": []},
                "accountability": {"score": 0, "details": []}
            },
            "recommendations": [],
            "priority_actions": []
        }

        async with get_session() as session:
            # Check data subject request response times
            recent_requests = await session.execute(
                select(DataSubjectRequest).where(
                    and_(
                        DataSubjectRequest.created_at >= datetime.utcnow() - timedelta(days=90),
                        DataSubjectRequest.organization_id == uuid.UUID(organization_id)
                    )
                )
            )
            requests = recent_requests.scalars().all()

            on_time_responses = sum(1 for req in requests if req.completed_at and req.completed_at <= req.response_due_date)
            total_requests = len(requests)

            if total_requests > 0:
                response_rate = on_time_responses / total_requests
                assessment["areas"]["accountability"]["score"] = int(response_rate * 100)
                assessment["areas"]["accountability"]["details"].append(
                    f"Data subject request response rate: {response_rate:.1%}"
                )

            # Check consent management
            active_consents = await session.execute(
                select(ConsentRecord).where(
                    and_(
                        ConsentRecord.status == ConsentStatus.GIVEN,
                        ConsentRecord.organization_id == uuid.UUID(organization_id)
                    )
                )
            )
            consent_count = len(active_consents.scalars().all())

            if consent_count > 0:
                assessment["areas"]["lawfulness"]["score"] = 85
                assessment["areas"]["lawfulness"]["details"].append(
                    f"Active consent records: {consent_count}"
                )

            # Calculate overall score
            area_scores = [area["score"] for area in assessment["areas"].values()]
            assessment["compliance_score"] = sum(area_scores) / len(area_scores)

        return assessment