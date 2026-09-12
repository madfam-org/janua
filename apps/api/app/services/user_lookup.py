"""Tenant-aware user lookup by email.

Since migration 013, ``users.email`` is unique PER TENANT, not globally: the same
address can exist once in each tenant's pool AND once in the untenanted (staff /
platform) pool. That means a bare ``select(User).where(User.email == x)`` can now
match MORE THAN ONE row, so:

- ``.scalar_one_or_none()`` on it can raise ``MultipleResultsFound``, and
- ``.first()`` / ``.scalar()`` on it silently return an ARBITRARY row — which,
  across tenants, is a cross-tenant identity confusion (log in as the wrong
  tenant's user).

Every email lookup must therefore declare WHICH pool it means. These helpers are
the single primitive for that. Passing ``tenant_id=None`` scopes to the
untenanted pool and reproduces EXACTLY the pre-013 behaviour for staff/platform
identities — which is what the great majority of existing call sites want.

There is deliberately no "search every pool" helper: an email is not a global
identifier any more, and code that wants a user must know the tenant context it
is operating in (an OAuth client's org for an end-user flow, ``None`` for the
platform pool, the target org for an admin/SCIM/SSO provisioning op).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserStatus


def _scope_by_pool(stmt, tenant_id: Optional[UUID]):
    """Constrain a User select to a single email-uniqueness pool.

    tenant_id is a real UUID → that tenant's pool; None → the untenanted pool
    (``tenant_id IS NULL``). This mirrors the two partial unique indexes from
    migration 013 exactly, so a lookup can match at most one row.
    """
    if tenant_id is None:
        return stmt.where(User.tenant_id.is_(None))
    return stmt.where(User.tenant_id == tenant_id)


async def get_user_by_email(
    db: AsyncSession,
    email: str,
    *,
    tenant_id: Optional[UUID] = None,
    active_only: bool = False,
) -> Optional[User]:
    """Return the single user with ``email`` in the given pool, or None.

    Because the lookup is pool-scoped it matches at most one row, so
    ``scalar_one_or_none`` is safe again. ``tenant_id=None`` is the untenanted /
    staff pool (pre-013 behaviour). ``active_only=True`` additionally requires
    ``status == ACTIVE`` (some callers filter this inline today).
    """
    stmt = select(User).where(User.email == email)
    stmt = _scope_by_pool(stmt, tenant_id)
    if active_only:
        stmt = stmt.where(User.status == UserStatus.ACTIVE)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


class AmbiguousEmailAcrossPools(Exception):
    """More than one user holds this email and no preference resolved it.

    Raised by :func:`resolve_user_by_email_across_pools`. This is the world
    migration 013 creates, and since 2026-09-06 it is production's world too
    (``apps/api/alembic/PROD_ALEMBIC_STATE.json``), so treat this as a branch
    that HAPPENS rather than one that guards. Callers must surface it as a 4xx
    and make it observable — picking a row arbitrarily is the cross-tenant
    identity confusion the module docstring warns about.
    """

    def __init__(self, email: str, count: int):
        self.email = email
        self.count = count
        super().__init__(f"{count} active users share the email {email!r} across pools")


async def resolve_user_by_email_across_pools(
    db: AsyncSession,
    email: str,
    *,
    preferred_tenant_id: Optional[UUID] = None,
    active_only: bool = True,
) -> Optional[User]:
    """BRIDGE helper: find the one user holding ``email`` in ANY pool.

    WHY THIS EXISTS, given the module docstring says there is deliberately no
    "search every pool" helper: the bare-email entry points — magic link,
    password reset, internal lifecycle addressed by email — are handed an
    address and nothing else. They have no tenant context to declare, so
    pool-scoped :func:`get_user_by_email` would make them GUESS a pool, and the
    guess they used to make (untenanted only) was wrong for everyone the
    internal provisioning API had created WITH a ``tenant_id``: the lookup
    missed them, the "not found → create" branch ran, and its INSERT collided
    with the then-global ``ix_users_email`` → IntegrityError → 503. Nobody got
    a magic link (2026-09-03, 21 users; see
    ``docs/architecture/ADR-001_AUTH_FLOW.md``).

    THE SCHEMA THIS RUNS ON TODAY. Migration 013 IS APPLIED in production. It
    was applied with the postgres role and stamped on 2026-09-06, and the
    ledger of that reading is ``apps/api/alembic/PROD_ALEMBIC_STATE.json``
    (the database is the truth; that file records the last time a human read
    it with ``scripts/alembic_converge.py --check``). Prod is converged at
    ``016_org_member_app_roles``, well past 013. So the global unique index
    ``ix_users_email`` is GONE, replaced by 013's two partial unique indexes:
    ``uq_users_tenant_email`` WHERE ``tenant_id IS NOT NULL``, and
    ``uq_users_email_global`` WHERE ``tenant_id IS NULL``.

    CONSEQUENCE — THIS LOOKUP IS NO LONGER EXACT. One address may now
    LEGITIMATELY hold a row in the platform pool (``tenant_id IS NULL``) AND a
    row in each of N tenant pools. That is what 013 is for; it is not a data
    defect and it will not be cleaned up. "The user holding this email" has
    therefore stopped being a well-defined phrase, so this helper resolves
    rather than assumes:

    - ``preferred_tenant_id`` — the pool of the OAuth client that owns the
      request's redirect host — is consulted FIRST, and wins when exactly one
      candidate sits in that pool.
    - Otherwise, with more than one candidate remaining, it raises
      :class:`AmbiguousEmailAcrossPools`. Returning an arbitrary row would be
      the cross-tenant identity confusion the module docstring warns about: it
      signs the requester in as somebody else's user.

    Read that raise as a REACHABLE production branch, not a defensive one. It
    was unreachable only while the schema still held the address globally
    unique; since 2026-09-06 nothing in the database prevents the collision.
    Callers must answer 4xx and must make it visible — a login path that fails
    silently is a login path nobody is told about.

    Callers that know their tenant context must keep using
    :func:`get_user_by_email`; this is only for the bare-email entry points that
    have no tenant to declare.
    """
    stmt = select(User).where(User.email == email)
    if active_only:
        stmt = stmt.where(User.status == UserStatus.ACTIVE)
    result = await db.execute(stmt)
    users = list(result.scalars().all())

    if not users:
        return None
    if len(users) == 1:
        return users[0]

    if preferred_tenant_id is not None:
        preferred = [u for u in users if u.tenant_id == preferred_tenant_id]
        if len(preferred) == 1:
            return preferred[0]

    raise AmbiguousEmailAcrossPools(email, len(users))
