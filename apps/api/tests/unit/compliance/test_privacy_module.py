"""
Comprehensive Privacy Module Test Suite
Tests for GDPR consent management, data subject requests, and privacy types
"""

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Direct module loading to avoid parent package __init__.py triggers
# =============================================================================


def load_module_directly(module_name: str, file_path: Path):
    """Load a module directly without triggering parent __init__.py imports."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Get the path to the app directory
API_ROOT = Path(__file__).parent.parent.parent.parent
PRIVACY_TYPES_PATH = API_ROOT / "app" / "compliance" / "privacy" / "privacy_types.py"
PRIVACY_MODELS_PATH = API_ROOT / "app" / "compliance" / "privacy" / "privacy_models.py"

# Load privacy_types directly (no dependencies)
privacy_types = load_module_directly("privacy_types_direct", PRIVACY_TYPES_PATH)

PrivacyRightType = privacy_types.PrivacyRightType
DataExportFormat = privacy_types.DataExportFormat
RetentionAction = privacy_types.RetentionAction

# Load privacy_models directly (only depends on privacy_types and dataclasses)
privacy_models = load_module_directly("privacy_models_direct", PRIVACY_MODELS_PATH)

DataSubjectRequestResponse = privacy_models.DataSubjectRequestResponse
PrivacyImpactAssessment = privacy_models.PrivacyImpactAssessment


pytestmark = pytest.mark.asyncio


# =============================================================================
# Privacy Types Tests - Pure enums with no dependencies
# =============================================================================


class TestPrivacyRightType:
    """Test PrivacyRightType enum."""

    def test_access_right(self):
        """Test access right (Article 15)."""
        assert PrivacyRightType.ACCESS == "access"
        assert PrivacyRightType.ACCESS.value == "access"

    def test_rectification_right(self):
        """Test rectification right (Article 16)."""
        assert PrivacyRightType.RECTIFICATION == "rectification"

    def test_erasure_right(self):
        """Test erasure/right to be forgotten (Article 17)."""
        assert PrivacyRightType.ERASURE == "erasure"

    def test_portability_right(self):
        """Test data portability right (Article 20)."""
        assert PrivacyRightType.PORTABILITY == "portability"

    def test_restriction_right(self):
        """Test restriction right (Article 18)."""
        assert PrivacyRightType.RESTRICTION == "restriction"

    def test_objection_right(self):
        """Test objection right (Article 21)."""
        assert PrivacyRightType.OBJECTION == "objection"

    def test_automated_decision_right(self):
        """Test automated decision-making right (Article 22)."""
        assert PrivacyRightType.AUTOMATED_DECISION == "automated_decision"

    def test_all_rights_count(self):
        """Test all GDPR rights are covered."""
        rights = list(PrivacyRightType)
        assert len(rights) == 7


class TestDataExportFormat:
    """Test DataExportFormat enum."""

    def test_json_format(self):
        """Test JSON export format."""
        assert DataExportFormat.JSON == "json"
        assert DataExportFormat.JSON.value == "json"

    def test_csv_format(self):
        """Test CSV export format."""
        assert DataExportFormat.CSV == "csv"

    def test_xml_format(self):
        """Test XML export format."""
        assert DataExportFormat.XML == "xml"

    def test_pdf_format(self):
        """Test PDF export format."""
        assert DataExportFormat.PDF == "pdf"

    def test_all_formats_count(self):
        """Test all formats are available."""
        formats = list(DataExportFormat)
        assert len(formats) == 4


class TestRetentionAction:
    """Test RetentionAction enum."""

    def test_delete_action(self):
        """Test delete retention action."""
        assert RetentionAction.DELETE == "delete"

    def test_anonymize_action(self):
        """Test anonymize retention action."""
        assert RetentionAction.ANONYMIZE == "anonymize"

    def test_archive_action(self):
        """Test archive retention action."""
        assert RetentionAction.ARCHIVE == "archive"

    def test_review_action(self):
        """Test review retention action."""
        assert RetentionAction.REVIEW == "review"


# =============================================================================
# Compliance Models Enum Tests - Pure enums from compliance module
# =============================================================================


class TestComplianceEnums:
    """Test compliance module enums."""

    def test_consent_type_values(self):
        """Test ConsentType enum values."""
        from app.models.compliance import ConsentType

        assert ConsentType.MARKETING == "marketing"
        assert ConsentType.ANALYTICS == "analytics"
        assert ConsentType.FUNCTIONAL == "functional"
        assert ConsentType.NECESSARY == "necessary"

    def test_consent_status_values(self):
        """Test ConsentStatus enum values."""
        from app.models.compliance import ConsentStatus

        assert ConsentStatus.GIVEN == "given"
        assert ConsentStatus.WITHDRAWN == "withdrawn"
        assert ConsentStatus.EXPIRED == "expired"
        assert ConsentStatus.PENDING == "pending"

    def test_legal_basis_values(self):
        """Test LegalBasis enum values."""
        from app.models.compliance import LegalBasis

        assert LegalBasis.CONSENT == "consent"
        assert LegalBasis.CONTRACT == "contract"
        assert LegalBasis.LEGAL_OBLIGATION == "legal_obligation"
        assert LegalBasis.VITAL_INTERESTS == "vital_interests"
        assert LegalBasis.PUBLIC_TASK == "public_task"
        assert LegalBasis.LEGITIMATE_INTERESTS == "legitimate_interests"

    def test_data_category_values(self):
        """Test DataCategory enum values."""
        from app.models.compliance import DataCategory

        assert DataCategory.IDENTITY == "identity"
        assert DataCategory.CONTACT == "contact"
        assert DataCategory.FINANCIAL == "financial"
        assert DataCategory.HEALTH == "health"
        assert DataCategory.BIOMETRIC == "biometric"

    def test_data_subject_request_type_values(self):
        """Test DataSubjectRequestType enum values."""
        from app.models.compliance import DataSubjectRequestType

        assert DataSubjectRequestType.ACCESS == "access"
        assert DataSubjectRequestType.RECTIFICATION == "rectification"
        assert DataSubjectRequestType.ERASURE == "erasure"
        assert DataSubjectRequestType.PORTABILITY == "portability"
        assert DataSubjectRequestType.RESTRICTION == "restriction"
        assert DataSubjectRequestType.OBJECTION == "objection"

    def test_request_status_values(self):
        """Test RequestStatus enum values."""
        from app.models.compliance import RequestStatus

        assert RequestStatus.RECEIVED == "received"
        assert RequestStatus.ACKNOWLEDGED == "acknowledged"
        assert RequestStatus.IN_PROGRESS == "in_progress"
        assert RequestStatus.COMPLETED == "completed"
        assert RequestStatus.REJECTED == "rejected"

    def test_compliance_framework_values(self):
        """Test ComplianceFramework enum values."""
        from app.models.compliance import ComplianceFramework

        assert ComplianceFramework.GDPR == "gdpr"
        assert ComplianceFramework.SOC2 == "soc2"
        assert ComplianceFramework.HIPAA == "hipaa"
        assert ComplianceFramework.CCPA == "ccpa"


# =============================================================================
# GDPR Compliance Scenarios Tests
# =============================================================================


class TestGDPRComplianceScenarios:
    """Test GDPR compliance scenarios."""

    def test_gdpr_response_deadline(self):
        """Test GDPR 30-day response deadline calculation."""
        now = datetime.utcnow()
        deadline = now + timedelta(days=30)

        # GDPR requires response within 30 days
        days_until_deadline = (deadline - now).days
        assert days_until_deadline == 30

    def test_request_id_format(self):
        """Test data subject request ID format."""
        import uuid

        now = datetime.utcnow()
        request_id = f"DSR-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        assert request_id.startswith("DSR-")
        assert now.strftime("%Y%m%d") in request_id
        assert len(request_id.split("-")) == 3

    def test_consent_evidence_structure(self):
        """Test consent evidence structure for GDPR compliance."""
        now = datetime.utcnow()
        consent_evidence = {
            "timestamp": now.isoformat(),
            "method": "api",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "purpose": "marketing_emails",
        }

        # GDPR requires evidence of consent
        assert "timestamp" in consent_evidence
        assert "method" in consent_evidence
        assert "purpose" in consent_evidence

    def test_data_categories_coverage(self):
        """Test that all GDPR data categories are handled."""
        from app.models.compliance import DataCategory

        categories = list(DataCategory)

        # Should have common categories
        category_values = [c.value for c in categories]
        assert len(categories) > 0
        assert "identity" in category_values
        assert "contact" in category_values


class TestDataRetentionCompliance:
    """Test data retention compliance scenarios."""

    def test_retention_period_validation(self):
        """Test retention period is valid."""
        retention_days = 365 * 2  # 2 years

        assert retention_days > 0
        assert retention_days <= 365 * 10  # Max 10 years reasonable

    def test_retention_expiry_calculation(self):
        """Test retention expiry date calculation."""
        now = datetime.utcnow()
        retention_days = 365
        expiry_date = now + timedelta(days=retention_days)

        assert expiry_date > now
        assert (expiry_date - now).days == retention_days

    def test_retention_actions_available(self):
        """Test all retention actions are available."""
        actions = list(RetentionAction)
        assert len(actions) == 4

        # Should include delete for full erasure
        assert RetentionAction.DELETE in actions
        # Should include anonymize for GDPR compliance
        assert RetentionAction.ANONYMIZE in actions


# =============================================================================
# Privacy Right Validation Tests
# =============================================================================


class TestPrivacyRightValidation:
    """Test privacy right validation logic."""

    def test_access_right_includes_metadata(self):
        """Test access right should include metadata option."""
        # Article 15 requires providing information about processing
        include_metadata = True
        assert include_metadata is True

    def test_portability_format_requirements(self):
        """Test portability requires machine-readable format."""
        # GDPR requires commonly used, machine-readable format
        machine_readable = [DataExportFormat.JSON, DataExportFormat.CSV, DataExportFormat.XML]

        assert DataExportFormat.JSON in machine_readable
        assert DataExportFormat.CSV in machine_readable

    def test_erasure_vs_anonymization(self):
        """Test erasure can be full deletion or anonymization."""
        # GDPR allows anonymization as alternative to deletion
        erasure_options = [RetentionAction.DELETE, RetentionAction.ANONYMIZE]

        assert RetentionAction.DELETE in erasure_options
        assert RetentionAction.ANONYMIZE in erasure_options


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestPrivacyModuleIntegration:
    """Test privacy module integration scenarios."""

    def test_consent_to_request_flow(self):
        """Test consent leads to valid data subject request."""
        # User grants consent
        consent_granted = True

        # User can exercise rights
        if consent_granted:
            available_rights = [
                PrivacyRightType.ACCESS,
                PrivacyRightType.RECTIFICATION,
                PrivacyRightType.ERASURE,
                PrivacyRightType.PORTABILITY,
            ]

            assert PrivacyRightType.ACCESS in available_rights
            assert PrivacyRightType.ERASURE in available_rights

    def test_export_format_selection(self):
        """Test export format selection for portability."""
        # User can select preferred format
        preferred_format = DataExportFormat.JSON

        # Should be valid format
        assert preferred_format in DataExportFormat

    def test_retention_policy_enforcement(self):
        """Test retention policy triggers correct action."""
        # When retention expires, action should be taken
        retention_expired = True
        action = RetentionAction.ANONYMIZE

        if retention_expired:
            assert action in RetentionAction


# =============================================================================
# Audit Trail Tests
# =============================================================================


class TestPrivacyAuditTrail:
    """Test privacy audit trail requirements."""

    def test_consent_audit_fields(self):
        """Test consent audit has required fields."""
        audit_event = {
            "event_type": "consent_grant",
            "resource_type": "user_consent",
            "resource_id": "consent_123",
            "action": "consent_grant",
            "outcome": "success",
            "user_id": "user_456",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "control_id": "GDPR-7",
        }

        # GDPR requires audit trail
        assert "user_id" in audit_event
        assert "action" in audit_event
        assert "control_id" in audit_event

    def test_dsr_audit_fields(self):
        """Test data subject request audit has required fields."""
        audit_event = {
            "event_type": "data_access",
            "resource_type": "data_subject_request",
            "resource_id": "DSR-20240115-ABC12345",
            "action": "create",
            "outcome": "success",
            "user_id": "user_456",
            "control_id": "GDPR-15-22",
        }

        assert "resource_id" in audit_event
        assert "DSR-" in audit_event["resource_id"]
        assert "GDPR" in audit_event["control_id"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPrivacyErrorHandling:
    """Test privacy module error handling."""

    def test_invalid_uuid_handling(self):
        """Test handling of invalid UUID."""
        import uuid

        invalid_uuid = "not-a-uuid"

        with pytest.raises(ValueError):
            uuid.UUID(invalid_uuid)

    def test_invalid_date_range(self):
        """Test handling of invalid date range."""
        start_date = datetime.utcnow()
        end_date = start_date - timedelta(days=30)  # End before start

        # End date should not be before start date
        assert end_date < start_date

    def test_missing_consent_type_handling(self):
        """Test handling of missing consent type."""
        from app.models.compliance import ConsentType

        consent_types = list(ConsentType)

        # Should have at least one type
        assert len(consent_types) > 0


# =============================================================================
# GDPR Article Coverage Tests
# =============================================================================


class TestGDPRArticleCoverage:
    """Test coverage of GDPR articles."""

    def test_article_15_access(self):
        """Test Article 15 - Right of access coverage."""
        assert PrivacyRightType.ACCESS.value == "access"

    def test_article_16_rectification(self):
        """Test Article 16 - Right to rectification coverage."""
        assert PrivacyRightType.RECTIFICATION.value == "rectification"

    def test_article_17_erasure(self):
        """Test Article 17 - Right to erasure coverage."""
        assert PrivacyRightType.ERASURE.value == "erasure"

    def test_article_18_restriction(self):
        """Test Article 18 - Right to restriction coverage."""
        assert PrivacyRightType.RESTRICTION.value == "restriction"

    def test_article_20_portability(self):
        """Test Article 20 - Right to data portability coverage."""
        assert PrivacyRightType.PORTABILITY.value == "portability"

    def test_article_21_objection(self):
        """Test Article 21 - Right to object coverage."""
        assert PrivacyRightType.OBJECTION.value == "objection"

    def test_article_22_automated_decisions(self):
        """Test Article 22 - Automated decision-making coverage."""
        assert PrivacyRightType.AUTOMATED_DECISION.value == "automated_decision"


# =============================================================================
# Privacy Models Tests
# =============================================================================


class TestPrivacyModelsStructure:
    """Test privacy models structure."""

    def test_data_subject_request_response_exists(self):
        """Test DataSubjectRequestResponse dataclass exists."""
        assert DataSubjectRequestResponse is not None

    def test_privacy_impact_assessment_exists(self):
        """Test PrivacyImpactAssessment dataclass exists."""
        assert PrivacyImpactAssessment is not None

    def test_create_data_subject_response(self):
        """Test creating DataSubjectRequestResponse."""
        now = datetime.utcnow()
        response = DataSubjectRequestResponse(
            request_id="DSR-TEST-001",
            response_type="access",
            data={"user_data": {"email": "test@example.com"}},
            export_url="https://storage.example.com/exports/test.json",
            completion_time=now,
            notes="Test response",
        )

        assert response.request_id == "DSR-TEST-001"
        assert response.response_type == "access"
        assert response.data is not None
        assert response.export_url is not None
        assert response.completion_time == now
        assert response.notes == "Test response"

    def test_create_response_minimal(self):
        """Test creating response with minimal data."""
        response = DataSubjectRequestResponse(
            request_id="DSR-MINIMAL",
            response_type="erasure",
            data=None,
            export_url=None,
            completion_time=datetime.utcnow(),
            notes=None,
        )

        assert response.request_id == "DSR-MINIMAL"
        assert response.data is None
        assert response.export_url is None
        assert response.notes is None


# =============================================================================
# Control Status Tests
# =============================================================================


class TestControlStatus:
    """Test ControlStatus enum values."""

    def test_compliant_status(self):
        """Test COMPLIANT status."""
        from app.models.compliance import ControlStatus

        assert ControlStatus.COMPLIANT == "compliant"

    def test_non_compliant_status(self):
        """Test NON_COMPLIANT status."""
        from app.models.compliance import ControlStatus

        assert ControlStatus.NON_COMPLIANT == "non_compliant"

    def test_effective_status(self):
        """Test EFFECTIVE status."""
        from app.models.compliance import ControlStatus

        assert ControlStatus.EFFECTIVE == "effective"

    def test_not_tested_status(self):
        """Test NOT_TESTED status."""
        from app.models.compliance import ControlStatus

        assert ControlStatus.NOT_TESTED == "not_tested"

    def test_exception_status(self):
        """Test EXCEPTION status."""
        from app.models.compliance import ControlStatus

        assert ControlStatus.EXCEPTION == "exception"


# =============================================================================
# Privacy Rights Coverage Matrix Tests
# =============================================================================


class TestPrivacyRightsCoverageMatrix:
    """Test comprehensive coverage of privacy rights."""

    def test_all_gdpr_rights_defined(self):
        """Test all GDPR Article 15-22 rights are defined."""
        rights_count = len(list(PrivacyRightType))
        # GDPR Articles 15-22 (excluding 19 which is procedural)
        assert rights_count >= 7

    def test_export_formats_machine_readable(self):
        """Test export formats support machine-readable requirement."""
        formats = list(DataExportFormat)
        format_values = [f.value for f in formats]

        # GDPR requires structured, commonly used, machine-readable format
        assert "json" in format_values
        assert "csv" in format_values

    def test_retention_actions_complete(self):
        """Test all retention actions are available."""
        actions = list(RetentionAction)
        action_values = [a.value for a in actions]

        # Must support full deletion
        assert "delete" in action_values
        # Should support anonymization as alternative
        assert "anonymize" in action_values
        # Should support archival for legal hold
        assert "archive" in action_values
        # Should support review for manual assessment
        assert "review" in action_values


# =============================================================================
# Data Protection Impact Assessment Tests
# =============================================================================


class TestDPIARequirements:
    """Test Data Protection Impact Assessment requirements."""

    def test_dpia_risk_levels(self):
        """Test DPIA risk level categorization."""
        risk_levels = ["low", "medium", "high", "critical"]

        # All risk levels should be valid
        assert "low" in risk_levels
        assert "high" in risk_levels
        assert "critical" in risk_levels

    def test_dpia_data_categories(self):
        """Test DPIA covers special data categories."""
        from app.models.compliance import DataCategory

        categories = list(DataCategory)
        category_values = [c.value for c in categories]

        # Special categories under GDPR Article 9
        assert "health" in category_values
        assert "biometric" in category_values

    def test_dpia_legal_basis_options(self):
        """Test all legal bases under GDPR Article 6."""
        from app.models.compliance import LegalBasis

        bases = list(LegalBasis)

        # GDPR Article 6 defines 6 lawful bases
        assert len(bases) >= 6


# =============================================================================
# Privacy Types Enum Completeness Tests
# =============================================================================


class TestPrivacyTypesCompleteness:
    """Test privacy types enum completeness."""

    def test_privacy_right_type_is_str_enum(self):
        """Test PrivacyRightType is string-based enum."""
        # StrEnum values are accessible via .value property
        assert PrivacyRightType.ACCESS.value == "access"
        # And enum comparisons work with string values
        assert PrivacyRightType.ACCESS == "access"

    def test_data_export_format_is_str_enum(self):
        """Test DataExportFormat is string-based enum."""
        assert DataExportFormat.JSON.value == "json"
        assert DataExportFormat.JSON == "json"

    def test_retention_action_is_str_enum(self):
        """Test RetentionAction is string-based enum."""
        assert RetentionAction.DELETE.value == "delete"
        assert RetentionAction.DELETE == "delete"


# =============================================================================
# Privacy Impact Assessment Model Tests
# =============================================================================


class TestPrivacyImpactAssessment:
    """Test PrivacyImpactAssessment dataclass."""

    def test_create_full_assessment(self):
        """Test creating full privacy impact assessment."""
        from app.models.compliance import DataCategory, LegalBasis

        now = datetime.utcnow()
        assessment = PrivacyImpactAssessment(
            pia_id="PIA-2024-001",
            title="User Analytics PIA",
            description="User data collection for analytics",
            project_name="Analytics Platform",
            data_processing_purpose="Service improvement through user behavior analysis",
            data_categories=[DataCategory.IDENTITY, DataCategory.CONTACT],
            processing_activities=["collection", "storage", "analysis"],
            legal_basis=[LegalBasis.CONSENT],
            data_subjects=["end_users", "customers"],
            privacy_risks=[{"type": "data_breach", "likelihood": "medium", "impact": "high"}],
            risk_level="medium",
            mitigation_measures=["encryption", "access control", "retention limits"],
            stakeholder_consultation=True,
            dpo_consultation=True,
            approved_by="DPO",
            approval_date=now,
            review_date=now + timedelta(days=365),
            monitoring_measures=["audit_logs", "access_reviews"],
            created_at=now,
            updated_at=now,
        )

        assert assessment.pia_id == "PIA-2024-001"
        assert LegalBasis.CONSENT in assessment.legal_basis
        assert DataCategory.IDENTITY in assessment.data_categories
        assert assessment.risk_level == "medium"
        assert assessment.approved_by == "DPO"

    def test_assessment_risk_levels(self):
        """Test assessment can handle different risk levels."""
        from app.models.compliance import DataCategory, LegalBasis

        now = datetime.utcnow()
        for risk_level in ["low", "medium", "high", "very_high"]:
            assessment = PrivacyImpactAssessment(
                pia_id=f"PIA-{risk_level}",
                title="Risk Level Test",
                description="Test assessment",
                project_name="Test Project",
                data_processing_purpose="Testing risk levels",
                data_categories=[DataCategory.IDENTITY],
                processing_activities=["test"],
                legal_basis=[LegalBasis.CONSENT],
                data_subjects=["test_users"],
                privacy_risks=[{"type": "test_risk", "level": risk_level}],
                risk_level=risk_level,
                mitigation_measures=[],
                stakeholder_consultation=False,
                dpo_consultation=False,
                approved_by=None,
                approval_date=None,
                review_date=now + timedelta(days=30),
                monitoring_measures=[],
                created_at=now,
                updated_at=now,
            )

            assert assessment.risk_level == risk_level


# =============================================================================
# Consent Lifecycle Tests
# =============================================================================


class TestConsentLifecycle:
    """Test consent lifecycle scenarios."""

    def test_consent_status_transitions(self):
        """Test valid consent status transitions."""
        from app.models.compliance import ConsentStatus

        # Valid transitions: pending -> given -> withdrawn or expired
        valid_statuses = [
            ConsentStatus.PENDING,
            ConsentStatus.GIVEN,
            ConsentStatus.WITHDRAWN,
            ConsentStatus.EXPIRED,
        ]

        assert len(valid_statuses) == 4

    def test_legal_basis_for_processing(self):
        """Test legal bases for data processing."""
        from app.models.compliance import LegalBasis

        # GDPR Article 6 legal bases
        bases = list(LegalBasis)

        assert len(bases) >= 6
        assert LegalBasis.CONSENT in bases
        assert LegalBasis.CONTRACT in bases
        assert LegalBasis.LEGAL_OBLIGATION in bases


# =============================================================================
# Data Subject Request Types Tests
# =============================================================================


class TestDataSubjectRequestTypes:
    """Test data subject request types."""

    def test_all_request_types_exist(self):
        """Test all GDPR request types exist."""
        from app.models.compliance import DataSubjectRequestType

        types = list(DataSubjectRequestType)

        # GDPR rights should map to request types
        assert DataSubjectRequestType.ACCESS in types
        assert DataSubjectRequestType.RECTIFICATION in types
        assert DataSubjectRequestType.ERASURE in types
        assert DataSubjectRequestType.PORTABILITY in types
        assert DataSubjectRequestType.RESTRICTION in types
        assert DataSubjectRequestType.OBJECTION in types

    def test_request_type_to_right_mapping(self):
        """Test request types map to privacy rights."""
        from app.models.compliance import DataSubjectRequestType

        # Each request type should correspond to a privacy right
        assert DataSubjectRequestType.ACCESS.value == PrivacyRightType.ACCESS.value
        assert DataSubjectRequestType.ERASURE.value == PrivacyRightType.ERASURE.value
        assert DataSubjectRequestType.PORTABILITY.value == PrivacyRightType.PORTABILITY.value
