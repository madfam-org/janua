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
    for product_tiers in (None, {}):
        verdict = audit.classify(_row(organization_id=None, product_tiers=product_tiers))
        assert verdict["tier_claims_dropped"] == ["hcm_tier", "yantra4d_tier"]


def test_unreadable_org_tiers_mean_no_token_so_nothing_changes():
    # The claims builder cannot read these, so the app issues the
    # organization's clients no token today either.
    for product_tiers in ("not json", ["yantra4d"]):
        verdict = audit.classify(_row(product_tiers=product_tiers))
        assert verdict["tier_claims_dropped"] == [] and not verdict["changes_active_client"]


def test_org_tiers_stored_as_object_text_are_read_like_the_app():
    verdict = audit.classify(_row(product_tiers=json.dumps({"hcm": "pro"})))
    assert verdict["tier_claims_dropped"] == ["yantra4d_tier"]


def test_entitlement_keys_are_normalised_like_the_claim():
    verdict = audit.classify(
        _row(allowed_scopes=["crea-map:read"], product_tiers={"crea-map": "pro"})
    )
    assert verdict["tier_claims_dropped"] == []


def test_non_confidential_client_gets_no_token_so_nothing_changes():
    verdict = audit.classify(_row(is_confidential=False))
    assert verdict["tier_claims_dropped"] == [] and not verdict["changes_active_client"]


# ---------------------------------------------------------------------------
# Stored-value shapes: the audit reads them exactly as the app does
# ---------------------------------------------------------------------------

#: Stored values of a JSON column, as the database driver decodes them (once).
#: The ORM writes through `app/models/types.JSON`, which stores a Python list as
#: a JSON string holding the array text ("array_text"); rows written by SQL
#: hold a JSON array ("array").
SHAPES = {
    "array": ["authorization_code", "client_credentials"],
    "array_text": json.dumps(["authorization_code", "client_credentials"]),
    "single_bare": "client_credentials",
    "single_text": json.dumps("client_credentials"),
    "double_encoded_array": json.dumps(json.dumps(["authorization_code", "client_credentials"])),
    "space_delimited": "authorization_code client_credentials",
    "comma_delimited": "authorization_code,client_credentials",
    "empty_string": "",
    "empty_list": [],
    "none": None,
}
MACHINE_SHAPES = {"array", "array_text"}


def _app_load(value):
    """The app's model-type step on a driver value; raises when it cannot load."""
    from sqlalchemy.dialects import postgresql

    from app.models.types import JSON

    return JSON().process_result_value(value, postgresql.dialect())


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_loading_is_the_apps(shape):
    value = SHAPES[shape]
    try:
        expected = _app_load(value)
    except ValueError:
        with pytest.raises(audit.Unloadable):
            audit.app_loaded(value)
        assert not audit.app_loads(value)
    else:
        assert audit.app_loaded(value) == expected
        assert audit.app_loads(value)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_grant_and_scope_parsing_is_the_apps(shape):
    from types import SimpleNamespace

    from app.routers.v1 import oauth_provider

    value = SHAPES[shape]
    try:
        loaded = _app_load(value)
    except ValueError:
        # The app cannot load the row, so it serves no grant and no scope.
        assert audit.app_grant_types(value) == set()
        assert audit.app_allowed_scopes(value) == set()
        return
    client = SimpleNamespace(grant_types=loaded, allowed_scopes=loaded)
    assert audit.app_grant_types(value) == oauth_provider._client_grant_types(client)
    assert audit.app_allowed_scopes(value) == oauth_provider._client_allowed_scopes(client)


def test_defaults_are_the_apps():
    from app.routers.v1 import oauth_provider

    assert audit.DEFAULT_CLIENT_GRANT_TYPES == oauth_provider.DEFAULT_CLIENT_GRANT_TYPES
    assert audit.DEFAULT_CLIENT_SCOPES == oauth_provider.DEFAULT_CLIENT_SCOPES


@pytest.mark.parametrize("value", [5, True, [{"grant": "client_credentials"}]])
def test_a_value_the_app_cannot_turn_into_a_set_grants_nothing(value):
    from types import SimpleNamespace

    from app.routers.v1 import oauth_provider

    with pytest.raises(TypeError):
        oauth_provider._client_grant_types(SimpleNamespace(grant_types=_app_load(value)))
    assert audit.app_grant_types(value) == set()
    assert audit.classify(_row(grant_types=value))["tier_claims_dropped"] == []


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_only_a_loadable_array_of_names_makes_a_machine_client(shape):
    verdict = audit.classify(_row(grant_types=SHAPES[shape]))
    assert bool(verdict["tier_claims_dropped"]) == (shape in MACHINE_SHAPES)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_scope_shapes_follow_the_same_reading(shape):
    scopes = SHAPES[shape]
    if isinstance(scopes, list) and scopes:
        scopes = ["openid", "yantra4d:render"]
    elif isinstance(scopes, str) and scopes:
        scopes = scopes.replace("authorization_code", "openid").replace(
            "client_credentials", "yantra4d:render"
        )
    verdict = audit.classify(_row(allowed_scopes=scopes, product_tiers={}))
    expected = ["yantra4d_tier"] if shape in MACHINE_SHAPES else []
    assert verdict["tier_claims_dropped"] == expected


def test_unloadable_redirect_uris_mean_no_token():
    assert audit.classify(_row(redirect_uris="not json"))["tier_claims_dropped"] == []
    assert audit.classify(_row(redirect_uris=json.dumps([])))["tier_claims_dropped"]


# ---------------------------------------------------------------------------
# Real PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_url():
    """A fresh schema on a disposable loopback *_test database, dropped after."""
    raw = os.getenv("AUDIT_TEST_DATABASE_URL")
    if not raw and os.getenv("LOCAL_DB") == "yes":
        # CI's guarded PostgreSQL service (see the payment-mail proof).
        raw = os.getenv("JANUA_MAIL_TEST_DATABASE_URL")
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


def test_real_postgres_stored_shapes_match_what_the_app_loads(pg_url):
    """Every stored shape, written by SQL: the audit flags a row iff the app,
    loading it through its own model, would serve it a client_credentials
    token carrying a namespaced scope (the claim a non-admin row loses)."""

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.models import Base, OAuthClient, User
    from app.routers.v1 import oauth_provider

    engine = create_engine(pg_url)
    Base.metadata.create_all(engine)
    registrar = uuid.uuid4()
    with Session(engine) as db:
        db.add(User(id=registrar, email="m@example.test"))
        db.commit()

    array_scopes = ["yantra4d:render"]
    cases = {}
    with engine.begin() as conn:
        for varied in ("grants", "scopes"):
            for shape, value in SHAPES.items():
                if varied == "grants":
                    grants, scopes = value, array_scopes
                elif isinstance(value, list):
                    grants, scopes = ["client_credentials"], (array_scopes if value else [])
                else:
                    grants = ["client_credentials"]
                    scopes = (
                        value.replace("authorization_code", "openid").replace(
                            "client_credentials", "yantra4d:render"
                        )
                        if value
                        else value
                    )
                row_id = uuid.uuid4()
                cases[str(row_id)] = (varied, shape)
                conn.execute(
                    text(
                        "INSERT INTO oauth_clients (id, created_by, client_id,"
                        " client_secret_hash, client_secret_prefix, name, redirect_uris,"
                        " allowed_scopes, grant_types, is_active, is_confidential, created_at)"
                        " VALUES (:id, :by, :cid, 'h', 'p', 'n', '[]'::jsonb,"
                        " CAST(:scopes AS jsonb), CAST(:grants AS jsonb), true, true, now())"
                    ),
                    {
                        "id": row_id,
                        "by": registrar,
                        "cid": f"jnc_shape_{row_id.hex[:12]}",
                        "scopes": None if scopes is None else json.dumps(scopes),
                        "grants": None if grants is None else json.dumps(grants),
                    },
                )

    def app_would_serve_a_scoped_token(row_id) -> bool:
        try:
            with Session(engine) as db:
                client = db.get(OAuthClient, uuid.UUID(row_id))
                grants = oauth_provider._client_grant_types(client)
                scopes = oauth_provider._client_allowed_scopes(client)
        except (ValueError, TypeError):
            return False  # the app cannot load or read the row: no token
        return "client_credentials" in grants and any(
            isinstance(s, str) and ":" in s and s.split(":", 1)[0] for s in scopes
        )

    flagged = {r["id"] for r in audit.collect(pg_url) if r["kind"] == "tier_claims"}
    for row_id, (varied, shape) in cases.items():
        expected = app_would_serve_a_scoped_token(row_id)
        assert (row_id in flagged) == expected, (varied, shape)
        # Written by SQL, both array forms load as arrays in the app.
        assert expected == (shape in MACHINE_SHAPES), (varied, shape)
    engine.dispose()
