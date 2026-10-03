"""
The R2 archival client is built once per process and shared by every AuditLogger.

Building a boto3 client is expensive: without explicit credentials botocore walks
the default credential chain, which includes network probes of the instance
metadata endpoint. Routers and services build an AuditLogger per request, so the
client must be built at most once, and never when R2 is not configured.
"""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AuditLogger, get_shared_r2_client

R2_ENDPOINT = "https://example-account.r2.cloudflarestorage.com"


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def fresh_shared_client(monkeypatch):
    """Each test starts with no cached client."""
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)


@pytest.fixture
def r2_configured(monkeypatch):
    settings = audit_logger_module.settings
    monkeypatch.setattr(settings, "R2_ENDPOINT", R2_ENDPOINT)
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key-id")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-access-key")
    return settings


@pytest.fixture
def r2_not_configured(monkeypatch):
    settings = audit_logger_module.settings
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", None)
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", None)
    return settings


@pytest.fixture
def boto3_client():
    with patch.object(audit_logger_module.boto3, "client") as factory:
        factory.side_effect = lambda *args, **kwargs: MagicMock(name="r2-client")
        yield factory


class TestSharedClientWhenConfigured:
    def test_one_client_serves_many_loggers(self, mock_db, r2_configured, boto3_client):
        loggers = [AuditLogger(mock_db) for _ in range(50)]

        assert boto3_client.call_count == 1
        first = loggers[0].r2_client
        assert first is not None
        assert all(logger.r2_client is first for logger in loggers)

    def test_client_uses_the_configured_endpoint_and_credentials(
        self, mock_db, r2_configured, boto3_client
    ):
        AuditLogger(mock_db)

        boto3_client.assert_called_once_with(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id="test-access-key-id",
            aws_secret_access_key="test-secret-access-key",
            region_name="auto",
        )

    def test_client_is_built_lazily_not_at_import(self, r2_configured, boto3_client):
        assert audit_logger_module._shared_r2_client is None
        assert boto3_client.call_count == 0

        get_shared_r2_client()

        assert boto3_client.call_count == 1

    def test_changed_settings_build_a_new_client(
        self, mock_db, r2_configured, boto3_client, monkeypatch
    ):
        before = AuditLogger(mock_db).r2_client
        monkeypatch.setattr(r2_configured, "R2_ENDPOINT", "https://other.r2.cloudflarestorage.com")
        after = AuditLogger(mock_db).r2_client

        assert boto3_client.call_count == 2
        assert after is not before
        assert AuditLogger(mock_db).r2_client is after
        assert boto3_client.call_count == 2

    def test_concurrent_first_use_builds_one_client(self, r2_configured, boto3_client):
        start = threading.Barrier(8)
        results = []

        def build():
            start.wait()
            results.append(get_shared_r2_client())

        threads = [threading.Thread(target=build) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert boto3_client.call_count == 1
        assert len(results) == 8
        assert all(client is results[0] for client in results)

    def test_injected_client_wins_and_builds_nothing(self, mock_db, r2_configured, boto3_client):
        injected = MagicMock()

        logger = AuditLogger(mock_db, r2_client=injected)

        assert logger.r2_client is injected
        assert boto3_client.call_count == 0


class TestNoClientWhenNotConfigured:
    def test_no_client_is_built(self, mock_db, r2_not_configured, boto3_client):
        loggers = [AuditLogger(mock_db) for _ in range(10)]

        assert boto3_client.call_count == 0
        assert all(logger.r2_client is None for logger in loggers)
        assert get_shared_r2_client() is None

    def test_credentials_without_an_endpoint_build_nothing(
        self, mock_db, r2_configured, boto3_client, monkeypatch
    ):
        monkeypatch.setattr(r2_configured, "R2_ENDPOINT", None)

        assert AuditLogger(mock_db).r2_client is None
        assert boto3_client.call_count == 0

    async def test_flush_without_a_client_neither_archives_nor_stores(
        self, mock_db, r2_not_configured, boto3_client
    ):
        logger = AuditLogger(mock_db)
        logger.buffer = [{"event_id": "1"}, {"event_id": "2"}]

        with (
            patch.object(logger, "_store_entry", new_callable=AsyncMock) as store,
            patch.object(logger, "_archive_to_r2", new_callable=AsyncMock) as archive,
        ):
            await logger._flush_buffer()

        # Entries are stored when logged; a flush only archives.
        store.assert_not_awaited()
        archive.assert_not_awaited()
        assert logger.buffer == []

    async def test_archive_without_a_client_is_a_no_op(
        self, mock_db, r2_not_configured, boto3_client
    ):
        logger = AuditLogger(mock_db)

        await logger._archive_to_r2(
            [{"tenant_id": "tenant-1", "timestamp": "2026-01-01T00:00:00", "event_id": "1"}]
        )

        assert boto3_client.call_count == 0
