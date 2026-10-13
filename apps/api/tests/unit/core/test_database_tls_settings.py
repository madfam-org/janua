"""Configured PostgreSQL verification must reach each real engine constructor."""

import importlib.util
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import settings
from app.core import database_manager
from app.core.database_ssl import asyncpg_options, create_ssl_context, sync_postgres_options


@pytest.fixture
def verified_database(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic database CA")])
    now = datetime.now(timezone.utc)
    ca = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    ca_file = tmp_path / "ca.crt"
    ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    for name, value in {
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "postgresql://runtime@database.fixture.svc:5432/staging_sim?sslmode=require",
        "DATABASE_SSL_MODE": "verify-full",
        "DATABASE_SSL_CA_FILE": str(ca_file),
        "DATABASE_SSL_CERT_FILE": None,
        "DATABASE_SSL_KEY_FILE": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    return ca.public_bytes(serialization.Encoding.DER)


def assert_verified(call, certificate):
    url = str(call.args[0])
    options = call.kwargs["connect_args"]
    context = options["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert certificate in context.get_ca_certs(binary_form=True)
    assert options["statement_cache_size"] == 0
    # SQLAlchemy passes URI query entries as asyncpg keyword arguments; libpq's
    # sslmode is a DSN option, not an asyncpg.connect keyword argument.
    assert "sslmode=" not in url


def test_router_database_engine_uses_configured_ca(verified_database):
    source = Path(__file__).parents[3] / "app" / "database.py"
    spec = importlib.util.spec_from_file_location("database_tls_probe", source)
    module = importlib.util.module_from_spec(spec)
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine") as asynchronous,
        patch("sqlalchemy.create_engine") as synchronous,
        patch("sqlalchemy.ext.asyncio.async_sessionmaker"),
        patch("sqlalchemy.orm.sessionmaker"),
    ):
        spec.loader.exec_module(module)
    assert_verified(asynchronous.call_args, verified_database)
    options = synchronous.call_args.kwargs["connect_args"]
    assert options["sslmode"] == "verify-full"
    assert options["sslrootcert"] == settings.DATABASE_SSL_CA_FILE


@pytest.mark.asyncio
async def test_health_database_engine_uses_configured_ca(verified_database):
    manager = database_manager.DatabaseManager()
    with (
        patch.object(database_manager, "create_async_engine", return_value=MagicMock()) as engine,
        patch.object(database_manager, "async_sessionmaker"),
        patch.object(manager, "_verify_connection", new_callable=AsyncMock),
    ):
        await manager.initialize()
    assert_verified(engine.call_args, verified_database)


def test_metadata_engine_uses_configured_ca(verified_database):
    source = Path(__file__).parents[3] / "app" / "core" / "database.py"
    spec = importlib.util.spec_from_file_location("database_metadata_tls_probe", source)
    module = importlib.util.module_from_spec(spec)
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine") as engine,
        patch("sqlalchemy.ext.asyncio.async_sessionmaker"),
    ):
        spec.loader.exec_module(module)
    assert_verified(engine.call_args, verified_database)


@pytest.mark.parametrize("encoded_password", ["", ":synthetic%40fixture%2Fvalue"])
def test_migrator_uses_same_ca_with_separate_direct_connection(
    verified_database, monkeypatch, encoded_password
):
    from alembic.config import Config

    import alembic

    monkeypatch.setattr(
        settings,
        "DIRECT_DATABASE_URL",
        f"postgresql://migrator{encoded_password}@database.fixture.svc:5432/staging_sim?sslmode=require",
    )
    context = MagicMock()
    context.config = Config()
    context.is_offline_mode.return_value = False
    connection = MagicMock()
    connection.connect.return_value.__aenter__.return_value = AsyncMock()
    connection.dispose = AsyncMock()
    source = Path(__file__).parents[3] / "alembic" / "env.py"
    spec = importlib.util.spec_from_file_location("database_migrator_tls_probe", source)
    module = importlib.util.module_from_spec(spec)
    with (
        patch.object(alembic, "context", context),
        patch("sqlalchemy.ext.asyncio.async_engine_from_config", return_value=connection) as engine,
    ):
        spec.loader.exec_module(module)
    call = engine.call_args
    assert call.args[0]["sqlalchemy.url"].username == "migrator"
    assert call.args[0]["sqlalchemy.url"].password == (
        "synthetic@fixture/value" if encoded_password else None
    )
    ssl_context = call.kwargs["connect_args"]["ssl"]
    assert ssl_context.check_hostname and ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert verified_database in ssl_context.get_ca_certs(binary_form=True)
    assert "sslmode" not in call.args[0]["sqlalchemy.url"].query
    connection.dispose.assert_awaited_once()


def test_disabled_default_keeps_pooler_compatibility(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_SSL_MODE", "disable")
    url, options = asyncpg_options("postgres://runtime@localhost/example", settings)
    assert url.drivername == "postgresql+asyncpg"
    assert options == {"ssl": False, "statement_cache_size": 0}
    assert sync_postgres_options(settings) == {}


def test_sqlite_has_no_postgres_transport_options():
    url = "sqlite+aiosqlite:///:memory:"
    assert asyncpg_options(url, settings) == (url, {})


def test_explicit_missing_ca_fails_closed(verified_database, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATABASE_SSL_CA_FILE", str(tmp_path / "missing.crt"))
    with pytest.raises(FileNotFoundError):
        asyncpg_options(settings.DATABASE_URL, settings)


def test_invalid_mode_is_not_an_unverified_fallback(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_SSL_MODE", "verify-invalid")
    with pytest.raises(ValueError, match="Unsupported DATABASE_SSL_MODE"):
        create_ssl_context(settings)


def test_partial_client_certificate_fails_closed(verified_database, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_SSL_CERT_FILE", "/fixture/client.crt")
    with pytest.raises(ValueError, match="configured together"):
        create_ssl_context(settings)
