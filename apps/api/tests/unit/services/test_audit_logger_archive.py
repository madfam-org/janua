"""
Audit archives go only to the dedicated R2_AUDIT_BUCKET, and storing an entry in
the database and archiving it to R2 are independent outcomes.

- Every entry is stored when it is logged; a flush only archives.
- With no R2_AUDIT_BUCKET, nothing is buffered or archived and exports return
  an export id.
- R2_AUDIT_BUCKET equal to CLOUDFLARE_R2_BUCKET (the general upload bucket) is
  refused: no R2 call at all, and one error with a stable code.
- A failed archive leaves the database rows exactly as they were and puts
  nothing back in the buffer.
- A failed store raises from ``log()`` with a stable code; the entry is neither
  buffered nor archived.
"""

import asyncio
import re
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import column

from app.config import Settings
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import (
    AUDIT_ARCHIVE_BUCKET_REFUSED,
    AUDIT_ARCHIVE_FAILED,
    AUDIT_STORE_FAILED,
    AuditEventType,
    AuditLogger,
    get_audit_archive_bucket,
)

AUDIT_BUCKET = "example-audit-archive"
UPLOAD_BUCKET = "example-uploads"
ARCHIVE_KEY = re.compile(
    r"^audit/(?P<tenant>[^/]+)/(?P<date>\d{4}-\d{2}-\d{2})/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$"
)


class _Row:
    """Stands in for the AuditLog ORM row.

    These tests cover the archive path, so they model the table with a plain
    row object and keep ``_store_entry`` itself unpatched. The fake session
    stands for one the logger owns (``owns_session=True``), so ``log()``
    commits each entry. The real model and database, and the caller-owned
    mode (archive only after the caller's commit), are covered by
    test_audit_logger_chain.py.
    """

    def __init__(self, **columns: Any):
        self.__dict__.update(columns)


class _DuplicateKey(Exception):
    pass


class _Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Table:
    """An async session over one table with a primary key on ``id``.

    ``commit`` inserts what was added and raises on a duplicate id, as the
    database would, so a second write of the same entry is visible.
    """

    def __init__(self):
        self.rows: Dict[str, _Row] = {}
        self.inserts = 0
        self.fail_commits = 0
        self._pending: List[_Row] = []

    def add(self, row: _Row) -> None:
        self._pending.append(row)

    def begin_nested(self) -> _Savepoint:
        return _Savepoint()

    async def rollback(self) -> None:
        self._pending = []

    async def commit(self) -> None:
        pending, self._pending = self._pending, []
        if self.fail_commits:
            self.fail_commits -= 1
            raise RuntimeError("database unavailable")
        for row in pending:
            row_id = str(row.id)
            if row_id in self.rows:
                raise _DuplicateKey(row_id)
            self.rows[row_id] = row
            self.inserts += 1

    async def execute(self, *args, **kwargs):
        result = MagicMock()
        result.first.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {row_id: dict(vars(row)) for row_id, row in self.rows.items()}


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    """Each test starts with no cached client and no reported refusal."""
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(audit_logger_module, "_refused_audit_bucket_reported", None)
    monkeypatch.setattr(audit_logger_module, "AuditLog", _Row)
    settings = audit_logger_module.settings
    monkeypatch.setattr(settings, "CLOUDFLARE_R2_BUCKET", UPLOAD_BUCKET)
    monkeypatch.setattr(settings, "R2_AUDIT_BUCKET", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)
    return settings


@pytest.fixture
def dedicated_bucket(isolated_state, monkeypatch):
    monkeypatch.setattr(isolated_state, "R2_AUDIT_BUCKET", AUDIT_BUCKET)


@pytest.fixture
def upload_bucket_as_audit_bucket(isolated_state, monkeypatch):
    monkeypatch.setattr(isolated_state, "R2_AUDIT_BUCKET", UPLOAD_BUCKET)


@pytest.fixture
def table():
    return _Table()


@pytest.fixture
def r2():
    client = MagicMock(name="r2-client")
    client.generate_presigned_url.return_value = "https://r2.example/presigned"
    return client


@pytest.fixture
def log_spy():
    with patch.object(audit_logger_module, "logger") as spy:
        yield spy


def _codes(spy: MagicMock, level: str) -> List[str]:
    return [c.kwargs.get("code") for c in getattr(spy, level).call_args_list]


async def _log_entries(audit: AuditLogger, severities: List[str], tenant="tenant-a") -> List[str]:
    """Log one entry per severity; every entry is stored at log time."""
    ids = []
    with patch.object(audit, "_chain_tail", AsyncMock(return_value=(None, None))):
        for severity in severities:
            ids.append(
                await audit.log(
                    event_type=AuditEventType.USER_UPDATE,
                    tenant_id=tenant,
                    severity=severity,
                )
            )
    return ids


@pytest.fixture
def audit(table, r2):
    logger = AuditLogger(table, r2_client=r2, owns_session=True)
    logger._flush_task = object()  # no periodic flush task in unit tests
    return logger


class TestSetting:
    def test_r2_audit_bucket_is_a_declared_setting_off_by_default(self):
        field = Settings.model_fields["R2_AUDIT_BUCKET"]
        assert field.default is None


class TestBucketResolution:
    def test_unset_means_off(self, isolated_state):
        assert get_audit_archive_bucket() is None

    def test_blank_means_off(self, isolated_state, monkeypatch):
        monkeypatch.setattr(isolated_state, "R2_AUDIT_BUCKET", "   ")
        assert get_audit_archive_bucket() is None

    def test_dedicated_bucket_is_used(self, dedicated_bucket):
        assert get_audit_archive_bucket() == AUDIT_BUCKET

    @pytest.mark.parametrize("value", [UPLOAD_BUCKET, f" {UPLOAD_BUCKET.upper()} "])
    def test_upload_bucket_is_refused_and_reported_once(
        self, isolated_state, monkeypatch, log_spy, value
    ):
        monkeypatch.setattr(isolated_state, "R2_AUDIT_BUCKET", value)

        assert get_audit_archive_bucket() is None
        assert get_audit_archive_bucket() is None

        assert _codes(log_spy, "error") == [AUDIT_ARCHIVE_BUCKET_REFUSED]


class TestNoBucket:
    async def test_flush_stores_and_archives_nothing(self, audit, table, r2):
        ids = await _log_entries(audit, ["info", "info"])

        await audit._flush_buffer()

        assert set(table.rows) == set(ids)
        assert r2.method_calls == []
        assert audit.buffer == []

    async def test_archive_call_is_a_no_op(self, audit, r2):
        await _log_entries(audit, ["info"])

        await audit._archive_to_r2(list(audit.buffer))

        assert r2.method_calls == []


class TestDedicatedBucket:
    async def test_one_put_object_to_the_dedicated_bucket(self, audit, table, r2, dedicated_bucket):
        ids = await _log_entries(audit, ["info", "info", "info"])

        await audit._flush_buffer()

        assert set(table.rows) == set(ids)
        r2.put_object.assert_called_once()
        call = r2.put_object.call_args.kwargs
        assert call["Bucket"] == AUDIT_BUCKET
        key = ARCHIVE_KEY.match(call["Key"])
        assert key is not None, call["Key"]
        assert key["tenant"] == "tenant-a"
        assert call["ContentType"] == "application/json"
        assert call["Metadata"] == {
            "tenant_id": "tenant-a",
            "date": key["date"],
            "count": "3",
        }

    async def test_one_object_per_tenant_and_day(self, audit, r2, dedicated_bucket):
        await _log_entries(audit, ["info"], tenant="tenant-a")
        await _log_entries(audit, ["info"], tenant="tenant-b")

        await audit._flush_buffer()

        keys = sorted(c.kwargs["Key"] for c in r2.put_object.call_args_list)
        assert [ARCHIVE_KEY.match(k)["tenant"] for k in keys] == ["tenant-a", "tenant-b"]
        assert {c.kwargs["Bucket"] for c in r2.put_object.call_args_list} == {AUDIT_BUCKET}

    async def test_entries_stored_at_log_time_are_archived_not_rewritten(
        self, audit, table, r2, dedicated_bucket
    ):
        ids = await _log_entries(audit, ["critical", "info", "high"])
        assert table.inserts == 3

        await audit._flush_buffer()

        assert table.inserts == 3
        assert set(table.rows) == set(ids)
        assert r2.put_object.call_args.kwargs["Metadata"]["count"] == "3"
        assert audit.buffer == []

    async def test_buffer_flushes_at_its_size(self, audit, table, r2, dedicated_bucket):
        audit.buffer_size = 3

        ids = await _log_entries(audit, ["info"] * 7)

        assert set(table.rows) == set(ids)
        assert [c.kwargs["Metadata"]["count"] for c in r2.put_object.call_args_list] == [
            "3",
            "3",
        ]
        assert [e["event_id"] for e in audit.buffer] == ids[6:]


class TestPeriodicFlush:
    async def test_ends_once_the_buffer_is_empty(self, table, r2, dedicated_bucket):
        audit = AuditLogger(table, r2_client=r2, owns_session=True)
        audit.flush_interval = 0

        await _log_entries(audit, ["info"])
        task = audit._flush_task
        assert task is not None
        await asyncio.wait_for(task, 5)

        assert audit._flush_task is None
        assert audit.buffer == []
        r2.put_object.assert_called_once()

    async def test_no_task_while_archiving_is_off(self, table, r2):
        audit = AuditLogger(table, r2_client=r2, owns_session=True)

        await _log_entries(audit, ["info"])

        assert audit._flush_task is None


class TestUploadBucketRefused:
    async def test_flush_stores_and_makes_no_r2_call(
        self, audit, table, r2, upload_bucket_as_audit_bucket, log_spy
    ):
        ids = await _log_entries(audit, ["info", "critical"])

        await audit._flush_buffer()
        await _log_entries(audit, ["info"])
        await audit._flush_buffer()

        assert len(table.rows) == 3 and set(ids) <= set(table.rows)
        assert r2.method_calls == []
        assert _codes(log_spy, "error") == [AUDIT_ARCHIVE_BUCKET_REFUSED]

    async def test_direct_archive_call_makes_no_r2_call(
        self, audit, r2, upload_bucket_as_audit_bucket, log_spy
    ):
        await _log_entries(audit, ["info"])

        await audit._archive_to_r2(list(audit.buffer))

        assert r2.method_calls == []


class TestArchiveFailure:
    @pytest.mark.parametrize(
        "error",
        [
            ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject"),
            ConnectionError("endpoint unreachable"),
        ],
    )
    async def test_database_unchanged_and_nothing_rebuffered(
        self, audit, table, r2, dedicated_bucket, log_spy, error
    ):
        ids = await _log_entries(audit, ["info", "critical", "info", "high"])
        r2.put_object.side_effect = error

        await audit._flush_buffer()
        after_flush = table.snapshot()

        assert set(after_flush) == set(ids)
        assert table.inserts == len(ids)
        assert audit.buffer == []
        assert _codes(log_spy, "warning") == [AUDIT_ARCHIVE_FAILED]
        assert log_spy.error.call_args_list == []

        # Nothing is retried: a later flush writes no row and uploads nothing.
        await audit._flush_buffer()
        assert table.snapshot() == after_flush
        assert table.inserts == len(ids)
        assert r2.put_object.call_count == 1

    async def test_unexpected_archive_error_is_contained(
        self, audit, table, dedicated_bucket, log_spy
    ):
        ids = await _log_entries(audit, ["info", "info"])

        with patch.object(audit, "_archive_to_r2", AsyncMock(side_effect=TypeError("boom"))):
            await audit._flush_buffer()

        assert set(table.rows) == set(ids)
        assert table.inserts == 2
        assert audit.buffer == []
        assert _codes(log_spy, "warning") == [AUDIT_ARCHIVE_FAILED]

    async def test_one_failed_group_does_not_stop_the_others(
        self, audit, r2, dedicated_bucket, log_spy
    ):
        await _log_entries(audit, ["info"], tenant="tenant-a")
        await _log_entries(audit, ["info", "info"], tenant="tenant-b")
        r2.put_object.side_effect = [ClientError({"Error": {"Code": "500"}}, "PutObject"), None]

        await audit._flush_buffer()

        assert r2.put_object.call_count == 2
        assert _codes(log_spy, "warning") == [AUDIT_ARCHIVE_FAILED]
        assert log_spy.warning.call_args.kwargs["entries"] == 1


class TestStoreFailure:
    async def test_failed_store_raises_and_is_neither_buffered_nor_archived(
        self, audit, table, r2, dedicated_bucket, log_spy
    ):
        table.fail_commits = 1

        with pytest.raises(RuntimeError):
            await _log_entries(audit, ["info"])

        assert table.rows == {}
        assert audit.buffer == []
        assert _codes(log_spy, "error") == [AUDIT_STORE_FAILED]

        ids = await _log_entries(audit, ["info"])
        await audit._flush_buffer()

        assert set(table.rows) == set(ids)
        assert r2.put_object.call_count == 1
        assert r2.put_object.call_args.kwargs["Metadata"]["count"] == "1"

    async def test_nothing_is_buffered_while_archiving_is_off(self, audit, table, log_spy):
        table.fail_commits = 3
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await _log_entries(audit, ["info"])
        await _log_entries(audit, ["info", "info"])

        assert audit.buffer == []
        assert table.inserts == 2
        assert _codes(log_spy, "error") == [AUDIT_STORE_FAILED] * 3


class TestExport:
    """The upload branch of ``export_logs``.

    The query is stubbed: these tests cover what happens after it. The query
    itself runs against the real model in test_audit_logger_chain.py.
    """

    @pytest.fixture(autouse=True)
    def stub_query(self):
        with (
            patch.object(
                audit_logger_module,
                "AuditLog",
                SimpleNamespace(
                    tenant_id=column("tenant_id"),
                    created_at=column("created_at"),
                    id=column("id"),
                ),
            ),
            patch.object(audit_logger_module, "select", MagicMock()),
            patch.object(audit_logger_module, "and_", MagicMock()),
        ):
            yield

    async def _export(self, audit: AuditLogger):
        from datetime import datetime

        return await audit.export_logs(
            tenant_id="tenant-a",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 31),
        )

    async def test_no_bucket_returns_the_export_id(self, audit, r2):
        result = await self._export(audit)

        assert uuid.UUID(result)
        assert r2.method_calls == []

    async def test_no_client_returns_the_export_id(self, table, dedicated_bucket):
        audit = AuditLogger(table, owns_session=True)
        assert audit.r2_client is None

        assert uuid.UUID(await self._export(audit))

    async def test_upload_bucket_is_refused(
        self, audit, r2, upload_bucket_as_audit_bucket, log_spy
    ):
        result = await self._export(audit)

        assert uuid.UUID(result)
        assert r2.method_calls == []
        assert _codes(log_spy, "error") == [AUDIT_ARCHIVE_BUCKET_REFUSED]

    async def test_dedicated_bucket_uploads_and_returns_a_presigned_url(
        self, audit, r2, dedicated_bucket
    ):
        result = await self._export(audit)

        assert result == "https://r2.example/presigned"
        put = r2.put_object.call_args.kwargs
        assert put["Bucket"] == AUDIT_BUCKET
        assert re.match(r"^exports/tenant-a/[0-9a-f-]{36}\.json$", put["Key"])
        presign = r2.generate_presigned_url.call_args
        assert presign.kwargs["Params"] == {"Bucket": AUDIT_BUCKET, "Key": put["Key"]}

    async def test_failed_export_upload_still_raises(self, audit, r2, dedicated_bucket):
        r2.put_object.side_effect = ClientError({"Error": {"Code": "500"}}, "PutObject")

        with pytest.raises(ClientError):
            await self._export(audit)
