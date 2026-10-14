"""Pure refusal gates of app.staging_seed (no database, no network).

The database gates against a real PostgreSQL role live in
tests/unit/services/test_staging_seed_postgres.py.
"""

import json
import secrets
from dataclasses import replace
from types import SimpleNamespace

import pytest

import app.config
from app import staging_seed
from app.staging_seed import RoleFacts, SeedRefused


@pytest.fixture
def ca_file(tmp_path):
    path = tmp_path / "ca.crt"
    path.write_text("synthetic placeholder, never loaded by the pure gates\n")
    return str(path)


def staging_settings(ca_file, **overrides):
    values = {
        "ENVIRONMENT": "staging",
        "BASE_URL": "https://staging-auth.madfam.io",
        "JWT_ISSUER": "https://staging-auth.madfam.io",
        "DATABASE_URL": "postgresql://runtime:placeholder@db.example.internal:5432/janua_staging_sim",
        "DATABASE_SSL_MODE": "verify-full",
        "DATABASE_SSL_CA_FILE": ca_file,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def strong():
    return secrets.token_urlsafe(18) + "aA1!"


def environ(**overrides):
    values = {
        "STAGING_OPERATOR_PASSWORD": strong(),
        "STAGING_INVITEE_PASSWORD": strong(),
        "STAGING_FOREIGN_PASSWORD": strong(),
    }
    values.update(overrides)
    return values


def test_staging_settings_with_verified_tls_pass(ca_file):
    staging_seed.require_staging_settings(staging_settings(ca_file))


@pytest.mark.parametrize("overrides,code", [
    ({"ENVIRONMENT": "production"}, "environment_not_staging"),
    ({"ENVIRONMENT": "development"}, "environment_not_staging"),
    ({"ENVIRONMENT": "test"}, "environment_not_staging"),
    ({"BASE_URL": "https://auth.madfam.io"}, "production_issuer"),
    ({"JWT_ISSUER": "https://janua.dev"}, "production_issuer"),
    ({"DATABASE_URL": "postgresql://runtime:placeholder@db/janua"}, "database_not_sim"),
    ({"DATABASE_URL": "postgresql://runtime:placeholder@db/janua_sim_copy"}, "database_not_sim"),
    ({"DATABASE_URL": "sqlite+aiosqlite:///janua_sim"}, "database_not_postgresql"),
    ({"DATABASE_SSL_MODE": "require"}, "tls_not_verify_full"),
    ({"DATABASE_SSL_MODE": "disable"}, "tls_not_verify_full"),
    ({"DATABASE_SSL_CA_FILE": None}, "tls_ca_missing"),
    ({"DATABASE_SSL_CA_FILE": "/nonexistent/ca.crt"}, "tls_ca_missing"),
])
def test_environment_and_transport_refusals(ca_file, overrides, code):
    with pytest.raises(SeedRefused) as refused:
        staging_seed.require_staging_settings(staging_settings(ca_file, **overrides))
    assert refused.value.code == code


def test_passwords_come_only_from_the_three_variables():
    values = environ()
    passwords = staging_seed.read_passwords(values)
    assert passwords == {
        "operator": values["STAGING_OPERATOR_PASSWORD"],
        "invitee": values["STAGING_INVITEE_PASSWORD"],
        "foreign": values["STAGING_FOREIGN_PASSWORD"],
    }


@pytest.mark.parametrize("change,code", [
    ({"STAGING_INVITEE_PASSWORD": ""}, "password_missing"),
    ({"STAGING_FOREIGN_PASSWORD": None}, "password_missing"),
    ({"STAGING_OPERATOR_PASSWORD": "short1!A"}, "password_weak"),
    ({"STAGING_OPERATOR_PASSWORD": "alllowercaseletters1!"}, "password_weak"),
    ("reuse", "password_reused"),
])
def test_missing_weak_or_reused_passwords_are_refused(change, code):
    values = environ()
    if change == "reuse":
        values["STAGING_FOREIGN_PASSWORD"] = values["STAGING_OPERATOR_PASSWORD"]
    else:
        values.update(change)
        values = {k: v for k, v in values.items() if v is not None}
    with pytest.raises(SeedRefused) as refused:
        staging_seed.read_passwords(values)
    assert refused.value.code == code


ORDINARY = RoleFacts(
    database="janua_staging_sim", superuser=False, bypassrls=False, createdb=False,
    createrole=False, replication=False, owns_database=False, can_create_in_database=False,
    can_create_in_public=False, owned_relations=0, owned_schemas=0,
)


def test_ordinary_runtime_role_passes():
    staging_seed.require_unprivileged(ORDINARY)


@pytest.mark.parametrize("change,code", [
    ({"database": "janua"}, "database_not_sim"),
    ({"superuser": True}, "role_superuser"),
    ({"bypassrls": True}, "role_bypassrls"),
    ({"createdb": True}, "role_has_admin_attributes"),
    ({"createrole": True}, "role_has_admin_attributes"),
    ({"replication": True}, "role_has_admin_attributes"),
    ({"owns_database": True}, "role_owns_objects"),
    ({"owned_relations": 1}, "role_owns_objects"),
    ({"owned_schemas": 1}, "role_owns_objects"),
    ({"can_create_in_public": True}, "role_can_create"),
    ({"can_create_in_database": True}, "role_can_create"),
])
def test_privileged_or_ddl_capable_roles_are_refused(change, code):
    with pytest.raises(SeedRefused) as refused:
        staging_seed.require_unprivileged(replace(ORDINARY, **change))
    assert refused.value.code == code


def test_repository_has_a_single_alembic_head():
    head = staging_seed.repository_head()
    assert head and isinstance(head, str)


def test_the_synthetic_client_carries_no_reserved_value():
    from app.core.reserved_oauth_boundaries import reserved_fields
    from app.staging_synthetic import ADMISSION_CLIENT_NAME, ADMISSION_SCOPES

    assert reserved_fields(name=ADMISSION_CLIENT_NAME, scopes=ADMISSION_SCOPES) == []


def run_main(monkeypatch, capsys, settings, values):
    monkeypatch.setattr(app.config, "settings", settings)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    status = staging_seed.main()
    lines = capsys.readouterr().out.strip().splitlines()
    return status, lines[-1], json.loads(lines[-1])


def test_refusal_receipt_is_bounded_and_secret_free(monkeypatch, capsys, ca_file):
    values = environ()
    status, raw, receipt = run_main(
        monkeypatch, capsys, staging_settings(ca_file, ENVIRONMENT="production"), values,
    )
    assert status == 2
    assert receipt == {"tool": "janua.staging_seed", "result": "refused",
                       "reason": "environment_not_staging"}
    assert not any(value in raw for value in values.values())


def test_unexpected_error_receipt_carries_class_name_only(monkeypatch, capsys, ca_file):
    leaked = "placeholder-" + secrets.token_hex(8)
    values = environ()
    settings = staging_settings(
        ca_file, DATABASE_URL=f"postgresql://runtime:{leaked}@db.example.internal/janua_sim",
    )
    # The placeholder CA is not a certificate: building the TLS context fails.
    status, raw, receipt = run_main(monkeypatch, capsys, settings, values)
    assert status == 1
    assert receipt["result"] == "refused" and receipt["reason"].startswith("error:")
    assert set(receipt) == {"tool", "result", "reason"}
    assert leaked not in raw and "@" not in raw
    assert not any(value in raw for value in values.values())
