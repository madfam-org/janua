"""Product tier claims on client_credentials tokens.

Real models on an in-memory database and the real token endpoint; only Redis
is stubbed. The rule under test (`oauth_provider._get_client_credentials_claims`):

- a client registered by a platform admin gets ``<product>_tier: "madfam"``
  for every product it holds a namespaced scope for, and its organization's
  ``product_tiers`` win over that;
- any other client gets ``<product>_tier`` only from its organization's
  ``product_tiers``; with no entitlement for a product there is no claim.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, OAuthClient, Organization, User, UserStatus
from app.routers.v1.oauth_provider import _get_client_credentials_claims

pytestmark = pytest.mark.asyncio

TOKEN_URL = "/api/v1/oauth/token"
AUDIENCE = "tier-fixture-api"
SECRET = "jns_fixture_placeholder_not_a_secret"
SECRET_HASH = bcrypt.hashpw(SECRET.encode(), bcrypt.gensalt(rounds=4)).decode()


def _user(email: str, *, is_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=is_admin,
        is_active=True,
    )


class Env:
    def __init__(self, http, factory):
        self.http = http
        self.factory = factory

    async def add_client(self, *, created_by: User, organization=None, scopes) -> OAuthClient:
        row = OAuthClient(
            id=uuid.uuid4(),
            organization_id=organization.id if organization is not None else None,
            created_by=created_by.id,
            client_id="jnc_tier_" + uuid.uuid4().hex[:12],
            client_secret_hash=SECRET_HASH,
            client_secret_prefix="jns_fixt",
            name="tier fixture client",
            redirect_uris=[],
            audience=AUDIENCE,
            allowed_scopes=list(scopes),
            grant_types=["client_credentials"],
            is_active=True,
            is_confidential=True,
        )
        async with self.factory.begin() as db:
            db.add(row)
        return row

    async def mint(self, client: OAuthClient, scope: str) -> dict:
        """Claims of a token minted through the real endpoint, verified."""
        response = await self.http.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client.client_id,
                "client_secret": SECRET,
                "scope": scope,
            },
        )
        assert response.status_code == 200, response.text
        claims = jwt_manager.verify_token(response.json()["access_token"], audience=AUDIENCE)
        assert claims is not None
        return claims

    async def claims(self, client: OAuthClient, scope: str) -> dict:
        """The claims builder on its own, against the same database."""
        async with self.factory() as db:
            return await _get_client_credentials_claims(client, scope, db)


@pytest_asyncio.fixture
async def env(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(jwt_manager, "private_key", key)
    monkeypatch.setattr(jwt_manager, "public_key", key.public_key())

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    redis = AsyncMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True

    platform_admin = _user("platform-admin@janua.test", is_admin=True)
    org_admin = _user("org-admin@janua.test")
    entitled = Organization(
        id=uuid.uuid4(),
        name="Entitled Org",
        slug="entitled-org",
        subscription_tier="pro",
        product_tiers={"yantra4d": "pro"},
    )
    plain = Organization(id=uuid.uuid4(), name="Plain Org", slug="plain-org", product_tiers={})
    async with factory.begin() as db:
        db.add_all([platform_admin, org_admin])
        await db.flush()
        db.add_all([entitled, plain])

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            handle = Env(http, factory)
            handle.platform_admin = platform_admin
            handle.org_admin = org_admin
            handle.entitled = entitled
            handle.plain = plain
            yield handle
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
        await engine.dispose()


def _tier_claims(claims: dict) -> dict:
    return {k: v for k, v in claims.items() if k.endswith("_tier")}


# ---------------------------------------------------------------------------
# Registered by a platform admin: unchanged
# ---------------------------------------------------------------------------


async def test_admin_registered_unbound_client_keeps_the_madfam_tier(env):
    client = await env.add_client(
        created_by=env.platform_admin, scopes=["yantra4d:render", "openid"]
    )
    claims = await env.mint(client, "yantra4d:render")
    assert claims["yantra4d_tier"] == "madfam"
    assert "org_id" not in claims


async def test_admin_registered_org_client_keeps_scope_tiers_and_org_overrides(env):
    client = await env.add_client(
        created_by=env.platform_admin,
        organization=env.entitled,
        scopes=["yantra4d:render", "dhanam:events"],
    )
    claims = await env.mint(client, "yantra4d:render dhanam:events")
    # The organization's entitlement wins for the product it names; the other
    # scoped product keeps the platform tier.
    assert _tier_claims(claims) == {"yantra4d_tier": "pro", "dhanam_tier": "madfam"}


# ---------------------------------------------------------------------------
# Any other client: only the organization's entitlements
# ---------------------------------------------------------------------------


async def test_org_bound_client_without_the_entitlement_gets_no_tier_claim(env):
    client = await env.add_client(
        created_by=env.org_admin, organization=env.plain, scopes=["yantra4d:render"]
    )
    claims = await env.mint(client, "yantra4d:render")
    assert _tier_claims(claims) == {}
    # Everything else about the token is as before.
    assert claims["org_id"] == str(env.plain.id)
    assert claims["actor_type"] == "service_account"
    assert claims["scope"] == "yantra4d:render"


async def test_org_bound_client_with_the_entitlement_gets_the_entitled_tier(env):
    client = await env.add_client(
        created_by=env.org_admin,
        organization=env.entitled,
        scopes=["yantra4d:render", "hcm:hr"],
    )
    claims = await env.mint(client, "yantra4d:render hcm:hr")
    # yantra4d comes from the entitlement; hcm, which the organization is not
    # entitled to, carries no claim.
    assert _tier_claims(claims) == {"yantra4d_tier": "pro"}
    assert claims["product_tiers"] == {"yantra4d": "pro"}


async def test_org_entitlements_are_emitted_without_a_scope_for_them(env):
    client = await env.add_client(
        created_by=env.org_admin, organization=env.entitled, scopes=["openid"]
    )
    claims = await env.mint(client, "openid")
    assert _tier_claims(claims) == {"yantra4d_tier": "pro"}


async def test_client_whose_registrar_is_no_longer_an_admin_loses_the_scope_tier(env):
    client = await env.add_client(
        created_by=env.platform_admin, organization=env.plain, scopes=["yantra4d:render"]
    )
    assert (await env.claims(client, "yantra4d:render"))["yantra4d_tier"] == "madfam"

    async with env.factory.begin() as db:
        admin = await db.get(User, env.platform_admin.id)
        admin.is_admin = False
    assert _tier_claims(await env.claims(client, "yantra4d:render")) == {}


async def test_client_without_namespaced_scopes_is_unchanged_for_any_registrar(env):
    for registrar in (env.platform_admin, env.org_admin):
        client = await env.add_client(
            created_by=registrar, organization=env.plain, scopes=["openid"]
        )
        claims = await env.claims(client, "openid")
        assert _tier_claims(claims) == {}
        assert claims["tier"] == "community"


# ---------------------------------------------------------------------------
# The pre-deploy audit lists exactly what the builder stops emitting
# ---------------------------------------------------------------------------


def _load_audit_script():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3] / "scripts" / "audit_client_credentials_tier_claims.py"
    )
    spec = importlib.util.spec_from_file_location("audit_client_credentials_tier_claims", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "org_key,scopes",
    [
        (None, ["yantra4d:render", "hcm:hr"]),
        ("plain", ["yantra4d:render"]),
        ("entitled", ["yantra4d:render", "Crea-Map:read", "openid"]),
        ("entitled", ["openid"]),
    ],
)
async def test_audit_script_lists_exactly_the_claims_the_builder_drops(env, org_key, scopes):
    audit = _load_audit_script()
    organization = getattr(env, org_key) if org_key else None
    scope = " ".join(scopes)
    by_admin = await env.add_client(
        created_by=env.platform_admin, organization=organization, scopes=scopes
    )
    by_other = await env.add_client(
        created_by=env.org_admin, organization=organization, scopes=scopes
    )
    kept = _tier_claims(await env.claims(by_admin, scope))
    now = _tier_claims(await env.claims(by_other, scope))

    verdict = audit.classify(
        {
            "allowed_scopes": scopes,
            "grant_types": ["client_credentials"],
            "audience": AUDIENCE,
            "creator_is_admin": False,
            "is_active": True,
            "is_confidential": True,
            "product_tiers": organization.product_tiers if organization is not None else None,
        }
    )
    assert verdict["tier_claims_dropped"] == sorted(set(kept) - set(now))
    # And nothing the non-admin client keeps differs from the admin's value
    # for a product its organization is entitled to.
    assert all(kept[k] == v for k, v in now.items())


# ---------------------------------------------------------------------------
# Value shapes written through the ORM: the audit flags a client iff the app
# would issue it a client_credentials token that changes under these rules.
# (Shapes written by SQL, which the ORM cannot produce, are covered against
# real PostgreSQL in tests/unit/test_audit_client_credentials_tier_claims.py.)
# ---------------------------------------------------------------------------

#: What each value round-trips to through the model's JSON column.
SHAPES = {
    "json_array": ["authorization_code", "client_credentials"],
    "json_string_single": "client_credentials",
    "double_encoded_array": '["authorization_code", "client_credentials"]',
    "space_delimited": "authorization_code client_credentials",
    "comma_delimited": "authorization_code,client_credentials",
    "empty_string": "",
    "empty_list": [],
    "none": None,
}


def _scope_shape(shape: str, scope: str):
    """The same shape with ``scope`` in place of the grant names."""
    value = SHAPES[shape]
    if isinstance(value, list):
        return [scope] if value else []
    if not value:
        return value
    if value.startswith("["):
        return '["' + scope + '"]'
    return value.replace("authorization_code", "openid").replace("client_credentials", scope)


async def _add_raw(env, *, created_by, audience, grant_types, allowed_scopes) -> OAuthClient:
    row = await env.add_client(created_by=created_by, organization=env.plain, scopes=[])
    async with env.factory.begin() as db:
        stored = await db.get(OAuthClient, row.id)
        stored.audience = audience
        stored.grant_types = grant_types
        stored.allowed_scopes = allowed_scopes
    async with env.factory() as db:
        return await db.get(OAuthClient, row.id)


async def _mint_raw(env, client: OAuthClient):
    """Mint with no scope (every allowed scope); None when the app refuses."""
    response = await env.http.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client.client_id,
            "client_secret": SECRET,
        },
    )
    if response.status_code != 200:
        return None
    return jwt_manager.verify_token(response.json()["access_token"], audience=client.audience)


def _as_driver_value(loaded):
    """What the PostgreSQL driver hands back for a value the ORM wrote.

    The model type (`app/models/types.JSON`) stores JSON text, so the driver's
    one decode yields that text and the model decodes it again on load. The
    audit is given the driver value and must reach the same loaded value.
    """
    return None if loaded is None else json.dumps(loaded)


def _audit_row(client: OAuthClient, *, admin: bool) -> dict:
    return {
        "allowed_scopes": _as_driver_value(client.allowed_scopes),
        "grant_types": _as_driver_value(client.grant_types),
        "audience": client.audience,
        "creator_is_admin": admin,
        "is_active": client.is_active,
        "is_confidential": client.is_confidential,
        "product_tiers": {},
    }


def _cases():
    grants_vary = [(shape, "grants") for shape in SHAPES]
    scopes_vary = [(shape, "scopes") for shape in SHAPES]
    return grants_vary + scopes_vary


@pytest.mark.parametrize("shape,varied", _cases())
async def test_audit_flags_a_tier_change_iff_the_app_would_issue_one(env, shape, varied):
    audit = _load_audit_script()
    if varied == "grants":
        grants, scopes = SHAPES[shape], ["yantra4d:render"]
    else:
        grants, scopes = ["client_credentials"], _scope_shape(shape, "yantra4d:render")

    rows = {}
    for who, registrar in (("admin", env.platform_admin), ("other", env.org_admin)):
        rows[who] = await _add_raw(
            env,
            created_by=registrar,
            audience=AUDIENCE,
            grant_types=grants,
            allowed_scopes=scopes,
        )
    # The driver hands back what was stored; the audit reads that same value.
    assert rows["other"].grant_types == grants
    assert rows["other"].allowed_scopes == scopes

    before = await _mint_raw(env, rows["admin"])
    after = await _mint_raw(env, rows["other"])
    assert (before is None) == (after is None)
    lost = sorted(set(_tier_claims(before or {})) - set(_tier_claims(after or {})))

    # Not vacuous: the one issuable shape does lose the claim.
    assert bool(lost) == (shape == "json_array")

    verdict = audit.classify(_audit_row(rows["other"], admin=False))
    assert verdict["tier_claims_dropped"] == lost
    assert verdict["changes_active_client"] == bool(lost)
    assert audit.classify(_audit_row(rows["admin"], admin=True))["tier_claims_dropped"] == []


@pytest.mark.parametrize("shape,varied", _cases())
async def test_audit_flags_a_connections_refusal_iff_the_app_would_refuse(env, shape, varied):
    from app.core.consent_purposes import CONNECTIONS_AUDIENCE, CONNECTIONS_DELEGATE_SCOPE
    from app.services.connections_service_auth import (
        DelegationServicePrincipal,
        current_service_client,
    )

    audit = _load_audit_script()
    if varied == "grants":
        grants, scopes = SHAPES[shape], [CONNECTIONS_DELEGATE_SCOPE]
    else:
        grants, scopes = ["client_credentials"], _scope_shape(shape, CONNECTIONS_DELEGATE_SCOPE)

    async def works(registrar) -> bool:
        """A delegate token is issued AND the boundary accepts its client."""
        row = await _add_raw(
            env,
            created_by=registrar,
            audience=CONNECTIONS_AUDIENCE,
            grant_types=grants,
            allowed_scopes=scopes,
        )
        claims = await _mint_raw(env, row)
        if claims is None or CONNECTIONS_DELEGATE_SCOPE not in claims["scope"].split():
            return False
        async with env.factory() as db:
            try:
                await current_service_client(db, DelegationServicePrincipal(row.client_id))
            except HTTPException:
                return False
        return True

    works_for_admin = await works(env.platform_admin)
    works_for_other = await works(env.org_admin)
    assert not works_for_other  # the rule under test
    assert works_for_admin == (shape == "json_array")

    # Before this change the boundary did not look at provenance, so the
    # non-admin row worked exactly when the admin row works now.
    row = {
        "allowed_scopes": _as_driver_value(scopes),
        "grant_types": _as_driver_value(grants),
        "audience": CONNECTIONS_AUDIENCE,
        "creator_is_admin": False,
        "is_active": True,
        "is_confidential": True,
        "product_tiers": {},
    }
    assert audit.classify(row)["refused_after_deploy"] == works_for_admin
