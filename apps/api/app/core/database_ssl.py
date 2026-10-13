"""PostgreSQL transport options shared by runtime and migration engines."""

import ssl

from sqlalchemy.engine import make_url


def create_ssl_context(settings):
    mode = getattr(settings, "DATABASE_SSL_MODE", "disable")
    if mode == "disable":
        return None
    if mode not in {"allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ValueError("Unsupported DATABASE_SSL_MODE")

    # An explicitly configured CA must load successfully. Falling back to system
    # roots would hide a missing/incorrect mounted dedicated database certificate.
    ca_file = getattr(settings, "DATABASE_SSL_CA_FILE", None)
    context = ssl.create_default_context(cafile=ca_file)
    context.check_hostname = mode == "verify-full"
    context.verify_mode = ssl.CERT_NONE if mode in {"allow", "prefer"} else ssl.CERT_REQUIRED

    certificate = getattr(settings, "DATABASE_SSL_CERT_FILE", None)
    key = getattr(settings, "DATABASE_SSL_KEY_FILE", None)
    if bool(certificate) != bool(key):
        raise ValueError("Database client certificate and key must be configured together")
    if certificate:
        context.load_cert_chain(certfile=certificate, keyfile=key)
    return context


def asyncpg_options(database_url, settings):
    """Keep libpq query names out of asyncpg keyword arguments; use real SSLContext."""
    url = make_url(database_url)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        return database_url, {}
    url = url.set(drivername="postgresql+asyncpg").difference_update_query(
        ["sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl"]
    )
    return url, {"ssl": create_ssl_context(settings) or False, "statement_cache_size": 0}


def sync_postgres_options(settings):
    """Preserve default sync-driver behavior; apply explicitly enabled verification."""
    mode = getattr(settings, "DATABASE_SSL_MODE", "disable")
    if mode == "disable":
        return {}
    create_ssl_context(settings)  # Validate the same explicit certificate custody.
    options = {"sslmode": mode}
    for setting, parameter in (
        ("DATABASE_SSL_CA_FILE", "sslrootcert"),
        ("DATABASE_SSL_CERT_FILE", "sslcert"),
        ("DATABASE_SSL_KEY_FILE", "sslkey"),
    ):
        value = getattr(settings, setting, None)
        if value:
            options[parameter] = value
    return options
