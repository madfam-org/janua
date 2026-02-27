"""
Seed MADFAM ecosystem OAuth clients into the Janua database.

Idempotent script that registers OAuth clients for each MADFAM ecosystem
application. Skips clients that already exist (matched by name). Prints
plain-text secrets for newly created clients so the operator can configure
each consumer application.

Usage:
    cd apps/api
    python scripts/seed_ecosystem_clients.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ecosystem client definitions
# ---------------------------------------------------------------------------

ECOSYSTEM_CLIENTS: list[dict[str, Any]] = [
    {
        "name": "janua-dashboard",
        "description": "Janua user management dashboard",
        "audience": "janua.dev",
        "redirect_uris": [
            "https://app.janua.dev/api/auth/callback",
            "http://localhost:4101/api/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email", "admin"],
    },
    {
        "name": "enclii-dispatch",
        "description": "Enclii platform administration console (Dispatch)",
        "audience": "enclii-api",
        # Pre-assigned: already deployed in admin.enclii.dev production config
        "client_id": "jnc_lofqyf9LQXG_OwENAIw89p_XvngkWMi-",
        "redirect_uris": [
            "https://admin.enclii.dev/auth/callback",
            "http://localhost:3001/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
    {
        "name": "enclii-switchyard",
        "description": "Enclii Switchyard platform (API + UI)",
        "audience": "enclii-api",
        # Pre-assigned: already deployed in Enclii K8s production secret
        "client_id": "jnc_RqeHy54KYGjVr8yQiBeUncMhnQFhS2NA",
        "redirect_uris": [
            "https://api.enclii.dev/v1/auth/callback",
            "https://app.enclii.dev/auth/callback",
            "http://localhost:3000/auth/callback",
            "http://localhost:8080/v1/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
    {
        "name": "tezca-web",
        "description": "Tezca web application (tezca.mx)",
        "audience": "tezca-api",
        # Pre-assigned: already deployed in Tezca K8s production secret
        "client_id": "jnc_e3T94-MNy1dXAUNR5KetwduopRALT_nR",
        "redirect_uris": [
            "https://tezca.mx/api/auth/callback",
            "http://localhost:3000/api/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
    {
        "name": "tezca-admin",
        "description": "Tezca admin panel (admin.tezca.mx)",
        "audience": "tezca-api",
        # Pre-assigned: already deployed in Tezca admin K8s production secret
        "client_id": "jnc_dyS_lo50uQU81nsuFsWaHZbnTKYTWe2m",
        "redirect_uris": [
            "https://admin.tezca.mx/api/auth/callback",
            "http://localhost:3001/api/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email", "tezca:admin"],
    },
    {
        "name": "dhanam-web",
        "description": "Dhanam web application (app.dhan.am)",
        "audience": "dhanam-api",
        # Pre-assigned: already deployed in Dhanam .env.production
        "client_id": "jnc_uE2zp9ume_Fd6jMl1elL6wqjiECM711t",
        "redirect_uris": [
            "https://app.dhan.am/auth/callback",
            "http://localhost:3000/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
    {
        "name": "yantra4d-studio",
        "description": "Yantra4D studio application (4d-app.madfam.io)",
        "audience": "yantra4d-api",
        "redirect_uris": [
            "https://4d-app.madfam.io",
            "https://4d-app.madfam.io/auth/callback",
            "http://localhost:5173/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
    {
        "name": "yantra4d-admin",
        "description": "Yantra4D admin panel (4d-admin.madfam.io)",
        "audience": "yantra4d-api",
        "redirect_uris": [
            "https://4d-admin.madfam.io",
            "https://4d-admin.madfam.io/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email", "admin"],
    },
    {
        "name": "stratum-tcg-client",
        "description": "Stratum TCG client application",
        "audience": "stratum-tcg-api",
        "redirect_uris": [
            "https://stratum-tcg.dev/api/auth/callback",
            "http://localhost:5173/api/auth/callback",
        ],
        "allowed_scopes": ["openid", "profile", "email"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_client_id() -> str:
    """Generate a client identifier: ``jnc_`` + URL-safe random string."""
    return f"jnc_{secrets.token_urlsafe(24)}"


def _generate_client_secret() -> str:
    """Generate a client secret: ``jns_`` + 48 random hex characters."""
    return f"jns_{secrets.token_hex(24)}"


def _hash_secret(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _resolve_database_url() -> str:
    """
    Read DATABASE_URL from the environment (or ``.env`` file) and convert
    the scheme to an async driver if necessary.
    """
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL is not set. Export it or add it to .env")
        sys.exit(1)

    # Swap synchronous driver for async equivalent
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def _get_admin_user_id(engine: AsyncEngine) -> uuid.UUID:
    """Return the id of the first admin user, or abort."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id FROM users WHERE is_admin = true ORDER BY created_at ASC LIMIT 1"
            )
        )
        row = result.fetchone()

    if row is None:
        logger.error(
            "No admin user found in the database. "
            "Create an admin user first (e.g. via ADMIN_BOOTSTRAP_PASSWORD)."
        )
        sys.exit(1)

    admin_id = row[0]
    logger.info("Using admin user %s as created_by", admin_id)
    return admin_id


async def _seed_clients(engine: AsyncEngine) -> None:
    """Insert missing ecosystem clients into ``oauth_clients``."""
    admin_id = await _get_admin_user_id(engine)
    now = datetime.now(timezone.utc)

    created_count = 0
    skipped_count = 0

    async with engine.begin() as conn:
        for client_def in ECOSYSTEM_CLIENTS:
            name = client_def["name"]

            # Idempotency check — match by name or pre-assigned client_id
            pre_assigned_id = client_def.get("client_id")
            existing = await conn.execute(
                text(
                    "SELECT id FROM oauth_clients "
                    "WHERE name = :name OR client_id = :cid"
                ),
                {"name": name, "cid": pre_assigned_id or ""},
            )
            if existing.fetchone() is not None:
                logger.info("SKIP  %-25s (already exists)", name)
                skipped_count += 1
                continue

            client_id = pre_assigned_id or _generate_client_id()
            plain_secret = _generate_client_secret()
            secret_hash = _hash_secret(plain_secret)
            secret_prefix = plain_secret[:8]

            await conn.execute(
                text(
                    """
                    INSERT INTO oauth_clients (
                        id,
                        created_by,
                        client_id,
                        client_secret_hash,
                        client_secret_prefix,
                        name,
                        description,
                        redirect_uris,
                        allowed_scopes,
                        grant_types,
                        audience,
                        is_active,
                        is_confidential,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :created_by,
                        :client_id,
                        :client_secret_hash,
                        :client_secret_prefix,
                        :name,
                        :description,
                        :redirect_uris::jsonb,
                        :allowed_scopes::jsonb,
                        :grant_types::jsonb,
                        :audience,
                        true,
                        true,
                        :now,
                        :now
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "created_by": str(admin_id),
                    "client_id": client_id,
                    "client_secret_hash": secret_hash,
                    "client_secret_prefix": secret_prefix,
                    "name": name,
                    "description": client_def.get("description"),
                    "redirect_uris": _json_dumps(client_def["redirect_uris"]),
                    "allowed_scopes": _json_dumps(client_def["allowed_scopes"]),
                    "grant_types": _json_dumps(
                        ["authorization_code", "refresh_token"]
                    ),
                    "audience": client_def.get("audience"),
                    "now": now,
                },
            )

            created_count += 1
            logger.info("NEW   %-25s  client_id=%s", name, client_id)
            # Print credentials for operator to capture — secret is shown
            # ONLY here and never again, so operator must save it now.
            print(
                f"\n{'=' * 64}\n"
                f"  Client:  {name}\n"
                f"  ID:      {client_id}\n"
                f"  Secret:  {plain_secret}\n"
                f"  SAVE THIS SECRET NOW — it cannot be retrieved later.\n"
                f"{'=' * 64}"
            )

    print()
    logger.info(
        "Done. Created %d client(s), skipped %d existing.",
        created_count,
        skipped_count,
    )


def _json_dumps(obj: Any) -> str:
    """Serialize to JSON string for JSONB parameter binding."""
    import json

    return json.dumps(obj)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    database_url = _resolve_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        await _seed_clients(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(130)
