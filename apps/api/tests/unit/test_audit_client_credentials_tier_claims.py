"""scripts/audit_client_credentials_tier_claims.py: verdicts, parity with the app,
and a real-PostgreSQL run (opt in with ``AUDIT_TEST_DATABASE_URL`` pointing at
a disposable loopback database whose name ends in ``_test``).

Parity of the dropped claim keys with the real token builder lives next to the
builder's tests (`tests/unit/routers/test_client_credentials_tier_claims.py`).
"""

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

from app.core import consent_purposes

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_client_credentials_tier_claims.py"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_client_credentials_tier_claims", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_script()


def test_script_copy_of_the_connections_grant_has_not_drifted():
    assert audit.CONNECTIONS_AUDIENCE == consent_purposes.CONNECTIONS_AUDIENCE
    assert audit.CONNECTIONS_DELEGATE_SCOPE == consent_purposes.CONNECTIONS_DELEGATE_SCOPE


def _row(**overrides):
    row = {
        "id": "row",
        "client_id": "jnc_fixture",
        "organization_id": "org",
        "created_by": "user",
        "creator_missing": False,
        "created_at": None,
        "last_used_at": None,
        "audience": "tenant-api",
        "allowed_scopes": ["yantra4d:render", "hcm:hr", "openid"],
        "grant_types": ["client_credentials"],
        "creator_is_admin": False,
        "is_active": True,
        "is_confidential": True,
        "product_tiers": {"yantra4d": "pro"},
    }
    row.update(overrides)
    return row


def test_non_admin_client_drops_the_claims_its_org_is_not_entitled_to():
    verdict = audit.classify(_row())
    assert verdict["tier_claims_dropped"] == ["hcm_tier"]
    assert verdict["changes_active_client"] and not verdict["connections"]


def test_admin_registered_client_changes_nothing():
    verdict = audit.classify(
        _row(creator_is_admin=True, audience="janua-connections", allowed_scopes=[
            "connections:delegate", "hcm:hr",
        ])  # fmt: skip
    )
    assert verdict == {
        "tier_claims_dropped": [],
        "connections": False,
        "refused_after_deploy": False,
        "changes_active_client": False,
    }


def test_unbound_or_missing_org_drops_every_scoped_product():
    for product_tiers in (None, {}, "{}"):
        verdict = audit.classify(_row(organization_id=None, product_tiers=product_tiers))
        assert verdict["tier_claims_dropped"] == ["hcm_tier", "yantra4d_tier"]


def test_entitlement_keys_are_normalised_like_the_claim():
    verdict = audit.classify(
        _row(allowed_scopes=json.dumps(["crea-map:read"]), product_tiers={"crea-map": "pro"})
    )
    assert verdict["tier_claims_dropped"] == []


def test_interactive_client_is_never_listed():
    verdict = audit.classify(_row(grant_types=["authorization_code"]))
    assert verdict["tier_claims_dropped"] == [] and not verdict["connections"]


def test_connections_client_from_a_non_admin_is_refused_after_deploy():
    verdict = audit.classify(
        _row(audience="janua-connections", allowed_scopes=["connections:delegate"])
    )
    assert verdict["connections"] and verdict["refused_after_deploy"]
    assert verdict["tier_claims_dropped"] == ["connections_tier"]


def test_inactive_connections_client_is_listed_but_changes_nothing():
    verdict = audit.classify(
        _row(
            audience="janua-connections",
            allowed_scopes=["connections:delegate"],
            is_active=False,
        )
    )
    assert verdict["connections"] and not verdict["refused_after_deploy"]
    assert not verdict["changes_active_client"]


def test_report_and_exit_status():
    rows = [
        _row(id="a"),
        _row(id="b", audience="janua-connections", allowed_scopes=["connections:delegate"]),
        _row(id="c", creator_is_admin=True),
        _row(id="d", is_active=False),
    ]
    report = audit.report_rows(rows)
    assert [(r["kind"], r["id"]) for r in report] == [
        ("tier_claims", "a"),
        ("tier_claims", "b"),
        ("connections", "b"),
        ("tier_claims", "d"),
    ]
    totals = audit.summary(report)
    assert totals["tier_claims_clients"] == 3
    assert totals["tier_claims_clients_active"] == 2
    assert totals["tier_claims_dropped_by_claim_active"] == {"connections_tier": 1, "hcm_tier": 1}
    assert totals["connections_refused_after_deploy"] == 1
    assert audit.exit_status(report) == 2
    assert audit.exit_status(audit.report_rows([rows[2]])) == 0


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
    schema = "audit_tier_fixture_" + uuid.uuid4().hex
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
    from sqlalchemy.orm import Session

    from app.models import Base, OAuthClient, Organization, User

    engine = create_engine(pg_url)
    Base.metadata.create_all(engine)
    admin, org_admin = uuid.uuid4(), uuid.uuid4()
    entitled, plain = uuid.uuid4(), uuid.uuid4()
    ids = {}

    with Session(engine) as db:
        db.add_all(
            [
                User(id=admin, email="a@example.test", is_admin=True),
                User(id=org_admin, email="m@example.test"),
            ]
        )
        db.flush()
        db.add_all(
            [
                Organization(
                    id=entitled, name="E", slug="tier-entitled", product_tiers={"yantra4d": "pro"}
                ),
                Organization(id=plain, name="P", slug="tier-plain", product_tiers={}),
            ]
        )
        db.flush()

        def client(key, created_by, org_id, audience, scopes, grants, active=True):
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
                is_active=active,
                is_confidential=True,
                created_at=datetime(2026, 9, 1),
            )
            ids[key] = str(row.id)
            db.add(row)

        cc = ["client_credentials"]
        client("admin_render", admin, None, "yantra4d-api", ["yantra4d:render"], cc)
        client("entitled", org_admin, entitled, None, ["yantra4d:render"], cc)
        client("plain", org_admin, plain, None, ["yantra4d:render", "hcm:hr"], cc)
        client("census", org_admin, plain, "janua-connections", ["connections:delegate"], cc)
        client("census_admin", admin, None, "janua-connections", ["connections:delegate"], cc)
        client("interactive", org_admin, None, None, ["x:y"], ["authorization_code"])
        db.commit()

    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM oauth_clients")).scalar_one()

    report = {(r["kind"], r["id"]): r for r in audit.collect(pg_url)}
    assert set(report) == {
        ("tier_claims", ids["plain"]),
        ("tier_claims", ids["census"]),
        ("connections", ids["census"]),
    }
    assert report[("tier_claims", ids["plain"])]["tier_claims_dropped"] == [
        "hcm_tier",
        "yantra4d_tier",
    ]
    assert report[("connections", ids["census"])]["refused_after_deploy"]

    # The stdin form the operator runs in the pod: JSON lines, exit 2 on change.
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
    assert "@example.test" not in result.stdout
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    totals = lines[-1]["summary"]
    assert totals["tier_claims_clients_active"] == 2
    assert totals["tier_claims_dropped_by_claim_active"] == {
        "connections_tier": 1,
        "hcm_tier": 1,
        "yantra4d_tier": 1,
    }
    assert totals["connections_refused_after_deploy"] == 1

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM oauth_clients")).scalar_one() == before
    engine.dispose()
