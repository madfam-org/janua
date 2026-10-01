"""scripts/audit_data_subject_request_access.py: aggregation, the per-request
query on SQLite, and a real-PostgreSQL run (opt in with
``AUDIT_TEST_DATABASE_URL`` pointing at a disposable loopback database whose
name ends in ``_test``)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_data_subject_request_access.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_data_subject_request_access", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load()


def _row(**overrides):
    row = {
        "request_type": "ACCESS",
        "status": "RECEIVED",
        "processed": False,
        "by_subject": None,
        "assignee_is_admin": False,
        "assignee_missing": False,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({}, "not_processed"),
        ({"processed": True, "by_subject": True}, "subject"),
        ({"processed": True, "by_subject": False, "assignee_is_admin": True}, "platform_admin"),
        ({"processed": True, "by_subject": False}, "other_user"),
        ({"processed": True, "by_subject": False, "assignee_missing": True}, "missing_user"),
    ],
)
def test_last_processor_category(overrides, expected):
    assert audit.last_processor_category(_row(**overrides)) == expected


def test_summarize_counts_by_type_status_and_last_processor():
    rows = [
        _row(),
        _row(status="COMPLETED", processed=True, by_subject=True),
        _row(status="COMPLETED", processed=True, by_subject=False, assignee_is_admin=True),
        _row(status="COMPLETED", processed=True, by_subject=False),
        _row(request_type="ERASURE"),
    ]
    report = audit.summarize(rows, {"gdpr.data_export": 2})

    assert report["data_subject_requests"] == 5
    assert report["by_type"] == {"ACCESS": 4, "ERASURE": 1}
    assert report["by_status"] == {"COMPLETED": 3, "RECEIVED": 2}
    assert report["by_type_and_status"]["ACCESS"] == {"COMPLETED": 3, "RECEIVED": 1}
    assert report["last_processor_by_type"]["ACCESS"] == {
        "not_processed": 1,
        "subject": 1,
        "platform_admin": 1,
        "other_user": 1,
        "missing_user": 0,
    }
    assert report["last_processed_by_other_user"] == 1
    assert report["audit_log_rows_by_action"] == {"gdpr.data_export": 2}
    assert report["audit_log_table_present"] is True
    assert report["not_knowable"]


def test_summarize_empty_and_without_audit_table():
    report = audit.summarize([], None)
    assert report["data_subject_requests"] == 0
    assert report["last_processed_by_other_user"] == 0
    assert report["audit_log_table_present"] is False


def _seed(session_factory_or_session, models):
    """Subject, another user, a platform admin and four access requests: not
    processed, processed by the subject, by the admin and by the other user."""
    User, DataSubjectRequest, DataSubjectRequestType, RequestStatus = models
    subject, other, admin = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db = session_factory_or_session
    db.add_all(
        [
            User(id=subject, email=f"s-{subject.hex[:8]}@example.test"),
            User(id=other, email=f"o-{other.hex[:8]}@example.test"),
            User(id=admin, email=f"a-{admin.hex[:8]}@example.test", is_admin=True),
        ]
    )
    db.flush()
    for assigned_to in (None, subject, admin, other):
        db.add(
            DataSubjectRequest(
                request_id=f"DSR-TEST-{uuid.uuid4().hex[:8].upper()}",
                user_id=subject,
                request_type=DataSubjectRequestType.ACCESS,
                status=RequestStatus.COMPLETED if assigned_to else RequestStatus.RECEIVED,
                assigned_to=assigned_to,
                received_at=datetime.utcnow(),
                response_due_date=datetime.utcnow() + timedelta(days=30),
            )
        )
    db.commit()


def _models():
    from app.models import User
    from app.models.compliance import (
        DataSubjectRequest,
        DataSubjectRequestType,
        RequestStatus,
    )

    return User, DataSubjectRequest, DataSubjectRequestType, RequestStatus


def test_queries_run_on_the_real_models_sqlite():
    """The per-request and audit queries are valid against the ORM schema and
    return only types, statuses and booleans."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db, _models())

    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(text(audit.REQUESTS_SQL))]
        audit_rows = list(conn.execute(text(audit.AUDIT_SQL)))
    engine.dispose()

    assert set(rows[0]) == {
        "request_type",
        "status",
        "processed",
        "by_subject",
        "assignee_is_admin",
        "assignee_missing",
    }
    report = audit.summarize(rows, {})
    assert report["data_subject_requests"] == 4
    assert report["last_processor_by_type"]["ACCESS"] == {
        "not_processed": 1,
        "subject": 1,
        "platform_admin": 1,
        "other_user": 1,
        "missing_user": 0,
    }
    assert audit_rows == []


# ---------------------------------------------------------------------------
# Real PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_url():
    """A fresh schema on a disposable loopback *_test database, dropped after."""
    raw = os.getenv("AUDIT_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set AUDIT_TEST_DATABASE_URL to a disposable loopback *_test database")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(raw).set(drivername="postgresql")
    if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").endswith("_test"):
        pytest.fail("AUDIT_TEST_DATABASE_URL must be loopback and name a *_test database")
    schema = "audit_fixture_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    try:
        yield scoped.render_as_string(hide_password=False)
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.database
def test_real_postgres_run_is_read_only_and_counts(pg_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.models import Base

    engine = create_engine(pg_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db, _models())

    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT count(*), count(assigned_to) FROM data_subject_requests")
        ).one()

    report = audit.collect(pg_url)
    assert report["data_subject_requests"] == 4
    assert report["by_status"] == {"COMPLETED": 3, "RECEIVED": 1}
    assert report["last_processed_by_other_user"] == 1
    assert report["last_processor_by_type"]["ACCESS"]["platform_admin"] == 1
    assert report["audit_log_table_present"] is True

    # The stdin form the operator runs in the pod: one JSON object, exit 2
    # because one request was last processed by another user, and no
    # identifying data in the output.
    env = {**os.environ, "DATABASE_URL": pg_url}
    env.pop("DIRECT_DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-", "--json"],
        stdin=SCRIPT.open(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 2, result.stderr
    assert "@example.test" not in result.stdout and "DSR-TEST-" not in result.stdout
    assert json.loads(result.stdout)["data_subject_requests"] == 4

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT count(*), count(assigned_to) FROM data_subject_requests")
        ).one()
    assert tuple(after) == tuple(before)
    engine.dispose()
