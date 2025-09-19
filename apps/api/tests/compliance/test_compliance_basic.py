"""
Basic compliance tests for core functionality validation
"""

import pytest
from datetime import datetime
from uuid import uuid4

def test_compliance_imports():
    """Test that all compliance modules can be imported"""
    try:
        from app.models.compliance import (
            ConsentRecord, ConsentType, ConsentStatus, LegalBasis,
            DataSubjectRequest, DataSubjectRequestType, RequestStatus,
            PrivacySettings, ComplianceFramework, DataCategory
        )
        from app.services.compliance_service import ComplianceService
        from app.services.audit_logger import AuditLogger, AuditEventType
        from app.routers.v1.compliance import router
        from app.config import settings

        # Test basic enum values
        assert ConsentType.MARKETING is not None
        assert ConsentStatus.GIVEN is not None
        assert LegalBasis.CONSENT is not None
        assert DataSubjectRequestType.ACCESS is not None
        assert RequestStatus.RECEIVED is not None
        assert ComplianceFramework.GDPR is not None
        assert DataCategory.CONTACT is not None

        # Test configuration values
        assert hasattr(settings, 'COMPLIANCE_GDPR_ENABLED')
        assert hasattr(settings, 'DEFAULT_RETENTION_PERIOD_DAYS')
        assert hasattr(settings, 'GDPR_DSR_RESPONSE_DAYS')

        print("✅ All compliance imports successful")

    except ImportError as e:
        pytest.fail(f"Import error: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")


def test_compliance_configuration():
    """Test compliance configuration values"""
    from app.config import settings

    # Test GDPR settings
    assert settings.COMPLIANCE_GDPR_ENABLED is True
    assert settings.GDPR_DSR_RESPONSE_DAYS == 30
    assert settings.GDPR_BREACH_NOTIFICATION_HOURS == 72

    # Test retention settings
    assert settings.DEFAULT_RETENTION_PERIOD_DAYS == 2555  # 7 years
    assert settings.CONSENT_COOKIE_LIFETIME_DAYS == 365

    # Test privacy settings
    assert settings.PRIVACY_BY_DEFAULT is True
    assert settings.AUTOMATIC_DATA_ANONYMIZATION is True

    # Test audit settings
    assert settings.COMPLIANCE_AUDIT_RETENTION_YEARS == 7
    assert settings.AUDIT_LOG_ENCRYPTION is True

    print("✅ Compliance configuration validation successful")


def test_audit_event_types():
    """Test that all compliance audit event types are available"""
    from app.services.audit_logger import AuditEventType

    # Test GDPR events
    assert hasattr(AuditEventType, 'GDPR_CONSENT_GIVEN')
    assert hasattr(AuditEventType, 'GDPR_CONSENT_WITHDRAWN')
    assert hasattr(AuditEventType, 'GDPR_DATA_EXPORT')
    assert hasattr(AuditEventType, 'GDPR_DATA_DELETION')

    # Test SOC2 events
    assert hasattr(AuditEventType, 'SOC2_ACCESS_GRANTED')
    assert hasattr(AuditEventType, 'SOC2_ACCESS_DENIED')
    assert hasattr(AuditEventType, 'SOC2_ACCESS_REVOKED')

    # Test HIPAA events
    assert hasattr(AuditEventType, 'HIPAA_PHI_ACCESS')
    assert hasattr(AuditEventType, 'HIPAA_PHI_EXPORT')

    # Test Breach events
    assert hasattr(AuditEventType, 'GDPR_BREACH_NOTIFICATION')
    assert hasattr(AuditEventType, 'HIPAA_BREACH_DETECTED')

    print("✅ Audit event types validation successful")


def test_compliance_model_creation():
    """Test basic compliance model instantiation"""
    from app.models.compliance import (
        ConsentRecord, ConsentType, ConsentStatus, LegalBasis,
        DataSubjectRequest, DataSubjectRequestType, RequestStatus,
        PrivacySettings, ComplianceFramework, DataCategory
    )

    # Test ConsentRecord creation
    consent = ConsentRecord(
        user_id=uuid4(),
        tenant_id=uuid4(),
        consent_type=ConsentType.MARKETING,
        purpose="Test marketing consent",
        legal_basis=LegalBasis.CONSENT,
        status=ConsentStatus.GIVEN,
        data_categories=[DataCategory.CONTACT.value],
        processing_purposes=["email_marketing"],
        given_at=datetime.utcnow()
    )
    assert consent.consent_type == ConsentType.MARKETING
    assert consent.status == ConsentStatus.GIVEN

    # Test DataSubjectRequest creation
    dsr = DataSubjectRequest(
        user_id=uuid4(),
        tenant_id=uuid4(),
        request_type=DataSubjectRequestType.ACCESS,
        description="Test access request",
        status=RequestStatus.RECEIVED,
        request_id="DSR-TEST-001",
        received_at=datetime.utcnow(),
        response_due_date=datetime.utcnow()
    )
    assert dsr.request_type == DataSubjectRequestType.ACCESS
    assert dsr.status == RequestStatus.RECEIVED

    print("✅ Compliance model creation successful")


def test_api_router_endpoints():
    """Test that compliance API router has required endpoints"""
    from app.routers.v1.compliance import router

    # Get all route paths
    routes = [route.path for route in router.routes]

    # Check for required endpoints
    required_endpoints = [
        "/consent",
        "/consent/withdraw",
        "/data-subject-request",
        "/privacy-settings",
        "/dashboard"
    ]

    for endpoint in required_endpoints:
        full_path = f"/compliance{endpoint}"
        found = any(full_path in route for route in routes)
        assert found, f"Missing endpoint: {full_path}"

    print("✅ API router endpoints validation successful")


if __name__ == "__main__":
    test_compliance_imports()
    test_compliance_configuration()
    test_audit_event_types()
    test_compliance_model_creation()
    test_api_router_endpoints()
    print("\n🎉 All basic compliance tests passed!")