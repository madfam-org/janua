"""
Comprehensive compliance API endpoints for GDPR, SOC 2, HIPAA, and other frameworks
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.compliance import (
    ConsentType,
    LegalBasis,
    DataCategory,
    DataSubjectRequestType,
    ComplianceFramework,
)
from app.services.compliance_service import ComplianceService
from app.services.audit_logger import AuditLogger
from app.core.logging import logger

router = APIRouter(prefix="/compliance", tags=["compliance"])


# Pydantic models for request/response
class ConsentRequest(BaseModel):
    consent_type: ConsentType
    purpose: str
    legal_basis: LegalBasis = LegalBasis.CONSENT
    data_categories: Optional[List[DataCategory]] = None
    processing_purposes: Optional[List[str]] = None
    third_parties: Optional[List[str]] = None
    retention_period: Optional[int] = None
    consent_method: str = "api"
    consent_version: str = "1.0"


class ConsentWithdrawalRequest(BaseModel):
    consent_type: ConsentType
    purpose: str
    withdrawal_reason: Optional[str] = None


class DataSubjectRightsRequest(BaseModel):
    request_type: DataSubjectRequestType
    description: Optional[str] = None
    data_categories: Optional[List[DataCategory]] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    specific_fields: Optional[List[str]] = None


class RetentionPolicyRequest(BaseModel):
    name: str
    data_category: DataCategory
    retention_period_days: int
    compliance_framework: ComplianceFramework
    description: Optional[str] = None
    deletion_method: str = "soft_delete"
    auto_deletion_enabled: bool = True


class PrivacySettingsUpdate(BaseModel):
    email_marketing: Optional[bool] = None
    email_product_updates: Optional[bool] = None
    email_security_alerts: Optional[bool] = None
    analytics_tracking: Optional[bool] = None
    personalization: Optional[bool] = None
    third_party_sharing: Optional[bool] = None
    profile_visibility: Optional[str] = None
    analytics_cookies: Optional[bool] = None
    marketing_cookies: Optional[bool] = None


class ComplianceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


async def get_compliance_service(db: AsyncSession = Depends(get_db)) -> ComplianceService:
    """Get compliance service instance"""
    audit_logger = AuditLogger(db)
    return ComplianceService(db, audit_logger)


@router.post("/consent", response_model=ComplianceResponse)
async def record_consent(
    request: ConsentRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Record user consent (GDPR Article 7)"""

    try:
        consent_record = await compliance_service.consent_service.record_consent(
            user_id=user.id,
            consent_type=request.consent_type,
            purpose=request.purpose,
            legal_basis=request.legal_basis,
            data_categories=request.data_categories,
            processing_purposes=request.processing_purposes,
            third_parties=request.third_parties,
            retention_period=request.retention_period,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
            consent_method=request.consent_method,
            consent_version=request.consent_version,
            tenant_id=user.tenant_id,
        )

        return ComplianceResponse(
            success=True,
            message="Consent recorded successfully",
            data={
                "consent_id": str(consent_record.id),
                "consent_type": consent_record.consent_type.value,
                "status": consent_record.status.value,
                "given_at": consent_record.given_at.isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Failed to record consent: {e}")
        raise HTTPException(status_code=500, detail="Failed to record consent")


@router.post("/consent/withdraw", response_model=ComplianceResponse)
async def withdraw_consent(
    request: ConsentWithdrawalRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Withdraw user consent (GDPR Article 7.3)"""

    try:
        success = await compliance_service.consent_service.withdraw_consent(
            user_id=user.id,
            consent_type=request.consent_type,
            purpose=request.purpose,
            withdrawal_reason=request.withdrawal_reason,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
            tenant_id=user.tenant_id,
        )

        if success:
            return ComplianceResponse(success=True, message="Consent withdrawn successfully")
        else:
            raise HTTPException(status_code=404, detail="Consent not found")

    except Exception as e:
        logger.error(f"Failed to withdraw consent: {e}")
        raise HTTPException(status_code=500, detail="Failed to withdraw consent")


@router.get("/consent", response_model=ComplianceResponse)
async def get_user_consents(
    include_withdrawn: bool = Query(False, description="Include withdrawn consents"),
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Get user's consent records"""

    try:
        consents = await compliance_service.consent_service.get_user_consents(
            user_id=user.id, include_withdrawn=include_withdrawn
        )

        consent_data = [
            {
                "id": str(consent.id),
                "consent_type": consent.consent_type.value,
                "purpose": consent.purpose,
                "status": consent.status.value,
                "legal_basis": consent.legal_basis.value,
                "given_at": consent.given_at.isoformat() if consent.given_at else None,
                "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                "data_categories": consent.data_categories,
                "processing_purposes": consent.processing_purposes,
                "consent_version": consent.consent_version,
            }
            for consent in consents
        ]

        return ComplianceResponse(
            success=True, message="Consents retrieved successfully", data={"consents": consent_data}
        )

    except Exception as e:
        logger.error(f"Failed to get consents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve consents")


@router.post("/data-subject-request", response_model=ComplianceResponse)
async def create_data_subject_request(
    request: DataSubjectRightsRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Create a data subject rights request (GDPR Articles 15-22)"""

    try:
        dsr = await compliance_service.data_subject_rights_service.create_request(
            user_id=user.id,
            request_type=request.request_type,
            description=request.description,
            data_categories=request.data_categories,
            date_range_start=request.date_range_start,
            date_range_end=request.date_range_end,
            specific_fields=request.specific_fields,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
            tenant_id=user.tenant_id,
        )

        return ComplianceResponse(
            success=True,
            message="Data subject request created successfully",
            data={
                "request_id": dsr.request_id,
                "request_type": dsr.request_type.value,
                "status": dsr.status.value,
                "response_due_date": dsr.response_due_date.isoformat(),
                "received_at": dsr.received_at.isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Failed to create data subject request: {e}")
        raise HTTPException(status_code=500, detail="Failed to create data subject request")


@router.get("/data-subject-request/{request_id}/data", response_model=ComplianceResponse)
async def get_personal_data_export(
    request_id: str,
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Get personal data export (GDPR Article 15)"""

    try:
        user_data = await compliance_service.data_subject_rights_service.process_access_request(
            request_id=request_id, processor_id=user.id  # Self-service for now
        )

        return ComplianceResponse(
            success=True, message="Personal data exported successfully", data=user_data
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export personal data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export personal data")


@router.get("/privacy-settings", response_model=ComplianceResponse)
async def get_privacy_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get user's privacy settings"""

    try:
        from sqlalchemy import select
        from app.models.compliance import PrivacySettings

        result = await db.execute(select(PrivacySettings).where(PrivacySettings.user_id == user.id))
        privacy_settings = result.scalar_one_or_none()

        if not privacy_settings:
            # Create default privacy settings
            privacy_settings = PrivacySettings(user_id=user.id, tenant_id=user.tenant_id)
            db.add(privacy_settings)
            await db.commit()
            await db.refresh(privacy_settings)

        settings_data = {
            "email_marketing": privacy_settings.email_marketing,
            "email_product_updates": privacy_settings.email_product_updates,
            "email_security_alerts": privacy_settings.email_security_alerts,
            "analytics_tracking": privacy_settings.analytics_tracking,
            "personalization": privacy_settings.personalization,
            "third_party_sharing": privacy_settings.third_party_sharing,
            "profile_visibility": privacy_settings.profile_visibility,
            "essential_cookies": privacy_settings.essential_cookies,
            "functional_cookies": privacy_settings.functional_cookies,
            "analytics_cookies": privacy_settings.analytics_cookies,
            "marketing_cookies": privacy_settings.marketing_cookies,
            "updated_at": privacy_settings.updated_at.isoformat()
            if privacy_settings.updated_at
            else None,
        }

        return ComplianceResponse(
            success=True,
            message="Privacy settings retrieved successfully",
            data={"privacy_settings": settings_data},
        )

    except Exception as e:
        logger.error(f"Failed to get privacy settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve privacy settings")


@router.put("/privacy-settings", response_model=ComplianceResponse)
async def update_privacy_settings(
    settings: PrivacySettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's privacy settings"""

    try:
        from sqlalchemy import select
        from app.models.compliance import PrivacySettings

        result = await db.execute(select(PrivacySettings).where(PrivacySettings.user_id == user.id))
        privacy_settings = result.scalar_one_or_none()

        if not privacy_settings:
            privacy_settings = PrivacySettings(user_id=user.id, tenant_id=user.tenant_id)
            db.add(privacy_settings)

        # Update only provided fields
        update_fields = settings.dict(exclude_unset=True)
        for field, value in update_fields.items():
            if hasattr(privacy_settings, field):
                setattr(privacy_settings, field, value)

        privacy_settings.last_updated_by = user.id
        privacy_settings.updated_at = datetime.utcnow()

        await db.commit()

        # Log privacy settings update
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type="privacy.settings_updated",
            tenant_id=str(user.tenant_id) if user.tenant_id else "default",
            identity_id=str(user.id),
            details={"updated_fields": list(update_fields.keys())},
            severity="info",
        )

        return ComplianceResponse(success=True, message="Privacy settings updated successfully")

    except Exception as e:
        logger.error(f"Failed to update privacy settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update privacy settings")


@router.get("/dashboard", response_model=ComplianceResponse)
async def get_compliance_dashboard(
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Get compliance dashboard metrics"""

    try:
        dashboard_data = await compliance_service.get_compliance_dashboard(tenant_id=user.tenant_id)

        return ComplianceResponse(
            success=True, message="Compliance dashboard retrieved successfully", data=dashboard_data
        )

    except Exception as e:
        logger.error(f"Failed to get compliance dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance dashboard")


# Admin endpoints (require admin privileges)
@router.post("/admin/retention-policy", response_model=ComplianceResponse)
async def create_retention_policy(
    policy: RetentionPolicyRequest,
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Create a data retention policy (Admin only)"""

    # Check if user is admin (simplified check - in production use proper RBAC)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        retention_policy = await compliance_service.data_retention_service.create_retention_policy(
            name=policy.name,
            data_category=policy.data_category,
            retention_period_days=policy.retention_period_days,
            compliance_framework=policy.compliance_framework,
            description=policy.description,
            deletion_method=policy.deletion_method,
            auto_deletion_enabled=policy.auto_deletion_enabled,
            tenant_id=user.tenant_id,
            approved_by=user.id,
        )

        return ComplianceResponse(
            success=True,
            message="Retention policy created successfully",
            data={
                "policy_id": str(retention_policy.id),
                "name": retention_policy.name,
                "data_category": retention_policy.data_category.value,
                "retention_period_days": retention_policy.retention_period_days,
            },
        )

    except Exception as e:
        logger.error(f"Failed to create retention policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to create retention policy")


@router.get("/admin/expired-data", response_model=ComplianceResponse)
async def check_expired_data(
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Check for data that has exceeded retention periods (Admin only)"""

    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        expired_items = await compliance_service.data_retention_service.check_expired_data()

        return ComplianceResponse(
            success=True,
            message="Expired data check completed",
            data={"expired_items_count": len(expired_items), "expired_items": expired_items},
        )

    except Exception as e:
        logger.error(f"Failed to check expired data: {e}")
        raise HTTPException(status_code=500, detail="Failed to check expired data")


@router.post("/admin/generate-report", response_model=ComplianceResponse)
async def generate_compliance_report(
    framework: ComplianceFramework = Body(...),
    period_start: datetime = Body(...),
    period_end: datetime = Body(...),
    user: User = Depends(get_current_user),
    compliance_service: ComplianceService = Depends(get_compliance_service),
):
    """Generate a compliance report (Admin only)"""

    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    try:
        report = await compliance_service.generate_compliance_report(
            framework=framework,
            period_start=period_start,
            period_end=period_end,
            tenant_id=user.tenant_id,
            generated_by=user.id,
        )

        return ComplianceResponse(
            success=True,
            message="Compliance report generated successfully",
            data={
                "report_id": report.report_id,
                "title": report.title,
                "compliance_framework": report.compliance_framework.value,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "compliance_score": report.compliance_score,
                "status": report.status,
            },
        )

    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate compliance report")
