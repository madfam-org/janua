"""Seed the isolated staging database with the admission probe's synthetic state.

    python -m app.staging_seed

Writes exactly three verified synthetic users and one public PKCE OAuth client
(``app/staging_synthetic.py``), and only when none of them exists yet. When all
four already exist with the expected shape it is a no-op; any other state is
refused before anything is written.

It connects with the ordinary runtime ``DATABASE_URL`` and the repo's TLS
options, never an owner credential, and proves that before writing: the role
is not superuser/BYPASSRLS, owns nothing, cannot CREATE in ``public`` or in the
database, and Alembic is at the single repository head. Everything happens in
one transaction behind an advisory lock, so a refusal or crash writes nothing.

Output is one bounded JSON line: counts, role-coded hashes of user ids and the
public client id. Never passwords, emails, tokens or exception text.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlsplit

from sqlalchemy import func, or_, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.staging_synthetic import (
    ADMISSION_CLIENT_ID,
    ADMISSION_CLIENT_NAME,
    ADMISSION_GRANT_TYPES,
    ADMISSION_REDIRECT_URI,
    ADMISSION_SCOPES,
    SYNTHETIC_USERS,
)

API_ROOT = Path(__file__).resolve().parents[1]
DATABASE_SUFFIX = "_sim"
PRODUCTION_HOSTS = frozenset({"auth.madfam.io", "janua.dev", "api.janua.dev", "app.janua.dev"})
# Arbitrary fixed key: two concurrent seeds serialize instead of racing.
ADVISORY_LOCK_KEY = 0x4A53_5345  # "JSSE"


class SeedRefused(Exception):
    """A fail-closed refusal. ``code`` is a fixed identifier, safe to print."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RoleFacts:
    database: str
    superuser: bool
    bypassrls: bool
    createdb: bool
    createrole: bool
    replication: bool
    owns_database: bool
    can_create_in_database: bool
    can_create_in_public: bool
    owned_relations: int
    owned_schemas: int


def _host(url: Optional[str]) -> str:
    return (urlsplit(url or "").hostname or "").lower()


def require_staging_settings(settings) -> None:
    """Environment and transport gates; pure, evaluated before any connection."""
    if getattr(settings, "ENVIRONMENT", None) != "staging":
        raise SeedRefused("environment_not_staging")
    for name in ("BASE_URL", "JWT_ISSUER"):
        if _host(getattr(settings, name, None)) in PRODUCTION_HOSTS:
            raise SeedRefused("production_issuer")
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        raise SeedRefused("database_not_postgresql")
    if not (url.database or "").endswith(DATABASE_SUFFIX):
        raise SeedRefused("database_not_sim")
    if getattr(settings, "DATABASE_SSL_MODE", None) != "verify-full":
        raise SeedRefused("tls_not_verify_full")
    ca_file = getattr(settings, "DATABASE_SSL_CA_FILE", None)
    if not ca_file or not os.path.isfile(ca_file):
        raise SeedRefused("tls_ca_missing")


def read_passwords(environ: Mapping[str, str]) -> dict[str, str]:
    """One distinct, strong password per synthetic role, from the environment only."""
    from app.services.auth_service import AuthService

    passwords = {}
    for user in SYNTHETIC_USERS:
        value = environ.get(user.password_env) or ""
        if not value:
            raise SeedRefused("password_missing")
        if not AuthService.validate_password_strength(value)[0]:
            raise SeedRefused("password_weak")
        passwords[user.role] = value
    if len(set(passwords.values())) != len(passwords):
        raise SeedRefused("password_reused")
    return passwords


def require_unprivileged(facts: RoleFacts) -> None:
    """The runtime role must be ordinary and provably unable to run DDL."""
    if not facts.database.endswith(DATABASE_SUFFIX):
        raise SeedRefused("database_not_sim")
    if facts.superuser:
        raise SeedRefused("role_superuser")
    if facts.bypassrls:
        raise SeedRefused("role_bypassrls")
    if facts.createdb or facts.createrole or facts.replication:
        raise SeedRefused("role_has_admin_attributes")
    if facts.owns_database or facts.owned_relations or facts.owned_schemas:
        raise SeedRefused("role_owns_objects")
    if facts.can_create_in_public or facts.can_create_in_database:
        raise SeedRefused("role_can_create")


def repository_head() -> str:
    """The single Alembic head of this checkout/image (revision files only)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise SeedRefused("repository_heads_not_single")
    return heads[0]


# MEMBER (not USAGE): a role that can SET ROLE to an owner can also run DDL.
_ROLE_FACTS = text(
    """
    SELECT current_database() AS database,
           r.rolsuper AS superuser, r.rolbypassrls AS bypassrls,
           r.rolcreatedb AS createdb, r.rolcreaterole AS createrole,
           r.rolreplication AS replication,
           pg_has_role(current_user, d.datdba, 'MEMBER') AS owns_database,
           has_database_privilege(current_database(), 'CREATE') AS can_create_in_database,
           has_schema_privilege(current_user, 'public', 'CREATE') AS can_create_in_public,
           (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname <> 'information_schema' AND n.nspname NOT LIKE 'pg\\_%'
               AND pg_has_role(current_user, c.relowner, 'MEMBER')) AS owned_relations,
           (SELECT count(*) FROM pg_namespace n
             WHERE n.nspname <> 'information_schema' AND n.nspname NOT LIKE 'pg\\_%'
               AND pg_has_role(current_user, n.nspowner, 'MEMBER')) AS owned_schemas
      FROM pg_roles r JOIN pg_database d ON d.datname = current_database()
     WHERE r.rolname = current_user
    """
)


async def _role_facts(db: AsyncSession) -> RoleFacts:
    row = (await db.execute(_ROLE_FACTS)).mappings().one()
    return RoleFacts(**row)


async def _require_alembic_head(db: AsyncSession) -> None:
    head = repository_head()
    try:
        versions = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
    except Exception as exc:
        raise SeedRefused("alembic_version_unreadable") from exc
    if versions != [head]:
        raise SeedRefused("alembic_not_at_head")


def _user_matches(user, password: str) -> bool:
    from app.models import UserStatus
    from app.services.auth_service import AuthService

    return (
        user.tenant_id is None
        and user.status == UserStatus.ACTIVE
        and user.is_active is not False
        and user.email_verified is True
        and user.is_admin is not True
        and user.is_service_account is False
        and not user.mfa_enabled
        and bool(user.password_hash)
        and AuthService.verify_password(password, user.password_hash)
    )


def _client_matches(client, operator_id) -> bool:
    return (
        client.client_id == ADMISSION_CLIENT_ID
        and client.name == ADMISSION_CLIENT_NAME
        and client.is_confidential is False
        and client.is_active is True
        and list(client.redirect_uris or []) == [ADMISSION_REDIRECT_URI]
        and list(client.allowed_scopes or []) == list(ADMISSION_SCOPES)
        and list(client.grant_types or []) == list(ADMISSION_GRANT_TYPES)
        and client.organization_id is None
        and client.audience is None
        and client.created_by == operator_id
    )


def _new_users(passwords: Mapping[str, str]) -> dict:
    from app.models import User, UserStatus
    from app.services.auth_service import AuthService

    return {
        user.role: User(
            email=user.email,
            password_hash=AuthService.hash_password(passwords[user.role]),
            status=UserStatus.ACTIVE,
            email_verified=True,
            is_active=True,
            is_admin=False,
            is_service_account=False,
            mfa_enabled=False,
            tenant_id=None,  # The untenanted pool that POST /auth/signin serves.
            first_name="Synthetic",
            last_name=user.role,
        )
        for user in SYNTHETIC_USERS
    }


def _new_client(operator) -> object:
    from app.models import OAuthClient
    from app.services.oauth_client_service import OAuthClientService

    # A hash of a secret nobody keeps: the column is NOT NULL, the client is public.
    _, secret_hash, secret_prefix = OAuthClientService.generate_client_secret()
    return OAuthClient(
        client_id=ADMISSION_CLIENT_ID,
        client_secret_hash=secret_hash,
        client_secret_prefix=secret_prefix,
        name=ADMISSION_CLIENT_NAME,
        description="Synthetic staging admission probe (public PKCE client)",
        redirect_uris=[ADMISSION_REDIRECT_URI],
        allowed_scopes=list(ADMISSION_SCOPES),
        grant_types=list(ADMISSION_GRANT_TYPES),
        audience=None,
        organization_id=None,
        is_confidential=False,
        is_active=True,
        created_by=operator.id,
    )


def user_ref(role: str, user_id) -> str:
    return hashlib.sha256(f"janua-staging:{role}:{user_id}".encode()).hexdigest()[:16]


async def seed(engine: AsyncEngine, passwords: Mapping[str, str]) -> dict:
    """All database gates, then create-or-verify, in one transaction."""
    from app.core.reserved_oauth_boundaries import reserved_fields
    from app.models import OAuthClient, User

    if reserved_fields(name=ADMISSION_CLIENT_NAME, scopes=ADMISSION_SCOPES):
        raise SeedRefused("client_values_reserved")
    emails = [user.email for user in SYNTHETIC_USERS]
    async with AsyncSession(engine, expire_on_commit=False) as db:
        async with db.begin():
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
            require_unprivileged(await _role_facts(db))
            await _require_alembic_head(db)

            users = (await db.execute(
                select(User).where(func.lower(User.email).in_(emails))
            )).scalars().all()
            clients = (await db.execute(select(OAuthClient).where(or_(
                OAuthClient.client_id == ADMISSION_CLIENT_ID,
                OAuthClient.name == ADMISSION_CLIENT_NAME,
            )))).scalars().all()

            if not users and not clients:
                by_role = _new_users(passwords)
                db.add_all(by_role.values())
                await db.flush()
                client = _new_client(by_role["operator"])
                db.add(client)
                await db.flush()
                result = "created"
            else:
                by_email = {u.email: u for u in users}
                if len(users) != len(SYNTHETIC_USERS) or set(by_email) != set(emails):
                    raise SeedRefused("partial_or_foreign_state")
                by_role = {u.role: by_email[u.email] for u in SYNTHETIC_USERS}
                if len(clients) != 1:
                    raise SeedRefused("partial_or_foreign_state")
                if not all(_user_matches(by_role[r], passwords[r]) for r in by_role):
                    raise SeedRefused("user_shape_mismatch")
                client = clients[0]
                if not _client_matches(client, by_role["operator"].id):
                    raise SeedRefused("client_shape_mismatch")
                result = "unchanged"

    return {
        "tool": "janua.staging_seed",
        "result": result,
        "users": len(by_role),
        "oauth_clients": 1,
        "user_refs": {role: user_ref(role, user.id) for role, user in by_role.items()},
        "client_id": client.client_id,
    }


def build_engine(settings) -> AsyncEngine:
    from app.core.database_ssl import asyncpg_options

    url, connect_args = asyncpg_options(settings.DATABASE_URL, settings)
    return create_async_engine(url, connect_args=connect_args, poolclass=NullPool)


async def run(settings, environ: Mapping[str, str]) -> dict:
    require_staging_settings(settings)
    passwords = read_passwords(environ)
    engine = build_engine(settings)
    try:
        return await seed(engine, passwords)
    finally:
        await engine.dispose()


def refusal(code: str) -> dict:
    return {"tool": "janua.staging_seed", "result": "refused", "reason": code}


def main() -> int:
    from app.config import settings

    try:
        receipt = asyncio.run(run(settings, os.environ))
        status = 0
    except SeedRefused as exc:
        receipt, status = refusal(exc.code), 2
    except Exception as exc:  # Class name only: messages can carry connection details.
        receipt, status = refusal("error:" + type(exc).__name__), 1
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    sys.exit(main())
