"""
Comprehensive Audit Logger Test Suite
Tests for audit logging with hash chain integrity and R2 archival
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditMiddleware,
    AuditAction,
)

pytestmark = pytest.mark.asyncio


class TestAuditEventType:
    """Test AuditEventType enum."""

    def test_auth_signin_value(self):
        """Test AUTH_SIGNIN event type."""
        assert AuditEventType.AUTH_SIGNIN.value == "auth.signin"

    def test_auth_signout_value(self):
        """Test AUTH_SIGNOUT event type."""
        assert AuditEventType.AUTH_SIGNOUT.value == "auth.signout"

    def test_auth_signup_value(self):
        """Test AUTH_SIGNUP event type."""
        assert AuditEventType.AUTH_SIGNUP.value == "auth.signup"

    def test_session_create_value(self):
        """Test SESSION_CREATE event type."""
        assert AuditEventType.SESSION_CREATE.value == "session.create"

    def test_user_create_value(self):
        """Test USER_CREATE event type."""
        assert AuditEventType.USER_CREATE.value == "user.create"

    def test_org_create_value(self):
        """Test ORG_CREATE event type."""
        assert AuditEventType.ORG_CREATE.value == "org.create"

    def test_security_threat_detected_value(self):
        """Test SECURITY_THREAT_DETECTED event type."""
        assert AuditEventType.SECURITY_THREAT_DETECTED.value == "security.threat_detected"

    def test_billing_subscription_create_value(self):
        """Test BILLING_SUBSCRIPTION_CREATE event type."""
        assert AuditEventType.BILLING_SUBSCRIPTION_CREATE.value == "billing.subscription_create"

    def test_gdpr_consent_given_value(self):
        """Test GDPR_CONSENT_GIVEN event type."""
        assert AuditEventType.GDPR_CONSENT_GIVEN.value == "gdpr.consent_given"

    def test_gdpr_data_export_value(self):
        """Test GDPR_DATA_EXPORT event type."""
        assert AuditEventType.GDPR_DATA_EXPORT.value == "gdpr.data_export"

    def test_gdpr_data_deletion_value(self):
        """Test GDPR_DATA_DELETION event type."""
        assert AuditEventType.GDPR_DATA_DELETION.value == "gdpr.data_deletion"

    def test_soc2_access_granted_value(self):
        """Test SOC2_ACCESS_GRANTED event type."""
        assert AuditEventType.SOC2_ACCESS_GRANTED.value == "soc2.access_granted"

    def test_hipaa_phi_access_value(self):
        """Test HIPAA_PHI_ACCESS event type."""
        assert AuditEventType.HIPAA_PHI_ACCESS.value == "hipaa.phi_access"

    def test_audit_action_alias(self):
        """Test AuditAction is an alias for AuditEventType."""
        assert AuditAction is AuditEventType


class TestAuditLoggerInitialization:
    """Test AuditLogger initialization."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    def test_initialization_with_db(self, mock_db):
        """Test logger initialization with database."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            logger = AuditLogger(mock_db)

        assert logger.db is mock_db
        assert logger.buffer == []
        assert logger.buffer_size == 100
        assert logger.flush_interval == 60

    def test_initialization_with_custom_r2_client(self, mock_db):
        """Test logger initialization with custom R2 client."""
        mock_r2 = MagicMock()

        logger = AuditLogger(mock_db, r2_client=mock_r2)

        assert logger.r2_client is mock_r2

    def test_initialization_buffer_defaults(self, mock_db):
        """Test buffer defaults are set correctly."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            logger = AuditLogger(mock_db)

        assert isinstance(logger.buffer, list)
        assert len(logger.buffer) == 0

    def test_initialization_flush_task_none(self, mock_db):
        """Test flush task is None initially."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            logger = AuditLogger(mock_db)

        assert logger._flush_task is None


class TestHashCalculation:
    """Test hash calculation for audit entries."""

    @pytest.fixture
    def logger(self):
        """Create AuditLogger instance."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            return AuditLogger(AsyncMock())

    def test_calculate_hash_returns_string(self, logger):
        """Test hash calculation returns a string."""
        entry = {
            "event_id": str(uuid4()),
            "event_type": AuditEventType.AUTH_SIGNIN,
            "tenant_id": "test-tenant",
            "identity_id": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "previous_hash": None,
        }

        result = logger._calculate_hash(entry)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest

    def test_calculate_hash_deterministic(self, logger):
        """Test hash calculation is deterministic."""
        entry = {
            "event_id": "fixed-id",
            "event_type": AuditEventType.AUTH_SIGNIN,
            "tenant_id": "test-tenant",
            "identity_id": "user-id",
            "timestamp": "2024-01-15T10:00:00",
            "previous_hash": None,
        }

        hash1 = logger._calculate_hash(entry)
        hash2 = logger._calculate_hash(entry)

        assert hash1 == hash2

    def test_calculate_hash_different_entries(self, logger):
        """Test different entries produce different hashes."""
        entry1 = {
            "event_id": str(uuid4()),
            "event_type": AuditEventType.AUTH_SIGNIN,
            "tenant_id": "tenant-1",
            "identity_id": "user-1",
            "timestamp": "2024-01-15T10:00:00",
            "previous_hash": None,
        }

        entry2 = {
            "event_id": str(uuid4()),
            "event_type": AuditEventType.AUTH_SIGNOUT,
            "tenant_id": "tenant-2",
            "identity_id": "user-2",
            "timestamp": "2024-01-15T10:00:00",
            "previous_hash": None,
        }

        hash1 = logger._calculate_hash(entry1)
        hash2 = logger._calculate_hash(entry2)

        assert hash1 != hash2

    def test_calculate_hash_includes_previous_hash(self, logger):
        """Test hash includes previous hash for chain integrity."""
        entry1 = {
            "event_id": "fixed-id",
            "event_type": AuditEventType.AUTH_SIGNIN,
            "tenant_id": "test-tenant",
            "identity_id": "user-id",
            "timestamp": "2024-01-15T10:00:00",
            "previous_hash": None,
        }

        entry2 = {
            "event_id": "fixed-id",
            "event_type": AuditEventType.AUTH_SIGNIN,
            "tenant_id": "test-tenant",
            "identity_id": "user-id",
            "timestamp": "2024-01-15T10:00:00",
            "previous_hash": "abc123def456",
        }

        hash1 = logger._calculate_hash(entry1)
        hash2 = logger._calculate_hash(entry2)

        assert hash1 != hash2


class TestLogMethod:
    """Test the main log method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.fixture
    def logger(self, mock_db):
        """Create AuditLogger instance."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            return AuditLogger(mock_db)

    async def test_log_returns_event_id(self, logger):
        """Test log returns event ID."""
        # Patch _get_previous_hash to avoid AuditLog model access
        with patch.object(logger, "_get_previous_hash", return_value=None):
            result = await logger.log(
                event_type=AuditEventType.AUTH_SIGNIN,
                tenant_id="test-tenant",
                identity_id="user-123",
            )

        assert isinstance(result, str)
        assert len(result) == 36  # UUID format

    async def test_log_adds_to_buffer(self, logger):
        """Test log adds entry to buffer."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            await logger.log(
                event_type=AuditEventType.AUTH_SIGNIN,
                tenant_id="test-tenant",
            )

        assert len(logger.buffer) == 1

    async def test_log_entry_has_required_fields(self, logger):
        """Test logged entry has all required fields."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            await logger.log(
                event_type=AuditEventType.AUTH_SIGNIN,
                tenant_id="test-tenant",
                identity_id="user-123",
            )

        entry = logger.buffer[0]
        assert "event_id" in entry
        assert "event_type" in entry
        assert "tenant_id" in entry
        assert "timestamp" in entry
        assert "hash" in entry

    async def test_log_with_all_parameters(self, logger):
        """Test log with all optional parameters."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            with patch.object(logger, "_store_entry", new_callable=AsyncMock):  # Patch to avoid AuditLog creation
                _ = await logger.log(
                    event_type=AuditEventType.AUTH_SIGNIN,
                    tenant_id="test-tenant",
                    identity_id="user-123",
                    organization_id="org-456",
                    resource_type="user",
                    resource_id="resource-789",
                    details={"key": "value"},
                    ip_address="192.168.1.1",
                    user_agent="Mozilla/5.0",
                    severity="high",
                    compliance_context={"framework": "GDPR"},
                    data_subject_id="subject-123",
                    legal_basis="consent",
                    retention_period=365,
                )

        entry = logger.buffer[-1]  # Get last entry (high severity may also be stored)
        assert entry["identity_id"] == "user-123"
        assert entry["organization_id"] == "org-456"
        assert entry["resource_type"] == "user"
        assert entry["resource_id"] == "resource-789"
        assert entry["details"] == {"key": "value"}
        assert entry["ip_address"] == "192.168.1.1"
        assert entry["user_agent"] == "Mozilla/5.0"
        assert entry["severity"] == "high"
        assert entry["compliance_context"] == {"framework": "GDPR"}
        assert entry["data_subject_id"] == "subject-123"
        assert entry["legal_basis"] == "consent"
        assert entry["retention_period"] == 365

    async def test_log_critical_severity_stores_immediately(self, logger, mock_db):
        """Test critical severity entries are stored immediately."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            with patch.object(logger, "_store_entry") as mock_store:
                await logger.log(
                    event_type=AuditEventType.SECURITY_THREAT_DETECTED,
                    tenant_id="test-tenant",
                    severity="critical",
                )

                mock_store.assert_called_once()

    async def test_log_high_severity_stores_immediately(self, logger, mock_db):
        """Test high severity entries are stored immediately."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            with patch.object(logger, "_store_entry") as mock_store:
                await logger.log(
                    event_type=AuditEventType.SECURITY_BRUTE_FORCE,
                    tenant_id="test-tenant",
                    severity="high",
                )

                mock_store.assert_called_once()

    async def test_log_info_severity_buffered(self, logger, mock_db):
        """Test info severity entries are only buffered."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            with patch.object(logger, "_store_entry") as mock_store:
                await logger.log(
                    event_type=AuditEventType.AUTH_SIGNIN,
                    tenant_id="test-tenant",
                    severity="info",
                )

                mock_store.assert_not_called()


class TestBufferManagement:
    """Test buffer management and flushing."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.fixture
    def logger(self, mock_db):
        """Create AuditLogger instance with small buffer."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            logger = AuditLogger(mock_db)
            logger.buffer_size = 3  # Small buffer for testing
            return logger

    async def test_buffer_flush_at_capacity(self, logger):
        """Test buffer flushes when capacity reached."""
        with patch.object(logger, "_get_previous_hash", return_value=None):
            with patch.object(logger, "_flush_buffer") as mock_flush:
                # Add entries up to buffer size
                for i in range(3):
                    await logger.log(
                        event_type=AuditEventType.AUTH_SIGNIN,
                        tenant_id="test-tenant",
                    )

                mock_flush.assert_called_once()

    async def test_flush_buffer_clears_buffer(self, logger, mock_db):
        """Test flushing clears the buffer."""
        # Add some entries with all required fields
        logger.buffer = [
            {
                "event_id": "1",
                "hash": "hash1",
                "timestamp": "2024-01-01T00:00:00",
                "event_type": "auth.signin",
                "tenant_id": "test-tenant",
            },
            {
                "event_id": "2",
                "hash": "hash2",
                "timestamp": "2024-01-01T00:00:00",
                "event_type": "auth.signout",
                "tenant_id": "test-tenant",
            },
        ]

        # Patch _store_entry to prevent actual AuditLog creation
        with patch.object(logger, "_store_entry", new_callable=AsyncMock) as mock_store:
            # Mock R2 client and settings to prevent R2 archival
            with patch.object(logger, "r2_client", None):
                await logger._flush_buffer()

        assert len(logger.buffer) == 0
        assert mock_store.call_count == 2

    async def test_flush_empty_buffer(self, logger):
        """Test flushing empty buffer does nothing."""
        logger.buffer = []

        with patch.object(logger, "_store_entry") as mock_store:
            await logger._flush_buffer()

            mock_store.assert_not_called()


class TestConvenienceMethods:
    """Test convenience logging methods."""

    @pytest.fixture
    def logger(self):
        """Create AuditLogger instance."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            return AuditLogger(mock_db)

    async def test_log_authentication(self, logger):
        """Test log_authentication convenience method."""
        with patch.object(logger, "log") as mock_log:
            await logger.log_authentication(
                user_id="user-123",
                event_type="login",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["identity_id"] == "user-123"
            assert call_kwargs["ip_address"] == "192.168.1.1"

    async def test_log_authorization(self, logger):
        """Test log_authorization convenience method."""
        with patch.object(logger, "log") as mock_log:
            await logger.log_authorization(
                user_id="user-123",
                resource="/api/users",
                action="read",
                ip_address="192.168.1.1",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["identity_id"] == "user-123"

    async def test_log_data_access(self, logger):
        """Test log_data_access convenience method."""
        with patch.object(logger, "log") as mock_log:
            await logger.log_data_access(
                user_id="user-123",
                resource_type="user_profile",
                resource_id="profile-456",
                action="read",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["resource_type"] == "user_profile"
            assert call_kwargs["resource_id"] == "profile-456"

    async def test_log_security_event(self, logger):
        """Test log_security_event convenience method."""
        with patch.object(logger, "log") as mock_log:
            await logger.log_security_event(
                event_type="brute_force_attempt",
                user_id="user-123",
                details={"attempts": 10},
                severity="high",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["severity"] == "high"


class TestVerifyIntegrity:
    """Test hash chain integrity verification."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def logger(self, mock_db):
        """Create AuditLogger instance."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            return AuditLogger(mock_db)

    def test_verify_integrity_method_exists(self, logger):
        """Test verify_integrity method exists."""
        assert hasattr(logger, "verify_integrity")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.verify_integrity)

    def test_verify_integrity_accepts_tenant_id(self, logger):
        """Test verify_integrity accepts tenant_id parameter."""
        import inspect
        sig = inspect.signature(logger.verify_integrity)
        assert "tenant_id" in sig.parameters

    def test_verify_integrity_accepts_date_range(self, logger):
        """Test verify_integrity accepts date range parameters."""
        import inspect
        sig = inspect.signature(logger.verify_integrity)
        assert "start_date" in sig.parameters
        assert "end_date" in sig.parameters


class TestAuditMiddleware:
    """Test AuditMiddleware class."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock AuditLogger."""
        logger = MagicMock()
        logger.log = AsyncMock()
        return logger

    @pytest.fixture
    def middleware(self, mock_logger):
        """Create AuditMiddleware instance."""
        return AuditMiddleware(mock_logger)

    def test_middleware_initialization(self, middleware, mock_logger):
        """Test middleware initialization."""
        assert middleware.audit_logger is mock_logger
        assert "/health" in middleware.excluded_paths
        assert "/docs" in middleware.excluded_paths

    def test_excluded_paths_contains_health(self, middleware):
        """Test excluded paths contains health endpoint."""
        assert "/health" in middleware.excluded_paths

    def test_excluded_paths_contains_ready(self, middleware):
        """Test excluded paths contains ready endpoint."""
        assert "/ready" in middleware.excluded_paths

    def test_excluded_paths_contains_jwks(self, middleware):
        """Test excluded paths contains JWKS endpoint."""
        assert "/.well-known/jwks.json" in middleware.excluded_paths

    def test_excluded_paths_contains_docs(self, middleware):
        """Test excluded paths contains docs endpoint."""
        assert "/docs" in middleware.excluded_paths

    def test_excluded_paths_contains_openapi(self, middleware):
        """Test excluded paths contains openapi endpoint."""
        assert "/openapi.json" in middleware.excluded_paths

    async def test_middleware_skips_excluded_paths(self, middleware, mock_logger):
        """Test middleware skips excluded paths."""
        mock_request = MagicMock()
        mock_request.url.path = "/health"
        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await middleware(mock_request, mock_call_next)

        assert result is mock_response
        mock_logger.log.assert_not_called()

    async def test_middleware_logs_api_request(self, middleware, mock_logger):
        """Test middleware logs API requests."""
        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/users"
        mock_request.method = "GET"
        mock_request.query_params = {}
        mock_request.headers = {"X-Tenant-ID": "test-tenant", "User-Agent": "Mozilla/5.0"}
        mock_request.client.host = "192.168.1.1"
        mock_request.state = MagicMock()
        mock_request.state.identity_id = "user-123"

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await middleware(mock_request, mock_call_next)

        assert result is mock_response
        mock_logger.log.assert_called_once()


class TestComplianceLogging:
    """Test compliance-specific logging in middleware."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock AuditLogger."""
        logger = MagicMock()
        logger.log = AsyncMock()
        return logger

    @pytest.fixture
    def middleware(self, mock_logger):
        """Create AuditMiddleware instance."""
        return AuditMiddleware(mock_logger)

    async def test_log_gdpr_consent_given(self, middleware, mock_logger):
        """Test logging GDPR consent given."""
        await middleware.log_gdpr_consent(
            user_id="user-123",
            consent_type="marketing",
            purpose="email_marketing",
            action="given",
            consent_data={"newsletter": True},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            tenant_id="test-tenant",
        )

        mock_logger.log.assert_called_once()
        call_kwargs = mock_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.GDPR_CONSENT_GIVEN
        assert call_kwargs["data_subject_id"] == "user-123"
        assert call_kwargs["legal_basis"] == "consent"

    async def test_log_gdpr_consent_withdrawn(self, middleware, mock_logger):
        """Test logging GDPR consent withdrawn."""
        await middleware.log_gdpr_consent(
            user_id="user-123",
            consent_type="marketing",
            purpose="email_marketing",
            action="withdrawn",
            tenant_id="test-tenant",
        )

        call_kwargs = mock_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.GDPR_CONSENT_WITHDRAWN

    async def test_log_data_subject_request_access(self, middleware, mock_logger):
        """Test logging data subject access request."""
        await middleware.log_data_subject_request(
            user_id="user-123",
            request_type="access",
            data_categories=["personal", "financial"],
            status="received",
            tenant_id="test-tenant",
        )

        mock_logger.log.assert_called_once()
        call_kwargs = mock_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.GDPR_DATA_EXPORT

    async def test_log_data_subject_request_erasure(self, middleware, mock_logger):
        """Test logging data subject erasure request."""
        await middleware.log_data_subject_request(
            user_id="user-123",
            request_type="erasure",
            data_categories=["all"],
            status="processing",
            tenant_id="test-tenant",
        )

        call_kwargs = mock_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.GDPR_DATA_DELETION

    async def test_log_data_subject_request_portability(self, middleware, mock_logger):
        """Test logging data subject portability request."""
        await middleware.log_data_subject_request(
            user_id="user-123",
            request_type="portability",
            data_categories=["personal"],
            status="completed",
            tenant_id="test-tenant",
        )

        call_kwargs = mock_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.GDPR_DATA_PORTABILITY


class TestExportLogs:
    """Test audit log export functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_r2(self):
        """Create mock R2 client."""
        r2 = MagicMock()
        r2.put_object = MagicMock()
        r2.generate_presigned_url = MagicMock(return_value="https://r2.example.com/export.json")
        return r2

    @pytest.fixture
    def logger(self, mock_db, mock_r2):
        """Create AuditLogger instance with mock R2."""
        return AuditLogger(mock_db, r2_client=mock_r2)

    def test_export_logs_method_exists(self, logger):
        """Test export_logs method exists."""
        assert hasattr(logger, "export_logs")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.export_logs)

    def test_export_logs_accepts_tenant_id(self, logger):
        """Test export_logs accepts tenant_id parameter."""
        import inspect
        sig = inspect.signature(logger.export_logs)
        assert "tenant_id" in sig.parameters

    def test_export_logs_accepts_date_range(self, logger):
        """Test export_logs accepts date range parameters."""
        import inspect
        sig = inspect.signature(logger.export_logs)
        assert "start_date" in sig.parameters
        assert "end_date" in sig.parameters

    def test_export_logs_accepts_format(self, logger):
        """Test export_logs accepts format parameter."""
        import inspect
        sig = inspect.signature(logger.export_logs)
        assert "format" in sig.parameters


class TestServiceMethodExistence:
    """Test that required service methods exist."""

    @pytest.fixture
    def logger(self):
        """Create AuditLogger instance."""
        with patch.object(AuditLogger, "_create_r2_client", return_value=MagicMock()):
            return AuditLogger(AsyncMock())

    def test_has_log_method(self, logger):
        """Test logger has log method."""
        assert hasattr(logger, "log")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.log)

    def test_has_verify_integrity_method(self, logger):
        """Test logger has verify_integrity method."""
        assert hasattr(logger, "verify_integrity")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.verify_integrity)

    def test_has_export_logs_method(self, logger):
        """Test logger has export_logs method."""
        assert hasattr(logger, "export_logs")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.export_logs)

    def test_has_log_authentication_method(self, logger):
        """Test logger has log_authentication method."""
        assert hasattr(logger, "log_authentication")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.log_authentication)

    def test_has_log_authorization_method(self, logger):
        """Test logger has log_authorization method."""
        assert hasattr(logger, "log_authorization")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.log_authorization)

    def test_has_log_data_access_method(self, logger):
        """Test logger has log_data_access method."""
        assert hasattr(logger, "log_data_access")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.log_data_access)

    def test_has_log_security_event_method(self, logger):
        """Test logger has log_security_event method."""
        assert hasattr(logger, "log_security_event")
        import asyncio
        assert asyncio.iscoroutinefunction(logger.log_security_event)

    def test_has_calculate_hash_method(self, logger):
        """Test logger has _calculate_hash method."""
        assert hasattr(logger, "_calculate_hash")

    def test_has_flush_buffer_method(self, logger):
        """Test logger has _flush_buffer method."""
        assert hasattr(logger, "_flush_buffer")
        import asyncio
        assert asyncio.iscoroutinefunction(logger._flush_buffer)


class TestAuditLogEncryption:
    """Test audit log details encryption (SOC 2 CF-11)."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def logger(self, mock_db):
        return AuditLogger(mock_db)

    def test_store_entry_has_encryption_logic(self):
        """Test _store_entry method references encryption for CF-11."""
        import inspect

        source = inspect.getsource(AuditLogger._store_entry)
        assert "AUDIT_LOG_ENCRYPTION" in source
        assert "FieldEncryptor" in source
        assert "encrypt_field" in source

    def test_store_entry_checks_encryption_key(self):
        """Test _store_entry checks FIELD_ENCRYPTION_KEY before encrypting."""
        import inspect

        source = inspect.getsource(AuditLogger._store_entry)
        assert "FIELD_ENCRYPTION_KEY" in source
