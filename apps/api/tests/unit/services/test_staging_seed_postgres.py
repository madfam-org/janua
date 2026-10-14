"""Real PostgreSQL proof of app.staging_seed: ordinary owner, separate runtime role.

The owner (CI step "Prepare staging seed fixture", or a local container with the
same roles) owns ``janua_staging_seed_sim`` and runs ``alembic upgrade head``;
the seed then runs as a runtime role holding DML grants only. Synthetic rows
are removed by the owner before and after every test. Transport (TLS) and
environment gates are pure and covered in tests/unit/core/test_staging_seed.py.
"""

import asyncio
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app import staging_seed
from app.models import OAuthClient, User, UserStatus
from app.services.auth_service import AuthService
from app.staging_synthetic import (
    ADMISSION_CLIENT_ID,
    ADMISSION_CLIENT_NAME,
    ADMISSION_REDIRECT_URI,
    SYNTHETIC_USERS,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.database]

RUNTIME_URL_ENV = "JANUA_STAGING_SEED_TEST_DATABASE_URL"
OWNER_URL_ENV = "JANUA_STAGING_SEED_OWNER_TEST_DATABASE_URL"
DATABASE = "janua_staging_seed_sim"
API_ROOT = Path(__file__).resolve().parents[3]
EMAILS = [user.email for user in SYNTHETIC_USERS]


def _fixture_urls():
    runtime, owner = os.getenv(RUNTIME_URL_ENV), os.getenv(OWNER_URL_ENV)
    if not runtime or not owner:
        if os.getenv("CI") == "true":
            pytest.fail("CI must supply both staging seed fixture URLs")
        pytest.skip(f"Set {RUNTIME_URL_ENV}, {OWNER_URL_ENV} and LOCAL_DB=yes")
    urls = make_url(runtime), make_url(owner)
    for url, user in zip(urls, ("janua_seed_runtime", "janua_seed_owner")):
        if (
            os.getenv("LOCAL_DB") != "yes"
            or url.host not in {"127.0.0.1", "localhost"}
            or url.database != DATABASE
            or url.username != user
            or url.drivername != "postgresql+asyncpg"
        ):
            pytest.fail("Staging seed proof requires the loopback *_sim fixture roles")
    return urls


async def _owner_sql(owner_url, *statements):
    engine = create_async_engine(owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def migrated():
    runtime_url, owner_url = _fixture_urls()
    rendered = owner_url.render_as_string(hide_password=False)
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT, capture_output=True, text=True, timeout=300,
        env={**os.environ, "DATABASE_URL": rendered, "DIRECT_DATABASE_URL": rendered},
    )
    assert upgrade.returncode == 0, upgrade.stderr[-2000:]
    asyncio.run(_owner_sql(
        owner_url,
        "GRANT USAGE ON SCHEMA public TO janua_seed_runtime",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO janua_seed_runtime",
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO janua_seed_runtime",
    ))
    return runtime_url, owner_url


CLEAN = (
    f"DELETE FROM oauth_clients WHERE client_id = '{ADMISSION_CLIENT_ID}' "
    f"OR name = '{ADMISSION_CLIENT_NAME}'",
    "DELETE FROM users WHERE lower(email) IN ({})".format(", ".join(f"'{e}'" for e in EMAILS)),
)


@pytest_asyncio.fixture
async def pg(migrated):
    runtime_url, owner_url = migrated
    await _owner_sql(owner_url, *CLEAN)
    owner = create_async_engine(owner_url, poolclass=NullPool)
    runtime = create_async_engine(runtime_url, poolclass=NullPool)
    try:
        yield SimpleNamespace(owner=owner, runtime=runtime, owner_url=owner_url)
    finally:
        await owner.dispose()
        await runtime.dispose()
        await _owner_sql(owner_url, *CLEAN)


def passwords():
    return {user.role: secrets.token_urlsafe(18) + "aA1!" for user in SYNTHETIC_USERS}


async def snapshot(engine):
    async with engine.connect() as conn:
        users = (await conn.execute(select(User.id, User.email, User.password_hash, User.is_admin)
                                    .where(User.email.in_(EMAILS)).order_by(User.email))).all()
        clients = (await conn.execute(select(OAuthClient.id, OAuthClient.redirect_uris)
                                      .order_by(OAuthClient.id))).all()
        totals = [(await conn.execute(select(func.count()).select_from(t))).scalar_one()
                  for t in (User, OAuthClient)]
    return users, [(c.id, list(c.redirect_uris or [])) for c in clients], totals


async def test_runtime_role_creates_exactly_once_then_is_a_no_op(pg):
    secret = passwords()
    first = await staging_seed.seed(pg.runtime, secret)
    assert first["result"] == "created"
    assert (first["users"], first["oauth_clients"], first["client_id"]) == (3, 1, ADMISSION_CLIENT_ID)
    before = await snapshot(pg.owner)

    second = await staging_seed.seed(pg.runtime, secret)
    assert second["result"] == "unchanged"
    assert second["user_refs"] == first["user_refs"]
    assert await snapshot(pg.owner) == before

    async with pg.owner.connect() as conn:
        users = {u.email: u for u in (await conn.execute(
            select(User).where(User.email.in_(EMAILS)))).all()}
        client = (await conn.execute(select(OAuthClient).where(
            OAuthClient.client_id == ADMISSION_CLIENT_ID))).one()
    assert set(users) == set(EMAILS)
    for user in SYNTHETIC_USERS:
        row = users[user.email]
        assert row.tenant_id is None and row.status == UserStatus.ACTIVE
        assert row.email_verified is True and row.is_admin is False
        assert row.is_service_account is False
        assert AuthService.verify_password(secret[user.role], row.password_hash)
    assert client.is_confidential is False and client.is_active is True
    assert list(client.redirect_uris) == [ADMISSION_REDIRECT_URI]
    assert client.created_by == users["operator@staging.example.com"].id

    rendered = json.dumps([first, second])
    assert "@" not in rendered
    assert not any(value in rendered for value in secret.values())


async def test_runtime_role_really_cannot_run_ddl(pg):
    async with pg.runtime.connect() as conn:
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(text("CREATE TABLE staging_seed_probe (id int)"))


DRIFT = {
    "foreign_user_missing": "DELETE FROM users WHERE email = 'foreign@staging.example.com'",
    "client_missing": f"DELETE FROM oauth_clients WHERE client_id = '{ADMISSION_CLIENT_ID}'",
    "client_redirect_drift": "UPDATE oauth_clients SET redirect_uris = "
                             "'[\"http://127.0.0.1/elsewhere\"]' "
                             f"WHERE client_id = '{ADMISSION_CLIENT_ID}'",
    "operator_promoted": "UPDATE users SET is_admin = true "
                         "WHERE email = 'operator@staging.example.com'",
}


@pytest.mark.parametrize("drift,code", [
    ("foreign_user_missing", "partial_or_foreign_state"),
    ("client_missing", "partial_or_foreign_state"),
    ("client_redirect_drift", "client_shape_mismatch"),
    ("operator_promoted", "user_shape_mismatch"),
    ("password_rotated", "user_shape_mismatch"),
])
async def test_partial_or_drifted_state_is_refused_without_writes(pg, drift, code):
    secret = passwords()
    await staging_seed.seed(pg.runtime, secret)
    if drift == "password_rotated":
        secret = {**secret, "invitee": secrets.token_urlsafe(18) + "bB2?"}
    else:
        await _owner_sql(pg.owner_url, DRIFT[drift])
    before = await snapshot(pg.owner)
    with pytest.raises(staging_seed.SeedRefused) as refused:
        await staging_seed.seed(pg.runtime, secret)
    assert refused.value.code == code
    assert await snapshot(pg.owner) == before


async def test_owner_role_is_refused_before_any_write(pg):
    before = await snapshot(pg.owner)
    with pytest.raises(staging_seed.SeedRefused) as refused:
        await staging_seed.seed(pg.owner, passwords())
    assert refused.value.code == "role_owns_objects"
    assert await snapshot(pg.owner) == before


async def test_stale_alembic_version_is_refused(pg):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = staging_seed.repository_head()
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    previous = ScriptDirectory.from_config(config).get_revision(head).down_revision
    await _owner_sql(pg.owner_url, f"UPDATE alembic_version SET version_num = '{previous}'")
    try:
        before = await snapshot(pg.owner)
        with pytest.raises(staging_seed.SeedRefused) as refused:
            await staging_seed.seed(pg.runtime, passwords())
        assert refused.value.code == "alembic_not_at_head"
        assert await snapshot(pg.owner) == before
    finally:
        await _owner_sql(pg.owner_url, f"UPDATE alembic_version SET version_num = '{head}'")
