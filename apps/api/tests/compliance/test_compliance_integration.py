import pytest

pytestmark = pytest.mark.asyncio

"""
Comprehensive compliance integration tests for GDPR, SOC 2, HIPAA
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.compliance import (
    ConsentType, ConsentStatus, LegalBasis, DataSubjectRequestType,
    RequestStatus, ComplianceFramework, DataCategory
)
from app.services.compliance_service import ComplianceService
from app.services.audit_logger import AuditLogger


class TestComplianceIntegration:
    """Integration tests for compliance features"""

    @pytest.fixture
    async def compliance_service(self, async_db_session):
        """Create compliance service for testing"""
        audit_logger = AuditLogger(async_db_session)
        return ComplianceService(async_db_session, audit_logger)

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return uuid4()

    @pytest.fixture
    def sample_tenant_id(self):
        """Sample tenant ID for testing"""
        return uuid4()

    @pytest.mark.asyncio
    async def test_gdpr_consent_lifecycle(self, compliance_service, sample_user_id, sample_tenant_id):
        """Test complete GDPR consent lifecycle"""

        # 1. Record initial consent
        consent_record = await compliance_service.consent_service.record_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns",
            legal_basis=LegalBasis.CONSENT,
            data_categories=[DataCategory.CONTACT, DataCategory.BEHAVIORAL],
            processing_purposes=["email_marketing", "analytics"],
            third_parties=["mailchimp", "google_analytics"],
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test",
            tenant_id=sample_tenant_id
        )

        assert consent_record.user_id == sample_user_id
        assert consent_record.consent_type == ConsentType.MARKETING
        assert consent_record.status == ConsentStatus.GIVEN
        assert consent_record.legal_basis == LegalBasis.CONSENT
        assert "email_marketing" in consent_record.processing_purposes

        # 2. Check consent is valid
        is_valid = await compliance_service.consent_service.check_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns"
        )
        assert is_valid

        # 3. Withdraw consent
        withdrawal_success = await compliance_service.consent_service.withdraw_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns",
            withdrawal_reason="No longer interested",
            ip_address="192.168.1.2",
            tenant_id=sample_tenant_id
        )
        assert withdrawal_success

        # 4. Verify consent is no longer valid
        is_valid_after_withdrawal = await compliance_service.consent_service.check_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns"
        )
        assert not is_valid_after_withdrawal

        # 5. Check consent records include withdrawal
        all_consents = await compliance_service.consent_service.get_user_consents(
            user_id=sample_user_id,
            include_withdrawn=True
        )
        assert len(all_consents) == 1
        assert all_consents[0].status == ConsentStatus.WITHDRAWN
        assert all_consents[0].withdrawal_reason == "No longer interested"

    @pytest.mark.asyncio
    async def test_data_subject_rights_request_flow(self, compliance_service, sample_user_id, sample_tenant_id):
        """Test GDPR data subject rights request flow"""

        # 1. Create access request (Article 15)
        access_request = await compliance_service.data_subject_rights_service.create_request(
            user_id=sample_user_id,
            request_type=DataSubjectRequestType.ACCESS,
            description="I want to see all my personal data",
            data_categories=[DataCategory.IDENTITY, DataCategory.CONTACT],
            ip_address="192.168.1.1",
            tenant_id=sample_tenant_id
        )

        assert access_request.user_id == sample_user_id
        assert access_request.request_type == DataSubjectRequestType.ACCESS
        assert access_request.status == RequestStatus.RECEIVED
        assert access_request.response_due_date > datetime.utcnow()
        assert access_request.request_id.startswith("DSR-")

        # 2. Create erasure request (Article 17)
        erasure_request = await compliance_service.data_subject_rights_service.create_request(
            user_id=sample_user_id,
            request_type=DataSubjectRequestType.ERASURE,
            description="Please delete all my personal data",
            data_categories=[DataCategory.IDENTITY, DataCategory.CONTACT, DataCategory.BEHAVIORAL],
            ip_address="192.168.1.1",
            tenant_id=sample_tenant_id
        )

        assert erasure_request.request_type == DataSubjectRequestType.ERASURE
        assert erasure_request.status == RequestStatus.RECEIVED

        # 3. Verify both requests have proper 30-day deadline
        expected_deadline = datetime.utcnow() + timedelta(days=30)
        assert abs((access_request.response_due_date - expected_deadline).total_seconds()) < 60
        assert abs((erasure_request.response_due_date - expected_deadline).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_data_retention_policy_creation(self, compliance_service, sample_user_id, sample_tenant_id):
        """Test data retention policy creation and enforcement"""

        # 1. Create retention policy for user data
        policy = await compliance_service.data_retention_service.create_retention_policy(
            name="User Data Retention Policy",
            data_category=DataCategory.IDENTITY,
            retention_period_days=2555,  # 7 years
            compliance_framework=ComplianceFramework.GDPR,
            description="GDPR-compliant user data retention",
            deletion_method="anonymize",
            auto_deletion_enabled=True,
            tenant_id=sample_tenant_id,
            approved_by=sample_user_id
        )

        assert policy.name == "User Data Retention Policy"
        assert policy.data_category == DataCategory.IDENTITY
        assert policy.retention_period_days == 2555
        assert policy.compliance_framework == ComplianceFramework.GDPR
        assert policy.deletion_method == "anonymize"
        assert policy.auto_deletion_enabled
        assert policy.is_active

        # 2. Check for expired data (should be none for new policy)
        expired_items = await compliance_service.data_retention_service.check_expired_data()
        assert isinstance(expired_items, list)

        # 3. Test dry run of retention policy execution
        execution_result = await compliance_service.data_retention_service.execute_retention_policy(
            policy_id=policy.id,
            dry_run=True
        )

        assert execution_result["dry_run"] is True
        assert "policy_name" in execution_result
        assert "expired_items_count" in execution_result

    @pytest.mark.asyncio
    async def test_compliance_dashboard_metrics(self, compliance_service, sample_user_id, sample_tenant_id):
        """Test compliance dashboard metrics calculation"""

        # 1. Create some test data
        await compliance_service.consent_service.record_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Website analytics",
            tenant_id=sample_tenant_id
        )

        await compliance_service.data_subject_rights_service.create_request(
            user_id=sample_user_id,
            request_type=DataSubjectRequestType.ACCESS,
            description="Test request",
            tenant_id=sample_tenant_id
        )

        # 2. Get dashboard metrics
        dashboard = await compliance_service.get_compliance_dashboard(
            tenant_id=sample_tenant_id
        )

        assert "consent_metrics" in dashboard
        assert "data_subject_request_metrics" in dashboard
        assert "breach_incidents_total" in dashboard
        assert "overdue_requests" in dashboard
        assert "compliance_score" in dashboard
        assert "last_updated" in dashboard

        # 3. Verify metrics structure
        assert isinstance(dashboard["compliance_score"], int)
        assert 0 <= dashboard["compliance_score"] <= 100
        assert isinstance(dashboard["consent_metrics"], dict)
        assert isinstance(dashboard["data_subject_request_metrics"], dict)

    @pytest.mark.asyncio
    async def test_privacy_settings_defaults(self, compliance_service, sample_user_id, sample_tenant_id, async_db_session):
        """Test privacy-by-default settings"""
        from app.models.compliance import PrivacySettings

        # 1. Create default privacy settings for new user
        privacy_settings = PrivacySettings(
            user_id=sample_user_id,
            tenant_id=sample_tenant_id
        )
        async_db_session.add(privacy_settings)
        await async_db_session.commit()
        await async_db_session.refresh(privacy_settings)

        # 2. Verify privacy-by-default values
        assert privacy_settings.email_marketing is False  # Default: opt-out
        assert privacy_settings.email_product_updates is True  # Default: opt-in for essential
        assert privacy_settings.email_security_alerts is True  # Default: opt-in for security
        assert privacy_settings.analytics_tracking is True  # Default: opt-in
        assert privacy_settings.third_party_sharing is False  # Default: opt-out
        assert privacy_settings.essential_cookies is True  # Always true
        assert privacy_settings.marketing_cookies is False  # Default: opt-out

        # 3. Test consent renewal tracking
        assert privacy_settings.consent_renewal_due is None  # No renewal needed yet

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_events(self, compliance_service, sample_user_id, sample_tenant_id, async_db_session):
        """Test that compliance events are properly logged in audit trail"""

        # Mock audit logger to capture events
        audit_events = []

        class MockAuditLogger:
            async def log(self, **kwargs):
                audit_events.append(kwargs)

        # Replace audit logger
        mock_audit_logger = MockAuditLogger()
        compliance_service.audit_logger = mock_audit_logger
        compliance_service.consent_service.audit_logger = mock_audit_logger
        compliance_service.data_subject_rights_service.audit_logger = mock_audit_logger

        # 1. Record consent (should trigger audit event)
        await compliance_service.consent_service.record_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.FUNCTIONAL,
            purpose="Essential website functionality",
            tenant_id=sample_tenant_id
        )

        # 2. Create data subject request (should trigger audit event)
        await compliance_service.data_subject_rights_service.create_request(
            user_id=sample_user_id,
            request_type=DataSubjectRequestType.ACCESS,
            description="Audit trail test",
            tenant_id=sample_tenant_id
        )

        # 3. Verify audit events were logged
        assert len(audit_events) >= 2

        # Check consent event
        consent_events = [e for e in audit_events if "GDPR_CONSENT" in str(e.get("event_type", ""))]
        assert len(consent_events) >= 1

        consent_event = consent_events[0]
        assert consent_event["identity_id"] == str(sample_user_id)
        assert consent_event["data_subject_id"] == str(sample_user_id)
        assert "compliance_context" in consent_event
        assert consent_event["compliance_context"]["framework"] == "GDPR"

        # Check data subject request event
        dsr_events = [e for e in audit_events if "GDPR_DATA" in str(e.get("event_type", ""))]
        assert len(dsr_events) >= 1

        dsr_event = dsr_events[0]
        assert dsr_event["identity_id"] == str(sample_user_id)
        assert "compliance_context" in dsr_event
        assert "article" in dsr_event["compliance_context"]

    @pytest.mark.asyncio
    async def test_compliance_framework_feature_flags(self, compliance_service):
        """Test compliance framework feature flags"""
        from app.config import settings

        # Test that framework-specific features can be enabled/disabled
        gdpr_enabled = settings.COMPLIANCE_GDPR_ENABLED
        soc2_enabled = settings.COMPLIANCE_SOC2_ENABLED
        hipaa_enabled = settings.COMPLIANCE_HIPAA_ENABLED

        # Verify default settings
        assert gdpr_enabled is True  # Should be enabled by default
        assert soc2_enabled is False  # Should be disabled by default
        assert hipaa_enabled is False  # Should be disabled by default

        # Test retention period settings
        assert settings.DEFAULT_RETENTION_PERIOD_DAYS == 2555  # 7 years
        assert settings.GDPR_DSR_RESPONSE_DAYS == 30
        assert settings.GDPR_BREACH_NOTIFICATION_HOURS == 72

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, compliance_service, sample_user_id, sample_tenant_id):
        """Test compliance report generation"""

        # 1. Create some test data for the report
        await compliance_service.consent_service.record_consent(
            user_id=sample_user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Reporting test",
            tenant_id=sample_tenant_id
        )

        # 2. Generate GDPR compliance report
        report = await compliance_service.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            tenant_id=sample_tenant_id,
            generated_by=sample_user_id
        )

        assert report.report_id.startswith("RPT-GDPR-")
        assert report.compliance_framework == ComplianceFramework.GDPR
        assert report.title == "GDPR Compliance Report"
        assert report.report_type == "periodic_assessment"
        assert report.status == "draft"
        assert report.generated_by == sample_user_id

        # 3. Verify report contains metrics
        assert "consent_requests" in report.metrics
        assert "data_subject_requests" in report.metrics
        assert isinstance(report.compliance_score, int)
        assert 0 <= report.compliance_score <= 100

    @pytest.mark.asyncio
    async def test_data_anonymization_compliance(self, compliance_service, sample_user_id, sample_tenant_id, async_db_session):
        """Test data anonymization for compliance"""
        from app.models import User

        # 1. Create a test user
        test_user = User(
            id=sample_user_id,
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            tenant_id=sample_tenant_id
        )
        async_db_session.add(test_user)
        await async_db_session.commit()

        # 2. Create and process erasure request
        erasure_request = await compliance_service.data_subject_rights_service.create_request(
            user_id=sample_user_id,
            request_type=DataSubjectRequestType.ERASURE,
            description="GDPR erasure test",
            tenant_id=sample_tenant_id
        )

        # 3. Process the erasure request (anonymization)
        success = await compliance_service.data_subject_rights_service.process_erasure_request(
            request_id=erasure_request.request_id,
            processor_id=sample_user_id,
            deletion_method="anonymize"
        )

        assert success

        # 4. Verify user data was anonymized
        await async_db_session.refresh(test_user)
        assert test_user.email.startswith("deleted-")
        assert test_user.email.endswith("@anonymized.local")
        assert test_user.first_name == "Deleted"
        assert test_user.last_name == "User"
        assert test_user.user_metadata.get("anonymized") is True

    def test_compliance_configuration_validation(self):
        """Test compliance configuration validation"""
        from app.config import settings

        # Test that configuration values are reasonable
        assert settings.DEFAULT_RETENTION_PERIOD_DAYS > 0
        assert settings.GDPR_DSR_RESPONSE_DAYS == 30  # GDPR requirement
        assert settings.GDPR_BREACH_NOTIFICATION_HOURS == 72  # GDPR requirement
        assert settings.CONSENT_COOKIE_LIFETIME_DAYS > 0
        assert settings.DATA_EXPORT_MAX_RECORDS > 0
        assert settings.DATA_EXPORT_FORMAT_DEFAULT in ["json", "csv", "xml"]


@pytest.mark.asyncio
class TestCompliancePerformance:
    """Performance tests for compliance operations"""

    @pytest.mark.asyncio
    async def test_bulk_consent_processing(self, compliance_service):
        """Test performance of bulk consent operations"""
        start_time = datetime.utcnow()

        # Process multiple consent records
        tasks = []
        for i in range(10):
            user_id = uuid4()
            task = compliance_service.consent_service.record_consent(
                user_id=user_id,
                consent_type=ConsentType.ANALYTICS,
                purpose=f"Bulk test {i}",
                tenant_id=uuid4()
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Should process 10 consent records in reasonable time
        assert len(results) == 10
        assert duration < 5.0  # Should complete in under 5 seconds
        assert all(result.status == ConsentStatus.GIVEN for result in results)

    @pytest.mark.asyncio
    async def test_compliance_dashboard_performance(self, compliance_service):
        """Test compliance dashboard performance"""
        start_time = datetime.utcnow()

        dashboard_data = await compliance_service.get_compliance_dashboard()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Dashboard should load quickly
        assert duration < 2.0  # Should load in under 2 seconds
        assert "compliance_score" in dashboard_data
        assert isinstance(dashboard_data["compliance_score"], int)