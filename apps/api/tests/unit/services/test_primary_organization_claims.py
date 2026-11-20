"""An operator-set primary organization resolves a multi-org person's token.

Before migration 022, a person with several ACTIVE memberships and no
`tenant_id` match got `orgs` and nothing else: no `org_id`, no
`madfam_org_roles` and — the part that hurt — no application roles, so a staff
account with several organization memberships could never pass a resource
server gating on an app role. `tenant_id` could not fix it: it is the identity
pool, and pointing it at an organization once made staff unreachable by magic
link and password reset.

The choice lives in its own table, `user_primary_organizations`, read only by
the resolver in a guarded read. These tests pin the rule and that guard:

  * several memberships + a primary organization the person is an ACTIVE member
    of ⇒ that organization's claims and ONLY its application roles;
  * a primary organization they are not an active member of (inactive
    membership, no membership, or a cleared pointer) ⇒ nothing, as before;
  * `tenant_id` naming an active membership still wins, and then the table is
    not even read; a single membership never reads it either;
  * the session mint and the OIDC mint both carry the app role;
  * on a database WITHOUT the table, both mints still succeed for a multi-org
    person — no app roles, no error, and the caller's later writes commit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.models import Session as UserSession
from app.models.app_role import OrganizationMemberAppRole
from app.models.user_primary_organization import UserPrimaryOrganization
from app.routers.v1 import oauth_provider_shared
from app.services.auth_service import AuthService
from app.services.org_claims_service import (
    APP_ROLES_CLAIM,
    APP_ROLES_KEY,
    ORG_ROLES_CLAIM,
    get_user_org_claims,
)
from tests.unit.services.test_app_role_claims import _db, _grant, _member, _org

APP_ROLE = ("ops", "platform-admin")
APP_ROLE_CLAIM = "ops:platform-admin"


# ---------------------------------------------------------------------------
# When the table is read at all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_single_membership_never_reads_the_table():
    org, member = _org("only"), _member("member")
    db = _db([(member, org)], {member.id: [_grant(*APP_ROLE)]})

    claims = await get_user_org_claims(SimpleNamespace(id=uuid.uuid4(), tenant_id=None), db)

    assert claims["org_id"] == str(org.id)
    db.begin_nested.assert_not_called()


@pytest.mark.asyncio
async def test_a_matching_tenant_id_never_reads_the_table():
    org_a, member_a = _org("a"), _member()
    org_b, member_b = _org("b"), _member()
    db = _db([(member_a, org_a), (member_b, org_b)])

    claims = await get_user_org_claims(SimpleNamespace(id=uuid.uuid4(), tenant_id=org_a.id), db)

    assert claims["org_id"] == str(org_a.id)
    db.begin_nested.assert_not_called()


# ---------------------------------------------------------------------------
# End to end against a real (SQLite) schema
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def schema():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed(factory) -> dict:
    """One staff person: ACTIVE in a, b and c, INACTIVE in d; org e unrelated.

    Grants: `hcm:hr` in a, `ops:platform-admin` in b, and `ops:platform-admin`
    on the INACTIVE membership in d (which must never surface).
    """
    ids = {key: uuid.uuid4() for key in ("a", "b", "c", "d", "e")}
    user_id = uuid.uuid4()
    async with factory() as session:
        for key, org_id in ids.items():
            session.add(Organization(id=org_id, name=key.upper(), slug=f"org-{key}"))
        session.add(
            User(
                id=user_id,
                email="staff@example.com",
                status=UserStatus.ACTIVE,
                is_admin=False,
                user_metadata={},
                tenant_id=None,
            )
        )
        members = {}
        for key, status in (("a", "active"), ("b", "active"), ("c", "active"), ("d", "inactive")):
            members[key] = uuid.uuid4()
            session.add(
                OrganizationMember(
                    id=members[key],
                    organization_id=ids[key],
                    user_id=user_id,
                    role="member",
                    status=status,
                )
            )
        await session.flush()
        for key, (app, role) in (("a", ("hcm", "hr")), ("b", APP_ROLE), ("d", APP_ROLE)):
            session.add(
                OrganizationMemberAppRole(
                    organization_member_id=members[key],
                    app=app,
                    role=role,
                    granted_by="test",
                )
            )
        await session.commit()
    return {"user_id": user_id, **ids}


async def _set_primary(factory, user_id, organization_id) -> None:
    async with factory() as session:
        session.add(
            UserPrimaryOrganization(
                user_id=user_id,
                organization_id=organization_id,
                set_by="test",
                set_at=datetime.utcnow(),
            )
        )
        await session.commit()


async def _claims(factory, user_id) -> dict:
    async with factory() as session:
        user = await session.get(User, user_id)
        return await get_user_org_claims(user, session)


async def _drop_table(factory) -> None:
    async with factory() as session:
        await session.execute(text("DROP TABLE user_primary_organizations"))
        await session.commit()


@pytest.mark.asyncio
async def test_no_primary_is_ambiguous(schema):
    ids = await _seed(schema)

    claims = await _claims(schema, ids["user_id"])

    assert len(claims["orgs"]) == 3  # the inactive membership is not listed
    assert "org_id" not in claims and APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_primary_resolves_that_orgs_claims_and_only_its_app_roles(schema):
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])

    claims = await _claims(schema, ids["user_id"])

    assert claims["org_id"] == claims["tenant_id"] == str(ids["b"])
    assert claims["org_slug"] == "org-b"
    assert claims[ORG_ROLES_CLAIM] == ["member"]
    # ONLY org b's grant: a's `hcm:hr` must not ride along.
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["d", "e"], ids=["inactive-membership", "not-a-member"])
async def test_primary_without_active_membership_resolves_nothing(schema, target):
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids[target])

    claims = await _claims(schema, ids["user_id"])

    assert "org_id" not in claims
    assert ORG_ROLES_CLAIM not in claims
    # d carries a live `ops:platform-admin` grant on its INACTIVE membership:
    # pointing at d must not revive it.
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_a_cleared_pointer_is_no_primary(schema):
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], None)

    claims = await _claims(schema, ids["user_id"])

    assert "org_id" not in claims and APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_tenant_id_still_wins(schema):
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])
    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        user.tenant_id = ids["a"]
        await session.commit()

    claims = await _claims(schema, ids["user_id"])

    assert claims["org_id"] == str(ids["a"])
    assert claims[APP_ROLES_KEY] == ["hcm:hr"]


@pytest.mark.asyncio
async def test_primary_applies_when_tenant_id_names_no_active_membership(schema):
    """`tenant_id` first, ELSE the primary organization."""
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])
    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        user.tenant_id = uuid.uuid4()
        await session.commit()

    claims = await _claims(schema, ids["user_id"])

    assert claims["org_id"] == str(ids["b"])
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]


@pytest.mark.asyncio
async def test_without_the_table_the_resolver_is_exactly_todays(schema):
    """A database that has not had 022 applied: no error, no org claims."""
    ids = await _seed(schema)
    await _drop_table(schema)

    claims = await _claims(schema, ids["user_id"])

    assert len(claims["orgs"]) == 3
    assert "org_id" not in claims and APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_a_failed_read_keeps_the_callers_pending_writes(schema):
    """The read runs in a SAVEPOINT: a failure must not discard what the
    caller had pending (the session-limit revocations in create_session, for
    one), and the caller's transaction must still commit."""
    ids = await _seed(schema)
    await _drop_table(schema)

    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        user.display_name = "pending before the read"
        claims = await get_user_org_claims(user, session)
        await session.commit()

    async with schema() as session:
        reloaded = await session.get(User, ids["user_id"])
    assert "org_id" not in claims
    assert reloaded.display_name == "pending before the read"


@pytest.mark.asyncio
async def test_the_model_declares_the_cascades():
    """PostgreSQL enforces them; tests/unit/test_user_primary_organization_postgres.py
    checks the real constraints."""
    table = UserPrimaryOrganization.__table__
    user_fk = next(iter(table.c.user_id.foreign_keys))
    org_fk = next(iter(table.c.organization_id.foreign_keys))
    assert (user_fk.target_fullname, user_fk.ondelete) == ("users.id", "CASCADE")
    assert (org_fk.target_fullname, org_fk.ondelete) == ("organizations.id", "CASCADE")
    assert [c.name for c in table.primary_key.columns] == ["user_id"]
    assert "primary_organization_id" not in User.__table__.c


# --- the mints --------------------------------------------------------------


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


async def _mint_session(factory, user_id) -> tuple[dict, uuid.UUID]:
    """Session path (magic link, password, MFA, passkey): the REAL resolver and
    schema; only redis and entitlements stubbed."""
    async with factory() as session:
        user = await session.get(User, user_id)
        with (
            patch(
                "app.services.entitlements_service.get_user_entitlements",
                AsyncMock(return_value=[]),
            ),
            patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
            patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
        ):
            access_token, _refresh, row = await AuthService.create_session(
                db=session, user=user, enforce_session_limit=False
            )
    return _decode(access_token), row.id


async def _mint_oidc(factory, user_id, monkeypatch) -> dict:
    """OIDC path: the authorization-code handler, with the shared resolver
    running for real against the schema and every unrelated claim source
    stubbed as tests/unit/routers/test_oauth_provider_scope_enforcement does."""
    from app.routers.v1 import oauth_provider as op
    from tests.unit.routers.test_oauth_provider_scope_enforcement import (
        REDIRECT,
        _client,
        _token_patches,
    )

    monkeypatch.setattr(oauth_provider_shared, "user_requires_mfa", AsyncMock(return_value=False))
    monkeypatch.setattr(oauth_provider_shared, "assurance_for_request", AsyncMock(return_value={}))

    async with factory() as session:
        user = await session.get(User, user_id)

        async def real_resolver(_user, _db):
            # The handler's own db is a double; the resolver gets the real one.
            return await get_user_org_claims(user, session)

        db, patches = _token_patches(user)
        replaced = {"_get_user_org_claims", "_get_user_entitlements"}
        patches = [p for p in patches if getattr(p, "attribute", None) not in replaced]
        assert len(patches) == len(_token_patches(user)[1]) - 2
        patches.append(patch("app.routers.v1.oauth_provider_shared._get_user_org_claims", AsyncMock(side_effect=real_resolver)))
        patches.append(
            patch(
                "app.routers.v1.oauth_provider_shared._get_user_entitlements",
                AsyncMock(
                    return_value={
                        "tier": "community",
                        "roles": ["member"],
                        "sub_status": "inactive",
                        "is_admin": False,
                    }
                ),
            )
        )
        code_data = {
            "client_id": "jnc_scope_test",
            "user_id": str(user.id),
            "redirect_uri": REDIRECT,
            "scope": "openid profile email",
            "nonce": None,
            "code_challenge": None,
        }
        with (
            patch("app.routers.v1.oauth_provider_shared._get_auth_code", AsyncMock(return_value=code_data)),
            patch("app.routers.v1.oauth_provider_shared._delete_auth_code", AsyncMock()),
        ):
            for p in patches:
                p.start()
            try:
                await op._handle_authorization_code_grant(
                    code="c",
                    redirect_uri=REDIRECT,
                    client=_client(),
                    code_verifier=None,
                    db=db,
                    redis=AsyncMock(),
                )
                return op.jwt_manager.create_access_token.call_args.kwargs["additional_claims"]
            finally:
                for p in reversed(patches):
                    p.stop()


@pytest.mark.asyncio
async def test_session_token_carries_the_primary_orgs_app_role(schema):
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])

    claims, _ = await _mint_session(schema, ids["user_id"])

    assert claims["org_id"] == str(ids["b"])
    assert claims[APP_ROLES_CLAIM] == [APP_ROLE_CLAIM]
    assert claims[ORG_ROLES_CLAIM] == ["member"]
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_oidc_code_grant_carries_the_primary_orgs_app_role(schema, monkeypatch):
    """The app role is UNIONED onto the legacy organization-role list."""
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])

    claims = await _mint_oidc(schema, ids["user_id"], monkeypatch)

    assert claims["org_id"] == str(ids["b"])
    assert claims["roles"] == ["member", APP_ROLE_CLAIM]
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_without_the_table_a_multi_org_session_still_mints(schema):
    """THE availability test: this code on a database without 022."""
    ids = await _seed(schema)
    await _drop_table(schema)

    claims, session_id = await _mint_session(schema, ids["user_id"])

    assert len(claims["orgs"]) == 3
    assert "org_id" not in claims
    assert APP_ROLES_CLAIM not in claims
    # The session row create_session writes AFTER the failed read committed.
    async with schema() as session:
        stored = (
            await session.execute(select(UserSession).where(UserSession.id == session_id))
        ).scalar_one_or_none()
    assert stored is not None


@pytest.mark.asyncio
async def test_without_the_table_a_multi_org_oidc_token_still_mints(schema, monkeypatch):
    ids = await _seed(schema)
    await _drop_table(schema)

    claims = await _mint_oidc(schema, ids["user_id"], monkeypatch)

    assert len(claims["orgs"]) == 3
    assert "org_id" not in claims
    # Only the legacy organization role list, exactly as before.
    assert claims["roles"] == ["member"]
