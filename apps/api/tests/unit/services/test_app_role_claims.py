"""Application roles reach the `roles` claim — and reach NOTHING else.

Revision 015 sealed `org_id` into session tokens and namespaced organization
roles as `madfam_org_roles`, on purpose: HCM's `HR_ROLES` contains the literal
string "admin", so org-account roles riding under a bare `roles` key would have
promoted every janua org admin to HR admin over payroll. That was right, and it
left the other half unbuilt — symbiosis-hcm authorizes on APPLICATION roles read
from `roles` (`hcm:hr`, `hcm:admin`), and janua emitted no `hcm:*` string at all.
CTM's Dirección held a valid membership, got a token with a correct `org_id`,
and was still refused every HR feature.

These tests pin the fix and, more importantly, the four ways it must NOT work:

  1. A grant reaches the token as `"<app>:<role>"`, and revoking it removes it
     at the next refresh.
  2. Another organization's grant NEVER appears — the resolver reads from ONE
     membership row, so the cross-org leak is prevented by the shape of the
     query rather than a filter someone could drop.
  3. Nothing is implicit: a service account, and an org `admin`, get exactly
     what was granted to them and not one string more. An org role must never
     become an application role by derivation — that is the payroll bridge the
     namespace exists to prevent, rebuilt by the back door.
  4. The legacy OIDC `roles` claim is not clobbered. `**org_claims` spreads
     AFTER `"roles": entitlements["roles"]` in the OIDC dict literal, so an
     unmerged `roles` key would have silently replaced a claim existing clients
     have read for years.
"""

from __future__ import annotations

import importlib
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.models.app_role import format_app_role
from app.services.auth_service import AuthService
from app.services.org_claims_service import (
    APP_ROLES_CLAIM,
    APP_ROLES_KEY,
    ORG_ROLES_CLAIM,
    get_user_org_claims,
    merge_app_roles_into_claims,
)


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


def _user(tenant_id=None, is_service_account=False):
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        tenant_id=tenant_id,
        is_admin=False,
        is_active=True,
        is_service_account=is_service_account,
    )


def _org(slug="crea"):
    return SimpleNamespace(id=uuid4(), slug=slug)


def _member(role="member"):
    return SimpleNamespace(id=uuid4(), role=role, status="active")


def _grant(app: str, role: str):
    return SimpleNamespace(app=app, role=role, revoked_at=None)


def _db(membership_rows, grants_by_member_id=None):
    """An AsyncSession double.

    The FIRST execute() answers the membership query (`.all()`); every later one
    answers an application-role query (`.scalars().all()`), keyed by the
    membership id the resolver actually filtered on. That keying is what lets
    the cross-org test below prove the resolver asked about ONE membership.
    """
    grants_by_member_id = grants_by_member_id or {}
    calls = {"n": 0, "app_role_queries": []}

    async def execute(stmt, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            result = MagicMock()
            result.all = MagicMock(return_value=membership_rows)
            return result

        compiled = str(stmt)
        calls["app_role_queries"].append(compiled)

        # Which membership did the resolver bind? Read it off the statement's
        # bound parameters rather than assuming, so the assertion is about what
        # the query really asked.
        bound = list(stmt.compile().params.values())
        matched = []
        for member_id, grants in grants_by_member_id.items():
            if member_id in bound:
                matched = grants
                break

        result = MagicMock()
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=matched)))
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()
    db._calls = calls
    return db


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_resolves_into_the_app_roles_key_as_app_colon_role():
    """The claim value is exactly the string symbiosis-hcm matches on."""
    org, member = _org("crea"), _member("member")
    db = _db([(member, org)], {member.id: [_grant("hcm", "hr")]})

    claims = await get_user_org_claims(_user(), db)

    assert claims[APP_ROLES_KEY] == ["hcm:hr"]
    assert format_app_role("hcm", "hr") == "hcm:hr"


@pytest.mark.asyncio
async def test_no_grants_emits_no_app_roles_key_at_all():
    """No grants ⇒ token shaped exactly as before this change."""
    org, member = _org(), _member()
    db = _db([(member, org)], {member.id: []})

    claims = await get_user_org_claims(_user(), db)

    assert APP_ROLES_KEY not in claims
    # Everything the previous change emitted is untouched.
    assert claims["org_id"] == str(org.id)
    assert claims[ORG_ROLES_CLAIM] == ["member"]


@pytest.mark.asyncio
async def test_revoked_grant_stops_contributing():
    """The resolver filters `revoked_at IS NULL`, in the query itself."""
    org, member = _org(), _member()
    db = _db([(member, org)], {member.id: []})

    await get_user_org_claims(_user(), db)

    compiled = db._calls["app_role_queries"][0].lower()
    assert "revoked_at" in compiled and "is null" in compiled


@pytest.mark.asyncio
async def test_grants_are_deduplicated_and_sorted():
    """A stable claim across mints: a reordering diff means nothing to anyone."""
    org, member = _org(), _member()
    db = _db(
        [(member, org)],
        {member.id: [_grant("hcm", "hr"), _grant("hcm", "admin"), _grant("hcm", "hr")]},
    )

    claims = await get_user_org_claims(_user(), db)

    assert claims[APP_ROLES_KEY] == ["hcm:admin", "hcm:hr"]


@pytest.mark.asyncio
async def test_another_orgs_grant_never_appears():
    """THE cross-tenant test.

    Two active memberships, `tenant_id` pinning org B. Org A carries an
    `hcm:hr` grant and org B carries none. The token must show NO application
    role: the resolver reads grants from the RESOLVED membership only, so org
    A's HR authority cannot ride along into a session scoped to org B.
    """
    org_a, member_a = _org("a"), _member("admin")
    org_b, member_b = _org("b"), _member("member")

    db = _db(
        [(member_a, org_a), (member_b, org_b)],
        {member_a.id: [_grant("hcm", "hr")], member_b.id: []},
    )

    claims = await get_user_org_claims(_user(tenant_id=org_b.id), db)

    assert claims["org_id"] == str(org_b.id)
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_ambiguous_membership_emits_no_app_roles():
    """No unambiguous org ⇒ no org_id, and therefore no application roles.

    There is no single membership to read grants from, and picking one of
    several would hand one tenant's HR authority to a session the user opened
    for another.
    """
    org_a, member_a = _org("a"), _member("admin")
    org_b, member_b = _org("b"), _member("member")

    db = _db(
        [(member_a, org_a), (member_b, org_b)],
        {member_a.id: [_grant("hcm", "hr")], member_b.id: [_grant("hcm", "admin")]},
    )

    claims = await get_user_org_claims(_user(tenant_id=None), db)

    assert "org_id" not in claims
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_service_account_without_a_grant_gets_no_application_roles():
    """A service principal is granted authority on exactly the same terms as a
    person: explicitly, or not at all. Being a technical login neither confers
    nor withholds an application role."""
    org, member = _org(), _member()
    db = _db([(member, org)], {member.id: []})

    claims = await get_user_org_claims(_user(is_service_account=True), db)

    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_service_account_with_an_explicit_grant_does_get_it():
    org, member = _org(), _member()
    db = _db([(member, org)], {member.id: [_grant("hcm", "importer")]})

    claims = await get_user_org_claims(_user(is_service_account=True), db)

    assert claims[APP_ROLES_KEY] == ["hcm:importer"]


@pytest.mark.asyncio
async def test_org_admin_gains_no_application_role_by_derivation():
    """THE anti-derivation test.

    An org `admin` with no grant gets NO application role. If a mapping ever
    turned an org role into an `hcm:*` role, it would rebuild exactly the
    org-role-to-payroll bridge the `madfam_org_roles` namespace exists to
    prevent — an account admin gaining HR authority as a side effect of being
    an account admin.
    """
    org, member = _org(), _member("admin")
    db = _db([(member, org)], {member.id: []})

    claims = await get_user_org_claims(_user(), db)

    assert claims[ORG_ROLES_CLAIM] == ["admin"]
    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_app_role_read_failure_fails_closed_without_losing_org_claims():
    """An unreachable grants table (migration 016 not yet applied by hand) must
    degrade to "no application roles" — today's behaviour exactly — never to a
    failed login and never to guessed roles."""
    org, member = _org(), _member()

    calls = {"n": 0}

    async def execute(stmt, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            result = MagicMock()
            result.all = MagicMock(return_value=[(member, org)])
            return result
        raise RuntimeError("relation organization_member_app_roles does not exist")

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()

    claims = await get_user_org_claims(_user(), db)

    assert APP_ROLES_KEY not in claims
    # The org claims resolved before the failure still ride.
    assert claims["org_id"] == str(org.id)


# ---------------------------------------------------------------------------
# The merge — where the private key becomes the public `roles` claim
# ---------------------------------------------------------------------------


def test_merge_pops_the_private_key_so_it_can_never_reach_a_token():
    merged = merge_app_roles_into_claims({"org_id": "x", APP_ROLES_KEY: ["hcm:hr"]})

    assert APP_ROLES_KEY not in merged
    assert merged[APP_ROLES_CLAIM] == ["hcm:hr"]


def test_merge_without_grants_emits_no_roles_key():
    """Absent, not empty: a user with no grants keeps the old token shape."""
    merged = merge_app_roles_into_claims({"org_id": "x"})

    assert APP_ROLES_CLAIM not in merged
    assert merged == {"org_id": "x"}


def test_merge_unions_onto_legacy_oidc_roles_without_removing_any():
    """The OIDC contract: existing clients keep every string they read today."""
    merged = merge_app_roles_into_claims(
        {APP_ROLES_KEY: ["hcm:hr"]},
        existing_roles=["admin", "member"],
    )

    assert merged[APP_ROLES_CLAIM] == ["admin", "member", "hcm:hr"]


def test_merge_preserves_legacy_roles_when_there_are_no_grants():
    merged = merge_app_roles_into_claims({}, existing_roles=["admin"])

    assert merged[APP_ROLES_CLAIM] == ["admin"]


def test_merge_does_not_mutate_its_input():
    original = {"org_id": "x", APP_ROLES_KEY: ["hcm:hr"]}
    merge_app_roles_into_claims(original)

    assert original[APP_ROLES_KEY] == ["hcm:hr"]


# ---------------------------------------------------------------------------
# The mint — end to end into a real token
# ---------------------------------------------------------------------------


def _session_db():
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


async def _mint_session(user, org_claims):
    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value=org_claims),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=_session_db(), user=user, enforce_session_limit=False
        )
    return _decode(access_token)


@pytest.mark.asyncio
async def test_session_token_carries_the_granted_application_role():
    """The CTM Dirección fix, end to end at the mint: `hcm:hr` in `roles`."""
    org = _org("crea")
    claims = await _mint_session(
        _user(),
        {
            "org_id": str(org.id),
            "org_slug": "crea",
            ORG_ROLES_CLAIM: ["admin"],
            APP_ROLES_KEY: ["hcm:hr"],
        },
    )

    assert claims[APP_ROLES_CLAIM] == ["hcm:hr"]
    # And the org role is STILL only under the namespaced key — the string
    # "admin" must not have followed it into `roles`.
    assert claims[ORG_ROLES_CLAIM] == ["admin"]
    assert "admin" not in claims[APP_ROLES_CLAIM]


@pytest.mark.asyncio
async def test_session_token_without_grants_has_no_roles_key():
    """Unchanged shape for everyone who was not granted anything — which is the
    test that keeps this change additive for the whole existing user base."""
    org = _org()
    claims = await _mint_session(
        _user(), {"org_id": str(org.id), ORG_ROLES_CLAIM: ["admin"]}
    )

    assert APP_ROLES_CLAIM not in claims


@pytest.mark.asyncio
async def test_private_transport_key_never_appears_in_a_minted_token():
    org = _org()
    claims = await _mint_session(
        _user(), {"org_id": str(org.id), APP_ROLES_KEY: ["hcm:hr"]}
    )

    assert APP_ROLES_KEY not in claims


@pytest.mark.asyncio
async def test_revoked_grant_is_gone_from_the_refreshed_token():
    """Revocation reaches a live session: the resolver re-runs on refresh, the
    grant no longer matches `revoked_at IS NULL`, and the claim drops."""
    user = _user()
    org = _org()
    session = SimpleNamespace(
        id=uuid4(),
        access_token_jti=None,
        refresh_token_jti="old-refresh-jti",
        last_activity_at=None,
        expires_at=None,
    )

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=session)
    db.execute = AsyncMock(return_value=exec_result)
    db.get = AsyncMock(return_value=user)
    db.commit = AsyncMock()

    with (
        patch.object(
            AuthService,
            "verify_token",
            AsyncMock(return_value={"jti": "old-refresh-jti", "sub": str(user.id), "family": "f1"}),
        ),
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        # Post-revocation resolution: org claims intact, application roles gone.
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={"org_id": str(org.id), ORG_ROLES_CLAIM: ["member"]}),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=AsyncMock())),
    ):
        result = await AuthService.refresh_tokens(db, "old-refresh-token")

    assert result is not None
    claims = _decode(result[0])
    assert claims["org_id"] == str(org.id)
    assert APP_ROLES_CLAIM not in claims


# ---------------------------------------------------------------------------
# SSOT-reuse source pins: no divergent re-implementation of the merge
# ---------------------------------------------------------------------------


def test_both_session_mint_paths_use_the_shared_merge():
    for fn in (AuthService.create_session, AuthService.refresh_tokens):
        source = inspect.getsource(fn)
        assert "merge_app_roles_into_claims" in source, fn.__name__


def test_oidc_router_merges_rather_than_clobbering_the_legacy_roles_claim():
    """The OIDC handler spreads `**org_claims` AFTER `"roles": entitlements[...]`.

    If the resolver ever returned a bare `roles` key, that spread would silently
    replace a claim existing clients have read for years. The router must call
    the shared merge with the legacy list, so the result is a UNION.
    """
    from app.routers.v1 import oauth_provider

    # The OAuth provider is several modules since the 2026-11-19 split.
    source = "".join(
        inspect.getsource(importlib.import_module(f"app.routers.v1.{m}"))
        for m in oauth_provider.MODULES
    )
    assert "merge_app_roles_into_claims" in source
    assert 'existing_roles=entitlements["roles"]' in source


def test_resolver_never_returns_the_public_roles_key_directly():
    """Belt and braces on the clobber hazard, at the source."""
    from app.services import org_claims_service

    source = inspect.getsource(org_claims_service.get_user_org_claims)
    assert "APP_ROLES_KEY" in source
    assert 'claims["roles"]' not in source
    assert 'claims[APP_ROLES_CLAIM]' not in source
