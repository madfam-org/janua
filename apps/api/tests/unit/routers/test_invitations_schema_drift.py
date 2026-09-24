"""The invitations router read and wrote columns the `invitations` table lacks.

`app/routers/v1/invitations.py` scoped every read on `Invitation.tenant_id` and
built its responses from `role_name`, `invited_by`, `message` and `email_sent`.
The table has ten columns -- (id, organization_id, email, role, status, token,
expires_at, accepted_at, created_by, created_at) -- and the SQLAlchemy model
matched it exactly, so model and migration agreed and the *router* was the
drift. `role_name` and `invited_by` are `role` and `created_by` under different
names; `message` and `email_sent` were not columns at all.

Three more references had nothing behind them either: `generate_invite_url`,
`is_expired` (defined on no class), `current_user.get_organizations()` (defined
on no class) and `settings.APP_URL` (not a setting). Every handler therefore
raised before reaching the database, which is why the production table held 0
rows.

`PATCH /invitations/{id}` was the quiet one: `invitation.role_name = ...` and
`invitation.message = ...` land on plain Python attributes, so the endpoint
returned the caller's new values with a 200 and committed none of them.

These tests use real model instances and a real session because that is the
only way to tell a real column from a missing one -- a mocked manager answers
to any attribute name, which is exactly how this survived.

Style follows `test_policies_schema_drift.py` (janua#527).
"""

import ast
import inspect
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base, Invitation, Organization, OrganizationMember, User
from app.models.invitation import InvitationResponse, InvitationStatus, InvitationUpdate
from app.routers.v1 import invitations as invitations_router

pytestmark = pytest.mark.asyncio

# Tables this module touches. Creating only these keeps the fixture independent
# of unrelated models that fail to map under SQLite.
_TABLES = ["users", "organizations", "organization_members", "invitations"]


@pytest_asyncio.fixture
async def db():
    """An isolated in-memory database per test.

    These tests assert on row visibility, so they must not see another test's
    rows.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    tables = [Base.metadata.tables[name] for name in _TABLES]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _org_with_admin(db, name):
    """Create an organization plus an admin/owner member of it."""
    org = Organization(id=uuid.uuid4(), name=name, slug=name)
    user = User(id=uuid.uuid4(), email=f"admin@{name}.test")
    db.add_all([org, user])
    await db.flush()
    db.add(
        OrganizationMember(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role="admin")
    )
    await db.commit()
    # The routers receive the authenticated principal, not an ORM instance.
    return org, SimpleNamespace(id=user.id, tenant_id=None)


async def _invite(db, org, creator, **overrides):
    """Persist one invitation, exercising every column the router reports."""
    fields = {
        "id": uuid.uuid4(),
        "organization_id": org.id,
        "email": "invitee@example.test",
        "role": "member",
        "status": InvitationStatus.PENDING.value,
        "token": f"tok-{uuid.uuid4().hex}",
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "created_by": creator.id,
        "created_at": datetime.utcnow(),
        "message": "join us",
        "email_sent": True,
    }
    fields.update(overrides)
    invitation = Invitation(**fields)
    db.add(invitation)
    await db.commit()
    return invitation


def _executable_source(obj) -> str:
    """Source of `obj` with docstrings stripped, so prose can't satisfy a scan."""
    tree = ast.parse(inspect.getsource(obj))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if ast.get_docstring(node):
                node.body = node.body[1:]
    return ast.unparse(tree)


def _attributes_accessed_on(module, names) -> set:
    """Every `<name>.<attr>` referenced in `module`'s executable source."""
    tree = ast.parse(_executable_source(module))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in names
    }


# ---------------------------------------------------------------------------
# Structural guards: no caller may reference something that isn't there
# ---------------------------------------------------------------------------


def test_router_uses_one_model():
    """`app.models.invitation.Invitation` is a re-export, not a second model."""
    from app.models import Invitation as FromPackage
    from app.models.invitation import Invitation as FromModule

    assert FromModule is FromPackage
    assert invitations_router.Invitation is FromPackage
    assert FromPackage.__table__.name == "invitations"


def test_scoped_by_column_that_exists():
    """The `Invitation.tenant_id` half of the drift, mirroring #525/#527."""
    assert hasattr(Invitation, "organization_id")
    assert "tenant_id" not in Invitation.__table__.columns, (
        "invitations has no tenant_id column; organization_id is the tenancy "
        "key, consistent with Policy, Role and OrganizationMember."
    )
    assert "Invitation.tenant_id" not in _executable_source(invitations_router), (
        "the router filters on Invitation.tenant_id, which does not exist."
    )


def test_attrs_are_real_columns():
    """The structural guard a mock-driven suite cannot provide.

    Every attribute the router reads off an invitation must resolve on the
    mapped class -- as a column, a property or a method.
    """
    touched = _attributes_accessed_on(invitations_router, {"invitation", "inv"})
    missing = sorted(a for a in touched if not hasattr(Invitation, a))
    assert not missing, f"router touches non-existent Invitation attributes: {missing}"


def test_no_get_organizations_call():
    """`User.get_organizations()` is defined on no class; scoping must not call it."""
    assert not hasattr(User, "get_organizations")
    assert "get_organizations" not in _executable_source(invitations_router)


def test_invite_base_url_resolves():
    """`settings.APP_URL` does not exist; the link root must come from one that does."""
    assert "APP_URL" not in _executable_source(invitations_router)
    assert invitations_router._invite_base_url().startswith("http")


def test_response_fields_have_columns():
    """Every persisted field `InvitationResponse` declares can be stored.

    `message` and `email_sent` are the two that had nowhere to land, which is
    what made `InvitationCreate.message` a field the API accepted and dropped.
    """
    for field in ("message", "email_sent", "role", "created_by", "expires_at", "status"):
        assert field in Invitation.__table__.columns, f"invitations lacks {field}"
    assert {"message", "email_sent"} <= set(InvitationResponse.model_fields)


# ---------------------------------------------------------------------------
# Behavioural round-trips against a real session
# ---------------------------------------------------------------------------


async def test_get_returns_all_fields(db):
    """Every field the response claims to support survives a database round-trip."""
    org, admin = await _org_with_admin(db, "acme")
    invitation = await _invite(db, org, admin)

    response = await invitations_router.get_invitation(
        invitation_id=str(invitation.id), current_user=admin, db=db
    )

    assert response.id == str(invitation.id)
    assert response.organization_id == str(org.id)
    assert response.email == "invitee@example.test"
    assert response.role == "member"
    assert response.status == InvitationStatus.PENDING.value
    assert response.invited_by == str(admin.id)
    assert response.message == "join us"
    assert response.email_sent is True
    assert response.expires_at == invitation.expires_at
    assert invitation.token in response.invite_url


async def test_patch_persists_fields(db):
    """PATCH must commit, not just echo.

    `role` was written as `role_name` and `message` was not a column, so both
    assignments used to land on plain Python attributes and vanish on commit.
    """
    org, admin = await _org_with_admin(db, "acme")
    invitation = await _invite(db, org, admin, role="member", message="before")
    invitation_id = invitation.id
    new_expiry = datetime.utcnow() + timedelta(days=21)

    response = await invitations_router.update_invitation(
        invitation_id=str(invitation.id),
        update_data=InvitationUpdate(role="admin", message="after", expires_at=new_expiry),
        current_user=admin,
        db=db,
    )

    assert response.role == "admin"
    assert response.message == "after"

    # Re-read from the database: the echo above must be backed by stored rows.
    db.expire_all()
    stored = (
        await db.execute(select(Invitation).where(Invitation.id == invitation_id))
    ).scalar_one()
    assert stored.role == "admin"
    assert stored.message == "after"
    assert stored.expires_at == new_expiry


async def test_list_scoped_to_member_orgs(db):
    """Listing is scoped by organization membership."""
    org, admin = await _org_with_admin(db, "acme")
    await _invite(db, org, admin, email="a@example.test")
    await _invite(db, org, admin, email="b@example.test")

    result = await invitations_router.list_invitations(current_user=admin, db=db, skip=0, limit=100)

    assert result.total == 2
    assert {i.email for i in result.invitations} == {"a@example.test", "b@example.test"}
    assert result.pending_count == 2


async def test_list_excludes_other_org(db):
    """An admin of org A never sees org B's invitations."""
    org_a, admin_a = await _org_with_admin(db, "acme")
    org_b, admin_b = await _org_with_admin(db, "globex")
    await _invite(db, org_b, admin_b, email="secret@globex.test")

    result = await invitations_router.list_invitations(current_user=admin_a, db=db, skip=0, limit=100)
    assert result.total == 0
    assert result.invitations == []

    # Naming org B explicitly must not widen the scope either.
    targeted = await invitations_router.list_invitations(
        organization_id=str(org_b.id), current_user=admin_a, db=db, skip=0, limit=100
    )
    assert targeted.total == 0


async def test_get_other_org_404(db):
    """Reading another organization's invitation by id is a 404, not a leak."""
    org_a, admin_a = await _org_with_admin(db, "acme")
    org_b, admin_b = await _org_with_admin(db, "globex")
    invitation = await _invite(db, org_b, admin_b)

    with pytest.raises(Exception) as exc:
        await invitations_router.get_invitation(
            invitation_id=str(invitation.id), current_user=admin_a, db=db
        )
    assert getattr(exc.value, "status_code", None) == 404


async def test_patch_other_org_404(db):
    """An admin of org A cannot mutate org B's invitation.

    `require_org_admin` only proves the caller administers *some*
    organization, so the handler must check the invitation's own organization.
    """
    org_a, admin_a = await _org_with_admin(db, "acme")
    org_b, admin_b = await _org_with_admin(db, "globex")
    invitation = await _invite(db, org_b, admin_b, role="member")
    invitation_id = invitation.id

    with pytest.raises(Exception) as exc:
        await invitations_router.update_invitation(
            invitation_id=str(invitation.id),
            update_data=InvitationUpdate(role="owner"),
            current_user=admin_a,
            db=db,
        )
    assert getattr(exc.value, "status_code", None) == 404

    db.expire_all()
    stored = (
        await db.execute(select(Invitation).where(Invitation.id == invitation_id))
    ).scalar_one()
    assert stored.role == "member"


async def test_expire_marks_pending(db):
    """The expire sweep marks lapsed pending invitations and leaves the rest."""
    org, admin = await _org_with_admin(db, "acme")
    lapsed = await _invite(
        db, org, admin, email="old@example.test", expires_at=datetime.utcnow() - timedelta(days=1)
    )
    live = await _invite(db, org, admin, email="new@example.test")

    result = await invitations_router.cleanup_expired_invitations(current_user=admin, db=db)
    assert result["count"] == 1

    db.expire_all()
    rows = {r.email: r.status for r in (await db.execute(select(Invitation))).scalars().all()}
    assert rows["old@example.test"] == InvitationStatus.EXPIRED.value
    assert rows["new@example.test"] == InvitationStatus.PENDING.value
    assert lapsed.organization_id == live.organization_id


async def test_expire_scoped_to_org(db):
    """The sweep only touches the caller's own organizations."""
    org_a, admin_a = await _org_with_admin(db, "acme")
    org_b, admin_b = await _org_with_admin(db, "globex")
    stale = datetime.utcnow() - timedelta(days=1)
    await _invite(db, org_a, admin_a, email="a@example.test", expires_at=stale)
    await _invite(db, org_b, admin_b, email="b@example.test", expires_at=stale)

    result = await invitations_router.cleanup_expired_invitations(current_user=admin_a, db=db)
    assert result["count"] == 1

    db.expire_all()
    rows = {r.email: r.status for r in (await db.execute(select(Invitation))).scalars().all()}
    assert rows["a@example.test"] == InvitationStatus.EXPIRED.value
    assert rows["b@example.test"] == InvitationStatus.PENDING.value


async def test_validate_ok(db):
    """A live token validates and reports the fields the accept page needs."""
    org, admin = await _org_with_admin(db, "acme")
    invitation = await _invite(db, org, admin)

    result = await invitations_router.validate_invitation_token(token=invitation.token, db=db)

    assert result["valid"] is True
    assert result["email"] == "invitee@example.test"
    assert result["organization_name"] == "acme"
    assert result["role"] == "member"
    assert result["message"] == "join us"


async def test_validate_expired(db):
    """A lapsed token reports itself invalid rather than raising."""
    org, admin = await _org_with_admin(db, "acme")
    invitation = await _invite(db, org, admin, expires_at=datetime.utcnow() - timedelta(days=1))

    result = await invitations_router.validate_invitation_token(token=invitation.token, db=db)

    assert result["valid"] is False
    assert result["reason"] == "Invitation has expired"


async def test_list_status_counts(db):
    """The status breakdown describes the whole scoped set."""
    org, admin = await _org_with_admin(db, "acme")
    await _invite(db, org, admin, email="p@example.test")
    await _invite(db, org, admin, email="a@example.test", status=InvitationStatus.ACCEPTED.value)
    await _invite(db, org, admin, email="e@example.test", status=InvitationStatus.EXPIRED.value)

    result = await invitations_router.list_invitations(current_user=admin, db=db, skip=0, limit=100)
    assert (result.pending_count, result.accepted_count, result.expired_count) == (1, 1, 1)
    assert result.total == 3

    filtered = await invitations_router.list_invitations(
        status=InvitationStatus.ACCEPTED, current_user=admin, db=db, skip=0, limit=100
    )
    assert filtered.total == 1
    assert filtered.invitations[0].email == "a@example.test"
    # The breakdown still describes the whole set, not just the filtered page.
    assert filtered.pending_count == 1


async def test_bad_uuid_is_404(db):
    """A non-UUID path id is a 404, not a database error."""
    org, admin = await _org_with_admin(db, "acme")

    with pytest.raises(Exception) as exc:
        await invitations_router.get_invitation(
            invitation_id="not-a-uuid", current_user=admin, db=db
        )
    assert getattr(exc.value, "status_code", None) == 404
