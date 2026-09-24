"""Admin create-organization endpoint (POST /api/v1/admin/organizations).

The self-service `POST /organizations/` always sets owner = the caller, and janua
exposes no ownership-transfer endpoint (the members/roles sub-routers are not
mounted). So an operator could not stand up a CUSTOMER's canonical org owned by
the customer's master user — it would be owned by the operator. This admin
endpoint fills that gap. These tests pin the security-critical behaviours:

  * happy path            -> org created owned by the NAMED existing user (not
                             the calling admin), owner added as an `owner` member
  * owner addressed by id  -> resolves by UUID too
  * non-admin caller       -> 403 (gate runs before any write)
  * unknown owner          -> 404 (fail before any write)
  * owner XOR              -> exactly one of owner_email/owner_id required (422)
  * no privilege escalation-> naming an owner does not set platform is_admin

Style follows tests/unit/routers/test_admin_create_user.py: call the endpoint
coroutine directly with an AsyncMock session and intercept db.add().
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.v1.admin import (
    AdminOrganizationCreateRequest,
    create_organization_admin,
)
from app.models import Organization, OrganizationMember, User

pytestmark = pytest.mark.asyncio


def _admin_user() -> User:
    return User(id=uuid.uuid4(), email="admin@madfam.io", password_hash="hashed", is_admin=True)


def _non_admin_user() -> User:
    return User(id=uuid.uuid4(), email="mallory@example.com", password_hash="hashed", is_admin=False)


def _owner_user(email="creatumundoautismo@hotmail.com") -> User:
    return User(id=uuid.uuid4(), email=email, password_hash=None, is_admin=False)


def _db(owner=None, existing_org_for_slug=None):
    """AsyncMock session.

    db.execute is called for: owner lookup, then validate_unique_slug's lookup.
    scalar_one_or_none yields, in order: [owner, slug-collision-or-None].
    """
    results = [owner, existing_org_for_slug]
    call = {"i": 0}

    def _make_result():
        idx = call["i"]
        call["i"] += 1
        value = results[idx] if idx < len(results) else None
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=value)
        return r

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda *a, **k: _make_result())
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    async def refresh(obj, *args, **kwargs):
        for column, default in (
            ("id", uuid.uuid4()),
            ("created_at", datetime.utcnow()),
            ("updated_at", datetime.utcnow()),
        ):
            if getattr(obj, column, None) is None:
                setattr(obj, column, default)

    db.refresh = AsyncMock(side_effect=refresh)
    return db


def _added(db, cls):
    return [c.args[0] for c in db.add.call_args_list if c.args and isinstance(c.args[0], cls)]


async def _create(request, caller, db):
    return await create_organization_admin(request=request, current_user=caller, db=db)


class TestHappyPath:
    async def test_creates_org_owned_by_named_user_not_the_admin(self):
        owner = _owner_user()
        admin = _admin_user()
        db = _db(owner=owner)
        resp = await _create(
            AdminOrganizationCreateRequest(
                name="Crea Tu Mundo Autismo",
                slug="crea",
                owner_email=owner.email,
            ),
            admin,
            db,
        )

        orgs = _added(db, Organization)
        assert len(orgs) == 1
        created = orgs[0]
        # The OWNER is the named user, NOT the calling admin.
        assert created.owner_id == owner.id
        assert created.owner_id != admin.id
        assert created.slug == "crea"
        assert created.billing_email == owner.email  # defaults to owner's email

        # Owner is added as an owner-role member.
        members = _added(db, OrganizationMember)
        assert len(members) == 1
        assert members[0].user_id == owner.id
        assert members[0].role == "owner"

        assert resp.owner_email == owner.email
        assert resp.members_count == 1

    async def test_owner_addressed_by_id(self):
        owner = _owner_user()
        db = _db(owner=owner)
        resp = await _create(
            AdminOrganizationCreateRequest(
                name="Crea Tu Mundo Autismo", slug="crea", owner_id=str(owner.id)
            ),
            _admin_user(),
            db,
        )
        assert _added(db, Organization)[0].owner_id == owner.id
        assert resp.owner_id == str(owner.id)

    async def test_naming_owner_does_not_grant_platform_admin(self):
        owner = _owner_user()
        db = _db(owner=owner)
        await _create(
            AdminOrganizationCreateRequest(name="X", slug="crea", owner_email=owner.email),
            _admin_user(),
            db,
        )
        # The owner user object is untouched w.r.t. platform admin.
        assert owner.is_admin is False
        # Membership is org-scoped 'owner', never a platform flag.
        assert _added(db, OrganizationMember)[0].role == "owner"


class TestGuards:
    async def test_non_admin_caller_forbidden_before_any_write(self):
        db = _db(owner=_owner_user())
        with pytest.raises(HTTPException) as exc:
            await _create(
                AdminOrganizationCreateRequest(name="X", slug="crea", owner_email="o@x.com"),
                _non_admin_user(),
                db,
            )
        assert exc.value.status_code == 403
        assert db.add.call_args_list == []

    async def test_unknown_owner_404_before_any_write(self):
        db = _db(owner=None)  # owner lookup yields nothing
        with pytest.raises(HTTPException) as exc:
            await _create(
                AdminOrganizationCreateRequest(
                    name="X", slug="crea", owner_email="ghost@example.com"
                ),
                _admin_user(),
                db,
            )
        assert exc.value.status_code == 404
        assert _added(db, Organization) == []

    async def test_requires_exactly_one_owner_identifier(self):
        db = _db(owner=_owner_user())
        # Neither provided.
        with pytest.raises(HTTPException) as exc_none:
            await _create(
                AdminOrganizationCreateRequest(name="X", slug="crea"),
                _admin_user(),
                db,
            )
        assert exc_none.value.status_code == 422

        # Both provided.
        db2 = _db(owner=_owner_user())
        with pytest.raises(HTTPException) as exc_both:
            await _create(
                AdminOrganizationCreateRequest(
                    name="X", slug="crea", owner_email="o@x.com", owner_id=str(uuid.uuid4())
                ),
                _admin_user(),
                db2,
            )
        assert exc_both.value.status_code == 422

    async def test_duplicate_slug_rejected(self):
        owner = _owner_user()
        collision = Organization(id=uuid.uuid4(), slug="crea", name="Existing", owner_id=owner.id)
        db = _db(owner=owner, existing_org_for_slug=collision)
        with pytest.raises(HTTPException) as exc:
            await _create(
                AdminOrganizationCreateRequest(name="X", slug="crea", owner_email=owner.email),
                _admin_user(),
                db,
            )
        # validate_unique_slug raises 400 on a taken slug.
        assert exc.value.status_code == 400
        assert _added(db, Organization) == []
