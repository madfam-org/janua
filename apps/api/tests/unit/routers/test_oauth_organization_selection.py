"""An explicit OAuth organization is bound to the grant, never the identity pool."""

import json
import re
from contextlib import ExitStack
from html import unescape
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth.authorize_resume import authorize_query
from app.models import Organization, OrganizationMember, User, UserEntitlement
from app.models.app_role import OrganizationMemberAppRole
from app.routers.v1 import auth
from app.routers.v1 import oauth_provider as op
from app.services.org_claims_service import InvalidOrganizationSelection, get_user_org_claims

pytestmark = pytest.mark.asyncio
CALLBACK = "https://rp.example.test/callback"


@pytest.fixture
def estate():
    user = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        email="fixture@example.test",
        is_admin=False,
        email_verified=True,
        created_at=None,
    )
    orgs = [
        SimpleNamespace(
            id=uuid4(),
            slug=f"org-{index}",
            subscription_tier=f"tier-{index}",
            product_tiers={f"product{index}": "pro"},
        )
        for index in range(3)
    ]
    members = [
        SimpleNamespace(
            id=uuid4(),
            organization_id=org.id,
            status="active",
            role="member" if index == 1 else "owner",
        )
        for index, org in enumerate(orgs)
    ]
    grants = {
        members[0].id: [SimpleNamespace(app="foreign", role="admin")],
        members[1].id: [SimpleNamespace(app="tulana", role="operator")],
    }
    db = AsyncMock()

    async def execute(query):
        entity = query.column_descriptions[0]["entity"]
        result = MagicMock()
        if entity is User:
            result.scalar_one_or_none.return_value = user
        elif entity is OrganizationMember:
            live = [member for member in members if member.status == "active"]
            result.all.return_value = [
                (member, org) for member, org in zip(members, orgs) if member.status == "active"
            ]
            result.scalars.return_value.all.return_value = live
        elif entity is Organization:
            params = query.compile().params
            target = str(next(iter(params.values())))
            result.scalar_one_or_none.return_value = next(
                (org for org in orgs if str(org.id) == target), None
            )
        elif entity is OrganizationMemberAppRole:
            member_id = next(iter(query.compile().params.values()))
            result.scalars.return_value.all.return_value = grants.get(member_id, [])
        elif entity is UserEntitlement:
            result.scalars.return_value.all.return_value = []
        else:
            raise AssertionError(f"Unexpected ORM read: {entity}")
        return result

    db.execute.side_effect = execute
    client = SimpleNamespace(
        client_id="fixture-rp",
        organization_id=None,
        is_active=True,
        is_confidential=True,
        name="fixture-rp",
        allowed_scopes=["openid", "email"],
        redirect_uris=[CALLBACK],
        audience=None,
        last_used_at=None,
        verify_secret=lambda secret: True,
        grant_types=None,
    )
    return SimpleNamespace(
        user=user,
        orgs=orgs,
        members=members,
        grants=grants,
        db=db,
        client=client,
        selected=str(orgs[1].id),
    )


def grant_sources(stack):
    access = stack.enter_context(
        patch.object(
            op.jwt_manager, "create_access_token", return_value=("access-fixture", "jti", None)
        )
    )
    refresh = stack.enter_context(
        patch.object(
            op.jwt_manager,
            "create_refresh_token",
            return_value=("refresh-fixture", "jti", "family", None),
        )
    )
    stack.enter_context(patch.object(op, "service_principal_claims", return_value={}))
    stack.enter_context(patch.object(op, "_generate_id_token", return_value="id-fixture"))
    return access, refresh


async def exchange(estate, organization_id):
    data = {
        "client_id": estate.client.client_id,
        "user_id": str(estate.user.id),
        "redirect_uri": CALLBACK,
        "scope": "openid email",
        "organization_id": organization_id,
    }
    with ExitStack() as stack:
        stack.enter_context(patch.object(op, "_get_auth_code", AsyncMock(return_value=data)))
        stack.enter_context(patch.object(op, "_delete_auth_code", AsyncMock(return_value=True)))
        access, refresh = grant_sources(stack)
        await op._handle_authorization_code_grant(
            code="fixture",
            redirect_uri=CALLBACK,
            client=estate.client,
            code_verifier=None,
            db=estate.db,
            redis=AsyncMock(),
        )
        return (
            access.call_args.kwargs["additional_claims"],
            refresh.call_args.kwargs["additional_claims"],
        )


async def rotate(estate, selection):
    payload = {
        "sub": str(estate.user.id),
        "client_id": estate.client.client_id,
        "scope": "openid email",
        **selection,
    }
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(op, "_verify_oauth_token", AsyncMock(return_value=payload))
        )
        stack.enter_context(
            patch.object(op.token_revocation, "is_revoked", AsyncMock(return_value=False))
        )
        access, refresh = grant_sources(stack)
        await op._handle_refresh_token_grant(
            refresh_token="fixture", client=estate.client, db=estate.db, redis=AsyncMock()
        )
        return (
            access.call_args.kwargs["additional_claims"],
            refresh.call_args.kwargs["additional_claims"],
        )


async def authorize(estate, *, user=True, consent=True, prompt=None, selection=None):
    store, redis = AsyncMock(), AsyncMock()
    with (
        patch.object(
            op,
            "get_user_from_cookie_or_header",
            AsyncMock(return_value=estate.user if user else None),
        ),
        patch.object(op, "_get_oauth_client", AsyncMock(return_value=estate.client)),
        patch.object(op.ConsentService, "has_consent", AsyncMock(return_value=consent)),
        patch.object(op, "_store_auth_code", store),
        patch.object(op, "settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
    ):
        response = await op.authorize_get(
            request=MagicMock(),
            response_type="code",
            client_id=estate.client.client_id,
            redirect_uri=CALLBACK,
            scope="openid email",
            state="fixture-state",
            nonce=None,
            code_challenge="fixture-challenge",
            code_challenge_method="S256",
            prompt=prompt,
            login_method=None,
            resource=None,
            organization_id=selection,
            db=estate.db,
            redis=redis,
        )
    return response, store, redis


async def test_three_memberships_explicit_selection_overrides_pool_without_changing_it(estate):
    pool = estate.user.tenant_id
    claims, refresh = await exchange(estate, estate.selected)
    assert claims["org_id"] == claims["tenant_id"] == estate.selected
    assert claims["roles"] == ["member", "tulana:operator"]
    assert claims["tier"] == "tier-1"
    assert claims["product1_tier"] == "pro"
    assert claims["madfam_entitled_products"] == ["product1:pro"]
    assert "foreign:admin" not in claims["roles"] and "product0_tier" not in claims
    assert refresh["organization_id"] == estate.selected
    assert estate.user.tenant_id == pool


async def test_signed_refresh_retains_selection_and_reloads_live_grants(estate):
    claims, refresh = await rotate(estate, {"organization_id": estate.selected})
    assert claims["org_id"] == refresh["organization_id"] == estate.selected
    assert claims["roles"] == ["member", "tulana:operator"]
    assert claims["madfam_entitled_products"] == ["product1:pro"]
    estate.grants[estate.members[1].id] = []
    claims, _ = await rotate(estate, {"organization_id": estate.selected})
    assert "tulana:operator" not in claims["roles"]
    assert claims["org_id"] == estate.selected


@pytest.mark.parametrize(
    "seam", [exchange, lambda estate, selected: rotate(estate, {"organization_id": selected})]
)
@pytest.mark.parametrize("invalid", ["foreign", "removed", "client", "malformed"])
async def test_invalid_selection_never_falls_back_at_exchange_or_refresh(estate, seam, invalid):
    selected = estate.selected
    if invalid == "foreign":
        selected = str(uuid4())
    elif invalid == "removed":
        estate.members[1].status = "removed"
    elif invalid == "client":
        estate.client.organization_id = estate.orgs[0].id
    else:
        selected = "not-a-uuid"
    with pytest.raises(HTTPException, match="invalid_grant"):
        await seam(estate, selected)


async def test_no_selection_keeps_multi_org_ambiguity(estate):
    claims, refresh = await rotate(estate, {})
    assert "org_id" not in claims and "tulana:operator" not in claims["roles"]
    assert "organization_id" not in refresh


async def test_authorize_code_binds_validated_selection(estate):
    response, store, _ = await authorize(estate, selection=estate.selected)
    assert "code" in parse_qs(urlparse(response.headers["location"]).query)
    assert store.await_args.args[1]["organization_id"] == estate.selected


async def test_nonmember_authorize_returns_validated_error_with_state_and_no_code(estate):
    response, store, _ = await authorize(estate, selection=str(uuid4()))
    assert response.headers["location"].startswith(CALLBACK)
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["error"] == ["access_denied"] and params["state"] == ["fixture-state"]
    store.assert_not_awaited()


async def test_login_and_mfa_resume_keep_the_stored_selection(estate):
    _, _, redis = await authorize(estate, user=False, selection=estate.selected)
    stored = json.loads(redis.strict_set.await_args.args[1])
    assert authorize_query(stored)["organization_id"] == estate.selected
    redis.get.return_value = json.dumps(stored)
    target = await auth._resolve_oauth_redirect_target(
        auth_request_id="fixture",
        client_id=estate.client.client_id,
        next_url="/",
        redis=redis,
        db=estate.db,
    )
    assert parse_qs(urlparse(target).query)["organization_id"] == [estate.selected]


async def test_consent_record_and_approval_keep_selection_and_recheck_membership(estate):
    _, _, redis = await authorize(estate, consent=False, selection=estate.selected)
    stored = json.loads(redis.strict_set.await_args.args[1])
    assert stored["organization_id"] == estate.selected
    redis.strict_get.return_value = json.dumps(stored)
    redis.strict_delete.return_value = 1
    store = AsyncMock()
    with (
        patch.object(op, "get_user_from_cookie_or_header", AsyncMock(return_value=estate.user)),
        patch.object(op, "_validate_csrf_token", AsyncMock(return_value=True)),
        patch.object(op, "_get_oauth_client", AsyncMock(return_value=estate.client)),
        patch.object(op.ConsentService, "grant_consent", AsyncMock()),
        patch.object(op, "_store_auth_code", store),
    ):
        await op.handle_consent(
            request=MagicMock(),
            auth_request_id="fixture",
            csrf_token="fixture",
            action="allow",
            db=estate.db,
            redis=redis,
        )
        assert store.await_args.args[1]["organization_id"] == estate.selected
        estate.members[1].status = "removed"
        store.reset_mock()
        denied = await op.handle_consent(
            request=MagicMock(),
            auth_request_id="fixture",
            csrf_token="fixture",
            action="allow",
            db=estate.db,
            redis=redis,
        )
        assert parse_qs(urlparse(denied.headers["location"]).query)["error"] == ["access_denied"]
        store.assert_not_awaited()


async def test_resolver_explicit_read_failure_refuses_without_fallback(estate):
    estate.db.execute.side_effect = RuntimeError("synthetic unavailable")
    with pytest.raises(InvalidOrganizationSelection):
        await get_user_org_claims(estate.user, estate.db, organization_id=estate.selected)


async def test_account_chooser_retains_org_and_cancel_is_a_nonmutating_validated_callback(estate):
    with (
        patch.object(op, "read_sessions_cookie", return_value=["fixture-sid"]),
        patch.object(
            op, "_resolve_held_accounts", AsyncMock(return_value=[("fixture-sid", estate.user)])
        ),
    ):
        response, store, _ = await authorize(
            estate, prompt="select_account", selection=estate.selected
        )
    text = response.body.decode()
    next_url = unescape(re.search(r'name="next" value="([^"]+)"', text).group(1))
    assert parse_qs(urlparse(next_url).query)["organization_id"] == [estate.selected]
    cancel = unescape(re.search(r'href="([^"]+)"[^>]*>Cancel and return', text).group(1))
    assert cancel.startswith(CALLBACK)
    assert parse_qs(urlparse(cancel).query)["state"] == ["fixture-state"]
    assert not response.headers.getlist("set-cookie")
    store.assert_not_awaited()


async def test_refresh_form_cannot_override_the_signed_organization(estate):
    app = FastAPI()
    app.include_router(op.router, prefix="/api/v1")
    app.dependency_overrides[op.get_db] = lambda: estate.db
    app.dependency_overrides[op.get_redis] = lambda: AsyncMock()
    payload = {
        "sub": str(estate.user.id),
        "client_id": estate.client.client_id,
        "scope": "openid email",
        "organization_id": estate.selected,
    }
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(op, "_get_oauth_client", AsyncMock(return_value=estate.client))
        )
        stack.enter_context(
            patch.object(op, "_verify_oauth_token", AsyncMock(return_value=payload))
        )
        stack.enter_context(
            patch.object(op.token_revocation, "is_revoked", AsyncMock(return_value=False))
        )
        access, _ = grant_sources(stack)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://issuer.example.test"
        ) as http:
            response = await http.post(
                "/api/v1/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": "fixture",
                    "client_id": estate.client.client_id,
                    "client_secret": "fixture",
                    "organization_id": str(estate.orgs[0].id),
                },
            )
        assert response.status_code == 200
        assert access.call_args.kwargs["additional_claims"]["org_id"] == estate.selected


async def test_client_bound_to_selected_org_is_supported(estate):
    estate.client.organization_id = estate.orgs[1].id
    claims, _ = await exchange(estate, estate.selected)
    assert claims["org_id"] == estate.selected


async def test_post_authorize_binds_the_validated_org_after_csrf(estate):
    store = AsyncMock()
    with (
        patch.object(op, "_validate_csrf_token", AsyncMock(return_value=True)),
        patch.object(op, "_get_oauth_client", AsyncMock(return_value=estate.client)),
        patch.object(op, "_store_auth_code", store),
        patch.object(op, "settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
    ):
        response = await op.authorize_post(
            request=MagicMock(),
            response_type="code",
            client_id=estate.client.client_id,
            redirect_uri=CALLBACK,
            scope="openid email",
            state="fixture-state",
            nonce=None,
            code_challenge="fixture-challenge",
            code_challenge_method="S256",
            csrf_token="fixture",
            resource=None,
            organization_id=estate.selected,
            db=estate.db,
            redis=AsyncMock(),
            current_user=estate.user,
        )
    assert "code" in parse_qs(urlparse(response.headers["location"]).query)
    assert store.await_args.args[1]["organization_id"] == estate.selected


@pytest.mark.parametrize("posted_selection", [None, "", "   "])
async def test_http_post_preserves_absent_but_rejects_present_empty_selection(
    estate, posted_selection
):
    app = FastAPI()
    app.include_router(op.router, prefix="/api/v1")
    app.dependency_overrides[op.get_db] = lambda: estate.db
    app.dependency_overrides[op.get_redis] = lambda: AsyncMock()
    app.dependency_overrides[op.get_current_user] = lambda: estate.user
    data = {
        "response_type": "code",
        "client_id": estate.client.client_id,
        "redirect_uri": CALLBACK,
        "scope": "openid email",
        "state": "fixture-state",
        "code_challenge": "fixture-challenge",
        "code_challenge_method": "S256",
        "csrf_token": "fixture",
    }
    if posted_selection is not None:
        data["organization_id"] = posted_selection
    store = AsyncMock()
    with (
        patch.object(op, "_get_oauth_client", AsyncMock(return_value=estate.client)),
        patch.object(op, "_validate_csrf_token", AsyncMock(return_value=True)),
        patch.object(op, "_store_auth_code", store),
        patch.object(op, "settings", MagicMock(REQUIRE_EMAIL_VERIFICATION=False)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://issuer.example.test"
        ) as http:
            response = await http.post("/api/v1/oauth/authorize", data=data)
    assert response.status_code == 302
    assert response.headers["location"].startswith(CALLBACK)
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["state"] == ["fixture-state"]
    if posted_selection is None:
        assert "code" in params and "organization_id" not in store.await_args.args[1]
    else:
        assert params["error"] == ["access_denied"] and "code" not in params
        store.assert_not_awaited()


async def test_organization_client_mismatch_stops_before_login_storage(estate):
    estate.client.organization_id = estate.orgs[0].id
    response, store, redis = await authorize(estate, user=False, selection=estate.selected)
    assert parse_qs(urlparse(response.headers["location"]).query)["error"] == ["invalid_request"]
    store.assert_not_awaited()
    redis.strict_set.assert_not_awaited()


async def test_explicit_selection_is_refused_for_protected_resource_flow(estate):
    with pytest.raises(HTTPException, match="not supported for protected resources"):
        await op.authorize_get(
            request=MagicMock(),
            response_type="code",
            client_id="https://rp.example.test/client.json",
            redirect_uri=CALLBACK,
            resource=None,
            organization_id=estate.selected,
            db=estate.db,
            redis=AsyncMock(),
        )
