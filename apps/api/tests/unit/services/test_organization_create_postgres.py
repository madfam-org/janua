"""Real AsyncSession/ORM proof; only a guarded, synthetic PostgreSQL fixture.

This calls the mounted endpoint's writer with a persisted synthetic actor. It
does not prove hosted JWT authentication, invitations, mail, or OCI provenance.
Use JANUA_ORG_CREATE_TEST_DATABASE_URL + LOCAL_DB=yes; local runs also attest the owned
container through JANUA_ORG_CREATE_FIXTURE_ID. No sync-session replacement.
"""

import asyncio
import json
import os
import subprocess
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
from app.routers.v1.organizations.core import create_organization
from app.routers.v1.organizations.schemas import OrganizationCreateRequest
from app.services.org_claims_service import get_user_org_claims

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


@pytest_asyncio.fixture
async def pg():
    raw = os.getenv("JANUA_ORG_CREATE_TEST_DATABASE_URL")
    if not raw:
        if os.getenv("CI") == "true":
            pytest.fail("CI must supply the isolated PostgreSQL service URL")
        pytest.skip("Set JANUA_ORG_CREATE_TEST_DATABASE_URL and LOCAL_DB=yes")
    url = make_url(raw)
    if (
        os.getenv("LOCAL_DB") != "yes"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "janua_org_create_test"
        or url.username != "janua_org_owner"
        or url.drivername != "postgresql+asyncpg"
    ):
        pytest.fail("Organization proof requires loopback asyncpg and a *_test database")
    if os.getenv("CI") != "true":
        cid = os.getenv("JANUA_ORG_CREATE_FIXTURE_ID", "")
        if len(cid) != 64 or any(c not in "0123456789abcdef" for c in cid):
            pytest.fail("Local proof needs an owned synthetic container")
        metadata = json.loads(subprocess.check_output(
            ["docker", "inspect", "--format",
             '["{{.Id}}","{{index .Config.Labels "codex.owner"}}",'
             '"{{index .Config.Labels "codex.purpose"}}",{{.State.Running}},'
             '{{json .NetworkSettings.Ports}}]', cid],
            text=True, timeout=5,
        ))
        assert metadata[:4] == [cid, "map_stabilization", "synthetic-janua-org-create-native-proof", True]
        assert metadata[4] == {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(url.port)}]}
    admin = create_async_engine(url)
    schema = "organization_fixture_" + uuid4().hex
    async with admin.begin() as conn:
        assert (await conn.execute(text("SELECT current_database()"))).scalar_one() == url.database
        # CI's Docker-created janua user is a superuser; the dedicated login
        # must prove ordinary attributes exactly as it does in a local fixture.
        safe = (await conn.execute(text("""SELECT rolcanlogin AND NOT (rolsuper OR rolbypassrls OR
            rolcreatedb OR rolcreaterole OR rolreplication) AND NOT EXISTS
            (SELECT 1 FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid)
            AND d.datdba=r.oid FROM pg_roles r JOIN pg_database d
            ON d.datname=current_database() WHERE rolname=current_user"""))).scalar_one()
        assert safe is True
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[
                User.__table__, Organization.__table__, OrganizationMember.__table__,
                OrganizationMemberAppRole.__table__,
            ]))
        async with factory() as db:
            actor = User(email=f"actor-{uuid4().hex}@sim.invalid", status=UserStatus.ACTIVE,
                         is_admin=False, is_service_account=False, email_verified=True)
            db.add(actor)
            await db.commit()
        yield factory, engine, actor
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


def request(slug=None):
    return OrganizationCreateRequest(name="Organización sintética", slug=slug or "training-" + uuid4().hex)


async def counts(factory):
    async with factory() as db:
        values = []
        for table in (Organization, OrganizationMember):
            values.append((await db.execute(select(func.count()).select_from(table))).scalar_one())
        return tuple(values)


async def test_creator_and_active_admin_membership_are_committed_with_native_org_claims(pg):
    factory, _, actor = pg
    async with factory() as db:
        result = await create_organization(request(), actor, db)
    async with factory() as db:
        org = (await db.execute(select(Organization))).scalar_one()
        member = (await db.execute(select(OrganizationMember))).scalar_one()
        assert result.member_count == 1
        assert org.id == member.organization_id and org.owner_id == member.user_id == actor.id
        assert member.role == "admin" and member.status == "active"
        assert org.billing_email == actor.email and org.billing_plan == "free"
        assert (await db.get(User, actor.id)).is_admin is False
        claims = await get_user_org_claims(actor, db)
        assert claims["orgs"] == [{"id": str(org.id), "slug": org.slug, "role": "admin"}]
        assert "_app_roles" not in claims and "roles" not in claims
    assert await counts(factory) == (1, 1)


async def test_existing_slug_keeps_original_owner_and_membership(pg):
    factory, _, actor = pg
    payload = request()
    async with factory() as db:
        await create_organization(payload, actor, db)
    async with factory() as db:
        with pytest.raises(HTTPException) as caught:
            await create_organization(payload, actor, db)
        assert caught.value.status_code == 400
        await db.rollback()
    assert await counts(factory) == (1, 1)


async def test_native_member_insert_refusal_rolls_back_org_and_leaves_session_usable(pg):
    factory, engine, actor = pg
    async with engine.begin() as conn:
        await conn.execute(text("""CREATE FUNCTION refuse_fixture_member() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic membership refusal'; END $$"""))
        await conn.execute(text("""CREATE TRIGGER refuse_fixture_member BEFORE INSERT
            ON organization_members FOR EACH ROW EXECUTE FUNCTION refuse_fixture_member()"""))
    async with factory() as db:
        with pytest.raises(DBAPIError):
            await create_organization(request(), actor, db)
        assert (await db.execute(select(func.count()).select_from(Organization))).scalar_one() == 0
        assert await get_user_org_claims(actor, db) == {}
    assert await counts(factory) == (0, 0)


async def test_concurrent_same_slug_has_one_org_one_membership_and_no_failed_tx(pg):
    factory, engine, actor = pg
    payload = request()
    async with engine.begin() as conn:
        await conn.execute(text("""CREATE FUNCTION delay_fixture_org() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(0.15); RETURN NEW; END $$"""))
        await conn.execute(text("""CREATE TRIGGER delay_fixture_org BEFORE INSERT
            ON organizations FOR EACH ROW EXECUTE FUNCTION delay_fixture_org()"""))

    async def create():
        async with factory() as db:
            try:
                await create_organization(payload, actor, db)
                return "created"
            except (IntegrityError, HTTPException):
                if not db.is_active:
                    pytest.fail("Writer left the native session in a failed transaction")
                return "collision"

    assert sorted(await asyncio.gather(create(), create())) == ["collision", "created"]
    assert await counts(factory) == (1, 1)


async def test_removed_membership_stops_feeding_orgs_without_changing_actor(pg):
    factory, _, actor = pg
    async with factory() as db:
        await create_organization(request(), actor, db)
        member = (await db.execute(select(OrganizationMember))).scalar_one()
        member.status = "removed"
        await db.commit()
        assert await get_user_org_claims(actor, db) == {}
        assert (await db.get(User, actor.id)).is_admin is False
