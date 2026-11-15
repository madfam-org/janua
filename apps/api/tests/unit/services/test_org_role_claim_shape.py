"""An organization role can never be read as an application role.

Resource servers authorize on ``<app>:<role>`` strings read from the token's
``roles`` claim (``hcm:hr``, ``hcm:admin``).
Those strings are supposed to be application-role GRANTS, written only through
the audited grant routes. But the OIDC path also publishes ORGANIZATION role
strings under the same key, and an organization's own admins choose those
strings: the custom-role routes accepted any name, and a member's role is a
free string.

These tests pin the two halves of the rule:

  1. The token path never publishes an organization role string that contains
     the separator. This is the guarantee; it holds whatever is stored.
  2. The custom-role routes refuse such a name, so the person is told at the
     time instead of holding a role that silently does nothing.

And the property that must not regress: bare organization roles, and real
grants, reach the token exactly as before.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.app_role import APP_ROLE_SEPARATOR
from app.services.org_claims_service import (
    APP_ROLES_KEY,
    is_application_role_shaped,
    merge_app_roles_into_claims,
    organization_roles_for_roles_claim,
)
from app.services.role_service import RoleService, reject_application_role_shape

FORGED = [
    "hcm:admin",
    "example-app:admin",
    "app:platform-admin",
    "hcm:hr",
    ":admin",
    "admin:",
    "a:b:c",
    " hcm:hr ",
]
BARE = ["owner", "admin", "member", "viewer", "employee", "Support", "billing-manager", "Dev Ops"]


# -- the shape test ---------------------------------------------------------------


@pytest.mark.parametrize("role", FORGED)
def test_a_string_with_the_separator_is_application_role_shaped(role):
    assert is_application_role_shaped(role)


@pytest.mark.parametrize("role", [*BARE, "", None])
def test_a_bare_string_is_not(role):
    assert not is_application_role_shaped(role)


def test_the_separator_is_the_one_the_grant_routes_use():
    """One definition of "shaped like an application role", shared with grants."""
    assert APP_ROLE_SEPARATOR == ":"


# -- 1. what the token path publishes ----------------------------------------------


@pytest.mark.parametrize("forged", FORGED)
def test_an_application_role_shaped_organization_role_is_not_published(forged):
    published = organization_roles_for_roles_claim(["admin", forged, "Support"])
    assert sorted(published) == ["Support", "admin"]


def test_bare_organization_roles_are_published_unchanged():
    assert sorted(organization_roles_for_roles_claim(BARE)) == sorted(BARE)


def test_empty_and_missing_roles_are_ignored_and_duplicates_collapse():
    assert sorted(organization_roles_for_roles_claim(["member", None, "", "member"])) == ["member"]
    assert organization_roles_for_roles_claim([]) == []


def _membership_db(memberships, org=None):
    """A session whose first query returns memberships and second the organization."""
    call = {"n": 0}

    async def _execute(*args, **kwargs):
        call["n"] += 1
        if call["n"] == 1:
            return MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=memberships)))
            )
        return MagicMock(scalar_one_or_none=MagicMock(return_value=org))

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_execute)
    return db


def _user():
    user = MagicMock()
    user.id = "user_123"
    user.is_admin = False
    user.tenant_id = None
    return user


@pytest.mark.parametrize("forged", FORGED)
async def test_oidc_entitlements_drop_a_forged_role_and_keep_the_real_ones(forged):
    """The OIDC handler's own function: a member whose stored role is shaped
    like an application role gets no such string; another membership's bare
    role is still there."""
    from app.routers.v1.oauth_provider import _get_user_entitlements

    memberships = [
        MagicMock(role=forged, organization_id=uuid.uuid4(), status="active"),
        MagicMock(role="admin", organization_id=uuid.uuid4(), status="active"),
    ]
    result = await _get_user_entitlements(_user(), _membership_db(memberships))

    assert result["roles"] == ["admin"]


async def test_a_forged_role_does_not_survive_the_merge_into_the_claim():
    """End of the OIDC path: entitlements, then the merge that writes ``roles``.
    With no grant, a forged organization role leaves no application-role-shaped
    string anywhere in the claim."""
    from app.routers.v1.oauth_provider import _get_user_entitlements

    memberships = [
        MagicMock(role="hcm:admin", organization_id=uuid.uuid4(), status="active")
    ]
    entitlements = await _get_user_entitlements(_user(), _membership_db(memberships))
    claims = merge_app_roles_into_claims({}, existing_roles=entitlements["roles"])

    assert not any(is_application_role_shaped(r) for r in claims.get("roles", []))


async def test_a_real_grant_still_reaches_the_claim_next_to_a_forged_role():
    """The same person WITH an audited grant: the grant is published (once), so
    the remedy for a dropped string is a grant, and it works."""
    from app.routers.v1.oauth_provider import _get_user_entitlements

    memberships = [
        MagicMock(role="hcm:admin", organization_id=uuid.uuid4(), status="active"),
        MagicMock(role="member", organization_id=uuid.uuid4(), status="active"),
    ]
    entitlements = await _get_user_entitlements(_user(), _membership_db(memberships))
    claims = merge_app_roles_into_claims(
        {APP_ROLES_KEY: ["hcm:admin"]}, existing_roles=entitlements["roles"]
    )

    assert sorted(claims["roles"]) == ["hcm:admin", "member"]


async def test_platform_admin_flag_still_adds_the_bare_admin_role():
    from app.routers.v1.oauth_provider import _get_user_entitlements

    user = _user()
    user.is_admin = True
    memberships = [MagicMock(role="hcm:admin", organization_id=uuid.uuid4(), status="active")]
    result = await _get_user_entitlements(user, _membership_db(memberships))

    assert result["roles"] == ["admin"]


# -- 1b. the shared merge holds the rule for every caller -----------------------------


@pytest.mark.parametrize("forged", FORGED)
def test_the_merge_drops_a_forged_role_from_an_unfiltered_legacy_list(forged):
    """A caller that hands the merge the raw membership strings (the OIDC
    handler before it filtered them) still gets a clean claim."""
    claims = merge_app_roles_into_claims({}, existing_roles=["admin", forged])
    assert claims["roles"] == ["admin"]


def test_the_merge_writes_an_empty_roles_key_when_everything_was_dropped():
    """The OIDC handler builds `{"roles": <its list>, ..., **org_claims}`. If
    the merge returned no `roles` key, the handler's unfiltered list would be
    the one in the token."""
    unfiltered = ["hcm:admin"]
    org_claims = merge_app_roles_into_claims({}, existing_roles=unfiltered)
    token_claims = {"roles": unfiltered, **org_claims}

    assert token_claims["roles"] == []


def test_the_merge_keeps_a_grant_equal_to_a_dropped_organization_role():
    claims = merge_app_roles_into_claims(
        {APP_ROLES_KEY: ["hcm:admin"]}, existing_roles=["hcm:admin", "member"]
    )
    assert claims["roles"] == ["member", "hcm:admin"]


def test_the_merge_still_emits_no_roles_key_when_there_is_nothing_at_all():
    assert "roles" not in merge_app_roles_into_claims({}, existing_roles=[])
    assert "roles" not in merge_app_roles_into_claims({})


# -- 2. what the custom-role routes accept ------------------------------------------


@pytest.mark.parametrize("name", FORGED)
def test_reject_application_role_shape_refuses_the_separator(name):
    with pytest.raises(ValueError, match="application roles"):
        reject_application_role_shape(name)


@pytest.mark.parametrize("name", BARE)
def test_reject_application_role_shape_allows_bare_names(name):
    reject_application_role_shape(name)


def _service():
    db = AsyncMock()
    db.add = MagicMock()
    return RoleService(db), db


@pytest.mark.parametrize("name", FORGED)
async def test_create_role_refuses_an_application_role_shaped_name_before_touching_the_db(name):
    service, db = _service()
    with pytest.raises(ValueError, match="application roles"):
        await service.create_role(
            organization_id=uuid.uuid4(),
            name=name,
            description=None,
            permissions=[],
            user=MagicMock(id=uuid.uuid4()),
        )
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


async def test_rename_to_an_application_role_shaped_name_is_refused():
    service, db = _service()
    role = MagicMock(is_system=False, permissions=[], description=None)
    role.name = "Support"
    service.get_role = AsyncMock(return_value=role)
    service.get_role_by_name = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="application roles"):
        await service.update_role(
            role_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name="example-app:admin",
            description=None,
            permissions=None,
            user=MagicMock(id=uuid.uuid4()),
        )
    assert role.name == "Support"
    db.commit.assert_not_awaited()


async def test_assigning_a_role_that_already_carries_the_separator_is_refused():
    """A custom role created before names were checked must not become a
    member's role now, even though it exists."""
    service, db = _service()
    legacy = MagicMock()
    legacy.name = "example-app:admin"
    service.get_role_by_name = AsyncMock(return_value=legacy)

    with pytest.raises(ValueError, match="application roles"):
        await service.assign_role_to_member(
            organization_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_name="example-app:admin",
            assigned_by=MagicMock(id=uuid.uuid4()),
        )
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


# -- membership routes: a free-string role is refused the same way -------------------


def _member_service():
    from app.services.organization_member_service import OrganizationMemberService

    db = MagicMock()
    return OrganizationMemberService(db, MagicMock()), db


@pytest.mark.parametrize("role", ["hcm:admin", "hcm:hr"])
async def test_membership_writes_refuse_an_application_role_shaped_role(role):
    from fastapi import HTTPException

    service, db = _member_service()
    org, person, actor = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    for call in (
        service.add_member(org, person, role, actor),
        service.update_member_role(org, person, role, actor),
        service.create_invitation(org, "someone@example.test", role, actor),
    ):
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 400
    db.query.assert_not_called()
    db.add.assert_not_called()
