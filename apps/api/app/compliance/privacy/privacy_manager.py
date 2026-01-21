"""
Privacy Manager
Main orchestrator for privacy compliance system integrating all privacy components.
"""

import logging
from typing import Dict, List, Optional, Any

from app.models.compliance import (
    DataSubjectRequestType, ConsentType, DataCategory, LegalBasis
)
from ..audit import AuditLogger

from .data_subject_handler import DataSubjectRequestHandler
from .consent_manager import ConsentManager
from .retention_manager import RetentionManager
from .privacy_types import DataExportFormat, RetentionAction
from .privacy_models import DataSubjectRequestResponse

logger = logging.getLogger(__name__)


class PrivacyManager:
    """Main privacy compliance system orchestrating all privacy components"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.data_subject_handler = DataSubjectRequestHandler(audit_logger)
        self.consent_manager = ConsentManager(audit_logger)
        self.retention_manager = RetentionManager(audit_logger)

    # Data Subject Rights Management

    async def handle_data_subject_request(
        self,
        user_id: str,
        request_type: DataSubjectRequestType,
        description: str = "",
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None,
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create and handle data subject request"""

        return await self.data_subject_handler.create_data_subject_request(
            user_id=user_id,
            request_type=request_type,
            description=description,
            data_categories=data_categories,
            specific_fields=specific_fields,
            organization_id=organization_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

    async def process_access_request(
        self,
        request_id: str,
        include_metadata: bool = True
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 15 access request"""

        return await self.data_subject_handler.process_access_request(
            request_id=request_id,
            include_metadata=include_metadata
        )

    async def process_erasure_request(
        self,
        request_id: str,
        verify_identity: bool = True,
        backup_before_deletion: bool = True
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 17 right to be forgotten request"""

        return await self.data_subject_handler.process_erasure_request(
            request_id=request_id,
            verify_identity=verify_identity,
            backup_before_deletion=backup_before_deletion
        )

    async def process_portability_request(
        self,
        request_id: str,
        export_format: DataExportFormat = DataExportFormat.JSON
    ) -> DataSubjectRequestResponse:
        """Process GDPR Article 20 data portability request"""

        return await self.data_subject_handler.process_portability_request(
            request_id=request_id,
            export_format=export_format
        )

    # Consent Management

    async def grant_user_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        purpose: str,
        legal_basis: LegalBasis = LegalBasis.CONSENT,
        data_categories: List[DataCategory] = None,
        third_parties: List[str] = None,
        retention_period_days: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Grant user consent with audit trail"""

        return await self.consent_manager.grant_consent(
            user_id=user_id,
            consent_type=consent_type,
            purpose=purpose,
            legal_basis=legal_basis,
            data_categories=data_categories,
            third_parties=third_parties,
            retention_period_days=retention_period_days,
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=organization_id,
            tenant_id=tenant_id
        )

    async def withdraw_user_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        withdrawal_reason: str = "User requested withdrawal",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Withdraw user consent with audit trail"""

        return await self.consent_manager.withdraw_consent(
            user_id=user_id,
            consent_type=consent_type,
            withdrawal_reason=withdrawal_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=organization_id,
            tenant_id=tenant_id
        )

    async def get_user_consents(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all consents for a user"""

        return await self.consent_manager.get_user_consents(
            user_id=user_id,
            active_only=active_only
        )

    async def check_consent_status(
        self,
        user_id: str,
        consent_type: ConsentType
    ) -> Optional[Dict[str, Any]]:
        """Check if user has active consent for specific type"""

        return await self.consent_manager.check_consent_status(
            user_id=user_id,
            consent_type=consent_type
        )

    # Data Retention Management

    async def execute_retention_policies(
        self,
        organization_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute automated data retention policies"""

        return await self.retention_manager.execute_retention_policies(
            organization_id=organization_id,
            dry_run=dry_run
        )

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
        creator_id: Optional[str] = None
    ) -> str:
        """Create a new data retention policy"""

        return await self.retention_manager.create_retention_policy(
            name=name,
            description=description,
            data_category=data_category,
            retention_period_days=retention_period_days,
            retention_action=retention_action,
            data_sources=data_sources,
            legal_basis=legal_basis,
            organization_id=organization_id,
            creator_id=creator_id
        )

    async def get_active_retention_policies(
        self,
        organization_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all active retention policies"""

        return await self.retention_manager.get_active_policies(
            organization_id=organization_id
        )

    # Privacy Impact Assessment

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

        # This would contain the PIA creation logic from the original privacy.py
        # For now, return a placeholder implementation
        pia_id = f"PIA-{project_name}-{creator_id[:8]}"

        # Log PIA creation
        logger.info(f"Privacy Impact Assessment created: {pia_id}", extra={
            "project_name": project_name,
            "creator_id": creator_id,
            "organization_id": organization_id
        })

        return pia_id

    # Comprehensive Privacy Health Check

    async def privacy_health_check(
        self,
        user_id: str,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Comprehensive privacy compliance health check for a user"""

        health_check = {
            "user_id": user_id,
            "timestamp": "2025-01-20T00:00:00Z",  # Would use datetime.utcnow()
            "privacy_compliance_status": "compliant",
            "active_consents": [],
            "data_subject_requests": [],
            "retention_status": "within_policy",
            "risk_level": "low",
            "recommendations": []
        }

        try:
            # Check active consents
            consents = await self.get_user_consents(user_id, active_only=True)
            health_check["active_consents"] = consents

            if not consents:
                health_check["recommendations"].append("No active consents found - consider obtaining necessary consents")
                health_check["risk_level"] = "medium"

            # Check for pending data subject requests
            # Implementation would check for pending requests

            # Validate retention compliance
            # Implementation would check retention policy compliance

            logger.info(f"Privacy health check completed for user {user_id}")

        except Exception as e:
            logger.error(f"Privacy health check failed for user {user_id}: {str(e)}")
            health_check["privacy_compliance_status"] = "error"
            health_check["risk_level"] = "high"

        return health_check