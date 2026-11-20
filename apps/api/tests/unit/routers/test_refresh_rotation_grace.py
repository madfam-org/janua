"""Refresh rotation under concurrency (edge-case roadmap 1.3, owner decision D5).

Before: two refreshes of one session at once both rotated (last write won) and
the loser's next refresh revoked the whole family; one arriving just after the
winner committed was refused by the rotation blacklist. Either way a person
with two tabs was signed out.

Now exactly one request rotates (row lock plus compare-and-set on the JTI) and,
for REFRESH_REUSE_GRACE_SECONDS, the rotated-away token gets the pair that
rotation issued. Reuse of an older token, of a token after the window, or
after a later rotation still revokes the family.

Runs POST /api/v1/auth/refresh against SQLite and an in-memory Redis, with the
fixture of test_revocation_routes.py.
"""

import asyncio

from sqlalchemy import select

from app.core.jwt_manager import jwt_manager
from app.models import Session as UserSession
from app.services import refresh_grace
from tests.unit.routers import test_revocation_routes as revocation

# The SQLite + in-memory Redis app fixture and helpers of the revocation tests.
env = revocation.env
_refresh, _row, _sign_in = revocation._refresh, revocation._row, revocation._sign_in


def _grace_key(jti):
    from app.services.refresh_grace import grace_key as _refresh_grace_key

    return _refresh_grace_key(jti)


def _jti(token):
    return jwt_manager.get_unverified_claims(token)["jti"]


async def _family_revoked(env, token):
    family = jwt_manager.get_unverified_claims(token)["family"]
    return bool(await env.redis.strict_exists(f"revoked_family:{family}"))


async def test_two_refreshes_at_once_both_succeed_and_keep_one_current_token(env):
    _, refresh, session_id = await _sign_in(env, env.alice)

    first, second = await asyncio.gather(_refresh(env, refresh), _refresh(env, refresh))

    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["refresh_token"] == second.json()["refresh_token"]
    row = await _row(env, session_id)
    assert row.is_active and not row.revoked
    assert row.refresh_token_jti == _jti(first.json()["refresh_token"])
    assert not await _family_revoked(env, refresh)
    # The pair both got keeps working.
    assert (await _refresh(env, first.json()["refresh_token"])).status_code == 200


async def test_a_repeat_just_after_the_rotation_gets_the_same_pair(env):
    _, refresh, session_id = await _sign_in(env, env.alice)
    first = await _refresh(env, refresh)
    assert first.status_code == 200

    repeat = await _refresh(env, refresh)  # e.g. the SSR render, 200 ms later

    assert repeat.status_code == 200, repeat.text
    assert repeat.json() == first.json()
    row = await _row(env, session_id)
    assert row.is_active and row.refresh_token_jti == _jti(first.json()["refresh_token"])
    assert not await _family_revoked(env, refresh)


async def test_reuse_after_the_window_still_revokes_the_family(env):
    _, refresh, session_id = await _sign_in(env, env.alice)
    assert (await _refresh(env, refresh)).status_code == 200
    await env.redis.strict_delete(_grace_key(_jti(refresh)))  # the window passed

    reuse = await _refresh(env, refresh)

    assert reuse.status_code == 401
    # Refused by the rotation blacklist, as before the change.
    row = await _row(env, session_id)
    assert row.refresh_token_jti != _jti(refresh)


async def test_a_token_two_rotations_old_is_not_in_the_window(env):
    _, oldest, session_id = await _sign_in(env, env.alice)
    middle = (await _refresh(env, oldest)).json()["refresh_token"]
    newest = (await _refresh(env, middle)).json()["refresh_token"]

    # `oldest` still has a grace record, but the session rotated again since.
    assert (await _refresh(env, oldest)).status_code == 401
    row = await _row(env, session_id)
    assert row.refresh_token_jti == _jti(newest)


async def test_the_grace_record_holds_no_readable_token(env):
    _, refresh, _ = await _sign_in(env, env.alice)
    issued = (await _refresh(env, refresh)).json()

    stored = await env.redis.strict_get(_grace_key(_jti(refresh)))
    assert stored and issued["refresh_token"] not in stored
    assert issued["access_token"] not in stored


async def test_a_signed_out_session_gets_nothing_from_the_window(env):
    access, refresh, _ = await _sign_in(env, env.alice)
    assert (await _refresh(env, refresh)).status_code == 200
    signed_out = await env.http.post(
        "/api/v1/auth/signout",
        headers={
            "Authorization": f"Bearer {(await _refresh(env, refresh)).json()['access_token']}"
        },
    )
    assert signed_out.status_code == 200, signed_out.text
    assert (await _refresh(env, refresh)).status_code == 401


async def test_grace_zero_restores_strict_single_use(env, monkeypatch):
    monkeypatch.setattr(refresh_grace, "REFRESH_REUSE_GRACE_SECONDS", 0)
    _, refresh, _ = await _sign_in(env, env.alice)
    assert (await _refresh(env, refresh)).status_code == 200
    assert (await _refresh(env, refresh)).status_code == 401


async def test_only_one_rotation_is_written(env):
    _, refresh, session_id = await _sign_in(env, env.alice)
    await asyncio.gather(*(_refresh(env, refresh) for _ in range(3)))
    async with env.factory() as db:
        rows = (
            (await db.execute(select(UserSession).where(UserSession.id == session_id)))
            .scalars()
            .all()
        )
    assert len(rows) == 1 and rows[0].is_active
