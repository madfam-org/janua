"""The connections service boundary trusts only clients a platform admin registered.

`connections_service_auth.current_service_client` re-reads the actor's client
row on every call. Besides the live grant (active, confidential, audience
``janua-connections``, scope ``connections:delegate``, ``client_credentials``)
the row's ``created_by`` must be a platform admin
(`oauth_client_authority.client_registered_by_platform_admin`), as at the
payment-mail and branding boundaries. The refusal is the same as for a missing
grant: 403 ``service_client_grant_unavailable``, and nothing is delegated.

Both paths are covered: the user-bound token exchange and the offline path.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from consent_helpers import (
    YT_PURPOSE,
    activity,
    add_connection,
    add_platform_admin,
    add_service_client,
    add_user,
    granted,
    mint_service_token,
    mint_user_token,
    reason,
    sqlite_app,
    use_rs256,
)
from sqlalchemy import update

from app.models import OAuthClient, User

pytestmark = pytest.mark.asyncio

EXCHANGE_ID = "jnc_provenance_exchange_fixture"
OFFLINE_ID = "jnc_provenance_offline_fixture"
EXCHANGE = "/api/v1/connections/token-exchange"
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
AT = "urn:ietf:params:oauth:token-type:access_token"


@pytest_asyncio.fixture
async def env(monkeypatch):
    use_rs256(monkeypatch)
    async with sqlite_app() as (client, factory):
        person = await add_user(factory, "person@example.com")
        org_admin = await add_user(factory, "org-admin@example.com")
        registrar = await add_platform_admin(factory)
        # The purpose registry names these clients; who registered them is
        # what each test varies.
        await add_service_client(
            factory, name="creator-census", client_id=EXCHANGE_ID, created_by=org_admin.id
        )
        await add_service_client(
            factory, name="creator-census-reauth", client_id=OFFLINE_ID, created_by=org_admin.id
        )
        conn = await add_connection(factory, user_id=person.id, purposes=granted())
        yield {
            "client": client,
            "factory": factory,
            "person": person,
            "org_admin": org_admin,
            "registrar": registrar,
            "conn": conn,
        }


async def _registered_by(env, client_id: str, user: User) -> None:
    async with env["factory"]() as db:
        await db.execute(
            update(OAuthClient).where(OAuthClient.client_id == client_id).values(created_by=user.id)
        )
        await db.commit()


async def _exchange(env):
    return await env["client"].post(
        EXCHANGE,
        data={
            "grant_type": GRANT,
            "subject_token": mint_user_token(env["person"].id),
            "subject_token_type": AT,
            "actor_token": mint_service_token(EXCHANGE_ID),
            "actor_token_type": AT,
            "purpose": YT_PURPOSE,
        },
    )


async def _offline(env):
    return await env["client"].post(
        f"/api/v1/connections/{env['conn'].id}/token",
        json={"purpose": YT_PURPOSE, "ttl_seconds": 300},
        headers={
            "Authorization": f"Bearer {mint_service_token(OFFLINE_ID)}",
            "X-Acting-User-Id": str(env["person"].id),
        },
    )


async def _assert_refused(env, resp) -> None:
    assert resp.status_code == 403, resp.text
    assert reason(resp) == "service_client_grant_unavailable"
    assert await activity(env["factory"], "tool.delegation.issued") == []


# ---- token exchange ------------------------------------------------------------


async def test_exchange_refuses_a_client_not_registered_by_a_platform_admin(env):
    await _assert_refused(env, await _exchange(env))


async def test_exchange_accepts_the_same_client_registered_by_a_platform_admin(env):
    await _registered_by(env, EXCHANGE_ID, env["registrar"])
    resp = await _exchange(env)
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"] == "provider-access-placeholder"
    (log,) = await activity(env["factory"], "tool.delegation.issued")
    assert log.activity_metadata["actor_client_id"] == EXCHANGE_ID


# ---- offline path --------------------------------------------------------------


async def test_offline_refuses_a_client_not_registered_by_a_platform_admin(env):
    await _assert_refused(env, await _offline(env))


async def test_offline_accepts_the_same_client_registered_by_a_platform_admin(env):
    await _registered_by(env, OFFLINE_ID, env["registrar"])
    resp = await _offline(env)
    assert resp.status_code == 200, resp.text
    assert resp.json()["purpose"] == YT_PURPOSE


# ---- provenance is read live ---------------------------------------------------


async def test_a_registrar_who_loses_platform_admin_takes_the_trust_with_them(env):
    await _registered_by(env, EXCHANGE_ID, env["registrar"])
    assert (await _exchange(env)).status_code == 200

    async with env["factory"]() as db:
        await db.execute(update(User).where(User.id == env["registrar"].id).values(is_admin=False))
        await db.commit()
    resp = await _exchange(env)
    assert resp.status_code == 403, resp.text
    assert reason(resp) == "service_client_grant_unavailable"
