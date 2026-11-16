"""An operator-set primary organization resolves a multi-org person's token.

Before migration 022, a person with several ACTIVE memberships and no
`tenant_id` match got `orgs` and nothing else: no `org_id`, no
`madfam_org_roles` and — the part that hurt — no application roles, so a staff
account with several organization memberships could never pass a resource
server gating on an app role. `tenant_id` could not fix it: it is the identity
pool, and pointing it at an organization once made staff unreachable by magic
link and password reset.

These tests pin the rule as built:

  * several memberships + a primary organization the person is an ACTIVE member
    of ⇒ that organization's claims and ONLY its application roles;
  * a primary organization they are not an active member of (inactive
    membership, or no membership at all) ⇒ nothing, exactly as before;
  * `tenant_id` naming an active membership still wins;
  * a single membership is unchanged whatever the pointer says;
  * the session mint and the OIDC mint both carry the app role for such a
    person, through the one shared resolver.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base, Organization, OrganizationMember, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
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


def _person(*, tenant_id=None, primary_organization_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="staff@example.com",
        tenant_id=tenant_id,
        primary_organization_id=primary_organization_id,
        is_admin=False,
        is_active=True,
        is_service_account=False,
    )


# ---------------------------------------------------------------------------
# The resolver, against a query double (what each branch reads)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_primary_organization_resolves_a_multi_org_person_to_that_org():
    org_a, member_a = _org("a"), _member("admin")
    org_b, member_b = _org("b"), _member("member")
    org_c, member_c = _org("c"), _member("owner")
    db = _db(
        [(member_a, org_a), (member_b, org_b), (member_c, org_c)],
        {
            member_a.id: [_grant("hcm", "hr")],
            member_b.id: [_grant(*APP_ROLE)],
            member_c.id: [_grant("hcm", "admin")],
        },
    )

    claims = await get_user_org_claims(_person(primary_organization_id=org_b.id), db)

    assert claims["org_id"] == claims["tenant_id"] == str(org_b.id)
    assert claims["org_slug"] == "b"
    assert claims[ORG_ROLES_CLAIM] == ["member"]
    # ONLY org B's grants: A's and C's must not ride along.
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]
    assert len(claims["orgs"]) == 3


@pytest.mark.asyncio
async def test_primary_organization_outside_the_active_memberships_resolves_to_nothing():
    """The pointer names an org that is not among the ACTIVE membership rows."""
    org_a, member_a = _org("a"), _member()
    org_b, member_b = _org("b"), _member()
    db = _db(
        [(member_a, org_a), (member_b, org_b)],
        {member_a.id: [_grant(*APP_ROLE)], member_b.id: [_grant(*APP_ROLE)]},
    )

    claims = await get_user_org_claims(_person(primary_organization_id=uuid.uuid4()), db)

    assert "org_id" not in claims
    assert ORG_ROLES_CLAIM not in claims
    assert APP_ROLES_KEY not in claims
    # No grants query ran at all: there was no membership to read from.
    assert db._calls["app_role_queries"] == []


@pytest.mark.asyncio
async def test_tenant_id_still_wins_over_the_primary_organization():
    org_a, member_a = _org("a"), _member("admin")
    org_b, member_b = _org("b"), _member("member")
    db = _db(
        [(member_a, org_a), (member_b, org_b)],
        {member_a.id: [_grant("hcm", "hr")], member_b.id: [_grant(*APP_ROLE)]},
    )

    claims = await get_user_org_claims(
        _person(tenant_id=org_a.id, primary_organization_id=org_b.id), db
    )

    assert claims["org_id"] == str(org_a.id)
    assert claims[APP_ROLES_KEY] == ["hcm:hr"]


@pytest.mark.asyncio
async def test_primary_organization_applies_when_tenant_id_names_no_active_membership():
    """`tenant_id` first, ELSE the primary organization: a pool id that is not
    an active membership does not block the explicit choice."""
    org_a, member_a = _org("a"), _member()
    org_b, member_b = _org("b"), _member()
    db = _db([(member_a, org_a), (member_b, org_b)], {member_b.id: [_grant(*APP_ROLE)]})

    claims = await get_user_org_claims(
        _person(tenant_id=uuid.uuid4(), primary_organization_id=org_b.id), db
    )

    assert claims["org_id"] == str(org_b.id)
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]


@pytest.mark.asyncio
async def test_single_membership_is_unchanged_whatever_the_pointer_says():
    org, member = _org("only"), _member("member")
    db = _db([(member, org)], {member.id: [_grant(*APP_ROLE)]})

    claims = await get_user_org_claims(_person(primary_organization_id=uuid.uuid4()), db)

    assert claims["org_id"] == str(org.id)
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]


@pytest.mark.asyncio
async def test_a_user_object_without_the_attribute_stays_ambiguous():
    """Callers that hand in a lightweight user keep today's behaviour."""
    org_a, member_a = _org("a"), _member()
    org_b, member_b = _org("b"), _member()
    db = _db([(member_a, org_a), (member_b, org_b)])
    user = SimpleNamespace(id=uuid.uuid4(), tenant_id=None)

    claims = await get_user_org_claims(user, db)

    assert "org_id" not in claims and APP_ROLES_KEY not in claims


# ---------------------------------------------------------------------------
# End to end against a real (SQLite) schema: memberships, grants, the mints
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


async def _set_primary(factory, user_id, organization_id) -> User:
    async with factory() as session:
        user = await session.get(User, user_id)
        user.primary_organization_id = organization_id
        await session.commit()
        await session.refresh(user)
        return user


@pytest.mark.asyncio
async def test_real_schema_no_primary_is_ambiguous(schema):
    ids = await _seed(schema)
    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        claims = await get_user_org_claims(user, session)

    assert len(claims["orgs"]) == 3  # the inactive membership is not listed
    assert "org_id" not in claims and APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_real_schema_primary_resolves_that_orgs_claims_and_app_roles(schema):
    ids = await _seed(schema)
    user = await _set_primary(schema, ids["user_id"], ids["b"])
    async with schema() as session:
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == str(ids["b"])
    assert claims["org_slug"] == "org-b"
    assert claims[APP_ROLES_KEY] == [APP_ROLE_CLAIM]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["d", "e"], ids=["inactive-membership", "not-a-member"])
async def test_real_schema_primary_without_active_membership_resolves_nothing(schema, target):
    ids = await _seed(schema)
    user = await _set_primary(schema, ids["user_id"], ids[target])
    async with schema() as session:
        claims = await get_user_org_claims(user, session)

    assert "org_id" not in claims
    assert ORG_ROLES_CLAIM not in claims
    # d carries a live `ops:platform-admin` grant on its INACTIVE membership:
    # pointing at d must not revive it.
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_real_schema_tenant_id_still_wins(schema):
    ids = await _seed(schema)
    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        user.tenant_id = ids["a"]
        user.primary_organization_id = ids["b"]
        await session.commit()
        claims = await get_user_org_claims(user, session)

    assert claims["org_id"] == str(ids["a"])
    assert claims[APP_ROLES_KEY] == ["hcm:hr"]


@pytest.mark.asyncio
async def test_deleting_the_primary_organization_clears_the_pointer_in_the_model(schema):
    """The model declares ON DELETE SET NULL (PostgreSQL enforces it; the
    parity test in tests/unit/test_user_primary_organization_postgres.py
    checks the real constraint)."""
    fk = next(iter(User.__table__.c.primary_organization_id.foreign_keys))
    assert fk.ondelete == "SET NULL"
    assert fk.target_fullname == "organizations.id"
    assert User.__table__.c.primary_organization_id.nullable is True


# --- the mints --------------------------------------------------------------


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


@pytest.mark.asyncio
async def test_session_token_carries_the_primary_orgs_app_role(schema):
    """Session path (magic link, password, MFA, passkey): the REAL resolver,
    the real schema, only redis and entitlements stubbed."""
    ids = await _seed(schema)
    await _set_primary(schema, ids["user_id"], ids["b"])

    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        with (
            patch(
                "app.services.entitlements_service.get_user_entitlements",
                AsyncMock(return_value=[]),
            ),
            patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
            patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
        ):
            access_token, _refresh, _session = await AuthService.create_session(
                db=session, user=user, enforce_session_limit=False
            )

    claims = _decode(access_token)
    assert claims["org_id"] == str(ids["b"])
    assert claims[APP_ROLES_CLAIM] == [APP_ROLE_CLAIM]
    assert claims[ORG_ROLES_CLAIM] == ["member"]
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_session_token_without_primary_carries_no_app_role(schema):
    """The control: same person, no pointer ⇒ today's token."""
    ids = await _seed(schema)

    async with schema() as session:
        user = await session.get(User, ids["user_id"])
        with (
            patch(
                "app.services.entitlements_service.get_user_entitlements",
                AsyncMock(return_value=[]),
            ),
            patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
            patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
        ):
            access_token, _refresh, _session = await AuthService.create_session(
                db=session, user=user, enforce_session_limit=False
            )

    claims = _decode(access_token)
    assert "org_id" not in claims
    assert APP_ROLES_CLAIM not in claims


@pytest.mark.asyncio
async def test_oidc_code_grant_carries_the_primary_orgs_app_role(schema, monkeypatch):
    """OIDC path: the authorization-code handler, with the shared resolver
    running for real against the seeded schema and every unrelated claim
    source stubbed as tests/unit/routers/test_oauth_provider_scope_enforcement
    does. The app role is UNIONED onto the legacy organization-role list."""
    from app.routers.v1 import oauth_provider as op
    from tests.unit.routers.test_oauth_provider_scope_enforcement import (
        MOD,
        REDIRECT,
        _client,
        _token_patches,
    )

    monkeypatch.setattr(op, "user_requires_mfa", AsyncMock(return_value=False))
    monkeypatch.setattr(op, "assurance_for_request", AsyncMock(return_value={}))

    ids = await _seed(schema)
    user = await _set_primary(schema, ids["user_id"], ids["b"])

    async with schema() as session:

        async def real_resolver(_user, _db):
            # The handler's own db is a double; the resolver gets the real one.
            return await get_user_org_claims(user, session)

        db, patches = _token_patches(user)
        replaced = {"_get_user_org_claims", "_get_user_entitlements"}
        patches = [p for p in patches if getattr(p, "attribute", None) not in replaced]
        assert len(patches) == len(_token_patches(user)[1]) - 2
        patches.append(patch(f"{MOD}._get_user_org_claims", AsyncMock(side_effect=real_resolver)))
        patches.append(
            patch(
                f"{MOD}._get_user_entitlements",
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
            patch(f"{MOD}._get_auth_code", AsyncMock(return_value=code_data)),
            patch(f"{MOD}._delete_auth_code", AsyncMock()),
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
                claims = op.jwt_manager.create_access_token.call_args.kwargs["additional_claims"]
            finally:
                for p in reversed(patches):
                    p.stop()

    assert claims["org_id"] == str(ids["b"])
    assert claims["roles"] == ["member", APP_ROLE_CLAIM]
    assert APP_ROLES_KEY not in claims
