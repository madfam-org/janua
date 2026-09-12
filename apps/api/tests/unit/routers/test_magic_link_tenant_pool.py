"""Magic link must find users the provisioning API put in a TENANT pool.

Production incident 2026-09-03 (request_id 47ef96c7-…, 15:51:54Z, 21 users):
janua#583 made every email lookup pool-scoped, and `send_magic_link` declared
the untenanted pool. But the internal provisioning API writes CTM staff with
`users.tenant_id = <org id>` (crea-map sends `tenant_id` in its provision
body), so the lookup missed them, the "not found → create" branch ran, and the
INSERT hit `ix_users_email` — which in PRODUCTION was then still the GLOBAL
unique index from 000_init, because migration 013's per-tenant partial indexes
had not been applied (prod `alembic_version` was 011, the DB hand-migrated).
Every such request became an IntegrityError → 503, and the requesting product
showed «revisa tu correo» while nobody got a link.

013 was applied and stamped on 2026-09-06 (`apps/api/alembic/PROD_ALEMBIC_STATE.json`,
converged at 016), so prod now runs the two partial indexes. The consequence for
these tests is case 4 below: it stopped being hypothetical.

These tests pin the four behaviours of the fix:
  1. a tenant-pooled user gets a link and NO second row is inserted;
  2. the untenanted case is unchanged (still creates on a genuine miss);
  3. an IntegrityError on the create re-selects instead of 503ing;
  4. a genuinely ambiguous email is refused with a 400, never resolved by
     picking an arbitrary pool.
"""

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

import app.routers.v1.auth as auth_mod
from app.models import User, UserStatus
from app.routers.v1.auth import MagicLinkRequest, _dispatch_password_reset, send_magic_link
from app.services import user_lookup as user_lookup_mod
from app.services.user_lookup import AMBIGUOUS_EMAIL_EVENT

pytestmark = pytest.mark.asyncio

EMAIL = "staff@creatumundo.example.com"


def _request():
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/magic-link",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("198.51.100.7", 51234),
        }
    )


def _user(*, tenant_id=None, status=UserStatus.ACTIVE):
    return User(
        id=uuid.uuid4(),
        email=EMAIL,
        tenant_id=tenant_id,
        status=status,
        email_verified=True,
    )


def _db(*, untenanted=None, across_pools=(), commit_raises=None):
    """Async session whose two lookups are answered independently.

    `get_user_by_email` resolves via ``scalar_one_or_none`` and
    ``resolve_user_by_email_across_pools`` via ``scalars().all()``, so one
    result object can serve both: the router's own call order decides which is
    consulted. ``commit_raises`` fires ONCE, standing in for the global
    ``ix_users_email`` rejecting the insert.
    """
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=untenanted)
    result.scalars.return_value.all = MagicMock(return_value=list(across_pools))
    # The OAuth-client scan for the preferred pool iterates scalars() directly;
    # with no redirect_url in these tests it is never reached, but keep it sane.
    result.scalars.return_value.__iter__ = lambda self: iter(())

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()

    state = {"raised": False}

    async def commit():
        if commit_raises is not None and not state["raised"]:
            state["raised"] = True
            raise commit_raises

    db.commit = AsyncMock(side_effect=commit)
    db.rollback = AsyncMock()

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


def _created_users(db):
    return [c.args[0] for c in db.add.call_args_list if c.args and isinstance(c.args[0], User)]


def _magic_links(db):
    from app.models import MagicLink

    return [c.args[0] for c in db.add.call_args_list if c.args and isinstance(c.args[0], MagicLink)]


async def _send(db, background=None):
    with (
        patch.object(auth_mod.settings, "ENABLE_MAGIC_LINKS", True),
        patch.object(auth_mod.settings, "EMAIL_ENABLED", True),
    ):
        return await send_magic_link(
            request=_request(),
            magic_link_data=MagicLinkRequest(email=EMAIL),
            background_tasks=background or MagicMock(),
            db=db,
        )


class TestTenantPooledUser:
    async def test_gets_a_link_without_a_duplicate_insert(self):
        """THE REGRESSION. Untenanted lookup misses, across-pools finds them."""
        pooled = _user(tenant_id=uuid.uuid4())
        db = _db(untenanted=None, across_pools=[pooled])

        await _send(db)

        assert _created_users(db) == [], "must not create a second row for an existing email"
        links = _magic_links(db)
        assert len(links) == 1
        assert links[0].user_id == pooled.id
        assert links[0].email == EMAIL

    async def test_the_email_is_actually_queued_for_that_user(self):
        pooled = _user(tenant_id=uuid.uuid4())
        db = _db(untenanted=None, across_pools=[pooled])
        background = MagicMock()

        await _send(db, background)

        background.add_task.assert_called_once()
        assert background.add_task.call_args.args[1] == EMAIL


class TestUntenantedUnchanged:
    async def test_existing_untenanted_user_is_used_directly(self):
        staff = _user(tenant_id=None)
        db = _db(untenanted=staff, across_pools=[staff])

        await _send(db)

        assert _created_users(db) == []
        assert _magic_links(db)[0].user_id == staff.id

    async def test_a_genuine_miss_still_creates(self):
        """No user anywhere: this endpoint is a signup in everything but name."""
        db = _db(untenanted=None, across_pools=[])

        await _send(db)

        created = _created_users(db)
        assert len(created) == 1
        assert created[0].email == EMAIL
        assert created[0].status == UserStatus.ACTIVE
        assert len(_magic_links(db)) == 1


class TestIntegrityErrorGuard:
    async def test_a_colliding_insert_re_selects_instead_of_503(self):
        """A race (or a row the lookups could not see) must not become a 503."""
        winner = _user(tenant_id=None)
        collision = IntegrityError("INSERT", {}, Exception("ix_users_email"))
        db = _db(untenanted=None, across_pools=[], commit_raises=collision)

        # Both lookups miss the first time round; after the rollback the row is
        # visible, which is exactly the race being modelled.
        calls = {"n": 0}
        original = db.execute

        async def execute(stmt, *a, **kw):
            calls["n"] += 1
            result = await original(stmt, *a, **kw)
            if calls["n"] > 1:
                result.scalar_one_or_none = MagicMock(return_value=winner)
            return result

        db.execute = AsyncMock(side_effect=execute)

        await _send(db)

        db.rollback.assert_awaited()
        assert _magic_links(db)[0].user_id == winner.id

    async def test_a_collision_with_an_inactive_row_is_a_400_not_a_503(self):
        collision = IntegrityError("INSERT", {}, Exception("ix_users_email"))
        db = _db(untenanted=None, across_pools=[], commit_raises=collision)

        with pytest.raises(HTTPException) as excinfo:
            await _send(db)

        assert excinfo.value.status_code == 400
        assert "not active" in excinfo.value.detail


class TestAmbiguityIsRefused:
    async def test_two_pools_holding_the_email_refuse_with_400(self):
        """Reachable in production since 013 landed (2026-09-06): one address
        may legitimately hold a row in the platform pool and one in each tenant
        pool. Never pick a pool arbitrarily."""
        db = _db(
            untenanted=None,
            across_pools=[_user(tenant_id=uuid.uuid4()), _user(tenant_id=uuid.uuid4())],
        )

        with pytest.raises(HTTPException) as excinfo:
            await _send(db)

        assert excinfo.value.status_code == 400
        assert "more than one tenant pool" in excinfo.value.detail
        assert _created_users(db) == [], "ambiguity must never fall through to a create"


class TestAmbiguityIsLogged:
    """The 400 above is correct and invisible.

    Nothing counted it, nothing alerted on it, and the one caller that cannot
    be told (password reset, which must stay enumeration-safe) produced no
    signal at all. These pin the event an operator alerts on — see
    `docs/internal/operations/INCIDENT_RESPONSE_PLAYBOOK.md`.
    """

    async def test_the_magic_link_refusal_emits_the_event(self):
        db = _db(
            untenanted=None,
            across_pools=[_user(tenant_id=uuid.uuid4()), _user(tenant_id=uuid.uuid4())],
        )

        with patch.object(user_lookup_mod, "logger") as log:
            with pytest.raises(HTTPException):
                await _send(db)

        log.warning.assert_called_once()
        assert log.warning.call_args[0][0] == AMBIGUOUS_EMAIL_EVENT
        fields = log.warning.call_args[1]
        assert fields["entry_point"] == "magic_link"
        assert fields["pool_count"] == 2
        assert EMAIL not in repr(log.warning.call_args)

    async def test_password_reset_emits_even_though_the_caller_is_told_nothing(self):
        """The important one. `_dispatch_password_reset` returns None on
        ambiguity so absence stays indistinguishable from success; the log line
        is therefore the ONLY evidence that recovery is broken for this person.
        """
        db = _db(
            untenanted=None,
            across_pools=[_user(tenant_id=uuid.uuid4()), _user(tenant_id=uuid.uuid4())],
        )
        background = MagicMock()

        with patch.object(user_lookup_mod, "logger") as log:
            result = await _dispatch_password_reset(EMAIL, None, background, db)

        assert result is None
        background.add_task.assert_not_called()
        log.warning.assert_called_once()
        assert log.warning.call_args[0][0] == AMBIGUOUS_EMAIL_EVENT
        assert log.warning.call_args[1]["entry_point"] == "password_reset"

    async def test_an_unambiguous_send_logs_nothing(self):
        """The event marks a broken identity. Emitting it on the healthy path
        would train an operator to ignore it."""
        pooled = _user(tenant_id=uuid.uuid4())
        db = _db(untenanted=None, across_pools=[pooled])

        with patch.object(user_lookup_mod, "logger") as log:
            await _send(db)

        log.warning.assert_not_called()
