"""Admin update-organization endpoint (PATCH /api/v1/admin/organizations/{id}).

Companion to POST /api/v1/admin/organizations (test_admin_create_organization.py).
The self-service `PATCH /organizations/{id}` requires the caller to be an org
admin, and ownership transfer requires the new owner to already be a member plus
a confirmation password. Neither lets an operator adopt an ownerless org they are
not a member of — set its owner to the customer's master user, or align its name.
This admin endpoint does. These tests pin the security-critical behaviours:

  * rename only            -> name changes, no owner/member writes
  * set owner (by email)   -> org.owner_id = named user, owner (re)asserted as an
                              `owner`-role member (insert when absent)
  * set owner (by id)      -> resolves by UUID too
  * owner already a member -> membership updated in place, not duplicated
  * non-admin caller       -> 403 (gate runs before any write)
  * unknown org            -> 404 (fail before any write)
  * unknown owner          -> 404 (fail before any write)
  * owner XOR              -> at most one of owner_email/owner_id (422)
  * no privilege escalation-> naming an owner does not set platform is_admin

Style follows test_admin_create_organization.py: call the endpoint coroutine
directly with an AsyncMock session and intercept db.add().
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.v1.admin import (
    AdminOrganizationUpdateRequest,
    update_organization_admin,
)
from app.models import Organization, OrganizationMember, User

pytestmark = pytest.mark.asyncio


def _admin_user() -> User:
    return User(id=uuid.uuid4(), email="admin@madfam.io", password_hash="hashed", is_admin=True)


def _non_admin_user() -> User:
    return User(id=uuid.uuid4(), email="mallory@example.com", password_hash="hashed", is_admin=False)


def _owner_user(email="creatumundoautismo@hotmail.com") -> User:
    return User(id=uuid.uuid4(), email=email, password_hash=None, is_admin=False)


def _org(owner_id=None, name="Crea", slug="crea") -> Organization:
    return Organization(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        owner_id=owner_id,
        billing_plan="free",
        billing_email=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _db(results):
    """AsyncMock session whose db.execute yields the given results in order.

    Each entry is what `.scalar_one_or_none()` returns for the next db.execute
    call; a member-count query reads `.scalar()`. Passing a plain value uses it
    for both accessors, so an int entry doubles as the count result.
    """
    call = {"i": 0}

    def _make_result():
        idx = call["i"]
        call["i"] += 1
        value = results[idx] if idx < len(results) else None
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=value)
        r.scalar = MagicMock(return_value=value if isinstance(value, int) else 1)
        return r

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda *a, **k: _make_result())
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _added(db, cls):
    return [c.args[0] for c in db.add.call_args_list if c.args and isinstance(c.args[0], cls)]


async def _update(org_id, request, caller, db):
    return await update_organization_admin(
        org_id=org_id, request=request, current_user=caller, db=db
    )


class TestRenameOnly:
    async def test_rename_changes_name_and_writes_no_members(self):
        org = _org(owner_id=uuid.uuid4(), name="Old Name")
        owner_for_response = _owner_user()
        # execute order: org lookup, (no owner block), owner-email-for-response, count.
        db = _db([org, owner_for_response, 3])
        resp = await _update(
            str(org.id),
            AdminOrganizationUpdateRequest(name="Crea Tu Mundo Autismo"),
            _admin_user(),
            db,
        )
        assert org.name == "Crea Tu Mundo Autismo"
        # No owner requested -> owner_id untouched, no member rows added.
        assert _added(db, OrganizationMember) == []
        assert resp.name == "Crea Tu Mundo Autismo"


class TestSetOwner:
    async def test_set_owner_by_email_inserts_owner_member(self):
        owner = _owner_user()
        org = _org(owner_id=None)  # ownerless
        # execute order: org, owner, existing-member(None), owner-email-for-response, count.
        db = _db([org, owner, None, owner, 1])
        resp = await _update(
            str(org.id),
            AdminOrganizationUpdateRequest(owner_email=owner.email),
            _admin_user(),
            db,
        )
        assert org.owner_id == owner.id
        members = _added(db, OrganizationMember)
        assert len(members) == 1
        assert members[0].user_id == owner.id
        assert members[0].role == "owner"
        assert members[0].status == "active"
        assert resp.owner_id == str(owner.id)

    async def test_set_owner_by_id(self):
        owner = _owner_user()
        org = _org(owner_id=None)
        db = _db([org, owner, None, owner, 1])
        resp = await _update(
            str(org.id),
            AdminOrganizationUpdateRequest(owner_id=str(owner.id)),
            _admin_user(),
            db,
        )
        assert org.owner_id == owner.id
        assert resp.owner_id == str(owner.id)

    async def test_existing_member_is_updated_in_place_not_duplicated(self):
        owner = _owner_user()
        org = _org(owner_id=None)
        existing = OrganizationMember(
            organization_id=org.id, user_id=owner.id, role="member", status="invited"
        )
        # existing-member lookup returns the row -> update, no insert.
        db = _db([org, owner, existing, owner, 1])
        await _update(
            str(org.id),
            AdminOrganizationUpdateRequest(owner_email=owner.email),
            _admin_user(),
            db,
        )
        assert _added(db, OrganizationMember) == []  # no new row
        assert existing.role == "owner"
        assert existing.status == "active"

    async def test_naming_owner_does_not_grant_platform_admin(self):
        owner = _owner_user()
        org = _org(owner_id=None)
        db = _db([org, owner, None, owner, 1])
        await _update(
            str(org.id),
            AdminOrganizationUpdateRequest(owner_email=owner.email),
            _admin_user(),
            db,
        )
        assert owner.is_admin is False
        assert _added(db, OrganizationMember)[0].role == "owner"


class TestGuards:
    async def test_non_admin_forbidden_before_any_write(self):
        org = _org(owner_id=uuid.uuid4())
        db = _db([org])
        with pytest.raises(HTTPException) as exc:
            await _update(
                str(org.id),
                AdminOrganizationUpdateRequest(name="X"),
                _non_admin_user(),
                db,
            )
        assert exc.value.status_code == 403
        assert db.add.call_args_list == []
        assert db.commit.call_args_list == []

    async def test_unknown_org_404_before_any_write(self):
        db = _db([None])  # org lookup yields nothing
        with pytest.raises(HTTPException) as exc:
            await _update(
                str(uuid.uuid4()),
                AdminOrganizationUpdateRequest(name="X"),
                _admin_user(),
                db,
            )
        assert exc.value.status_code == 404
        assert db.commit.call_args_list == []

    async def test_invalid_org_id_400(self):
        db = _db([])
        with pytest.raises(HTTPException) as exc:
            await _update(
                "not-a-uuid",
                AdminOrganizationUpdateRequest(name="X"),
                _admin_user(),
                db,
            )
        assert exc.value.status_code == 400

    async def test_unknown_owner_404_before_commit(self):
        org = _org(owner_id=None)
        db = _db([org, None])  # org found, owner lookup yields nothing
        with pytest.raises(HTTPException) as exc:
            await _update(
                str(org.id),
                AdminOrganizationUpdateRequest(owner_email="ghost@example.com"),
                _admin_user(),
                db,
            )
        assert exc.value.status_code == 404
        assert db.commit.call_args_list == []

    async def test_at_most_one_owner_identifier(self):
        org = _org(owner_id=None)
        db = _db([org])
        with pytest.raises(HTTPException) as exc:
            await _update(
                str(org.id),
                AdminOrganizationUpdateRequest(
                    owner_email="o@x.com", owner_id=str(uuid.uuid4())
                ),
                _admin_user(),
                db,
            )
        assert exc.value.status_code == 422
        assert db.commit.call_args_list == []
