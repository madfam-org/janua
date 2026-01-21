"""
Consent Manager
Handles GDPR consent management with comprehensive audit trails and evidence collection.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy import select, and_, desc

from app.core.database import get_session
from app.models.compliance import (
    ConsentRecord, ConsentType, ConsentStatus,
    LegalBasis, DataCategory, ComplianceFramework
)
from ..audit import AuditLogger, AuditEventType

logger = logging.getLogger(__name__)


class ConsentManager:
    """Manages user consent records with GDPR compliance"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger

    async def grant_consent(
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
        consent_method: str = "api",
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Grant user consent with comprehensive audit trail"""

        async with get_session() as session:
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

        # Log consent event
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.USER_ACCESS,
            resource_type="user_consent",
            resource_id=consent_id,
            action="consent_grant",
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

        logger.info(f"Consent granted", extra={
            "user_id": user_id,
            "consent_type": consent_type.value,
            "consent_id": consent_id
        })

        return consent_id

    async def withdraw_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        withdrawal_reason: str = "User requested withdrawal",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        consent_method: str = "api",
        organization_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> str:
        """Withdraw user consent with audit trail"""

        async with get_session() as session:
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
            consent.withdrawal_reason = withdrawal_reason

            await session.commit()
            consent_id = str(consent.id)

        # Log consent withdrawal
        await self.audit_logger.log_compliance_event(
            event_type=AuditEventType.USER_ACCESS,
            resource_type="user_consent",
            resource_id=consent_id,
            action="consent_withdraw",
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
                "withdrawal_reason": withdrawal_reason,
                "consent_method": consent_method
            }
        )

        logger.info(f"Consent withdrawn", extra={
            "user_id": user_id,
            "consent_type": consent_type.value,
            "consent_id": consent_id
        })

        return consent_id

    async def get_user_consents(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all consents for a user"""

        async with get_session() as session:
            query = select(ConsentRecord).where(ConsentRecord.user_id == uuid.UUID(user_id))

            if active_only:
                query = query.where(ConsentRecord.status == ConsentStatus.GIVEN)

            result = await session.execute(query.order_by(desc(ConsentRecord.given_at)))
            consents = result.scalars().all()

            return [
                {
                    "consent_id": str(consent.id),
                    "consent_type": consent.consent_type.value,
                    "purpose": consent.purpose,
                    "status": consent.status.value,
                    "legal_basis": consent.legal_basis.value,
                    "given_at": consent.given_at.isoformat() if consent.given_at else None,
                    "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                    "withdrawal_reason": consent.withdrawal_reason,
                    "data_categories": [cat.value for cat in consent.data_categories],
                    "third_parties": consent.third_parties,
                    "retention_period": consent.retention_period
                }
                for consent in consents
            ]

    async def check_consent_status(
        self,
        user_id: str,
        consent_type: ConsentType
    ) -> Optional[Dict[str, Any]]:
        """Check if user has active consent for specific type"""

        async with get_session() as session:
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
                return None

            return {
                "consent_id": str(consent.id),
                "consent_type": consent.consent_type.value,
                "purpose": consent.purpose,
                "status": consent.status.value,
                "given_at": consent.given_at.isoformat(),
                "data_categories": [cat.value for cat in consent.data_categories],
                "legal_basis": consent.legal_basis.value
            }

    async def bulk_consent_check(
        self,
        user_id: str,
        consent_types: List[ConsentType]
    ) -> Dict[str, bool]:
        """Check multiple consent types at once"""

        async with get_session() as session:
            result = await session.execute(
                select(ConsentRecord).where(
                    and_(
                        ConsentRecord.user_id == uuid.UUID(user_id),
                        ConsentRecord.consent_type.in_(consent_types),
                        ConsentRecord.status == ConsentStatus.GIVEN
                    )
                )
            )
            active_consents = result.scalars().all()
            active_types = {consent.consent_type for consent in active_consents}

            return {
                consent_type.value: consent_type in active_types
                for consent_type in consent_types
            }