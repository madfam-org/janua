"""
Unit tests for POST /api/v1/checkout/dhanam — the Dhanam federation relay.

The endpoint must relay checkout creation to Dhanam's real federation API
(resolve -> checkout, Bearer FEDERATION_API_TOKEN), return Dhanam's actual
hosted checkout URL, qualify bare plan ids as janua/{tier}, fail closed with
503 when unconfigured, and keep a local CheckoutSession audit row.

Dhanam HTTP is mocked with respx; the contract mirrored here is
dhanam apps/api/src/modules/billing/customer-federation.controller.ts:
- POST /v1/customers/resolve {email, januaSub?, name?} -> {externalId, created}
- POST /v1/customers/{externalId}/checkout {planId, successUrl, cancelUrl,
  metadata} -> {checkoutUrl, sessionId}
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import (
    Base,
    CheckoutSession,
    Organization,
    OrganizationMember,
    User,
    UserStatus,
)
from app.routers.v1.checkout_dhanam import build_catalog_plan_id

# Only the tables these tests touch. Creating the full Base.metadata is
# order-dependent in the full suite: other test modules import optional model
# modules that register PostgreSQL-only column types on the shared Base,
# which breaks metadata-wide create_all on SQLite once they are loaded.
CHECKOUT_TABLES = [
    User.__table__,
    Organization.__table__,
    OrganizationMember.__table__,
    CheckoutSession.__table__,
]

CHECKOUT_URL = "/api/v1/checkout/dhanam"
DHANAM_BASE = "https://dhanam-api.test"
FEDERATION_TOKEN = "test-federation-token"
RESOLVE_URL = f"{DHANAM_BASE}/v1/customers/resolve"


class CheckoutEnv:
    """Bundle of the app client plus seeded identities for a test."""

    def __init__(self, client, session_factory, owner, plain_member, admin_member, org, current):
        self.client = client
        self.session_factory = session_factory
        self.owner = owner
        self.plain_member = plain_member
        self.admin_member = admin_member
        self.org = org
        self._current = current

    def act_as(self, user: User) -> None:
        self._current["user"] = user


@pytest_asyncio.fixture
async def checkout_env():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=CHECKOUT_TABLES)
        )

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    owner = User(
        id=uuid.uuid4(),
        email="owner@janua.test",
        first_name="Olive",
        last_name="Owner",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    plain_member = User(
        id=uuid.uuid4(),
        email="member@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    admin_member = User(
        id=uuid.uuid4(),
        email="admin@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    org = Organization(id=uuid.uuid4(), name="Acme", slug="acme", owner_id=owner.id)

    async with session_factory() as session:
        session.add_all(
            [
                owner,
                plain_member,
                admin_member,
                org,
                OrganizationMember(organization_id=org.id, user_id=plain_member.id, role="member"),
                OrganizationMember(organization_id=org.id, user_id=admin_member.id, role="admin"),
            ]
        )
        await session.commit()

    current = {"user": owner}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    settings.DHANAM_FEDERATION_URL = DHANAM_BASE
    settings.FEDERATION_API_TOKEN = FEDERATION_TOKEN

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield CheckoutEnv(client, session_factory, owner, plain_member, admin_member, org, current)

    app.dependency_overrides.clear()
    settings.DHANAM_FEDERATION_URL = None
    settings.FEDERATION_API_TOKEN = None
    await engine.dispose()


def _checkout_payload(env: CheckoutEnv, plan_id: str = "pro") -> dict:
    return {
        "plan_id": plan_id,
        "organization_id": str(env.org.id),
        "success_url": "https://app.janua.dev/settings/billing?checkout=success",
        "cancel_url": "https://app.janua.dev/settings/billing?checkout=cancelled",
    }


def _mock_dhanam(
    external_id: str = "dhanam-user-1",
    checkout_url: str = "https://checkout.stripe.com/c/pay/cs_test_123",
    session_id: str = "cs_test_123",
    created: bool = True,
):
    resolve_route = respx.post(RESOLVE_URL).mock(
        return_value=httpx.Response(200, json={"externalId": external_id, "created": created})
    )
    checkout_route = respx.post(f"{DHANAM_BASE}/v1/customers/{external_id}/checkout").mock(
        return_value=httpx.Response(
            201, json={"checkoutUrl": checkout_url, "sessionId": session_id}
        )
    )
    return resolve_route, checkout_route


# ---------------------------------------------------------------------------
# Plan id -> Dhanam catalog plan id resolution
# ---------------------------------------------------------------------------


class TestBuildCatalogPlanId:
    @pytest.mark.parametrize(
        "plan_id, expected",
        [
            # Bare tiers come from Janua's own dashboard -> janua product
            ("pro", ("janua", "pro", "janua_pro")),
            ("PRO", ("janua", "pro", "janua_pro")),
            ("essentials", ("janua", "essentials", "janua_essentials")),
            ("madfam", ("janua", "madfam", "janua_madfam")),
            # Billing period suffixes survive so Dhanam resolves the interval
            ("pro_yearly", ("janua", "pro", "janua_pro_yearly")),
            ("pro_monthly", ("janua", "pro", "janua_pro_monthly")),
            ("pro_annual", ("janua", "pro", "janua_pro_annual")),
            # Qualified ids pass through untouched
            ("enclii_pro", ("enclii", "pro", "enclii_pro")),
            ("tezca_essentials_monthly", ("tezca", "essentials", "tezca_essentials_monthly")),
            ("karafiel_pro", ("karafiel", "pro", "karafiel_pro")),
            # Qualified legacy names keep their historical product mapping
            ("enclii_sovereign", ("enclii", "pro", "enclii_pro")),
        ],
    )
    def test_catalog_plan_ids(self, plan_id: str, expected: tuple):
        assert build_catalog_plan_id(plan_id) == expected

    @pytest.mark.parametrize(
        "plan_id",
        # Bare legacy names map to another product's plan ("scale" -> dhanam_pro);
        # Janua's checkout must not sell those, so they resolve to no tier.
        ["scale", "enterprise", "sovereign", "sovereign_yearly", "scale_yearly"],
    )
    def test_bare_legacy_names_for_other_products_have_no_catalog_id(self, plan_id: str):
        _, tier, catalog_id = build_catalog_plan_id(plan_id)
        assert tier is None
        assert catalog_id == ""

    @pytest.mark.parametrize("plan_id", ["free", "community", "trial", ""])
    def test_cancel_tiers_have_no_catalog_id(self, plan_id: str):
        _, tier, catalog_id = build_catalog_plan_id(plan_id)
        assert tier is None
        assert catalog_id == ""


# ---------------------------------------------------------------------------
# Relay happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_relays_resolve_then_checkout_and_returns_dhanam_url(checkout_env: CheckoutEnv):
    resolve_route, checkout_route = _mock_dhanam()

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 200
    body = response.json()
    # Dhanam's ACTUAL hosted checkout URL is passed through, not a synthetic
    # {DHANAM_URL}/checkout/session/{id} path (which dhanam does not serve).
    assert body["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_123"
    assert body["session_id"] == "cs_test_123"
    assert body["customer_id"] == "dhanam-user-1"
    assert body["provider"] == "dhanam"
    assert body["plan_id"] == "janua_pro"
    assert body["product"] == "janua"
    assert body["janua_tier"] == "pro"
    assert body["organization_id"] == str(checkout_env.org.id)

    # Call sequence: resolve first, then checkout for the resolved customer
    assert resolve_route.called and checkout_route.called
    assert respx.calls[0].request.url.path == "/v1/customers/resolve"
    assert respx.calls[1].request.url.path == "/v1/customers/dhanam-user-1/checkout"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_payload_carries_janua_identity_and_bearer_token(
    checkout_env: CheckoutEnv,
):
    resolve_route, _ = _mock_dhanam()

    await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    request = resolve_route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {FEDERATION_TOKEN}"
    assert json.loads(request.content) == {
        "email": "owner@janua.test",
        "januaSub": str(checkout_env.owner.id),
        "name": "Olive Owner",
    }


@pytest.mark.asyncio
@respx.mock
async def test_checkout_payload_sends_qualified_plan_and_org_metadata(
    checkout_env: CheckoutEnv,
):
    _, checkout_route = _mock_dhanam()
    payload = _checkout_payload(checkout_env, plan_id="pro")

    await checkout_env.client.post(CHECKOUT_URL, json=payload)

    request = checkout_route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {FEDERATION_TOKEN}"
    body = json.loads(request.content)
    assert body["planId"] == "janua_pro"
    assert body["successUrl"] == payload["success_url"]
    assert body["cancelUrl"] == payload["cancel_url"]
    # metadata threads the org through the PSP session and back on webhooks:
    # orgId is what Dhanam's webhook processor reads; organization_id is the
    # fallback key Janua's own webhook handler resolves organizations by.
    assert body["metadata"]["orgId"] == str(checkout_env.org.id)
    assert body["metadata"]["organization_id"] == str(checkout_env.org.id)
    assert body["metadata"]["organization_slug"] == "acme"
    assert body["metadata"]["product"] == "janua"
    assert body["metadata"]["janua_tier"] == "pro"


@pytest.mark.asyncio
@respx.mock
async def test_prefixed_plan_id_passes_through_for_other_products(checkout_env: CheckoutEnv):
    _, checkout_route = _mock_dhanam()

    response = await checkout_env.client.post(
        CHECKOUT_URL, json=_checkout_payload(checkout_env, plan_id="enclii_pro")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] == "enclii_pro"
    assert body["product"] == "enclii"
    sent = json.loads(checkout_route.calls[0].request.content)
    assert sent["planId"] == "enclii_pro"
    assert sent["metadata"]["product"] == "enclii"


@pytest.mark.asyncio
@respx.mock
async def test_yearly_suffix_is_preserved_on_the_catalog_plan_id(checkout_env: CheckoutEnv):
    _, checkout_route = _mock_dhanam()

    response = await checkout_env.client.post(
        CHECKOUT_URL, json=_checkout_payload(checkout_env, plan_id="pro_yearly")
    )

    assert response.status_code == 200
    sent = json.loads(checkout_route.calls[0].request.content)
    assert sent["planId"] == "janua_pro_yearly"


@pytest.mark.asyncio
@respx.mock
async def test_admin_member_can_initiate_checkout(checkout_env: CheckoutEnv):
    _mock_dhanam()
    checkout_env.act_as(checkout_env.admin_member)

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_audit_row_records_dhanam_session_reference(checkout_env: CheckoutEnv):
    _mock_dhanam()

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))
    assert response.status_code == 200

    async with checkout_env.session_factory() as session:
        result = await session.execute(
            select(CheckoutSession).where(CheckoutSession.session_id == "cs_test_123")
        )
        row = result.scalar_one()

    assert row.organization_id == checkout_env.org.id
    assert row.user_id == checkout_env.owner.id
    assert row.price_id == "janua_pro"
    assert row.provider == "dhanam"
    assert row.status == "pending"
    stored = json.loads(row.session_metadata)
    assert stored["dhanam_customer_id"] == "dhanam-user-1"
    assert stored["dhanam_session_id"] == "cs_test_123"
    assert stored["requested_plan_id"] == "pro"


@pytest.mark.asyncio
@respx.mock
async def test_empty_dhanam_session_id_gets_local_audit_reference(checkout_env: CheckoutEnv):
    _mock_dhanam(session_id="")

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("checkout_")
    async with checkout_env.session_factory() as session:
        result = await session.execute(
            select(CheckoutSession).where(CheckoutSession.session_id == body["session_id"])
        )
        row = result.scalar_one()
    assert json.loads(row.session_metadata)["dhanam_session_id"] == ""


# ---------------------------------------------------------------------------
# Validation and permission errors (no Dhanam traffic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_invalid_plan_id_returns_400_without_calling_dhanam(checkout_env: CheckoutEnv):
    response = await checkout_env.client.post(
        CHECKOUT_URL, json=_checkout_payload(checkout_env, plan_id="free")
    )

    assert response.status_code == 400
    assert not respx.calls


@pytest.mark.asyncio
@respx.mock
async def test_dashboard_scale_plan_returns_400_and_never_sells_dhanam_pro(checkout_env: CheckoutEnv):
    response = await checkout_env.client.post(
        CHECKOUT_URL, json=_checkout_payload(checkout_env, plan_id="scale")
    )

    assert response.status_code == 400
    assert not respx.calls


@pytest.mark.asyncio
@respx.mock
async def test_unknown_organization_returns_404(checkout_env: CheckoutEnv):
    payload = _checkout_payload(checkout_env)
    payload["organization_id"] = str(uuid.uuid4())

    response = await checkout_env.client.post(CHECKOUT_URL, json=payload)

    assert response.status_code == 404
    assert not respx.calls


@pytest.mark.asyncio
@respx.mock
async def test_plain_member_gets_403_without_calling_dhanam(checkout_env: CheckoutEnv):
    checkout_env.act_as(checkout_env.plain_member)

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 403
    assert not respx.calls


# ---------------------------------------------------------------------------
# Fail-closed configuration gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("missing", ["url", "token", "both"])
async def test_missing_federation_config_returns_503(checkout_env: CheckoutEnv, missing: str):
    if missing in ("url", "both"):
        settings.DHANAM_FEDERATION_URL = None
    if missing in ("token", "both"):
        settings.FEDERATION_API_TOKEN = None

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 503
    assert not respx.calls


# ---------------------------------------------------------------------------
# Dhanam-side failures map to clear client errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resolve_conflict_maps_to_409(checkout_env: CheckoutEnv):
    respx.post(RESOLVE_URL).mock(
        return_value=httpx.Response(
            409, json={"message": "Email is already linked to a different Janua identity"}
        )
    )

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 409


@pytest.mark.asyncio
@respx.mock
async def test_resolve_provisioning_disabled_maps_to_503(checkout_env: CheckoutEnv):
    respx.post(RESOLVE_URL).mock(
        return_value=httpx.Response(403, json={"message": "provisioning is disabled"})
    )

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 503


@pytest.mark.asyncio
@respx.mock
async def test_dhanam_unreachable_maps_to_503(checkout_env: CheckoutEnv):
    respx.post(RESOLVE_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 503


@pytest.mark.asyncio
@respx.mock
async def test_checkout_call_failure_maps_to_502(checkout_env: CheckoutEnv):
    respx.post(RESOLVE_URL).mock(
        return_value=httpx.Response(200, json={"externalId": "dhanam-user-1", "created": False})
    )
    respx.post(f"{DHANAM_BASE}/v1/customers/dhanam-user-1/checkout").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 502


@pytest.mark.asyncio
@respx.mock
async def test_missing_checkout_url_maps_to_502(checkout_env: CheckoutEnv):
    _mock_dhanam(checkout_url="")

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 502


@pytest.mark.asyncio
@respx.mock
async def test_resolve_without_external_id_maps_to_502(checkout_env: CheckoutEnv):
    respx.post(RESOLVE_URL).mock(return_value=httpx.Response(200, json={"created": True}))

    response = await checkout_env.client.post(CHECKOUT_URL, json=_checkout_payload(checkout_env))

    assert response.status_code == 502
