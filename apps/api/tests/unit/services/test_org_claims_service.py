"""Organization claims are one resolver, shared by every token-minting seam.

Until this change `org_id` reached ONLY OIDC tokens: the resolver lived inline
in `routers/v1/oauth_provider.py`, structurally unreachable from
`AuthService.create_session`. A magic-link session token therefore carried no
`org_id`, and symbiosis-hcm — which 403s any token without it — refused every
CTM team member who arrived through the MAP's «Mi espacio (RH)» link.

These tests pin the two halves of the fix, and the SECOND half is the one that
matters most:

  1. Session tokens (magic link, password login) now carry `org_id`,
     `tenant_id`, `org_slug` and `orgs`, resolved through the SAME SSOT the
     OIDC path uses — no second copy of the resolver.

  2. The role claim they carry is the NAMESPACED `madfam_org_roles`, NEVER a
     bare `roles`. Organization roles are owner/admin/member — authority over
     the ACCOUNT — and symbiosis-hcm's `HR_ROLES` set contains the literal
     string `"admin"`. Sealing `org_id` while stamping org roles as `roles`
     would have promoted every janua org admin to HR admin over payroll and
     labour files: it converts today's honest 403 into a leak. The namespace
     is not cosmetic and there is a test below that fails if someone
     "simplifies" it back.

Plus the invariants that keep the claim honest: ambiguity emits no `org_id`
(consumers must not guess a tenant), a revoked membership stops contributing,
and resolution failure never blocks a login.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.models import UserStatus
from app.services.auth_service import AuthService
from app.services.org_claims_service import (
    ORG_ROLES_CLAIM,
    get_user_org_claims,
    get_user_org_claims_safe,
)


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


def _user(tenant_id=None):
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        tenant_id=tenant_id,
        is_admin=False,
        is_active=True,
        status=UserStatus.ACTIVE,
        is_service_account=False,
    )


def _org(slug="crea"):
    return SimpleNamespace(id=uuid4(), slug=slug)


def _member(role="member"):
    return SimpleNamespace(role=role, status="active")


def _db_returning(rows):
    """An AsyncSession double whose single execute() yields `rows`."""
    db = AsyncMock()
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_org_membership_emits_unambiguous_org_id():
    org = _org("crea")
    db = _db_returning([(_member("member"), org)])

    claims = await get_user_org_claims(_user(), db)

    assert claims["org_id"] == str(org.id)
    assert claims["tenant_id"] == str(org.id)
    assert claims["org_slug"] == "crea"
    assert claims["orgs"] == [{"id": str(org.id), "slug": "crea", "role": "member"}]


@pytest.mark.asyncio
async def test_single_org_membership_emits_namespaced_role_claim():
    org = _org()
    db = _db_returning([(_member("admin"), org)])

    claims = await get_user_org_claims(_user(), db)

    assert claims[ORG_ROLES_CLAIM] == ["admin"]


@pytest.mark.asyncio
async def test_org_roles_never_ride_under_the_bare_roles_key():
    """THE security test of this change.

    symbiosis-hcm reads `roles` and its HR_ROLES set contains "admin". If org
    roles ever reach a consumer under the bare `roles` key alongside a working
    `org_id`, every janua org-account admin silently becomes an HR admin over
    payroll. The org-role claim must be namespaced, always.
    """
    org = _org()
    db = _db_returning([(_member("admin"), org)])

    claims = await get_user_org_claims(_user(), db)

    assert "roles" not in claims
    assert ORG_ROLES_CLAIM == "madfam_org_roles"
    assert claims[ORG_ROLES_CLAIM] == ["admin"]


@pytest.mark.asyncio
async def test_multi_org_without_tenant_pin_emits_no_org_id():
    """Ambiguity is silence. A consumer must never guess which tenant."""
    org_a, org_b = _org("a"), _org("b")
    db = _db_returning([(_member("admin"), org_a), (_member("member"), org_b)])

    claims = await get_user_org_claims(_user(tenant_id=None), db)

    assert "org_id" not in claims
    assert "tenant_id" not in claims
    assert "org_slug" not in claims
    # …and no role claim either: a role means nothing without the org it is in.
    assert ORG_ROLES_CLAIM not in claims
    # The full membership list still rides, so a consumer that knows its own
    # tenant can pick correctly.
    assert {o["slug"] for o in claims["orgs"]} == {"a", "b"}


@pytest.mark.asyncio
async def test_multi_org_with_tenant_pin_resolves_that_org_and_its_role():
    org_a, org_b = _org("a"), _org("b")
    db = _db_returning([(_member("admin"), org_a), (_member("member"), org_b)])

    claims = await get_user_org_claims(_user(tenant_id=org_b.id), db)

    assert claims["org_id"] == str(org_b.id)
    assert claims["org_slug"] == "b"
    # The role of the RESOLVED org, not of the first row.
    assert claims[ORG_ROLES_CLAIM] == ["member"]


@pytest.mark.asyncio
async def test_no_active_membership_emits_nothing():
    """A revoked/pending membership contributes nothing.

    The resolver's query filters `status == "active"`, so a membership that has
    been revoked stops feeding the claim on the very next mint — which is what
    makes revocation reach a live session at refresh time.
    """
    claims = await get_user_org_claims(_user(), _db_returning([]))
    assert claims == {}


@pytest.mark.asyncio
async def test_active_status_filter_is_in_the_query():
    """Pin the filter itself: a removed member must not keep tenant access."""
    db = _db_returning([])
    await get_user_org_claims(_user(), db)

    compiled = str(db.execute.await_args.args[0]).lower()
    assert "status" in compiled


@pytest.mark.asyncio
async def test_resolution_failure_fails_closed_to_no_claims():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))
    db.rollback = AsyncMock()

    assert await get_user_org_claims(_user(), db) == {}


@pytest.mark.asyncio
async def test_safe_wrapper_swallows_anything_unexpected():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("boom"))
    db.rollback = AsyncMock(side_effect=RuntimeError("rollback also failed"))

    assert await get_user_org_claims_safe(_user(), db) == {}


# ---------------------------------------------------------------------------
# create_session threads the claims into the minted token
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
async def test_magic_link_session_token_now_carries_org_id():
    """The CTM «Mi espacio (RH)» fix, end to end at the mint.

    Before this change the assertion below was the bug report: symbiosis-hcm
    403'd because this key was simply absent.
    """
    org = _org("crea")
    claims = await _mint_session(
        _user(),
        {
            "orgs": [{"id": str(org.id), "slug": "crea", "role": "admin"}],
            "org_id": str(org.id),
            "tenant_id": str(org.id),
            "org_slug": "crea",
            ORG_ROLES_CLAIM: ["admin"],
        },
    )

    assert claims["org_id"] == str(org.id)
    assert claims["org_slug"] == "crea"
    assert claims[ORG_ROLES_CLAIM] == ["admin"]
    # Still carries what it carried before — this change is additive.
    assert claims["madfam_entitled_products"] == []
    assert claims["sub"] and claims["type"] == "access"


@pytest.mark.asyncio
async def test_session_token_has_no_bare_roles_claim():
    """A session token must not hand an org role to a consumer reading `roles`."""
    org = _org()
    claims = await _mint_session(
        _user(),
        {"org_id": str(org.id), "tenant_id": str(org.id), ORG_ROLES_CLAIM: ["admin"]},
    )

    assert "roles" not in claims


@pytest.mark.asyncio
async def test_session_token_without_membership_is_shaped_exactly_as_before():
    """No membership ⇒ no org keys at all: unchanged behaviour for the staff pool."""
    claims = await _mint_session(_user(), {})

    for key in ("org_id", "org_slug", "orgs", ORG_ROLES_CLAIM):
        assert key not in claims


@pytest.mark.asyncio
async def test_org_claims_cannot_spoof_reserved_identity_claims():
    """`additional_claims` merges first and reserved keys win — a hostile or
    buggy org-claims dict cannot rewrite sub/tid/jti/iss/type."""
    claims = await _mint_session(
        _user(),
        {"sub": "attacker", "tid": "attacker-tenant", "iss": "evil", "type": "refresh"},
    )

    assert claims["sub"] != "attacker"
    assert claims["tid"] != "attacker-tenant"
    assert claims["iss"] != "evil"
    assert claims["type"] == "access"


@pytest.mark.asyncio
async def test_org_claim_failure_never_blocks_login():
    """A resolver blow-up degrades to a token with no org claims — not a 500."""
    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=_session_db(), user=_user(), enforce_session_limit=False
        )

    assert "org_id" not in _decode(access_token)


# ---------------------------------------------------------------------------
# refresh re-resolves — this is what makes revocation reach a live session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_restamps_org_claims_from_current_membership():
    user = _user()
    org = _org("crea")
    session = SimpleNamespace(
        id=uuid4(),
        access_token_jti=None,
        refresh_token_jti="old-refresh-jti",
        user_id=user.id,
        revoked=False,
        revoked_at=None,
        is_active=True,
        last_activity_at=None,
        expires_at=datetime.utcnow() + timedelta(days=7),
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
            AsyncMock(return_value={"jti": "old-refresh-jti", "sub": str(user.id), "family": "f1", "type": "refresh", "exp": (datetime.utcnow() + timedelta(days=7)).timestamp()}),
        ),
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={"org_id": str(org.id), ORG_ROLES_CLAIM: ["member"]}),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=None), set=AsyncMock(return_value=True)))),
    ):
        result = await AuthService.refresh_tokens(db, "old-refresh-token")

    assert result is not None
    claims = _decode(result[0])
    assert claims["org_id"] == str(org.id)
    assert claims[ORG_ROLES_CLAIM] == ["member"]


@pytest.mark.asyncio
async def test_revoked_membership_drops_off_the_refreshed_token():
    """Membership revoked between mint and refresh ⇒ the refreshed token has no
    org_id, so the org-scoped resource server stops authorizing the caller."""
    user = _user()
    session = SimpleNamespace(
        id=uuid4(),
        access_token_jti=None,
        refresh_token_jti="old-refresh-jti",
        user_id=user.id,
        revoked=False,
        revoked_at=None,
        is_active=True,
        last_activity_at=None,
        expires_at=datetime.utcnow() + timedelta(days=7),
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
            AsyncMock(return_value={"jti": "old-refresh-jti", "sub": str(user.id), "family": "f1", "type": "refresh", "exp": (datetime.utcnow() + timedelta(days=7)).timestamp()}),
        ),
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        # The resolver's `status == "active"` filter now matches nothing.
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={}),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=None), set=AsyncMock(return_value=True)))),
    ):
        result = await AuthService.refresh_tokens(db, "old-refresh-token")

    assert result is not None
    assert "org_id" not in _decode(result[0])


# ---------------------------------------------------------------------------
# SSOT-reuse source pins: no divergent re-implementation
# ---------------------------------------------------------------------------


def test_session_mint_paths_reuse_the_shared_org_claims_ssot():
    for fn in (AuthService.create_session, AuthService.refresh_tokens):
        source = inspect.getsource(fn)
        assert "get_user_org_claims_safe" in source, fn.__name__


def test_oidc_router_imports_the_shared_resolver_rather_than_redefining_it():
    """The OIDC path must address the same function object, not a copy.

    Two hand-maintained copies of an authorization-claim resolver drift, and a
    drifted claim fails either closed (someone stops working) or open (someone
    gains a tenant). The historical private name is kept as an alias so the
    router's own tests keep addressing it.
    """
    from app.routers.v1 import oauth_provider

    assert oauth_provider._get_user_org_claims is get_user_org_claims
