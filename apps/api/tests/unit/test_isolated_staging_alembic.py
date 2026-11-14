"""Transport and authority refusal; the required native gate proves real DDL."""

import ssl
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.core.database_ssl import asyncpg_options
from app.core.isolated_staging_alembic import (
    EXPECTED_RECEIPT,
    inspect_isolated_staging_connection,
    isolated_staging_connect_args,
    isolated_staging_requested,
)


def test_only_explicit_internal_boolean_selects_profile():
    assert not isolated_staging_requested({})
    assert not isolated_staging_requested({"janua_staging_isolated": False})
    assert isolated_staging_requested({"janua_staging_isolated": True})
    for value in ("true", 1, 0, None, {}, []):
        with pytest.raises(RuntimeError):
            isolated_staging_requested({"janua_staging_isolated": value})


def test_verified_staging_transport_has_fixed_independent_connection_limits():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    original = {"ssl": context, "statement_cache_size": 0}
    actual = isolated_staging_connect_args("staging", original)
    assert actual["ssl"] is context
    assert actual["timeout"] == 5
    assert actual["command_timeout"] == 120
    assert actual["statement_cache_size"] == 0
    assert actual["server_settings"] == {"statement_timeout": "120000", "lock_timeout": "5000"}
    assert original == {"ssl": context, "statement_cache_size": 0}


def test_real_migration_ssl_adapter_composes_without_losing_pool_safety(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "F-901 fixture CA")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    ca_file = tmp_path / "fixture-ca.crt"
    ca_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    settings = SimpleNamespace(DATABASE_SSL_MODE="verify-full", DATABASE_SSL_CA_FILE=str(ca_file))
    url, args = asyncpg_options(
        "postgresql://enclii_migrator:synthetic@fixture.invalid:5432/janua_staging?sslmode=verify-full",
        settings,
    )
    actual = isolated_staging_connect_args("staging", args)
    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert actual["ssl"].check_hostname
    assert actual["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert actual["statement_cache_size"] == 0
    assert actual["ssl"].cert_store_stats()["x509_ca"] == 1


@pytest.mark.parametrize("environment", ["production", "development", "test", "STAGING", ""])
def test_other_environments_cannot_select_stage_migration(environment):
    with pytest.raises(RuntimeError):
        isolated_staging_connect_args(
            environment, {"ssl": ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "statement_cache_size": 0}
        )


def test_missing_insecure_or_extra_transport_options_are_refused():
    verified = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    for arguments in (
        {},
        {"ssl": verified},
        {"ssl": True, "statement_cache_size": 0},
        {"ssl": insecure, "statement_cache_size": 0},
        {"ssl": verified, "statement_cache_size": 1},
        {"ssl": verified, "statement_cache_size": False},
        {"ssl": verified, "statement_cache_size": 0, "server_settings": {"statement_timeout": "0"}},
    ):
        with pytest.raises(RuntimeError):
            isolated_staging_connect_args("staging", arguments)


@pytest.mark.parametrize("field", list(EXPECTED_RECEIPT))
def test_actual_connection_authority_tls_and_limits_must_all_match(field):
    connection = MagicMock()
    row = dict(EXPECTED_RECEIPT)
    row[field] = "wrong"
    connection.execute.return_value.mappings.return_value.one.return_value = row
    with pytest.raises(RuntimeError, match="DDL connection refused"):
        inspect_isolated_staging_connection(connection)


def test_receipt_refuses_missing_extra_and_boolean_integer_substitution():
    for mutate in (
        lambda row: row.pop("tls"),
        lambda row: row.update(unexpected="not allowed"),
        lambda row: row.update(tls=1),
    ):
        row = dict(EXPECTED_RECEIPT)
        mutate(row)
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value.one.return_value = row
        with pytest.raises(RuntimeError):
            inspect_isolated_staging_connection(connection)


def test_receipt_uses_actual_connection_and_contains_only_fixed_nonsecret_metadata():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = dict(EXPECTED_RECEIPT)
    result = inspect_isolated_staging_connection(connection)
    assert result == EXPECTED_RECEIPT
    assert result is not EXPECTED_RECEIPT
    statement = str(connection.execute.call_args.args[0])
    assert "pg_backend_pid()" in statement
    assert "pg_settings" in statement
    assert "pg_roles" in statement
