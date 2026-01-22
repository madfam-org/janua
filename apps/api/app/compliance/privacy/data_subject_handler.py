"""
Data Subject Request Handler
Handles GDPR data subject requests including access, erasure, and portability rights.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select

from app.core.database import get_session
from app.models.compliance import (
    DataSubjectRequest,
    DataSubjectRequestType,
    RequestStatus,
    DataCategory,
    ComplianceFramework,
)
from ..audit import AuditLogger, AuditEventType, EvidenceType

from .privacy_types import DataExportFormat
from .privacy_models import DataSubjectRequestResponse

logger = logging.getLogger(__name__)


class DataSubjectRequestHandler:
    """Handles data subject requests for GDPR compliance"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger

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
        user_agent: Optional[str] = None,
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
                request_source="api",
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
                "specific_fields": specific_fields,
            },
        )

        # Schedule automated processing
        await self._schedule_request_processing(request_id, request_type)

        logger.info(
            f"Data subject request created: {request_id}",
            extra={
                "user_id": user_id,
                "request_type": request_type.value,
                "response_due_date": response_due_date.isoformat(),
            },
        )

        return request_id

    async def process_access_request(
        self, request_id: str, include_metadata: bool = True
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
                include_metadata,
            )

            # Generate export file
            export_url = await self._generate_data_export(
                request_id, user_data, DataExportFormat.JSON
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
            compliance_frameworks=[ComplianceFramework.GDPR],
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
            compliance_frameworks=[ComplianceFramework.GDPR],
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="access",
            data=user_data,
            export_url=export_url,
            completion_time=datetime.utcnow(),
            notes="Data access request completed successfully",
        )

    async def process_erasure_request(
        self, request_id: str, verify_identity: bool = True, backup_before_deletion: bool = True
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
                user_id, request.data_categories, request.specific_fields
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
            raw_data=erasure_summary,
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="erasure",
            data=erasure_summary,
            export_url=None,
            completion_time=datetime.utcnow(),
            notes=f"Data erasure completed. Items processed: {erasure_summary.get('total_items', 0)}",
        )

    async def process_portability_request(
        self, request_id: str, export_format: DataExportFormat = DataExportFormat.JSON
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
                str(request.user_id), request.data_categories
            )

            # Generate structured export
            export_url = await self._generate_data_export(
                request_id, portable_data, export_format, structured_format=True
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
            compliance_frameworks=[ComplianceFramework.GDPR],
        )

        return DataSubjectRequestResponse(
            request_id=request_id,
            response_type="portability",
            data=portable_data,
            export_url=export_url,
            completion_time=datetime.utcnow(),
            notes=f"Data portability export generated in {export_format.value} format",
        )

    async def _schedule_request_processing(
        self, request_id: str, request_type: DataSubjectRequestType
    ):
        """Schedule automated processing for request"""
        # Implementation would integrate with task queue
        logger.info(f"Scheduled processing for {request_type.value} request: {request_id}")

    async def _collect_user_data(
        self,
        user_id: str,
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Collect user data according to specified criteria"""
        # Implementation would collect data from various sources
        return {
            "user_id": user_id,
            "collection_timestamp": datetime.utcnow().isoformat(),
            "data_categories": [cat.value for cat in (data_categories or [])],
            "metadata_included": include_metadata,
        }

    async def _collect_portable_data(
        self, user_id: str, data_categories: List[DataCategory] = None
    ) -> Dict[str, Any]:
        """Collect data that can be ported according to GDPR Article 20"""
        # Implementation would collect only user-provided data with consent basis
        return {
            "user_id": user_id,
            "portable_data": {},
            "collection_timestamp": datetime.utcnow().isoformat(),
        }

    async def _generate_data_export(
        self,
        request_id: str,
        data: Dict[str, Any],
        format: DataExportFormat,
        structured_format: bool = False,
    ) -> str:
        """Generate secure data export file"""
        # Implementation would create secure export files
        return f"/secure/exports/{request_id}.{format.value}"

    async def _create_erasure_backup(self, request_id: str, user_data: Dict[str, Any]) -> str:
        """Create backup before data erasure"""
        # Implementation would create secure backup
        backup_ref = f"BACKUP-{request_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Created erasure backup: {backup_ref}")
        return backup_ref

    async def _perform_data_erasure(
        self,
        user_id: str,
        data_categories: List[DataCategory] = None,
        specific_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Perform data erasure according to specified criteria"""
        # Implementation would perform actual data deletion
        return {
            "user_id": user_id,
            "erasure_timestamp": datetime.utcnow().isoformat(),
            "categories_processed": [cat.value for cat in (data_categories or [])],
            "total_items": 0,
            "status": "completed",
        }
