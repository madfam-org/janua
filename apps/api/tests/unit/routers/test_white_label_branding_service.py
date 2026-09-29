"""Branding routes accept an org-bound service token and keep the person path.

Real SQL sessions (sqlite), real RS256-signed tokens, the real router.
"""

import uuid
from time import time

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.redis import get_redis
from app.database import get_db
from app.models import Base, OAuthClient, Organization, User
from app.models.white_label import BrandingConfiguration
from app.routers.v1.white_label import router
from app.services import branding_service_auth as auth

pytestmark = pytest.mark.asyncio

CLIENT_ID = "fixture-branding-edge"


class _NoRedis:
    async def get(self, *_args, **_kwargs):
        return None

    async def set(self, *_args, **_kwargs):
        return None


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    org_id, other_org_id = uuid.uuid4(), uuid.uuid4()
    person_id, admin_id = uuid.uuid4(), uuid.uuid4()
    async with factory.begin() as db:
        db.add(Organization(id=org_id, name="Synthetic Org", slug="synthetic-brand"))
        db.add(Organization(id=other_org_id, name="Other Org", slug="synthetic-other"))
        db.add(User(id=person_id, email="persona01@example.com"))
        db.add(User(id=admin_id, email="persona02@example.com", is_admin=True))
        await db.flush()
        db.add(
            OAuthClient(
                id=uuid.uuid4(),
                organization_id=org_id,
                created_by=admin_id,
                client_id=CLIENT_ID,
                client_secret_hash="fixture-not-a-secret",
                client_secret_prefix="fixture",
                name="Fixture branding edge",
                redirect_uris=[],
                audience=auth.BRANDING_AUDIENCE,
                allowed_scopes=[auth.BRANDING_SCOPE],
                grant_types=["client_credentials"],
                is_active=True,
                is_confidential=True,
            )
        )
    yield {
        "factory": factory,
        "org": org_id,
        "other_org": other_org_id,
        "person": person_id,
        "admin": admin_id,
    }
    await engine.dispose()


@pytest.fixture
def key(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth.jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(auth.jwt_manager, "public_key", private.public_key())
    return private


@pytest.fixture
def service_token(key):
    def sign(org_id, changes=None):
        payload = {
            "iss": auth.jwt_manager.issuer,
            "aud": auth.BRANDING_AUDIENCE,
            "iat": int(time()) - 1,
            "exp": int(time()) + 3599,
            "type": "access",
            "token_use": "client_credentials",
            "actor_type": "service_account",
            "sub": f"service-account:{CLIENT_ID}",
            "client_id": CLIENT_ID,
            "org_id": str(org_id),
            "scope": auth.BRANDING_SCOPE,
        }
        payload.update(changes or {})
        payload = {k: v for k, v in payload.items() if v is not None}
        return jwt.encode(payload, key, algorithm="RS256")

    return sign


@pytest.fixture
def person_token(key):
    def sign(user_id):
        payload = {
            "iss": auth.jwt_manager.issuer,
            "aud": auth.jwt_manager.audience,
            "iat": int(time()) - 1,
            "exp": int(time()) + 900,
            "type": "access",
            "sub": str(user_id),
        }
        return jwt.encode(payload, key, algorithm="RS256")

    return sign


@pytest_asyncio.fixture
async def http(env):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def database():
        async with env["factory"]() as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_redis] = lambda: _NoRedis()
    async with AsyncClient(transport=ASGITransport(app), base_url="http://fixture") as client:
        yield client


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


BRAND = {
    "company_name": "Synthetic",
    "company_favicon_url": "https://example.com/icon.svg",
    "primary_color": "#2d2f86",
}


async def test_service_token_manages_its_own_org(env, http, service_token):
    headers = bearer(service_token(env["org"]))
    path = f"/api/v1/white-label/branding/{env['org']}"

    missing = await http.get(path, headers=headers)
    # An answer, not a failure: this used to surface as a 500.
    assert missing.status_code == 404

    created = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json=BRAND,
        headers=headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["primary_color"] == "#2d2f86"

    again = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json=BRAND,
        headers=headers,
    )
    assert again.status_code == 400

    updated = await http.put(path, json={"accent_color": "#f4a261"}, headers=headers)
    assert updated.status_code == 200
    read = await http.get(path, headers=headers)
    assert read.status_code == 200
    body = read.json()
    assert body["accent_color"] == "#f4a261"
    assert body["primary_color"] == "#2d2f86"
    assert body["company_name"] == "Synthetic"
    assert body["company_favicon_url"] == "https://example.com/icon.svg"
    assert body["is_enabled"] is True

    # Stored where the table can hold it: columns for the named fields, the
    # rest under features["branding"].
    async with env["factory"]() as db:
        row = (await db.execute(select(BrandingConfiguration))).scalar_one()
        assert row.brand_name == "Synthetic"
        assert row.favicon_url == "https://example.com/icon.svg"
        assert row.features["branding"]["accent_color"] == "#f4a261"


async def test_public_stylesheet_renders_the_stored_tokens(env, http, service_token):
    headers = bearer(service_token(env["org"]))
    await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json={**BRAND, "accent_color": "#f2581e"},
        headers=headers,
    )
    css = await http.get(f"/api/v1/white-label/css/{env['org']}")
    assert css.status_code == 200
    assert "--primary-color: #2d2f86" in css.text
    assert "--accent-color: #f2581e" in css.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("primary_color", "rgb(0,0,0)"),
        ("accent_color", "#12345678"),
        ("font_family", "x;} body{display:none"),
        ("border_radius", "8px;}"),
    ],
)
async def test_style_tokens_are_validated(env, http, service_token, field, value):
    result = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json={**BRAND, field: value},
        headers=bearer(service_token(env["org"])),
    )
    assert result.status_code == 422


async def test_service_token_cannot_reach_another_org(env, http, service_token):
    headers = bearer(service_token(env["org"]))
    other = str(env["other_org"])
    assert (
        await http.get(f"/api/v1/white-label/branding/{other}", headers=headers)
    ).status_code == 403
    assert (
        await http.put(f"/api/v1/white-label/branding/{other}", json=BRAND, headers=headers)
    ).status_code == 403
    assert (
        await http.post(
            "/api/v1/white-label/branding",
            params={"organization_id": other},
            json=BRAND,
            headers=headers,
        )
    ).status_code == 403
    assert (
        await http.get("/api/v1/white-label/branding/not-a-uuid", headers=headers)
    ).status_code == 403
    async with env["factory"]() as db:
        assert (await db.execute(select(BrandingConfiguration))).scalar_one_or_none() is None


async def test_service_token_cannot_set_custom_css(env, http, service_token):
    result = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json={**BRAND, "custom_css": "body{}"},
        headers=bearer(service_token(env["org"])),
    )
    assert result.status_code == 403
    assert result.json()["detail"]["code"] == "branding_service_custom_css_forbidden"


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "other-issuer"},
        {"exp": int(time()) + 7200},
        {"iat": int(time()) + 300},
        {"iat": None},
        {"token_use": "session"},
        {"actor_type": "user"},
        {"sub": "human"},
        {"client_id": "other-client"},
        {"scope": "openid"},
        {"org_id": None},
        {"org_id": "invalid"},
        {"org_id": str(uuid.uuid4())},
    ],
)
async def test_invalid_service_claims_are_refused(env, http, service_token, changes):
    result = await http.get(
        f"/api/v1/white-label/branding/{env['org']}",
        headers=bearer(service_token(env["org"], changes)),
    )
    # Either refused by this authority (403) or not a janua token at all (401);
    # never a read.
    assert result.status_code in (401, 403)


@pytest.mark.parametrize(
    "change",
    [
        {"is_active": False},
        {"is_confidential": False},
        {"audience": "other-api"},
        {"allowed_scopes": ["openid"]},
        {"grant_types": ["authorization_code"]},
        {"organization_id": None},
    ],
)
async def test_revoked_grant_is_refused_before_expiry(env, http, service_token, change):
    async with env["factory"].begin() as db:
        client = (
            await db.execute(select(OAuthClient).where(OAuthClient.client_id == CLIENT_ID))
        ).scalar_one()
        for name, value in change.items():
            setattr(client, name, value)
    result = await http.get(
        f"/api/v1/white-label/branding/{env['org']}",
        headers=bearer(service_token(env["org"])),
    )
    assert result.status_code == 403
    assert result.json()["detail"]["code"] == "branding_service_grant_unavailable"


async def test_person_path_is_unchanged(env, http, person_token, service_token):
    path = f"/api/v1/white-label/branding/{env['org']}"
    created = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json=BRAND,
        headers=bearer(person_token(env["admin"])),
    )
    assert created.status_code == 200

    # Any signed-in person may read, whatever their organization.
    assert (await http.get(path, headers=bearer(person_token(env["person"])))).status_code == 200
    # Only a platform admin may write.
    refused = await http.put(
        path, json={"accent_color": "#000000"}, headers=bearer(person_token(env["person"]))
    )
    assert refused.status_code == 403
    assert refused.json()["detail"] == "Admin privileges required"
    allowed = await http.put(
        path, json={"custom_css": "body{}"}, headers=bearer(person_token(env["admin"]))
    )
    assert allowed.status_code == 200


async def test_symmetric_runtime_does_not_open_the_service_path(
    env, http, service_token, monkeypatch
):
    token = service_token(env["org"])
    monkeypatch.setattr(auth.jwt_manager, "algorithm", "HS256")
    result = await http.get(f"/api/v1/white-label/branding/{env['org']}", headers=bearer(token))
    assert result.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-API-Key": "fixture-shared-key"}, {"Authorization": "Bearer invalid"}],
)
async def test_no_token_or_shared_key_is_not_authority(env, http, headers):
    result = await http.get(f"/api/v1/white-label/branding/{env['org']}", headers=headers)
    assert result.status_code in (401, 403)
