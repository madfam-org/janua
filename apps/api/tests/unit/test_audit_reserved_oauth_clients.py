"""scripts/audit_reserved_oauth_clients.py: verdicts, registry parity, and a
real-PostgreSQL run (opt in with ``AUDIT_TEST_DATABASE_URL`` pointing at a
disposable loopback database whose name ends in ``_test``)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from app.core import reserved_oauth_boundaries as registry

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_reserved_oauth_clients.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_reserved_oauth_clients", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load()


def test_script_copy_of_the_registry_has_not_drifted():
    assert audit.RESERVED_AUDIENCE_PREFIXES == registry.RESERVED_AUDIENCE_PREFIXES
    assert audit.RESERVED_AUDIENCES == registry.RESERVED_AUDIENCES
    assert audit.RESERVED_SCOPES == registry.RESERVED_SCOPES
    assert audit.RESERVED_SCOPE_SUFFIXES == registry.RESERVED_SCOPE_SUFFIXES
    assert audit.FIRST_PARTY_NAME_PREFIXES == registry.FIRST_PARTY_NAME_PREFIXES
    assert audit.RESERVED_CLIENT_NAMES == registry.RESERVED_CLIENT_NAMES
    assert audit.PAYMENT_MAIL_AUDIENCE == registry.MAIL_AUDIENCE
    assert audit.PAYMENT_MAIL_SCOPE == registry.PAYMENT_MAIL_SCOPE


@pytest.mark.parametrize(
    "name,audience,scopes",
    [
        ("madfam-x", None, []),
        ("tenant", "janua-email", ["openid"]),
        ("tenant", None, ["hcm:admin"]),
        ("tenant", "tenant-api", ["hcm:hr"]),
        ("creator-census", "janua-connections", ["connections:delegate"]),
    ],
)
def test_script_matches_the_registry(name, audience, scopes):
    assert audit.reserved_fields(name, audience, scopes) == registry.reserved_fields(
        name=name, audience=audience, scopes=scopes
    )


def _row(**overrides):
    row = {
        "name": "tenant-worker",
        "audience": None,
        "allowed_scopes": ["hcm:hr"],
        "grant_types": ["client_credentials"],
        "organization_id": "org",
        "creator_is_admin": False,
        "creator_is_org_admin": True,
        "is_active": True,
    }
    row.update(overrides)
    return row


def test_org_admin_ordinary_machine_client_is_info():
    verdict = audit.classify(_row())
    assert verdict["listed"] and verdict["verdict"] == "info" and verdict["reasons"] == []


def test_non_admin_payment_mail_client_needs_review_and_breaks_after_deploy():
    verdict = audit.classify(
        _row(audience="janua-email", allowed_scopes=json.dumps(["crea-map:payment-mail"]))
    )
    assert verdict["verdict"] == "review"
    assert verdict["reasons"] == ["reserved:audience+allowed_scopes"]
    assert verdict["refused_after_deploy"]


def test_admin_payment_mail_client_is_ok():
    verdict = audit.classify(
        _row(
            audience="janua-email",
            allowed_scopes=["crea-map:payment-mail"],
            creator_is_admin=True,
        )
    )
    assert verdict["verdict"] == "ok" and not verdict["refused_after_deploy"]


def test_foreign_org_binding_and_unbound_machine_need_review():
    assert audit.classify(_row(creator_is_org_admin=False))["reasons"] == [
        "org_bound_by_non_org_admin"
    ]
    assert audit.classify(_row(organization_id=None, creator_is_org_admin=None))["reasons"] == [
        "client_credentials_without_org"
    ]


def test_plain_interactive_client_is_not_listed():
    row = _row(
        organization_id=None,
        grant_types=["authorization_code"],
        allowed_scopes=["openid"],
        creator_is_org_admin=None,
    )
    assert not audit.classify(row)["listed"]


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


def test_real_postgres_run_is_read_only_and_classifies(pg_url):
    from sqlalchemy import create_engine, text

    from app.models import Base, OAuthClient, Organization, OrganizationMember, User

    engine = create_engine(pg_url)
    Base.metadata.create_all(engine)
    admin, member, outsider = (uuid.uuid4() for _ in range(3))
    org, foreign = uuid.uuid4(), uuid.uuid4()
    ids = {}
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        db.add_all(
            [
                User(id=admin, email="a@example.test", is_admin=True),
                User(id=member, email="m@example.test"),
                User(id=outsider, email="o@example.test"),
            ]
        )
        db.flush()
        db.add_all(
            [
                Organization(id=org, name="Org", slug="audit-org"),
                Organization(id=foreign, name="Foreign", slug="audit-foreign"),
            ]
        )
        db.flush()
        db.add(
            OrganizationMember(organization_id=org, user_id=member, role="admin", status="active")
        )

        def client(key, created_by, org_id, audience, scopes, grants):
            row = OAuthClient(
                id=uuid.uuid4(),
                organization_id=org_id,
                created_by=created_by,
                client_id=f"jnc_audit_{key}",
                client_secret_hash="never-printed-hash",
                client_secret_prefix="jns_x",
                name=f"secret-name-{key}",
                redirect_uris=[],
                audience=audience,
                allowed_scopes=scopes,
                grant_types=grants,
                is_active=True,
                is_confidential=True,
                created_at=datetime(2026, 9, 1),
            )
            ids[key] = str(row.id)
            db.add(row)

        cc = ["client_credentials"]
        client("admin_mail", admin, org, "janua-email", ["crea-map:payment-mail"], cc)
        client("self_mail", outsider, foreign, "janua-email", ["crea-map:payment-mail"], cc)
        client("member_ok", member, org, None, ["hcm:hr"], cc)
        client("interactive", outsider, None, None, ["openid"], ["authorization_code"])
        db.commit()

    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM oauth_clients")).scalar_one()

    report = {r["id"]: r for r in audit.collect(pg_url)}
    assert report[ids["admin_mail"]]["verdict"] == "ok"
    assert report[ids["self_mail"]]["verdict"] == "review"
    assert report[ids["self_mail"]]["refused_after_deploy"]
    assert "org_bound_by_non_org_admin" in report[ids["self_mail"]]["reasons"]
    assert report[ids["member_ok"]]["verdict"] == "info"
    assert ids["interactive"] not in report

    # The stdin form the operator runs in the pod: JSON lines, exit 2 on review.
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
    assert "secret-name" not in result.stdout and "never-printed" not in result.stdout
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[-1]["summary"]["review"] == 1
    assert lines[-1]["summary"]["active_payment_mail_clients_refused_after_deploy"] == 1

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM oauth_clients")).scalar_one() == before
    engine.dispose()
