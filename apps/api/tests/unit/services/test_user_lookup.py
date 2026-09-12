"""Unit tests for the tenant-aware user lookup helper — `get_user_by_email`.

Since migration 013 email is unique PER TENANT, so a lookup must declare its
pool. These tests assert the statement is scoped correctly for each pool and that
`scalar_one_or_none` is what runs (safe again, because a pool-scoped lookup is
single-row).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import user_lookup as user_lookup_mod
from app.services.user_lookup import (
    AMBIGUOUS_EMAIL_EVENT,
    AmbiguousEmailAcrossPools,
    get_user_by_email,
    log_ambiguous_email,
    redact_email,
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


class TestAmbiguityIsObservable:
    """The refusal became reachable on 2026-09-06 and nothing watched it.

    `AmbiguousEmailAcrossPools` surfaces as a 400 on magic link, a 409 on the
    internal lifecycle surface, and — worst — as an ordinary 200 on password
    reset, where enumeration safety forbids telling the caller anything. Until
    these emissions existed, a login path could stop working for a person and
    leave no trace anywhere.
    """

    def test_the_event_name_is_stable(self):
        """An alert queries this string. It is part of the contract, not a
        detail of the call site, which is why it is a module constant."""
        assert AMBIGUOUS_EMAIL_EVENT == "auth.ambiguous_email_across_pools"

    def test_it_logs_the_event_with_the_operator_fields(self):
        exc = AmbiguousEmailAcrossPools("alice@creatumundo.mx", 2)

        with patch.object(user_lookup_mod, "logger") as log:
            log_ambiguous_email(exc, entry_point="magic_link")

        log.warning.assert_called_once()
        event = log.warning.call_args[0][0]
        fields = log.warning.call_args[1]
        assert event == AMBIGUOUS_EMAIL_EVENT
        assert fields["entry_point"] == "magic_link"
        assert fields["pool_count"] == 2

    def test_the_raw_address_never_reaches_the_log(self):
        """The whole point of the redaction. A log stream is not an identity
        store, and this event fires on an address that by definition belongs to
        someone with accounts in more than one place."""
        exc = AmbiguousEmailAcrossPools("alice@creatumundo.mx", 2)

        with patch.object(user_lookup_mod, "logger") as log:
            log_ambiguous_email(exc, entry_point="magic_link")

        rendered = repr(log.warning.call_args)
        assert "alice@creatumundo.mx" not in rendered
        assert log.warning.call_args[1]["email"] == "al***@creatumundo.mx"

    def test_it_is_a_warning_not_an_error(self):
        """The request was refused correctly; the service is fine. What is
        broken is the data, and that is a repair, not a page."""
        exc = AmbiguousEmailAcrossPools("alice@creatumundo.mx", 2)

        with patch.object(user_lookup_mod, "logger") as log:
            log_ambiguous_email(exc, entry_point="magic_link")

        log.error.assert_not_called()
        log.info.assert_not_called()
        log.warning.assert_called_once()

    def test_extra_context_rides_along(self):
        org = uuid4()
        exc = AmbiguousEmailAcrossPools("alice@creatumundo.mx", 3)

        with patch.object(user_lookup_mod, "logger") as log:
            log_ambiguous_email(
                exc, entry_point="internal_user_lifecycle", organization_id=str(org)
            )

        assert log.warning.call_args[1]["organization_id"] == str(org)

    def test_the_domain_survives_because_it_is_what_identifies_the_pools(self):
        assert redact_email("ana@ctm.example.com") == "an***@ctm.example.com"

    def test_a_one_character_local_part_is_still_redacted(self):
        """`a***@x` must not degenerate into the address itself."""
        assert redact_email("a@example.com") == "a***@example.com"

    def test_a_malformed_address_redacts_wholesale(self):
        """Nothing parseable means nothing safe to show."""
        assert redact_email("not-an-address") == "[redacted]"
        assert redact_email("") == "[redacted]"

