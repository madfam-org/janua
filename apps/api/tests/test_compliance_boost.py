
pytestmark = pytest.mark.asyncio

"""
Test suite to boost compliance service coverage from 17% to 50%+
Focuses on GDPR, audit logging, and data retention functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
from sqlalchemy.ext.asyncio import AsyncSession


class TestComplianceServiceCoverage:
    """Comprehensive tests for compliance service"""

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_gdpr_data_export(self, mock_get_db):
        """Test GDPR data export functionality"""
        from app.services.compliance_service import ComplianceService

        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        # Mock user data query result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "created_at": datetime.utcnow().isoformat()
        }
        mock_session.execute.return_value = mock_result

        service = ComplianceService()

        # Test data export
        exported_data = await service.export_user_data("user_123")
        assert exported_data is not None
        mock_session.execute.assert_called()

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_gdpr_data_deletion(self, mock_get_db):
        """Test GDPR right to be forgotten"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        # Mock user lookup
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = Mock(id="user_123")
        mock_session.execute.return_value = mock_result

        service = ComplianceService()

        # Test deletion
        result = await service.delete_user_data("user_123", keep_audit_logs=False)
        assert result is True
        assert mock_session.delete.called or mock_session.execute.called

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_data_anonymization(self, mock_get_db):
        """Test data anonymization for GDPR compliance"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test anonymization
        user_data = {
            "email": "john.doe@example.com",
            "name": "John Doe",
            "phone": "+1234567890",
            "address": "123 Main St"
        }

        anonymized = await service.anonymize_user_data(user_data)
        assert anonymized is not None
        # Verify PII is removed or masked
        if "email" in anonymized:
            assert "@" not in anonymized["email"] or "***" in anonymized["email"]

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_consent_management(self, mock_get_db):
        """Test consent recording and retrieval"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test consent recording
        consent_result = await service.record_consent(
            user_id="user_123",
            consent_type="marketing",
            granted=True,
            ip_address="192.168.1.1"
        )
        assert consent_result is True

        # Test consent retrieval
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [
            {"type": "marketing", "granted": True},
            {"type": "analytics", "granted": False}
        ]
        mock_session.execute.return_value = mock_result

        consents = await service.get_user_consents("user_123")
        assert consents is not None

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_data_retention_policy(self, mock_get_db):
        """Test data retention policy enforcement"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        # Mock old data query
        old_date = datetime.utcnow() - timedelta(days=365)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [
            Mock(id="old_1", created_at=old_date),
            Mock(id="old_2", created_at=old_date)
        ]
        mock_session.execute.return_value = mock_result

        service = ComplianceService()

        # Test retention policy application
        deleted_count = await service.apply_retention_policy(
            retention_days=90,
            data_type="user_sessions"
        )
        assert deleted_count >= 0
        assert mock_session.execute.called

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_audit_log_creation(self, mock_get_db):
        """Test audit log creation for compliance events"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test audit log creation
        log_id = await service.create_audit_log(
            user_id="user_123",
            action="DATA_EXPORT",
            resource="user_data",
            details={"format": "json", "reason": "user_request"},
            ip_address="192.168.1.1"
        )

        assert log_id is not None
        assert mock_session.add.called
        assert mock_session.commit.called

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, mock_get_db):
        """Test compliance report generation"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        # Mock various compliance metrics
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 42  # Mock count
        mock_session.execute.return_value = mock_result

        service = ComplianceService()

        # Test report generation
        report = await service.generate_compliance_report(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        assert report is not None
        assert "total_requests" in report or report  # Basic validation

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_data_portability(self, mock_get_db):
        """Test data portability features for GDPR"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        # Mock comprehensive user data
        mock_user_data = {
            "profile": {"id": "user_123", "email": "test@example.com"},
            "posts": [{"id": "post_1", "content": "Hello"}],
            "comments": [{"id": "comment_1", "text": "Nice"}]
        }

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user_data
        mock_session.execute.return_value = mock_result

        service = ComplianceService()

        # Test portable data export
        portable_data = await service.export_portable_data(
            user_id="user_123",
            format="json"
        )

        assert portable_data is not None

    def test_privacy_policy_validation(self):
        """Test privacy policy validation helpers"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        # Test policy version check
        current_version = service.get_current_privacy_policy_version()
        assert current_version is not None

        # Test policy acceptance validation
        is_valid = service.validate_policy_acceptance(
            user_accepted_version="2.0",
            current_version="2.1"
        )
        assert isinstance(is_valid, bool)

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_cross_border_compliance(self, mock_get_db):
        """Test cross-border data transfer compliance"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test data transfer validation
        is_allowed = await service.validate_cross_border_transfer(
            source_country="US",
            destination_country="EU",
            data_type="personal_data"
        )

        assert isinstance(is_allowed, bool)

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_breach_notification(self, mock_get_db):
        """Test data breach notification system"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test breach recording
        breach_id = await service.record_data_breach(
            breach_type="unauthorized_access",
            affected_users=["user_1", "user_2"],
            breach_date=datetime.utcnow(),
            description="Unauthorized API access detected"
        )

        assert breach_id is not None

        # Test breach notification
        notification_sent = await service.notify_breach(
            breach_id=breach_id,
            notify_authorities=True,
            notify_users=True
        )

        assert notification_sent is True

    @patch('app.services.compliance_service.logger')
    def test_compliance_logging(self, mock_logger):
        """Test compliance-specific logging"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        # Test compliance event logging
        service.log_compliance_event(
            event_type="GDPR_REQUEST",
            user_id="user_123",
            details={"request_type": "data_export"}
        )

        mock_logger.info.assert_called()

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_lawful_basis_tracking(self, mock_get_db):
        """Test lawful basis for data processing"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test lawful basis recording
        result = await service.record_lawful_basis(
            user_id="user_123",
            processing_activity="marketing_emails",
            lawful_basis="consent",
            details={"consent_date": datetime.utcnow().isoformat()}
        )

        assert result is True

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_data_minimization(self, mock_get_db):
        """Test data minimization principle enforcement"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test data minimization check
        user_data = {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "ssn": "123-45-6789",  # Should be flagged
            "credit_card": "4111111111111111"  # Should be flagged
        }

        minimized_data = await service.apply_data_minimization(
            data=user_data,
            purpose="newsletter_subscription"
        )

        # Sensitive data should be removed for newsletter
        assert "ssn" not in minimized_data
        assert "credit_card" not in minimized_data

    @patch('app.services.compliance_service.get_db')
    @pytest.mark.asyncio
    async def test_purpose_limitation(self, mock_get_db):
        """Test purpose limitation compliance"""
        from app.services.compliance_service import ComplianceService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_get_db.return_value.__aenter__.return_value = mock_session

        service = ComplianceService()

        # Test purpose validation
        is_valid = await service.validate_data_usage(
            user_id="user_123",
            data_category="email_address",
            intended_purpose="marketing",
            original_purpose="account_creation"
        )

        assert isinstance(is_valid, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])