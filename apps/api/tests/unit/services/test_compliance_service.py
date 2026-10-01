"""
Comprehensive Compliance Service Test Suite
Tests for GDPR compliance: ConsentService, DataSubjectRightsService, DataRetentionService
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.compliance_service import (
    ConsentService,
    DataSubjectRightsService,
    DataRetentionService,
    ComplianceService,
)
from app.models.compliance import (
    ConsentType,
    ConsentStatus,
    LegalBasis,
    DataSubjectRequestType,
    RequestStatus,
    DataCategory,
    ComplianceFramework,
)
from app.services.audit_logger import AuditEventType

pytestmark = pytest.mark.asyncio


class TestConsentServiceInitialization:
    """Test consent service initialization."""

    def test_consent_service_init(self):
        """Test consent service initializes correctly."""
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()

        service = ConsentService(mock_db, mock_audit_logger)

        assert service is not None
        assert service.db == mock_db
        assert service.audit_logger == mock_audit_logger

    def test_consent_enums_available(self):
        """Test that consent-related enums are properly configured."""
        assert isinstance(ConsentType.MARKETING, ConsentType)
        assert isinstance(ConsentType.ANALYTICS, ConsentType)
        assert isinstance(ConsentStatus.GIVEN, ConsentStatus)
        assert isinstance(ConsentStatus.WITHDRAWN, ConsentStatus)
        assert isinstance(LegalBasis.CONSENT, LegalBasis)
        assert isinstance(DataCategory.IDENTITY, DataCategory)


class TestConsentManagement:
    """Test GDPR consent management functionality."""

    @pytest.fixture
    def consent_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ConsentService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    async def test_record_consent_new(self, consent_service):
        """Test recording new consent."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no existing consent
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = Mock()

        result = await service.record_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing campaigns",
            legal_basis=LegalBasis.CONSENT,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            consent_method="cookie_banner",
            consent_version="1.0",
        )

        assert result is not None
        assert result.user_id == user_id
        assert result.consent_type == ConsentType.MARKETING
        assert result.purpose == "Email marketing campaigns"
        mock_db.add.assert_called_once()
        # The service's own commit, then the commit of its audit row.
        assert mock_db.commit.call_count == 2
        mock_audit_logger.log.assert_called_once()

    async def test_record_consent_update_existing(self, consent_service):
        """Test updating existing consent."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock existing consent
        existing_consent = Mock()
        existing_consent.status = ConsentStatus.PENDING
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = existing_consent
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.record_consent(
            user_id=user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Website analytics",
            ip_address="192.168.1.1",
        )

        assert result == existing_consent
        assert existing_consent.status == ConsentStatus.GIVEN
        assert existing_consent.ip_address == "192.168.1.1"
        # The service's own commit, then the commit of its audit row.
        assert mock_db.commit.call_count == 2
        mock_audit_logger.log.assert_called_once()

    async def test_withdraw_consent_success(self, consent_service):
        """Test successful consent withdrawal."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock existing active consent
        consent_record = Mock()
        consent_record.status = ConsentStatus.GIVEN
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = consent_record
        mock_db.execute.return_value = mock_execute_result
        mock_db.commit = AsyncMock()

        result = await service.withdraw_consent(
            user_id=user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Email marketing",
            withdrawal_reason="No longer interested",
            ip_address="192.168.1.1",
        )

        assert result is True
        assert consent_record.status == ConsentStatus.WITHDRAWN
        assert consent_record.withdrawal_reason == "No longer interested"
        # The service's own commit, then the commit of its audit row.
        assert mock_db.commit.call_count == 2
        mock_audit_logger.log.assert_called_once()

    async def test_withdraw_consent_not_found(self, consent_service):
        """Test consent withdrawal when consent not found."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no existing consent
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        result = await service.withdraw_consent(
            user_id=user_id, consent_type=ConsentType.MARKETING, purpose="Email marketing"
        )

        assert result is False
        mock_audit_logger.log.assert_not_called()

    async def test_get_user_consents(self, consent_service):
        """Test retrieving user consents."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock consent records
        consent1 = Mock()
        consent1.status = ConsentStatus.GIVEN

        mock_execute_result = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = [consent1]
        mock_execute_result.scalars.return_value = mock_scalars_result
        mock_db.execute.return_value = mock_execute_result

        result = await service.get_user_consents(user_id=user_id, include_withdrawn=False)

        assert len(result) == 1
        assert result[0] == consent1

    async def test_check_consent_valid(self, consent_service):
        """Test checking valid consent."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock valid consent
        mock_consent = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_consent
        mock_db.execute.return_value = mock_execute_result

        result = await service.check_consent(
            user_id=user_id, consent_type=ConsentType.ANALYTICS, purpose="Website tracking"
        )

        assert result is True

    async def test_check_consent_invalid(self, consent_service):
        """Test checking invalid consent."""
        service, mock_db, mock_audit_logger = consent_service
        user_id = uuid4()

        # Mock no valid consent
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        result = await service.check_consent(
            user_id=user_id, consent_type=ConsentType.MARKETING, purpose="Email campaigns"
        )

        assert result is False


class TestDataSubjectRightsService:
    """Test GDPR data subject rights functionality."""

    @pytest.fixture
    def dsr_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return DataSubjectRightsService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    async def test_create_request(self, dsr_service):
        """Test creating data subject request."""
        service, mock_db, mock_audit_logger = dsr_service
        user_id = uuid4()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock getattr for AuditEventType to avoid missing enum issue
        with patch("app.services.compliance_service.getattr") as mock_getattr:
            mock_getattr.return_value = AuditEventType.GDPR_DATA_EXPORT

            result = await service.create_request(
                user_id=user_id,
                request_type=DataSubjectRequestType.ACCESS,
                description="Need access to my personal data",
                data_categories=[DataCategory.IDENTITY, DataCategory.CONTACT],
                ip_address="192.168.1.1",
            )

        assert result is not None
        assert result.user_id == user_id
        assert result.request_type == DataSubjectRequestType.ACCESS
        assert result.description == "Need access to my personal data"
        mock_db.add.assert_called_once()
        # The service's own commit, then the commit of its audit row.
        assert mock_db.commit.call_count == 2

    async def test_create_request_generates_unique_id(self, dsr_service):
        """Test that create_request generates unique request IDs."""
        service, mock_db, mock_audit_logger = dsr_service
        user_id = uuid4()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock getattr for AuditEventType to avoid missing enum issue
        with patch("app.services.compliance_service.getattr") as mock_getattr:
            mock_getattr.return_value = AuditEventType.GDPR_DATA_DELETION

            result = await service.create_request(
                user_id=user_id,
                request_type=DataSubjectRequestType.ERASURE,
                description="Delete my data",
            )

        assert result.request_id.startswith("DSR-")
        assert len(result.request_id) > 10

    async def test_create_request_sets_response_due_date(self, dsr_service):
        """Test that create_request sets 30-day response deadline."""
        service, mock_db, mock_audit_logger = dsr_service
        user_id = uuid4()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock getattr for AuditEventType to avoid missing enum issue
        with patch("app.services.compliance_service.getattr") as mock_getattr:
            mock_getattr.return_value = AuditEventType.GDPR_DATA_EXPORT

            result = await service.create_request(
                user_id=user_id,
                request_type=DataSubjectRequestType.PORTABILITY,
            )

        # Due date should be approximately 30 days from now
        expected_due = datetime.utcnow() + timedelta(days=30)
        assert result.response_due_date is not None
        assert abs((result.response_due_date - expected_due).total_seconds()) < 60

    async def test_process_access_request_success(self, dsr_service):
        """Test processing data access request successfully.

        ``process_access_request`` now gathers the full identity data set via
        the export serializer (memberships, sessions, MFA/passkey, OAuth,
        audit logs) in addition to the historical personal_information /
        consent / privacy sections. This test drives it with a flexible
        execute mock instead of a fixed query-order ``side_effect``.
        """
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "DSR-20240101-ABC123"
        processor_id = uuid4()
        user_id = uuid4()

        # Mock data subject request
        mock_request = Mock()
        mock_request.request_type = DataSubjectRequestType.ACCESS
        mock_request.user_id = user_id
        mock_request.status = RequestStatus.RECEIVED
        mock_request.date_range_start = None
        mock_request.date_range_end = None
        mock_request.received_at = datetime.utcnow() - timedelta(days=2)
        mock_request.tenant_id = None

        # Mock user data (secret fields are set but must never be exported)
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.first_name = "John"
        mock_user.last_name = "Doe"
        mock_user.phone = "+1234567890"
        mock_user.avatar_url = "https://example.com/avatar.jpg"
        mock_user.created_at = datetime.utcnow()
        mock_user.last_login = datetime.utcnow()
        mock_user.user_metadata = {"preferences": "test"}
        mock_user.mfa_enabled = False
        mock_user.password_hash = "SENTINEL-should-not-export"
        mock_user.mfa_secret = "SENTINEL-should-not-export"

        def execute_side_effect(statement, *_args, **_kwargs):
            # Entity-aware routing: the method looks up the DSR + User, and the
            # export serializer independently queries User plus collection
            # tables. Decide what to return from the compiled SQL text.
            text = str(getattr(statement, "compile", lambda: statement)()).lower()
            result = MagicMock()
            if "data_subject_request" in text:
                result.scalar_one_or_none.return_value = mock_request
            elif "from users" in text:
                result.scalar_one_or_none.return_value = mock_user
            else:
                # privacy settings / any other scalar lookup -> None
                result.scalar_one_or_none.return_value = None
            scalars = MagicMock()
            scalars.all.return_value = []
            result.scalars.return_value = scalars
            return result

        mock_db.execute.side_effect = execute_side_effect
        mock_db.commit = AsyncMock()

        result = await service.process_access_request(request_id, processor_id)

        # Historical response shape preserved.
        assert "personal_information" in result
        assert result["personal_information"]["email"] == "test@example.com"
        assert result["personal_information"]["first_name"] == "John"
        # Enriched sections present.
        assert "profile" in result
        assert result["profile"]["email"] == "test@example.com"
        assert "sessions" in result
        assert "security" in result
        assert "audit_logs" in result
        # No secret material leaked into the export.
        from app.services.data_export_serializer import find_secret_fields

        assert find_secret_fields(result) == []
        assert "SENTINEL-should-not-export" not in str(result)
        assert mock_request.status == RequestStatus.COMPLETED
        assert mock_request.assigned_to == processor_id
        mock_db.commit.assert_called_once()
        # The completion is audited before that one commit.
        mock_audit_logger.log.assert_awaited_once()
        assert (
            mock_audit_logger.log.await_args.kwargs["event_type"]
            == AuditEventType.DATA_REQUEST_PROCESSED
        )

    async def test_process_access_request_invalid(self, dsr_service):
        """Test processing access request with invalid request."""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "INVALID-REQUEST"
        processor_id = uuid4()

        # Mock no request found
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        with pytest.raises(ValueError, match="Invalid access request"):
            await service.process_access_request(request_id, processor_id)

    async def test_process_access_request_wrong_type(self, dsr_service):
        """Test processing access request with wrong request type."""
        service, mock_db, mock_audit_logger = dsr_service
        request_id = "DSR-WRONG-TYPE"
        processor_id = uuid4()

        # Mock request with wrong type
        mock_request = Mock()
        mock_request.request_type = DataSubjectRequestType.ERASURE  # Not ACCESS

        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_request
        mock_db.execute.return_value = mock_execute_result

        with pytest.raises(ValueError, match="Invalid access request"):
            await service.process_access_request(request_id, processor_id)


class TestDataRetentionService:
    """Test data retention and lifecycle management."""

    @pytest.fixture
    def retention_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return DataRetentionService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    async def test_create_retention_policy(self, retention_service):
        """Test creating data retention policy."""
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
            deletion_method="anonymize",
        )

        assert result is not None
        assert result.name == "User Data Retention"
        assert result.data_category == DataCategory.IDENTITY
        assert result.retention_period_days == 365
        assert result.compliance_framework == ComplianceFramework.GDPR
        mock_db.add.assert_called_once()
        # The service's own commit, then the commit of its audit row.
        assert mock_db.commit.call_count == 2
        mock_audit_logger.log.assert_called_once()

    async def test_check_expired_data(self, retention_service):
        """Test checking for expired data."""
        service, mock_db, mock_audit_logger = retention_service

        # Mock retention policies
        mock_policy = Mock()
        mock_policy.id = uuid4()
        mock_policy.name = "Identity Data Policy"
        mock_policy.retention_period_days = 365
        mock_policy.data_category = DataCategory.IDENTITY
        mock_policy.deletion_method = "anonymize"
        mock_policy.require_approval = False

        # Mock expired users
        mock_user = Mock()
        mock_user.id = uuid4()
        mock_user.created_at = datetime.utcnow() - timedelta(days=400)

        mock_policies_result = MagicMock()
        mock_policies_scalars = MagicMock()
        mock_policies_scalars.all.return_value = [mock_policy]
        mock_policies_result.scalars.return_value = mock_policies_scalars

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [mock_user]
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [mock_policies_result, mock_users_result]

        result = await service.check_expired_data()

        assert len(result) == 1
        assert result[0]["policy_name"] == "Identity Data Policy"
        assert result[0]["data_type"] == "user"
        assert result[0]["deletion_method"] == "anonymize"

    async def test_execute_retention_policy_not_found(self, retention_service):
        """Test executing retention policy when policy not found."""
        service, mock_db, mock_audit_logger = retention_service
        policy_id = uuid4()

        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute_result

        with pytest.raises(ValueError, match="not found"):
            await service.execute_retention_policy(policy_id)

    async def test_execute_retention_policy_dry_run(self, retention_service):
        """Test executing retention policy in dry run mode."""
        service, mock_db, mock_audit_logger = retention_service
        policy_id = uuid4()

        # Mock policy
        mock_policy = Mock()
        mock_policy.name = "Test Policy"
        mock_policy.retention_period_days = 365

        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = mock_policy
        mock_db.execute.return_value = mock_execute_result

        # Mock expired items
        with patch.object(service, "check_expired_data") as mock_check:
            mock_check.return_value = [
                {"policy_id": str(policy_id), "data_type": "user", "data_id": str(uuid4())}
            ]

            result = await service.execute_retention_policy(policy_id, dry_run=True)

        assert result["dry_run"] is True
        assert result["policy_id"] == str(policy_id)
        # Service returns 'deleted' and 'anonymized', not 'deleted_count'
        assert "deleted" in result or "anonymized" in result


class TestComplianceService:
    """Test main compliance service orchestrator."""

    @pytest.fixture
    def compliance_service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db, mock_audit_logger

    async def test_compliance_service_init(self, compliance_service):
        """Test compliance service initialization."""
        service, mock_db, mock_audit_logger = compliance_service

        assert service is not None
        assert service.db == mock_db
        assert service.audit_logger == mock_audit_logger
        assert isinstance(service.consent_service, ConsentService)
        assert isinstance(service.data_subject_rights_service, DataSubjectRightsService)
        assert isinstance(service.data_retention_service, DataRetentionService)

    async def test_get_compliance_dashboard(self, compliance_service):
        """Test getting compliance dashboard metrics."""
        service, mock_db, mock_audit_logger = compliance_service
        tenant_id = uuid4()

        # Mock database queries
        mock_consent_result = MagicMock()
        mock_consent_result.fetchall.return_value = [("given", 50), ("withdrawn", 5)]

        mock_dsr_result = MagicMock()
        mock_dsr_result.fetchall.return_value = [("received", 10), ("completed", 8)]

        mock_breach_result = MagicMock()
        mock_breach_result.scalar.return_value = 2

        mock_overdue_result = MagicMock()
        mock_overdue_result.scalar.return_value = 1

        mock_db.execute.side_effect = [
            mock_consent_result,
            mock_dsr_result,
            mock_breach_result,
            mock_overdue_result,
        ]

        result = await service.get_compliance_dashboard(tenant_id=tenant_id)

        assert "consent_metrics" in result
        assert "data_subject_request_metrics" in result
        assert "breach_incidents_total" in result
        assert "overdue_requests" in result
        assert "compliance_score" in result
        assert result["breach_incidents_total"] == 2
        assert result["overdue_requests"] == 1

    def test_calculate_compliance_score_perfect(self, compliance_service):
        """Test compliance score calculation with perfect metrics."""
        service, mock_db, mock_audit_logger = compliance_service

        consent_metrics = {"given": 100, "withdrawn": 0}
        dsr_metrics = {"received": 10, "completed": 10}
        breach_count = 0
        overdue_count = 0

        score = service._calculate_compliance_score(
            consent_metrics, dsr_metrics, breach_count, overdue_count
        )

        assert score == 100

    def test_calculate_compliance_score_with_issues(self, compliance_service):
        """Test compliance score calculation with issues."""
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

    def test_calculate_compliance_score_minimum(self, compliance_service):
        """Test compliance score never goes below 0."""
        service, mock_db, mock_audit_logger = compliance_service

        consent_metrics = {"given": 10, "withdrawn": 100}  # Very high withdrawal
        dsr_metrics = {}
        breach_count = 100  # Many breaches
        overdue_count = 100  # Many overdue

        score = service._calculate_compliance_score(
            consent_metrics, dsr_metrics, breach_count, overdue_count
        )

        assert score >= 0


class TestComplianceServiceMetrics:
    """Test compliance service metric methods."""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db

    async def test_get_consent_metrics(self, service):
        """Test getting consent metrics for reporting."""
        compliance_service, mock_db = service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_execute_result = MagicMock()
        mock_execute_result.fetchall.return_value = [("given", 100), ("withdrawn", 10)]
        mock_db.execute.return_value = mock_execute_result

        result = await compliance_service._get_consent_metrics(start_date, end_date, tenant_id)

        assert result["given"] == 100
        assert result["withdrawn"] == 10

    async def test_get_dsr_metrics(self, service):
        """Test getting data subject request metrics."""
        compliance_service, mock_db = service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 15

        mock_overdue_result = MagicMock()
        mock_overdue_result.scalar.return_value = 2

        mock_db.execute.side_effect = [mock_total_result, mock_overdue_result]

        result = await compliance_service._get_dsr_metrics(start_date, end_date, tenant_id)

        assert result["total_requests"] == 15
        assert result["overdue_responses"] == 2

    async def test_get_breach_metrics(self, service):
        """Test getting breach metrics."""
        compliance_service, mock_db = service

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        tenant_id = uuid4()

        mock_execute_result = MagicMock()
        mock_execute_result.scalar.return_value = 3
        mock_db.execute.return_value = mock_execute_result

        result = await compliance_service._get_breach_metrics(start_date, end_date, tenant_id)

        assert result["total"] == 3


class TestComplianceReport:
    """Test compliance report generation."""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db

    async def test_generate_compliance_report_gdpr(self, service):
        """Test generating GDPR compliance report."""
        compliance_service, mock_db = service
        tenant_id = uuid4()
        generated_by = uuid4()

        period_start = datetime.utcnow() - timedelta(days=30)
        period_end = datetime.utcnow()

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock metric methods
        with patch.object(compliance_service, "_get_consent_metrics") as mock_consent, patch.object(
            compliance_service, "_get_dsr_metrics"
        ) as mock_dsr, patch.object(compliance_service, "_get_breach_metrics") as mock_breach:
            mock_consent.return_value = {"given": 100, "withdrawn": 5}
            mock_dsr.return_value = {"total_requests": 10, "overdue_responses": 1}
            mock_breach.return_value = {"total": 0}

            result = await compliance_service.generate_compliance_report(
                framework=ComplianceFramework.GDPR,
                period_start=period_start,
                period_end=period_end,
                tenant_id=tenant_id,
                generated_by=generated_by,
            )

        assert result is not None
        assert result.compliance_framework == ComplianceFramework.GDPR
        assert result.tenant_id == tenant_id
        assert result.generated_by == generated_by
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestAuditEventTypes:
    """Test audit event type usage in compliance service."""

    def test_gdpr_consent_given_exists(self):
        """Test GDPR_CONSENT_GIVEN event type exists."""
        assert hasattr(AuditEventType, "GDPR_CONSENT_GIVEN")
        assert AuditEventType.GDPR_CONSENT_GIVEN.value == "gdpr.consent_given"

    def test_gdpr_consent_withdrawn_exists(self):
        """Test GDPR_CONSENT_WITHDRAWN event type exists."""
        assert hasattr(AuditEventType, "GDPR_CONSENT_WITHDRAWN")
        assert AuditEventType.GDPR_CONSENT_WITHDRAWN.value == "gdpr.consent_withdrawn"

    def test_gdpr_data_export_exists(self):
        """Test GDPR_DATA_EXPORT event type exists."""
        assert hasattr(AuditEventType, "GDPR_DATA_EXPORT")
        assert AuditEventType.GDPR_DATA_EXPORT.value == "gdpr.data_export"

    def test_gdpr_data_deletion_exists(self):
        """Test GDPR_DATA_DELETION event type exists."""
        assert hasattr(AuditEventType, "GDPR_DATA_DELETION")
        assert AuditEventType.GDPR_DATA_DELETION.value == "gdpr.data_deletion"


class TestComplianceFrameworks:
    """Test compliance framework enum."""

    def test_gdpr_framework_exists(self):
        """Test GDPR framework exists."""
        assert hasattr(ComplianceFramework, "GDPR")

    def test_soc2_framework_exists(self):
        """Test SOC2 framework exists."""
        assert hasattr(ComplianceFramework, "SOC2")

    def test_hipaa_framework_exists(self):
        """Test HIPAA framework exists."""
        assert hasattr(ComplianceFramework, "HIPAA")


class TestDataSubjectRequestTypes:
    """Test data subject request type enum."""

    def test_access_request_type(self):
        """Test ACCESS request type exists."""
        assert hasattr(DataSubjectRequestType, "ACCESS")

    def test_erasure_request_type(self):
        """Test ERASURE request type exists."""
        assert hasattr(DataSubjectRequestType, "ERASURE")

    def test_portability_request_type(self):
        """Test PORTABILITY request type exists."""
        assert hasattr(DataSubjectRequestType, "PORTABILITY")

    def test_rectification_request_type(self):
        """Test RECTIFICATION request type exists."""
        assert hasattr(DataSubjectRequestType, "RECTIFICATION")


class TestConsentTypes:
    """Test consent type enum."""

    def test_marketing_consent_type(self):
        """Test MARKETING consent type exists."""
        assert hasattr(ConsentType, "MARKETING")

    def test_analytics_consent_type(self):
        """Test ANALYTICS consent type exists."""
        assert hasattr(ConsentType, "ANALYTICS")


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def service(self):
        mock_db = AsyncMock()
        mock_audit_logger = AsyncMock()
        return ComplianceService(mock_db, mock_audit_logger), mock_db

    async def test_database_error_handling(self, service):
        """Test handling of database errors."""
        compliance_service, mock_db = service

        # Mock database error
        mock_db.execute.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await compliance_service.get_compliance_dashboard()
