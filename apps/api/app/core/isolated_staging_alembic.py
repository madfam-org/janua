"""Closed staging-migrator transport, selected only by trusted Alembic code."""

from __future__ import annotations

import ssl
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

RECEIPT_ATTRIBUTE = "janua_staging_connection_receipt"
EXPECTED_RECEIPT: dict[str, Any] = {
    "profile": "janua-staging-ddl-connection-v1",
    "database": "janua_staging",
    "role": "enclii_migrator",
    "postgres_major": 18,
    "statement_timeout_ms": 120000,
    "lock_timeout_ms": 5000,
    "tls": True,
    "owner_nonprivileged": True,
    "owner_without_memberships": True,
    "database_owned": True,
}


def isolated_staging_requested(attributes: Mapping[str, Any]) -> bool:
    value = attributes.get("janua_staging_isolated", False)
    if type(value) is not bool:
        raise RuntimeError("Invalid isolated staging migration selector")
    return value


def isolated_staging_connect_args(
    environment: str, connect_args: Mapping[str, Any]
) -> dict[str, Any]:
    """No caller-selected limits, inherited options or insecure TLS fallback."""
    transport = connect_args.get("ssl")
    if (
        environment != "staging"
        or set(connect_args) != {"ssl", "statement_cache_size"}
        or type(connect_args.get("statement_cache_size")) is not int
        or connect_args["statement_cache_size"] != 0
        or not isinstance(transport, ssl.SSLContext)
        or not transport.check_hostname
        or transport.verify_mode != ssl.CERT_REQUIRED
    ):
        raise RuntimeError("Isolated staging migration transport refused")
    return {
        "ssl": transport,
        "statement_cache_size": 0,
        "timeout": 5,
        "command_timeout": 120,
        "server_settings": {"statement_timeout": "120000", "lock_timeout": "5000"},
    }


def inspect_isolated_staging_connection(connection: Connection) -> dict[str, Any]:
    """Called inside Alembic's transaction, on its real DDL connection."""
    row = connection.execute(text("""SELECT 'janua-staging-ddl-connection-v1' AS profile,
            current_database() AS database, current_user AS role,
            current_setting('server_version_num')::int / 10000 AS postgres_major,
            (SELECT setting::int FROM pg_settings WHERE name='statement_timeout')
              AS statement_timeout_ms,
            (SELECT setting::int FROM pg_settings WHERE name='lock_timeout')
              AS lock_timeout_ms,
            EXISTS(SELECT 1 FROM pg_stat_ssl WHERE pid=pg_backend_pid() AND ssl) AS tls,
            NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole
              OR r.rolreplication) AS owner_nonprivileged,
            NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid)
              AS owner_without_memberships,
            d.datdba=r.oid AS database_owned
            FROM pg_roles r JOIN pg_database d ON d.datname=current_database()
            WHERE r.rolname=current_user""")).mappings().one()
    actual = dict(row)
    if actual != EXPECTED_RECEIPT or any(
        type(actual[key]) is not type(value) for key, value in EXPECTED_RECEIPT.items()
    ):
        raise RuntimeError("Isolated staging DDL connection refused")
    return dict(EXPECTED_RECEIPT)
