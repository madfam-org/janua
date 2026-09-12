"""Unit tests for the tenant-aware user lookup helper — `get_user_by_email`.

Since migration 013 email is unique PER TENANT, so a lookup must declare its
pool. These tests assert the statement is scoped correctly for each pool and that
`scalar_one_or_none` is what runs (safe again, because a pool-scoped lookup is
single-row).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    get_user_by_email,
    resolve_user_by_email_across_pools,
)


def _db_capture():
    """AsyncMock db that records the statement passed to execute() and returns a
    result whose scalar_one_or_none yields a sentinel user."""
    sentinel = SimpleNamespace(id=uuid4())
    result = MagicMock()
    result.scalar_one_or_none.return_value = sentinel
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db, result, sentinel


def _compiled(stmt) -> str:
    # Render the WHERE clause with literal binds so we can assert on the SQL text
    # without a live dialect-specific engine.
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


class TestGetUserByEmail:
    async def test_returns_the_single_row(self):
        db, result, sentinel = _db_capture()
        got = await get_user_by_email(db, "a@example.com", tenant_id=None)
        assert got is sentinel
        # It resolves via scalar_one_or_none (single-row safe), not first().
        result.scalar_one_or_none.assert_called_once()

    async def test_untenanted_pool_scopes_tenant_id_is_null(self):
        db, *_ = _db_capture()
        await get_user_by_email(db, "a@example.com", tenant_id=None)
        sql = _compiled(db.execute.call_args.args[0])
        assert "tenant_id IS NULL" in sql
        assert "a@example.com" in sql

    async def test_tenanted_pool_scopes_to_that_tenant(self):
        db, *_ = _db_capture()
        org = uuid4()
        await get_user_by_email(db, "a@example.com", tenant_id=org)
        sql = _compiled(db.execute.call_args.args[0])
        assert str(org) in sql
        # Must NOT collapse to the untenanted pool.
        assert "tenant_id IS NULL" not in sql

    @staticmethod
    def _where(stmt) -> str:
        # Just the WHERE clause text (status appears in the SELECT column list
        # regardless, so assert on the predicate, not the whole statement).
        # SQLAlchemy renders "WHERE" after a newline, so match the bare keyword.
        sql = _compiled(stmt)
        idx = sql.upper().find("WHERE")
        return sql[idx:] if idx != -1 else ""

    async def test_active_only_adds_status_predicate(self):
        db, *_ = _db_capture()
        await get_user_by_email(db, "a@example.com", tenant_id=None, active_only=True)
        where = self._where(db.execute.call_args.args[0]).lower()
        # ACTIVE is the enum value; its DB representation appears in the predicate.
        assert "status" in where

    async def test_active_only_default_is_false(self):
        db, *_ = _db_capture()
        await get_user_by_email(db, "a@example.com", tenant_id=None)
        where = self._where(db.execute.call_args.args[0]).lower()
        # No status predicate in the WHERE clause when active_only is not set.
        assert "status" not in where


class TestResolveUserByEmailAcrossPools:
    """The bridge helper for bare-email entry points, which have no tenant
    context to declare.

    Regression cover for 2026-09-03: magic link looked only in the untenanted
    pool, missed users the internal provisioning API had created WITH a
    tenant_id, and the create branch then collided with the then-global
    ix_users_email.

    Migration 013 is applied in production as of 2026-09-06
    (apps/api/alembic/PROD_ALEMBIC_STATE.json), so the address is no longer
    globally unique and the two refusal tests below cover a branch production
    can actually reach.
    """

    @staticmethod
    def _db_returning(users):
        result = MagicMock()
        result.scalars.return_value.all.return_value = users
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_finds_a_user_that_lives_in_a_tenant_pool(self):
        org = uuid4()
        pooled = SimpleNamespace(id=uuid4(), tenant_id=org)
        db = self._db_returning([pooled])
        got = await resolve_user_by_email_across_pools(db, "staff@ctm.test")
        assert got is pooled

    async def test_does_not_scope_to_a_single_pool(self):
        db = self._db_returning([])
        await resolve_user_by_email_across_pools(db, "a@example.com")
        sql = _compiled(db.execute.call_args.args[0])
        assert "tenant_id IS NULL" not in sql
        assert "a@example.com" in sql

    async def test_missing_user_is_none(self):
        db = self._db_returning([])
        assert await resolve_user_by_email_across_pools(db, "nobody@example.com") is None

    async def test_active_only_is_the_default(self):
        db = self._db_returning([])
        await resolve_user_by_email_across_pools(db, "a@example.com")
        sql = _compiled(db.execute.call_args.args[0]).lower()
        where = sql[sql.find("where"):]
        assert "status" in where

    async def test_preference_picks_the_redirect_hosts_pool(self):
        wanted, other = uuid4(), uuid4()
        mine = SimpleNamespace(id=uuid4(), tenant_id=wanted)
        theirs = SimpleNamespace(id=uuid4(), tenant_id=other)
        db = self._db_returning([theirs, mine])
        got = await resolve_user_by_email_across_pools(
            db, "alice@example.com", preferred_tenant_id=wanted
        )
        assert got is mine

    async def test_multiple_matches_without_a_preference_refuses(self):
        db = self._db_returning(
            [SimpleNamespace(id=uuid4(), tenant_id=uuid4()) for _ in range(2)]
        )
        with pytest.raises(AmbiguousEmailAcrossPools) as excinfo:
            await resolve_user_by_email_across_pools(db, "alice@example.com")
        assert excinfo.value.count == 2
        assert excinfo.value.email == "alice@example.com"

    async def test_preference_that_matches_nothing_still_refuses(self):
        db = self._db_returning(
            [SimpleNamespace(id=uuid4(), tenant_id=uuid4()) for _ in range(2)]
        )
        with pytest.raises(AmbiguousEmailAcrossPools):
            await resolve_user_by_email_across_pools(
                db, "alice@example.com", preferred_tenant_id=uuid4()
            )
