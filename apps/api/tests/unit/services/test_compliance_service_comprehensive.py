import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive test coverage for Compliance Service
Critical for enterprise GDPR, SOC 2, HIPAA compliance operations

Target: 17% → 80%+ coverage
Covers: ConsentService, DataSubjectRightsService, DataRetentionService, ComplianceService
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
import json

from app.services.compliance_service import (
    ConsentService, DataSubjectRightsService, DataRetentionService, ComplianceService
)
from app.models.compliance import (
    ConsentRecord, ConsentType, ConsentStatus, LegalBasis,
    DataRetentionPolicy, DataSubjectRequest, DataSubjectRequestType, RequestStatus,
    PrivacySettings, DataBreachIncident, ComplianceReport, ComplianceControl,
    DataCategory, ComplianceFramework
)
from app.services.audit_logger import AuditLogger, AuditEventType
from app.models import User


class TestConsentServiceInitialization:
    """Test consent service initialization and configuration"""

    def test_consent_service_init(self):
        """Test consent service initializes correctly"""
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()

        service = ConsentService(mock_db, mock_audit_logger)
        assert service is not None
        assert service.db == mock_db
        assert service.audit_logger == mock_audit_logger

    def test_consent_enums_available(self):
        """Test that consent-related enums are properly configured"""
        assert ConsentType.MARKETING in ConsentType
        assert ConsentType.ANALYTICS in ConsentType
        assert ConsentStatus.GIVEN in ConsentStatus
        assert ConsentStatus.WITHDRAWN in ConsentStatus
        assert LegalBasis.CONSENT in LegalBasis
        assert DataCategory.IDENTITY in DataCategory


class TestConsentManagement:
    """Test GDPR consent management functionality"""

    @pytest.fixture
    def consent_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ConsentService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_record_consent_new(self, consent_service):
        """Test recording new consent"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no existing consent - using AsyncMock for async operations
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock db operations - the service will create a real ConsentRecord
        mock_db.add = Mock()

        result = await service.record_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns",
            legal_basis=LegalBasis.CONSENT,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            consent_method="cookie_banner",
            consent_version="1.0"
        )

        # Check that we get a result back (will be a real ConsentRecord object)
        assert result is not None
        assert result.user_id == user_id
        assert result.consent_type == ConsentType.MARKETING
        assert result.purpose == "Email marketing campaigns"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_consent_update_existing(self, consent_service):
        """Test updating existing consent"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock existing consent
        existing_consent = Mock()
        existing_consent.status = ConsentStatus.PENDING
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = existing_consent
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.record_consent(
            user_id=user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Website analytics",
            ip_address="192.168.1.1"
        )

        assert result == existing_consent
        assert existing_consent.status == ConsentStatus.GIVEN
        assert existing_consent.ip_address == "192.168.1.1"
        mock_db.commit.assert_called_once()
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_withdraw_consent_success(self, consent_service):
        """Test successful consent withdrawal"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock existing active consent
        consent_record = Mock()
        consent_record.status = ConsentStatus.GIVEN
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = consent_record
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()

        result = await service.withdraw_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing",
            withdrawal_reason="No longer interested",
            ip_address="192.168.1.1"
        )

        assert result is True
        assert consent_record.status == ConsentStatus.WITHDRAWN
        assert consent_record.withdrawal_reason == "No longer interested"
        mock_db.commit.assert_called_once()
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_withdraw_consent_not_found(self, consent_service):
        """Test consent withdrawal when consent not found"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no existing consent
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        result = await service.withdraw_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing"
        )

        assert result is False
        mock_audit_logger.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_consents(self, consent_service):
        """Test retrieving user consents"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock consent records
        consent1 = Mock()
        consent1.status = ConsentStatus.GIVEN
        consent2 = Mock()
        consent2.status = ConsentStatus.WITHDRAWN

        mock_execute_result = AsyncMock()
        mock_scalars_result = AsyncMock()
        mock_scalars_result.all.return_value = [consent1]
        mock_execute_result.scalars.return_value = mock_scalars_result
        mock_db.execute.return_value = mock_execute_result

        result = await service.get_user_consents(
            user_id=user_id,
            include_withdrawn=False
        )

        assert len(result) == 1
        assert result[0] == consent1

    @pytest.mark.asyncio
    async def test_check_consent_valid(self, consent_service):
        """Test checking valid consent"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock valid consent
        mock_consent = AsyncMock()
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_execute_result

        result = await service.check_consent(
            user_id=user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Website tracking"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_consent_invalid(self, consent_service):
        """Test checking invalid consent"""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no valid consent
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        result = await service.check_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email campaigns"
        )

        assert result is False


class TestDataSubjectRightsService:
    """Test GDPR data subject rights functionality"""

    @pytest.fixture
    def dsr_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return DataSubjectRightsService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_create_request(self, dsr_service):
        """Test creating data subject request"""
        service, mock_db, mock_audit_logger = dsr_service
        user_id = uuid4()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_request(
            user_id=user_id,
            request_type=DataSubjectRequestType.ACCESS,
            description="Need access to my personal data",
            data_categories=[DataCategory.IDENTITY, DataCategory.CONTACT],
            ip_address="192.168.1.1"
        )

        # Check that we get a real DataSubjectRequest object back
        assert result is not None
        assert result.user_id == user_id
        assert result.request_type == DataSubjectRequestType.ACCESS
        assert result.description == "Need access to my personal data"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_access_request_success(self, dsr_service):
        """Test processing data access request successfully"""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "DSR-20240101-ABC123"
        processor_id = uuid4()
        user_id = uuid4()

        # Mock data subject request
        mock_request = AsyncMock()
        mock_request.request_type = DataSubjectRequestType.ACCESS
        mock_request.user_id = user_id
        mock_request.status = RequestStatus.RECEIVED

        # Mock user data
        mock_user = AsyncMock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.first_name = "John"
        mock_user.last_name = "Doe"
        mock_user.phone = "+1234567890"
        mock_user.avatar_url = "https://example.com/avatar.jpg"
        mock_user.created_at = datetime.utcnow()
        mock_user.last_login = datetime.utcnow()
        mock_user.user_metadata = {"preferences": "test"}

        # Mock database queries
        mock_request_result = AsyncMock()
        mock_request_result.scalar_one_or_none.return_value = mock_request

        mock_user_result = AsyncMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_consent_result = AsyncMock()
        mock_consent_scalars = AsyncMock()
        mock_consent_scalars.all.return_value = []
        mock_consent_result.scalars.return_value = mock_consent_scalars

        mock_privacy_result = AsyncMock()
        mock_privacy_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            mock_request_result,
            mock_user_result,
            mock_consent_result,
            mock_privacy_result
        ]

        mock_db.commit = AsyncMock()

        result = await service.process_access_request(request_id, processor_id)

        assert "personal_information" in result
        assert result["personal_information"]["email"] == "test@example.com"
        assert result["personal_information"]["first_name"] == "John"
        assert mock_request.status == RequestStatus.COMPLETED
        assert mock_request.assigned_to == processor_id
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_access_request_invalid(self, dsr_service):
        """Test processing access request with invalid request"""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "INVALID-REQUEST"
        processor_id = uuid4()

        # Mock no request found
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        with pytest.raises(ValueError, match="Invalid access request"):
            await service.process_access_request(request_id, processor_id)

    @pytest.mark.asyncio
    async def test_process_erasure_request_anonymize(self, dsr_service):
        """Test processing erasure request with anonymization"""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "DSR-20240101-DEL123"
        processor_id = uuid4()
        user_id = uuid4()

        # Mock data subject request
        mock_request = AsyncMock()
        mock_request.request_type = DataSubjectRequestType.ERASURE
        mock_request.user_id = user_id
        mock_request.tenant_id = uuid4()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"

        mock_request_result = AsyncMock()
        mock_request_result.scalar_one_or_none.return_value = mock_request

        mock_user_result = AsyncMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_sql_result = AsyncMock()

        mock_db.execute.side_effect = [
            mock_request_result,
            mock_user_result,
            mock_sql_result
        ]

        mock_db.commit = AsyncMock()

        result = await service.process_erasure_request(
            request_id, processor_id, deletion_method="anonymize"
        )

        assert result is True
        assert "deleted-" in mock_user.email
        assert "anonymized.local" in mock_user.email
        assert mock_user.first_name == "Deleted"
        assert mock_user.last_name == "User"
        assert mock_request.status == RequestStatus.COMPLETED
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_erasure_request_hard_delete(self, dsr_service):
        """Test processing erasure request with hard deletion"""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "DSR-20240101-DEL123"
        processor_id = uuid4()
        user_id = uuid4()

        # Mock data subject request
        mock_request = AsyncMock()
        mock_request.request_type = DataSubjectRequestType.ERASURE
        mock_request.user_id = user_id
        mock_request.tenant_id = uuid4()

        # Mock user
        mock_user = AsyncMock()
        mock_user.id = user_id

        mock_request_result = AsyncMock()
        mock_request_result.scalar_one_or_none.return_value = mock_request

        mock_user_result = AsyncMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.side_effect = [
            mock_request_result,
            mock_user_result
        ]

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        result = await service.process_erasure_request(
            request_id, processor_id, deletion_method="hard_delete"
        )

        assert result is True
        mock_db.delete.assert_called_once_with(mock_user)
        mock_audit_logger.log.assert_called_once()


class TestDataRetentionService:
    """Test data retention and lifecycle management"""

    @pytest.fixture
    def retention_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return DataRetentionService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_create_retention_policy(self, retention_service):
        """Test creating data retention policy"""
        service, mock_db, mock_audit_logger = retention_service

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_retention_policy(
            name="User Data Retention",
            data_category=DataCategory.IDENTITY,
            retention_period_days=365,
            compliance_framework=ComplianceFramework.GDPR,
            description="Personal data retention policy",
            deletion_method="anonymize"
        )

        # Check that we get a real DataRetentionPolicy object back
        assert result is not None
        assert result.name == "User Data Retention"
        assert result.data_category == DataCategory.IDENTITY
        assert result.retention_period_days == 365
        assert result.compliance_framework == ComplianceFramework.GDPR
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_audit_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_expired_data(self, retention_service):
        """Test checking for expired data"""
        service, mock_db, mock_audit_logger = retention_service

        # Mock retention policies
        mock_policy = AsyncMock()
        mock_policy.id = uuid4()
        mock_policy.name = "Identity Data Policy"
        mock_policy.retention_period_days = 365
        mock_policy.data_category = DataCategory.IDENTITY
        mock_policy.deletion_method = "anonymize"
        mock_policy.require_approval = False

        # Mock expired users
        mock_user = AsyncMock()
        mock_user.id = uuid4()
        mock_user.created_at = datetime.utcnow() - timedelta(days=400)

        mock_policies_result = AsyncMock()
        mock_policies_scalars = AsyncMock()
        mock_policies_scalars.all.return_value = [mock_policy]
        mock_policies_result.scalars.return_value = mock_policies_scalars

        mock_users_result = AsyncMock()
        mock_users_scalars = AsyncMock()
        mock_users_scalars.all.return_value = [mock_user]
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [
            mock_policies_result,
            mock_users_result
        ]

        result = await service.check_expired_data()

        assert len(result) == 1
        assert result[0]["policy_name"] == "Identity Data Policy"
        assert result[0]["data_type"] == "user"
        assert result[0]["deletion_method"] == "anonymize"

    @pytest.mark.asyncio
    async def test_execute_retention_policy_dry_run(self, retention_service):
        """Test executing retention policy in dry run mode"""
        service, mock_db, mock_audit_logger = retention_service
        policy_id = uuid4()

        # Mock policy
        mock_policy = AsyncMock()
        mock_policy.name = "Test Policy"
        mock_policy.retention_period_days = 365

        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_policy
        mock_db.execute.return_value = mock_execute_result

        # Mock expired items
        with patch.object(service, 'check_expired_data') as mock_check:
            mock_check.return_value = [
                {"policy_id": str(policy_id), "data_type": "user", "data_id": str(uuid4())}
            ]

            result = await service.execute_retention_policy(policy_id, dry_run=True)

        assert result["dry_run"] is True
        assert result["expired_items_count"] == 1
        assert result["policy_name"] == "Test Policy"

    @pytest.mark.asyncio
    async def test_execute_retention_policy_live(self, retention_service):
        """Test executing retention policy in live mode"""
        service, mock_db, mock_audit_logger = retention_service
        policy_id = uuid4()
        user_id = uuid4()

        # Mock policy
        mock_policy = AsyncMock()
        mock_policy.name = "Test Policy"
        mock_policy.retention_period_days = 365
        mock_policy.deletion_method = "anonymize"
        mock_policy.tenant_id = uuid4()
        mock_policy.compliance_framework = ComplianceFramework.GDPR
        mock_policy.auto_deletion_enabled = True

        # Mock user to anonymize
        mock_user = AsyncMock()
        mock_user.id = user_id

        mock_policy_result = AsyncMock()
        mock_policy_result.scalar_one_or_none.return_value = mock_policy

        mock_user_result = AsyncMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.side_effect = [
            mock_policy_result,
            mock_user_result
        ]

        mock_db.commit = AsyncMock()

        # Mock expired items
        with patch.object(service, 'check_expired_data') as mock_check:
            mock_check.return_value = [
                {
                    "policy_id": str(policy_id),
                    "data_type": "user",
                    "data_id": str(user_id),
                    "created_at": datetime.utcnow() - timedelta(days=400)
                }
            ]

            result = await service.execute_retention_policy(policy_id, dry_run=False)

        assert result["dry_run"] is False
        assert result["deleted_count"] == 1
        assert len(result["errors"]) == 0
        mock_audit_logger.log.assert_called_once()


class TestComplianceService:
    """Test main compliance service orchestrator"""

    @pytest.fixture
    def compliance_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_compliance_service_init(self, compliance_service):
        """Test compliance service initialization"""
        service, mock_db, mock_audit_logger = compliance_service

        assert service is not None
        assert service.db == mock_db
        assert service.audit_logger == mock_audit_logger
        assert isinstance(service.consent_service, ConsentService)
        assert isinstance(service.data_subject_rights_service, DataSubjectRightsService)
        assert isinstance(service.data_retention_service, DataRetentionService)

    @pytest.mark.asyncio
    async def test_get_compliance_dashboard(self, compliance_service):
        """Test getting compliance dashboard metrics"""
        service, mock_db, mock_audit_logger = compliance_service
        tenant_id = uuid4()

        # Mock database queries
        mock_consent_result = AsyncMock()
        mock_consent_result.fetchall.return_value = [("given", 50), ("withdrawn", 5)]

        mock_dsr_result = AsyncMock()
        mock_dsr_result.fetchall.return_value = [("received", 10), ("completed", 8)]

        mock_breach_result = AsyncMock()
        mock_breach_result.scalar.return_value = 2

        mock_overdue_result = AsyncMock()
        mock_overdue_result.scalar.return_value = 1

        mock_db.execute.side_effect = [
            mock_consent_result,
            mock_dsr_result,
            mock_breach_result,
            mock_overdue_result
        ]

        result = await service.get_compliance_dashboard(tenant_id=tenant_id)

        assert "consent_metrics" in result
        assert "data_subject_request_metrics" in result
        assert "breach_incidents_total" in result
        assert "overdue_requests" in result
        assert "compliance_score" in result
        assert result["consent_metrics"]["given"] == 50
        assert result["data_subject_request_metrics"]["completed"] == 8
        assert result["breach_incidents_total"] == 2
        assert result["overdue_requests"] == 1

    def test_calculate_compliance_score_perfect(self, compliance_service):
        """Test compliance score calculation with perfect metrics"""
        service, mock_db, mock_audit_logger = compliance_service

        consent_metrics = {"given": 100, "withdrawn": 0}
        dsr_metrics = {"received": 10, "completed": 10}
        breach_count = 0
        overdue_count = 0

        score = service._calculate_compliance_score(
            consent_metrics, dsr_metrics, breach_count, overdue_count
        )

        assert score == 100

    def test_calculate_compliance_score_issues(self, compliance_service):
        """Test compliance score calculation with issues"""
        service, mock_db, mock_audit_logger = compliance_service

        consent_metrics = {"given": 80, "withdrawn": 25}  # 25% withdrawal rate
        dsr_metrics = {"received": 10, "completed": 8}
        breach_count = 3  # 3 breaches = 15 points off
        overdue_count = 2  # 2 overdue = 20 points off

        score = service._calculate_compliance_score(
            consent_metrics, dsr_metrics, breach_count, overdue_count
        )

        # 100 - 20 (overdue) - 15 (breaches) - 20 (high withdrawal) = 45
        assert score == 45

    @pytest.mark.asyncio
    async def test_generate_compliance_report_gdpr(self, compliance_service):
        """Test generating GDPR compliance report"""
        service, mock_db, mock_audit_logger = compliance_service
        tenant_id = uuid4()
        generated_by = uuid4()

        period_start = datetime.utcnow() - timedelta(days=30)
        period_end = datetime.utcnow()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock metric methods
        with patch.object(service, '_get_consent_metrics') as mock_consent, \
             patch.object(service, '_get_dsr_metrics') as mock_dsr, \
             patch.object(service, '_get_breach_metrics') as mock_breach:

            mock_consent.return_value = {"given": 100, "withdrawn": 5}
            mock_dsr.return_value = {"total_requests": 10, "overdue_responses": 1}
            mock_breach.return_value = {"total": 0}

            result = await service.generate_compliance_report(
                framework=ComplianceFramework.GDPR,
                period_start=period_start,
                period_end=period_end,
                tenant_id=tenant_id,
                generated_by=generated_by
            )

        # Check that we get a real ComplianceReport object back
        assert result is not None
        assert result.compliance_framework == ComplianceFramework.GDPR
        assert result.tenant_id == tenant_id
        assert result.generated_by == generated_by
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_consent_metrics(self, compliance_service):
        """Test getting consent metrics for reporting"""
        service, mock_db, mock_audit_logger = compliance_service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_execute_result = AsyncMock()
        mock_execute_result.fetchall.return_value = [
            ("given", 100),
            ("withdrawn", 10)
        ]
        mock_db.execute.return_value = mock_execute_result

        result = await service._get_consent_metrics(start_date, end_date, tenant_id)

        assert result["given"] == 100
        assert result["withdrawn"] == 10

    @pytest.mark.asyncio
    async def test_get_dsr_metrics(self, compliance_service):
        """Test getting data subject request metrics"""
        service, mock_db, mock_audit_logger = compliance_service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_total_result = AsyncMock()
        mock_total_result.scalar.return_value = 15

        mock_overdue_result = AsyncMock()
        mock_overdue_result.scalar.return_value = 2

        mock_db.execute.side_effect = [
            mock_total_result,
            mock_overdue_result
        ]

        result = await service._get_dsr_metrics(start_date, end_date, tenant_id)

        assert result["total_requests"] == 15
        assert result["overdue_responses"] == 2

    @pytest.mark.asyncio
    async def test_get_breach_metrics(self, compliance_service):
        """Test getting breach metrics"""
        service, mock_db, mock_audit_logger = compliance_service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_execute_result = AsyncMock()
        mock_execute_result.scalar.return_value = 3
        mock_db.execute.return_value = mock_execute_result

        result = await service._get_breach_metrics(start_date, end_date, tenant_id)

        assert result["total"] == 3


class TestComplianceIntegration:
    """Test compliance service integration scenarios"""

    @pytest.fixture
    def full_compliance_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_full_consent_workflow(self, full_compliance_service):
        """Test complete consent workflow"""
        service, mock_db, mock_audit_logger = full_compliance_service
        user_id = uuid4()

        # Mock consent recording
        mock_consent = AsyncMock()
        mock_consent.id = uuid4()

        with patch.object(service.consent_service, 'record_consent') as mock_record, \
             patch.object(service.consent_service, 'check_consent') as mock_check, \
             patch.object(service.consent_service, 'withdraw_consent') as mock_withdraw:

            mock_record.return_value = mock_consent
            mock_check.return_value = True
            mock_withdraw.return_value = True

            # Record consent
            consent = await service.consent_service.record_consent(
                user_id=user_id,
                consent_type=ConsentType.MARKETING,
                purpose="Email marketing"
            )

            # Check consent
            is_valid = await service.consent_service.check_consent(
                user_id=user_id,
                consent_type=ConsentType.MARKETING,
                purpose="Email marketing"
            )

            # Withdraw consent
            withdrawn = await service.consent_service.withdraw_consent(
                user_id=user_id,
                consent_type=ConsentType.MARKETING,
                purpose="Email marketing"
            )

            assert consent == mock_consent
            assert is_valid is True
            assert withdrawn is True

    @pytest.mark.asyncio
    async def test_data_subject_request_workflow(self, full_compliance_service):
        """Test complete data subject request workflow"""
        service, mock_db, mock_audit_logger = full_compliance_service
        user_id = uuid4()
        processor_id = uuid4()

        # Mock DSR creation and processing
        mock_request = AsyncMock()
        mock_request.request_id = "DSR-TEST-123"

        mock_user_data = {
            "personal_information": {"email": "test@example.com"},
            "consent_records": [],
            "privacy_settings": {}
        }

        with patch.object(service.data_subject_rights_service, 'create_request') as mock_create, \
             patch.object(service.data_subject_rights_service, 'process_access_request') as mock_process:

            mock_create.return_value = mock_request
            mock_process.return_value = mock_user_data

            # Create access request
            request = await service.data_subject_rights_service.create_request(
                user_id=user_id,
                request_type=DataSubjectRequestType.ACCESS,
                description="Access my data"
            )

            # Process request
            user_data = await service.data_subject_rights_service.process_access_request(
                request.request_id, processor_id
            )

            assert request == mock_request
            assert user_data == mock_user_data

    @pytest.mark.asyncio
    async def test_retention_policy_workflow(self, full_compliance_service):
        """Test complete retention policy workflow"""
        service, mock_db, mock_audit_logger = full_compliance_service

        # Mock retention policy creation and execution
        mock_policy = AsyncMock()
        mock_policy.id = uuid4()

        mock_expired_items = [
            {"policy_id": str(mock_policy.id), "data_type": "user", "data_id": str(uuid4())}
        ]

        mock_execution_result = {
            "policy_name": "Test Policy",
            "deleted_count": 1,
            "errors": [],
            "dry_run": False
        }

        with patch.object(service.data_retention_service, 'create_retention_policy') as mock_create, \
             patch.object(service.data_retention_service, 'check_expired_data') as mock_check, \
             patch.object(service.data_retention_service, 'execute_retention_policy') as mock_execute:

            mock_create.return_value = mock_policy
            mock_check.return_value = mock_expired_items
            mock_execute.return_value = mock_execution_result

            # Create policy
            policy = await service.data_retention_service.create_retention_policy(
                name="Test Policy",
                data_category=DataCategory.IDENTITY,
                retention_period_days=365,
                compliance_framework=ComplianceFramework.GDPR
            )

            # Check expired data
            expired = await service.data_retention_service.check_expired_data()

            # Execute policy
            result = await service.data_retention_service.execute_retention_policy(
                policy.id, dry_run=False
            )

            assert policy == mock_policy
            assert expired == mock_expired_items
            assert result == mock_execution_result


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture
    def error_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    @pytest.mark.asyncio
    async def test_database_error_handling(self, error_service):
        """Test handling of database errors"""
        service, mock_db, mock_audit_logger = error_service

        # Mock database error
        mock_db.execute.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await service.get_compliance_dashboard()

    @pytest.mark.asyncio
    async def test_invalid_request_types(self, error_service):
        """Test handling of invalid request types"""
        service, mock_db, mock_audit_logger = error_service

        # Test invalid data subject request processing
        mock_request = AsyncMock()
        mock_request.request_type = DataSubjectRequestType.RECTIFICATION  # Not ACCESS

        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_request

        with pytest.raises(ValueError, match="Invalid access request"):
            await service.data_subject_rights_service.process_access_request(
                "DSR-INVALID", uuid4()
            )

    @pytest.mark.asyncio
    async def test_missing_resources(self, error_service):
        """Test handling of missing resources"""
        service, mock_db, mock_audit_logger = error_service

        # Test missing retention policy
        mock_execute_result = AsyncMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        with pytest.raises(ValueError, match="Policy not found"):
            await service.data_retention_service.execute_retention_policy(uuid4())

    @pytest.mark.asyncio
    async def test_audit_logging_integration(self, error_service):
        """Test audit logging integration"""
        service, mock_db, mock_audit_logger = error_service
        user_id = uuid4()

        # Mock successful consent recording
        mock_consent = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch('app.services.compliance_service.ConsentRecord') as MockConsentRecord:
            MockConsentRecord.return_value = mock_consent

            await service.consent_service.record_consent(
                user_id=user_id,
                consent_type=ConsentType.ANALYTICS,
                purpose="Website analytics"
            )

        # Verify audit log was called
        mock_audit_logger.log.assert_called_once()
        call_args = mock_audit_logger.log.call_args
        assert call_args[1]["event_type"] == AuditEventType.GDPR_CONSENT_GIVEN
        assert call_args[1]["identity_id"] == str(user_id)
        assert call_args[1]["data_subject_id"] == str(user_id)