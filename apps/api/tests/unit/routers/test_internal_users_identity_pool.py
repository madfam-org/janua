"""Org STAFF are provisioned into the PLATFORM pool, not a tenant pool.

Owner decision 2026-09-03: `users.tenant_id` selects the identity's
email-uniqueness pool and must NOT be used to express organization membership.
Staff belong to an org through `organization_members`; only real BaaS end users
(`identity_pool="tenant"`) get a tenant-pooled identity.

This is the upstream half of this PR's outage. `provision_user` used one field —
`tenant_id` — for BOTH jobs, so every CTM staff member crea-map provisioned
landed in a tenant pool where the bare-email magic-link lookup could not see
them; the handler then took its create branch and collided with the still-global
`ix_users_email` (prod alembic_version was 011, migration 013 not yet
applied; it landed 2026-09-06) → 503.

The request now separates the two concerns:
  * `organization_id` (preferred) / `tenant_id` (deprecated alias) — the org;
  * `identity_pool` ("platform" default | "tenant") — the identity's pool.

COMPATIBILITY CONTRACT: crea-map's `src/server/janua-provision.ts` sends
`tenant_id` only and never sends `identity_pool`, on all three endpoints. It
must keep working unchanged across this deploy — it moves to `organization_id`
in a follow-up. `TestCreaMapCallerUnchanged` pins exactly that payload shape.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from test_internal_users import (
    AUTH,
    PROVISION_URL,
    REACTIVATE_URL,
    SUSPEND_URL,
    TENANT_A,
    TENANT_B,
    _get_user,
)

from app.models import OrganizationMember, User, UserStatus

# `provisioning_env` / `provisioning_client` come from the sibling module's
# fixtures via conftest.py rather than being imported here: importing a fixture
# by name and then shadowing it with a test parameter is what F811 flags.

pytestmark = pytest.mark.asyncio


def _payload(email="staff@crea.example.com", **overrides) -> dict:
    body = {"email": email, "first_name": "Ana", "last_name": "Ruiz"}
    body.update(overrides)
    return body


async def _membership(session_factory, user_id, organization_id) -> OrganizationMember | None:
    async with session_factory() as session:
        result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == uuid.UUID(str(user_id)),
                OrganizationMember.organization_id == uuid.UUID(str(organization_id)),
            )
        )
        return result.scalars().first()


class TestPlatformPoolIsTheDefault:
    async def test_staff_get_a_null_tenant_id_and_a_membership(self, provisioning_env):
        """THE FIX. Identity in the platform pool, org binding in the membership."""
        client, session_factory = provisioning_env

        response = await client.post(
            PROVISION_URL, json=_payload(organization_id=TENANT_A), headers=AUTH
        )

        assert response.status_code == 201
        user_id = response.json()["id"]

        user = await _get_user(session_factory, user_id)
        assert user.tenant_id is None, "staff must not be tenant-pooled"

        membership = await _membership(session_factory, user_id, TENANT_A)
        assert membership is not None, "the org binding must still be recorded"
        assert membership.status == "active"
        assert response.json()["org_role"] == "member"

    async def test_the_provisioned_staff_user_is_visible_to_the_untenanted_lookup(
        self, provisioning_env
    ):
        """The end-to-end point: magic link must be able to find this person.

        `get_user_by_email(..., tenant_id=None)` is exactly what
        `send_magic_link` calls. Before this change it returned None for a
        provisioned staff member, which is how the outage happened.
        """
        client, session_factory = provisioning_env
        email = "buscable@crea.example.com"

        await client.post(PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH)

        from app.services.user_lookup import get_user_by_email

        async with session_factory() as session:
            found = await get_user_by_email(session, email, tenant_id=None, active_only=True)

        assert found is not None, "magic link could not see this user — the outage"
        assert found.email == email

    async def test_re_provisioning_converges_on_one_row(self, provisioning_env):
        client, session_factory = provisioning_env
        email = "repetido@crea.example.com"

        first = await client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )
        second = await client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )

        assert first.status_code == 201 and first.json()["created"] is True
        assert second.status_code == 200 and second.json()["created"] is False
        assert first.json()["id"] == second.json()["id"]

        async with session_factory() as session:
            rows = (await session.execute(select(User).where(User.email == email))).scalars().all()
        assert len(rows) == 1

    async def test_idempotency_is_by_lowercased_email(self, provisioning_env):
        client, session_factory = provisioning_env

        first = await client.post(
            PROVISION_URL, json=_payload("Mixta@Crea.Example.Com", organization_id=TENANT_A),
            headers=AUTH,
        )
        second = await client.post(
            PROVISION_URL, json=_payload("mixta@crea.example.com", organization_id=TENANT_A),
            headers=AUTH,
        )

        assert first.json()["id"] == second.json()["id"]
        assert second.json()["created"] is False

    async def test_two_orgs_share_one_platform_identity(self, provisioning_env):
        """A colleague who works with two orgs is ONE person in the platform pool.

        Under the old model this produced two user rows — and, on the
        then-global ix_users_email, the second INSERT would have 503'd.
        """
        client, session_factory = provisioning_env
        email = "compartida@crea.example.com"

        in_a = await client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )
        in_b = await client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_B), headers=AUTH
        )

        assert in_a.status_code == 201
        assert in_b.status_code == 200, "same platform identity, second organization"
        assert in_a.json()["id"] == in_b.json()["id"]

        assert await _membership(session_factory, in_a.json()["id"], TENANT_A) is not None
        assert await _membership(session_factory, in_a.json()["id"], TENANT_B) is not None


class TestTenantPoolStillAvailable:
    async def test_explicit_tenant_pool_sets_users_tenant_id(self, provisioning_env):
        """Real BaaS end-user provisioning keeps the old shape, opted into."""
        client, session_factory = provisioning_env

        response = await client.post(
            PROVISION_URL,
            json=_payload("enduser@cliente.example.com", organization_id=TENANT_A,
                          identity_pool="tenant"),
            headers=AUTH,
        )

        assert response.status_code == 201
        user = await _get_user(session_factory, response.json()["id"])
        assert str(user.tenant_id) == TENANT_A

    async def test_tenant_pooled_end_user_still_gets_its_membership(self, provisioning_env):
        client, session_factory = provisioning_env
        response = await client.post(
            PROVISION_URL,
            json=_payload("enduser2@cliente.example.com", organization_id=TENANT_A,
                          identity_pool="tenant"),
            headers=AUTH,
        )
        assert await _membership(session_factory, response.json()["id"], TENANT_A) is not None

    async def test_an_invalid_pool_is_rejected(self, provisioning_client):
        response = await provisioning_client.post(
            PROVISION_URL,
            json=_payload(organization_id=TENANT_A, identity_pool="whatever"),
            headers=AUTH,
        )
        assert response.status_code == 422


class TestOrganizationIdAlias:
    async def test_tenant_id_alias_is_accepted(self, provisioning_env):
        client, session_factory = provisioning_env
        response = await client.post(
            PROVISION_URL, json=_payload("alias@crea.example.com", tenant_id=TENANT_A), headers=AUTH
        )
        assert response.status_code == 201
        assert await _membership(session_factory, response.json()["id"], TENANT_A) is not None

    async def test_both_spellings_agree(self, provisioning_client):
        response = await provisioning_client.post(
            PROVISION_URL,
            json=_payload("ambas@crea.example.com", organization_id=TENANT_A, tenant_id=TENANT_A),
            headers=AUTH,
        )
        assert response.status_code == 201

    async def test_conflicting_spellings_are_rejected(self, provisioning_client):
        """No defensible way to pick one — provisioning into the wrong org."""
        response = await provisioning_client.post(
            PROVISION_URL,
            json=_payload("conflicto@crea.example.com", organization_id=TENANT_A,
                          tenant_id=TENANT_B),
            headers=AUTH,
        )
        assert response.status_code == 422

    async def test_neither_spelling_is_rejected(self, provisioning_client):
        response = await provisioning_client.post(
            PROVISION_URL, json=_payload("ninguno@crea.example.com"), headers=AUTH
        )
        assert response.status_code == 422


class TestLifecycleResolvesEitherPool:
    async def test_suspend_finds_a_platform_pooled_staff_member(self, provisioning_client):
        email = "suspender@crea.example.com"
        await provisioning_client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )

        response = await provisioning_client.post(
            SUSPEND_URL, json={"email": email, "organization_id": TENANT_A}, headers=AUTH
        )

        assert response.status_code == 200
        assert response.json()["changed"] is True
        assert response.json()["status"] == UserStatus.SUSPENDED.value

    async def test_suspend_still_finds_a_legacy_tenant_pooled_user(self, provisioning_client):
        """The 21 CTM accounts' shape. Provisioned tenant-pooled, must stay
        manageable after the default flips — otherwise «baja» silently 404s."""
        email = "heredado@crea.example.com"
        await provisioning_client.post(
            PROVISION_URL,
            json=_payload(email, organization_id=TENANT_A, identity_pool="tenant"),
            headers=AUTH,
        )

        response = await provisioning_client.post(
            SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
        )

        assert response.status_code == 200
        assert response.json()["changed"] is True

    async def test_reactivate_finds_a_platform_pooled_staff_member(self, provisioning_client):
        email = "realta@crea.example.com"
        await provisioning_client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )
        await provisioning_client.post(
            SUSPEND_URL, json={"email": email, "organization_id": TENANT_A}, headers=AUTH
        )

        response = await provisioning_client.post(
            REACTIVATE_URL, json={"email": email, "organization_id": TENANT_A}, headers=AUTH
        )

        assert response.status_code == 200
        assert response.json()["changed"] is True
        assert response.json()["status"] == UserStatus.ACTIVE.value

    async def test_another_org_cannot_suspend_a_platform_pooled_staff_member(
        self, provisioning_client
    ):
        """The scope check moved from users.tenant_id to the membership row;
        the guarantee it provided must not have moved with it."""
        email = "ajeno@crea.example.com"
        await provisioning_client.post(
            PROVISION_URL, json=_payload(email, organization_id=TENANT_A), headers=AUTH
        )

        response = await provisioning_client.post(
            SUSPEND_URL, json={"email": email, "organization_id": TENANT_B}, headers=AUTH
        )

        assert response.status_code == 404

    async def test_lifecycle_for_an_unknown_email_is_404(self, provisioning_client):
        response = await provisioning_client.post(
            SUSPEND_URL, json={"email": "nadie@crea.example.com", "organization_id": TENANT_A},
            headers=AUTH,
        )
        assert response.status_code == 404


class TestCreaMapCallerUnchanged:
    """crea-map's exact payloads (`src/server/janua-provision.ts`), which send
    `tenant_id` only and no `identity_pool`. These must not break on deploy."""

    async def test_the_full_alta_baja_realta_cycle(self, provisioning_env):
        client, session_factory = provisioning_env
        email = "integrante@crea.example.com"

        alta = await client.post(
            PROVISION_URL,
            json={"email": email, "first_name": "Ana", "last_name": "Ruiz",
                  "tenant_id": TENANT_A},
            headers=AUTH,
        )
        assert alta.status_code == 201
        # and it lands in the platform pool, which is the whole point
        assert (await _get_user(session_factory, alta.json()["id"])).tenant_id is None
        assert alta.json()["org_role"] == "member"

        baja = await client.post(
            SUSPEND_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
        )
        assert baja.status_code == 200 and baja.json()["changed"] is True

        realta = await client.post(
            REACTIVATE_URL, json={"email": email, "tenant_id": TENANT_A}, headers=AUTH
        )
        assert realta.status_code == 200 and realta.json()["changed"] is True
