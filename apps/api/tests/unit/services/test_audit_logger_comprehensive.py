"""
Comprehensive tests for AuditLogger service
Target: 95%+ coverage (from 54% baseline)
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.audit_logger import AuditEventType, AuditLogger, AuditMiddleware

pytestmark = pytest.mark.asyncio


class TestAuditLoggerInitialization:
    """Test AuditLogger initialization"""

    async def test_init_with_custom_r2_client(self):
        """Test initialization with custom R2 client"""
        mock_db = AsyncMock()
        mock_r2 = Mock()

        logger = AuditLogger(db=mock_db, r2_client=mock_r2)

        assert logger.db == mock_db
        assert logger.r2_client == mock_r2
        assert logger.buffer == []
        assert logger.buffer_size == 100
        assert logger.flush_interval == 60
        assert logger._flush_task is None

    async def test_init_creates_r2_client_when_none(self):
        """Test R2 client is created when not provided"""
        mock_db = AsyncMock()

        with patch("app.services.audit_logger.boto3.client") as mock_boto:
            mock_boto.return_value = Mock()
            logger = AuditLogger(db=mock_db, r2_client=None)

            assert logger.r2_client is not None
            mock_boto.assert_called_once()


class TestAuditLoggerCoreLogging:
    """Test core logging functionality"""

    @pytest.fixture
    def audit_logger(self):
        """Create AuditLogger instance with mocks"""
        mock_db = AsyncMock()
        mock_r2 = Mock()
        logger = AuditLogger(db=mock_db, r2_client=mock_r2)
        return logger

    async def test_log_creates_event_with_all_fields(self, audit_logger):
        """Test log method creates complete audit entry"""
        # Mock dependencies
        audit_logger._get_previous_hash = AsyncMock(return_value="prev_hash_123")
        audit_logger._store_entry = AsyncMock()

        event_id = await audit_logger.log(
            event_type=AuditEventType.AUTH_SIGNIN,
            tenant_id="tenant_123",
            identity_id="user_123",
            organization_id="org_123",
            resource_type="api",
            resource_id="res_123",
            details={"action": "login"},
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
            severity="info",
            compliance_context={"framework": "GDPR"},
            data_subject_id="subject_123",
            legal_basis="consent",
            retention_period=365,
        )

        assert event_id is not None
        assert len(audit_logger.buffer) == 1

        entry = audit_logger.buffer[0]
        assert entry["event_type"] == AuditEventType.AUTH_SIGNIN
        assert entry["tenant_id"] == "tenant_123"
        assert entry["identity_id"] == "user_123"
        assert entry["organization_id"] == "org_123"
        assert entry["resource_type"] == "api"
        assert entry["resource_id"] == "res_123"
        assert entry["details"] == {"action": "login"}
        assert entry["ip_address"] == "127.0.0.1"
        assert entry["user_agent"] == "Mozilla/5.0"
        assert entry["severity"] == "info"
        assert entry["compliance_context"] == {"framework": "GDPR"}
        assert entry["data_subject_id"] == "subject_123"
        assert entry["legal_basis"] == "consent"
        assert entry["retention_period"] == 365
        assert entry["previous_hash"] == "prev_hash_123"
        assert "hash" in entry
        assert "timestamp" in entry

    async def test_log_critical_event_stores_immediately(self, audit_logger):
        """Test critical severity events are stored immediately"""
        audit_logger._get_previous_hash = AsyncMock(return_value=None)
        audit_logger._store_entry = AsyncMock()

        await audit_logger.log(
            event_type=AuditEventType.SECURITY_THREAT_DETECTED,
            tenant_id="tenant_123",
            severity="critical",
        )

        # Should have called _store_entry immediately
        audit_logger._store_entry.assert_called_once()

    async def test_log_high_severity_stores_immediately(self, audit_logger):
        """Test high severity events are stored immediately"""
        audit_logger._get_previous_hash = AsyncMock(return_value=None)
        audit_logger._store_entry = AsyncMock()

        await audit_logger.log(
            event_type=AuditEventType.SECURITY_BRUTE_FORCE, tenant_id="tenant_123", severity="high"
        )

        audit_logger._store_entry.assert_called_once()

    async def test_log_flushes_when_buffer_full(self, audit_logger):
        """Test buffer flushes when reaching buffer_size"""
        audit_logger._get_previous_hash = AsyncMock(return_value=None)
        audit_logger._store_entry = AsyncMock()
        audit_logger._flush_buffer = AsyncMock()
        audit_logger.buffer_size = 2

        # Add entries to fill buffer
        await audit_logger.log(event_type=AuditEventType.AUTH_SIGNIN, tenant_id="tenant_123")
        await audit_logger.log(event_type=AuditEventType.AUTH_SIGNOUT, tenant_id="tenant_123")

        # Should trigger flush
        audit_logger._flush_buffer.assert_called()


class TestAuditLoggerHashing:
    """Test hash calculation and integrity"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        return AuditLogger(db=mock_db, r2_client=mock_r2)

    def test_calculate_hash_deterministic(self, audit_logger):
        """Test hash calculation is deterministic"""
        entry = {
            "event_id": "evt_123",
            "event_type": "auth.signin",
            "tenant_id": "tenant_123",
            "identity_id": "user_123",
            "timestamp": "2024-01-01T00:00:00",
            "previous_hash": "prev_hash",
        }

        hash1 = audit_logger._calculate_hash(entry)
        hash2 = audit_logger._calculate_hash(entry)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

    def test_calculate_hash_changes_with_data(self, audit_logger):
        """Test hash changes when data changes"""
        entry1 = {
            "event_id": "evt_123",
            "event_type": "auth.signin",
            "tenant_id": "tenant_123",
            "identity_id": "user_123",
            "timestamp": "2024-01-01T00:00:00",
            "previous_hash": "prev_hash",
        }

        entry2 = {**entry1, "event_id": "evt_456"}

        hash1 = audit_logger._calculate_hash(entry1)
        hash2 = audit_logger._calculate_hash(entry2)

        assert hash1 != hash2

    async def test_get_previous_hash_returns_latest(self, audit_logger):
        """Test getting previous hash from database"""
        # Mock database result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = "previous_hash_value"
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        hash_value = await audit_logger._get_previous_hash("tenant_123")

        assert hash_value == "previous_hash_value"
        audit_logger.db.execute.assert_called_once()

    async def test_get_previous_hash_returns_none_when_no_logs(self, audit_logger):
        """Test getting previous hash when no logs exist"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        hash_value = await audit_logger._get_previous_hash("tenant_123")

        assert hash_value is None


class TestAuditLoggerBuffering:
    """Test buffering and flushing functionality"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        return AuditLogger(db=mock_db, r2_client=mock_r2)

    async def test_store_entry_creates_audit_log(self, audit_logger):
        """Test storing entry creates AuditLog model"""
        entry = {
            "event_id": "evt_123",
            "event_type": "auth.signin",
            "tenant_id": "tenant_123",
            "identity_id": "user_123",
            "resource_type": "api",
            "resource_id": "res_123",
            "details": {"action": "login"},
            "ip_address": "127.0.0.1",
            "user_agent": "Mozilla/5.0",
            "hash": "hash_value",
            "previous_hash": "prev_hash",
            "timestamp": "2024-01-01T12:00:00",
        }

        audit_logger.db.add = Mock()
        audit_logger.db.commit = AsyncMock()

        await audit_logger._store_entry(entry)

        audit_logger.db.add.assert_called_once()
        audit_logger.db.commit.assert_called_once()

    async def test_flush_buffer_clears_buffer(self, audit_logger):
        """Test flush clears the buffer"""
        # Add entries to buffer
        audit_logger.buffer = [
            {
                "event_id": "1",
                "event_type": "auth.signin",
                "tenant_id": "t1",
                "timestamp": "2024-01-01T12:00:00",
                "hash": "h1",
                "previous_hash": None,
            },
            {
                "event_id": "2",
                "event_type": "auth.signin",
                "tenant_id": "t1",
                "timestamp": "2024-01-01T12:00:00",
                "hash": "h2",
                "previous_hash": None,
            },
        ]

        audit_logger._store_entry = AsyncMock()
        audit_logger._archive_to_r2 = AsyncMock()

        with patch("app.services.audit_logger.settings") as mock_settings:
            mock_settings.R2_AUDIT_BUCKET = "audit-bucket"
            await audit_logger._flush_buffer()

        assert len(audit_logger.buffer) == 0

    async def test_flush_buffer_stores_all_entries(self, audit_logger):
        """Test flush stores all buffered entries"""
        entries = [
            {
                "event_id": f"evt_{i}",
                "event_type": "auth.signin",
                "tenant_id": "tenant_123",
                "timestamp": "2024-01-01T12:00:00",
                "hash": f"hash_{i}",
                "previous_hash": None,
            }
            for i in range(3)
        ]
        audit_logger.buffer = entries.copy()

        audit_logger._store_entry = AsyncMock()
        audit_logger._archive_to_r2 = AsyncMock()

        await audit_logger._flush_buffer()

        assert audit_logger._store_entry.call_count == 3

    async def test_flush_buffer_handles_database_error(self, audit_logger):
        """Test flush handles database errors gracefully"""
        audit_logger.buffer = [
            {
                "event_id": "evt_1",
                "hash": "h1",
                "tenant_id": "t1",
                "timestamp": "2024-01-01T12:00:00",
            }
        ]

        audit_logger._store_entry = AsyncMock(side_effect=Exception("DB error"))
        audit_logger._archive_to_r2 = AsyncMock()

        # Should not raise, but re-add to buffer
        await audit_logger._flush_buffer()

        # Buffer should have entry back for retry
        assert len(audit_logger.buffer) > 0


class TestAuditLoggerR2Archival:
    """Test R2 archival functionality"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        logger = AuditLogger(db=mock_db, r2_client=mock_r2)
        return logger

    async def test_archive_to_r2_groups_by_tenant_and_date(self, audit_logger):
        """Test archival groups entries by tenant and date"""
        entries = [
            {"tenant_id": "tenant_1", "timestamp": "2024-01-01T12:00:00", "event_id": "evt_1"},
            {"tenant_id": "tenant_1", "timestamp": "2024-01-01T13:00:00", "event_id": "evt_2"},
            {"tenant_id": "tenant_2", "timestamp": "2024-01-01T12:00:00", "event_id": "evt_3"},
        ]

        with patch.object(audit_logger.r2_client, "put_object") as mock_put:
            with patch("app.services.audit_logger.settings") as mock_settings:
                mock_settings.R2_AUDIT_BUCKET = "audit-bucket"

                await audit_logger._archive_to_r2(entries)

                # Should have 2 calls: tenant_1/2024-01-01 (2 entries), tenant_2/2024-01-01 (1 entry)
                assert mock_put.call_count == 2

    async def test_archive_to_r2_uploads_with_metadata(self, audit_logger):
        """Test R2 upload includes metadata"""
        entries = [
            {
                "tenant_id": "tenant_1",
                "timestamp": "2024-01-01T12:00:00",
                "event_id": "evt_1",
                "event_type": "auth.signin",
            }
        ]

        with patch.object(audit_logger.r2_client, "put_object") as mock_put:
            with patch("app.services.audit_logger.settings") as mock_settings:
                mock_settings.R2_AUDIT_BUCKET = "audit-bucket"

                await audit_logger._archive_to_r2(entries)

                call_kwargs = mock_put.call_args[1]
                assert call_kwargs["Bucket"] == "audit-bucket"
                assert "audit/tenant_1/2024-01-01/" in call_kwargs["Key"]
                assert call_kwargs["ContentType"] == "application/json"
                assert call_kwargs["Metadata"]["tenant_id"] == "tenant_1"
                assert call_kwargs["Metadata"]["date"] == "2024-01-01"
                assert call_kwargs["Metadata"]["count"] == "1"

    async def test_archive_to_r2_handles_client_error(self, audit_logger):
        """Test R2 archival handles ClientError gracefully"""
        entries = [
            {"tenant_id": "tenant_1", "timestamp": "2024-01-01T12:00:00", "event_id": "evt_1"}
        ]

        audit_logger.r2_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Server error"}}, "PutObject"
        )

        with patch("app.services.audit_logger.settings") as mock_settings:
            mock_settings.R2_AUDIT_BUCKET = "audit-bucket"

            # Should not raise
            await audit_logger._archive_to_r2(entries)

    async def test_archive_to_r2_skips_when_no_entries(self, audit_logger):
        """Test archival skips when entries list is empty"""
        with patch.object(audit_logger.r2_client, "put_object") as mock_put:
            await audit_logger._archive_to_r2([])

            mock_put.assert_not_called()


class TestAuditLoggerIntegrity:
    """Test integrity verification"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        return AuditLogger(db=mock_db, r2_client=mock_r2)

    async def test_verify_integrity_valid_chain(self, audit_logger):
        """Test integrity verification with valid hash chain"""
        # Create mock logs with valid hash chain
        mock_logs = []
        prev_hash = None

        for i in range(3):
            log = Mock()
            log.id = f"evt_{i}"
            log.event_type = "auth.signin"
            log.tenant_id = "tenant_123"
            log.user_id = f"user_{i}"
            log.timestamp = datetime(2024, 1, 1, 12, i, 0)
            log.previous_hash = prev_hash

            # Calculate proper hash
            entry = {
                "event_id": str(log.id),
                "event_type": log.event_type,
                "tenant_id": str(log.tenant_id),
                "identity_id": str(log.user_id),
                "timestamp": log.timestamp.isoformat(),
                "previous_hash": log.previous_hash,
            }
            log.current_hash = audit_logger._calculate_hash(entry)
            prev_hash = log.current_hash

            mock_logs.append(log)

        # Mock database
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        result = await audit_logger.verify_integrity("tenant_123")

        assert result["valid"] is True
        assert result["count"] == 3
        assert result["broken_at"] is None

    async def test_verify_integrity_broken_chain(self, audit_logger):
        """Test integrity verification detects broken chain"""
        # Create first log with proper hash
        log1 = Mock()
        log1.id = "evt_1"
        log1.event_type = "auth.signin"
        log1.tenant_id = "tenant_123"
        log1.user_id = "user_1"
        log1.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        log1.previous_hash = None

        # Calculate proper hash for log1
        entry1 = {
            "event_id": str(log1.id),
            "event_type": log1.event_type,
            "tenant_id": str(log1.tenant_id),
            "identity_id": str(log1.user_id),
            "timestamp": log1.timestamp.isoformat(),
            "previous_hash": log1.previous_hash,
        }
        log1.current_hash = audit_logger._calculate_hash(entry1)

        # Create second log with WRONG previous hash (broken chain)
        log2 = Mock()
        log2.id = "evt_2"
        log2.event_type = "auth.signin"
        log2.tenant_id = "tenant_123"
        log2.user_id = "user_2"
        log2.timestamp = datetime(2024, 1, 1, 12, 1, 0)
        log2.previous_hash = "wrong_hash_breaks_chain"  # This should be log1.current_hash

        # Calculate proper hash for log2
        entry2 = {
            "event_id": str(log2.id),
            "event_type": log2.event_type,
            "tenant_id": str(log2.tenant_id),
            "identity_id": str(log2.user_id),
            "timestamp": log2.timestamp.isoformat(),
            "previous_hash": log2.previous_hash,
        }
        log2.current_hash = audit_logger._calculate_hash(entry2)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [log1, log2]
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        result = await audit_logger.verify_integrity("tenant_123")

        assert result["valid"] is False
        assert result["broken_at"] == 1

    async def test_verify_integrity_no_logs(self, audit_logger):
        """Test integrity verification with no logs"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        result = await audit_logger.verify_integrity("tenant_123")

        assert result["valid"] is True
        assert result["count"] == 0
        assert "No logs found" in result["message"]


class TestAuditLoggerExport:
    """Test log export functionality"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        return AuditLogger(db=mock_db, r2_client=mock_r2)

    async def test_export_logs_generates_json(self, audit_logger):
        """Test export generates JSON format"""
        # Mock logs
        mock_log = Mock()
        mock_log.id = "evt_123"
        mock_log.event_type = "auth.signin"
        mock_log.user_id = "user_123"
        mock_log.resource_type = "api"
        mock_log.resource_id = "res_123"
        mock_log.details = {"action": "login"}
        mock_log.ip_address = "127.0.0.1"
        mock_log.user_agent = "Mozilla/5.0"
        mock_log.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_log.current_hash = "hash_123"

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        # Mock R2
        audit_logger.r2_client.put_object = Mock()
        audit_logger.r2_client.generate_presigned_url = Mock(return_value="https://presigned-url")

        with patch("app.services.audit_logger.settings") as mock_settings:
            mock_settings.R2_AUDIT_BUCKET = "audit-bucket"

            url = await audit_logger.export_logs(
                tenant_id="tenant_123",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
                format="json",
            )

            assert url == "https://presigned-url"
            audit_logger.r2_client.put_object.assert_called_once()

    async def test_export_logs_handles_r2_error(self, audit_logger):
        """Test export handles R2 errors"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        audit_logger.db.execute = AsyncMock(return_value=mock_result)

        audit_logger.r2_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Error"}}, "PutObject"
        )

        with patch("app.services.audit_logger.settings") as mock_settings:
            mock_settings.R2_AUDIT_BUCKET = "audit-bucket"

            with pytest.raises(ClientError):
                await audit_logger.export_logs(
                    tenant_id="tenant_123",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                )


class TestAuditLoggerSpecializedMethods:
    """Test specialized logging methods"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        logger = AuditLogger(db=mock_db, r2_client=mock_r2)
        logger.log = AsyncMock()  # Mock the main log method
        return logger

    async def test_log_authentication(self, audit_logger):
        """Test authentication event logging"""
        await audit_logger.log_authentication(
            user_id="user_123",
            event_type="signin",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
        )

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.AUTH_SIGNIN
        assert call_kwargs["identity_id"] == "user_123"
        assert call_kwargs["ip_address"] == "127.0.0.1"
        assert call_kwargs["user_agent"] == "Mozilla/5.0"

    async def test_log_authorization(self, audit_logger):
        """Test authorization event logging"""
        await audit_logger.log_authorization(
            user_id="user_123", resource="api/users", action="read", ip_address="127.0.0.1"
        )

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.SECURITY_ACCESS_DENIED
        assert call_kwargs["identity_id"] == "user_123"
        assert call_kwargs["details"]["resource"] == "api/users"
        assert call_kwargs["details"]["action"] == "read"

    async def test_log_data_access(self, audit_logger):
        """Test data access event logging"""
        await audit_logger.log_data_access(
            user_id="user_123",
            resource_type="user_profile",
            resource_id="profile_456",
            action="update",
        )

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args[1]
        assert call_kwargs["identity_id"] == "user_123"
        assert call_kwargs["resource_type"] == "user_profile"
        assert call_kwargs["resource_id"] == "profile_456"

    async def test_log_security_event(self, audit_logger):
        """Test security event logging"""
        await audit_logger.log_security_event(
            event_type="brute_force_attempt",
            user_id="user_123",
            details={"attempts": 5},
            severity="high",
        )

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args[1]
        assert call_kwargs["event_type"] == AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY
        assert call_kwargs["severity"] == "high"
        assert call_kwargs["details"]["security_event_type"] == "brute_force_attempt"


class TestAuditMiddleware:
    """Test AuditMiddleware for request/response logging"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        logger = AuditLogger(db=mock_db, r2_client=mock_r2)
        logger.log = AsyncMock()
        return logger

    @pytest.fixture
    def middleware(self, audit_logger):
        return AuditMiddleware(audit_logger)

    async def test_middleware_logs_api_requests(self, middleware, audit_logger):
        """Test middleware logs API requests"""
        # Mock request
        mock_request = Mock()
        mock_request.url.path = "/api/users"
        mock_request.method = "GET"
        mock_request.headers = {"X-Tenant-ID": "tenant_123", "User-Agent": "Mozilla/5.0"}
        mock_request.client.host = "127.0.0.1"
        mock_request.query_params = {"page": "1"}
        mock_request.state.identity_id = "user_123"

        # Mock call_next
        async def mock_call_next(request):
            return Mock()

        await middleware(mock_request, mock_call_next)

        audit_logger.log.assert_called_once()

    async def test_middleware_skips_excluded_paths(self, middleware, audit_logger):
        """Test middleware skips health check and docs endpoints"""
        for excluded_path in ["/health", "/ready", "/docs", "/openapi.json"]:
            mock_request = Mock()
            mock_request.url.path = excluded_path

            async def mock_call_next(request):
                return Mock()

            await middleware(mock_request, mock_call_next)

        # Should not have logged anything
        audit_logger.log.assert_not_called()

    async def test_middleware_handles_missing_tenant_id(self, middleware, audit_logger):
        """Test middleware handles missing tenant ID"""
        mock_request = Mock()
        mock_request.url.path = "/api/users"
        mock_request.method = "GET"
        mock_request.headers = {"User-Agent": "Mozilla/5.0"}
        mock_request.client.host = "127.0.0.1"
        mock_request.query_params = {}
        mock_request.state = Mock(spec=[])  # No identity_id

        async def mock_call_next(request):
            return Mock()

        await middleware(mock_request, mock_call_next)

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args[1]
        assert call_kwargs["tenant_id"] == "unknown"


class TestCompleteAuditLogger:
    """Integration tests for complete AuditLogger workflows"""

    @pytest.fixture
    def audit_logger(self):
        mock_db = AsyncMock()
        mock_r2 = Mock()
        return AuditLogger(db=mock_db, r2_client=mock_r2)

    async def test_complete_logging_workflow(self, audit_logger):
        """Test complete workflow: log -> buffer -> flush -> archive"""
        audit_logger._get_previous_hash = AsyncMock(return_value=None)
        audit_logger._store_entry = AsyncMock()
        audit_logger._archive_to_r2 = AsyncMock()
        audit_logger.buffer_size = 2

        # Log first event
        event_id_1 = await audit_logger.log(
            event_type=AuditEventType.AUTH_SIGNIN, tenant_id="tenant_123", identity_id="user_123"
        )

        assert event_id_1 is not None
        assert len(audit_logger.buffer) == 1

        # Log second event (should trigger flush)
        event_id_2 = await audit_logger.log(
            event_type=AuditEventType.AUTH_SIGNOUT, tenant_id="tenant_123", identity_id="user_123"
        )

        assert event_id_2 is not None

    async def test_hash_chain_continuity(self, audit_logger):
        """Test hash chain maintains continuity across multiple events"""
        previous_hashes = [None]

        async def mock_get_previous_hash(tenant_id):
            return previous_hashes[-1]

        audit_logger._get_previous_hash = mock_get_previous_hash
        audit_logger._store_entry = AsyncMock()

        # Log multiple events
        for i in range(3):
            await audit_logger.log(
                event_type=AuditEventType.USER_UPDATE,
                tenant_id="tenant_123",
                identity_id=f"user_{i}",
            )

            # Get hash from buffered entry
            if audit_logger.buffer:
                previous_hashes.append(audit_logger.buffer[-1]["hash"])

        # Verify chain
        for i, entry in enumerate(audit_logger.buffer):
            if i == 0:
                assert entry["previous_hash"] is None
            else:
                assert entry["previous_hash"] == audit_logger.buffer[i - 1]["hash"]
