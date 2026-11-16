"""Run inside an image: print what its organization claims do for a multi-org
person with an operator-set primary organization, as one JSON line.

Runs in the base image too, which has no primary-organization table, model or
routes, so nothing new is imported directly. Importing ``app.main`` imports the
whole application, so a clean run also proves the image imports with the copied
files. Nothing connects to a database: the claims resolver gets a session
double that answers the three queries it can ask (active memberships, the
primary-organization pointer, application-role grants) from fixed synthetic
rows, and records which ones it asked.

    docker run --rm -i --entrypoint python <env> IMAGE - < check_primary_org.py
"""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

from app.main import app
from app.models import User
from app.services import org_claims_service as claims

GRANT_APP, GRANT_ROLE = "example-app", "operator"
ROUTES = {
    "/api/v1/internal/primary-organization/set",
    "/api/v1/internal/primary-organization/clear",
    "/api/v1/internal/primary-organization/{user_id}",
}


class _Result:
    def __init__(self, rows=(), scalar=None, scalars=()):
        self._rows, self._scalar, self._scalars = list(rows), scalar, list(scalars)

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars, first=lambda: next(iter(self._scalars), None))


class _Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Db:
    """An AsyncSession double. Every grant belongs to one membership id; the
    application-role query is answered for the membership id it binds."""

    def __init__(self, rows, primary=None, grants=None, primary_fails=False):
        self.rows, self.primary, self.grants = rows, primary, grants or {}
        self.primary_fails, self.primary_reads = primary_fails, 0

    async def execute(self, stmt, *args, **kwargs):
        sql = str(stmt)
        if "user_primary_organizations" in sql:
            self.primary_reads += 1
            if self.primary_fails:
                raise RuntimeError('relation "user_primary_organizations" does not exist')
            return _Result(scalar=self.primary)
        if "organization_member_app_roles" in sql:
            bound = set(stmt.compile().params.values())
            return _Result(scalars=[g for mid, gs in self.grants.items() if mid in bound for g in gs])
        return _Result(rows=self.rows)

    def begin_nested(self):
        return _Savepoint()

    async def rollback(self):
        return None


def _person(tenant_id=None):
    return SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)


def _membership(slug):
    org = SimpleNamespace(id=uuid.uuid4(), slug=slug)
    member = SimpleNamespace(id=uuid.uuid4(), role="member", status="active")
    return member, org


def _grant():
    return SimpleNamespace(app=GRANT_APP, role=GRANT_ROLE, revoked_at=None)


async def _run():
    (member_a, org_a), (member_b, org_b) = _membership("org-a"), _membership("org-b")
    rows = [(member_a, org_a), (member_b, org_b)]
    grants = {member_b.id: [_grant()]}
    expected = f"{GRANT_APP}:{GRANT_ROLE}"

    # 1. Several memberships, no tenant match, primary = b: b's claims and grant.
    db = _Db(rows, primary=org_b.id, grants=grants)
    resolved = await claims.get_user_org_claims(_person(), db)
    session_roles = claims.merge_app_roles_into_claims(resolved).get("roles", [])
    primary_resolves = resolved.get("org_id") == str(org_b.id) and session_roles == [expected]

    # 2. A primary organization the person is not an active member of: nothing.
    db = _Db(rows, primary=uuid.uuid4(), grants=grants)
    resolved = await claims.get_user_org_claims(_person(), db)
    non_member_resolves_nothing = "org_id" not in resolved and claims.APP_ROLES_KEY not in resolved

    # 3. tenant_id naming an active membership wins, and the pointer is not read.
    db = _Db(rows, primary=org_b.id, grants=grants)
    resolved = await claims.get_user_org_claims(_person(tenant_id=org_a.id), db)
    tenant_wins = resolved.get("org_id") == str(org_a.id) and db.primary_reads == 0

    # 4. The pointer read fails (a database without migration 022): no claims, no error.
    db = _Db(rows, primary=org_b.id, grants=grants, primary_fails=True)
    try:
        resolved = await claims.get_user_org_claims(_person(), db)
        read_failure_fails_closed = "org_id" not in resolved and len(resolved.get("orgs", [])) == 2
    except Exception:
        read_failure_fails_closed = False

    # 5. One membership: the pointer is never read.
    db = _Db([(member_b, org_b)], primary=org_a.id, grants=grants)
    resolved = await claims.get_user_org_claims(_person(), db)
    single_membership_unread = resolved.get("org_id") == str(org_b.id) and db.primary_reads == 0

    return {
        "primary_resolves_with_app_role": primary_resolves,
        "non_member_primary_resolves_nothing": non_member_resolves_nothing,
        "tenant_id_wins_without_reading": tenant_wins,
        "read_failure_fails_closed": read_failure_fails_closed,
        "single_membership_never_reads": single_membership_unread,
        "routes_registered": ROUTES <= set(app.openapi()["paths"]),
        # The hotfix must not touch the User model, read on every login.
        "user_model_untouched": "primary_organization_id" not in User.__table__.c,
    }


print("PRIMARY_ORG=" + json.dumps(asyncio.run(_run()), sort_keys=True))
