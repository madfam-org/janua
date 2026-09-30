"""White-label custom domains and email templates, through the real router.

Real SQL sessions (sqlite), real RS256-signed person tokens, the real models:
what a route answers is checked against what it stored.
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

from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.database import get_db
from app.models import Base, Organization, User
from app.models.white_label import BrandingConfiguration, CustomDomain, EmailTemplate
from app.routers.v1.white_label import router

pytestmark = pytest.mark.asyncio

DOMAINS = "/api/v1/white-label/domains"
TEMPLATES = "/api/v1/white-label/email-templates"
TEMPLATE = {"template_type": "welcome", "subject": "Bienvenida", "html_body": "<p>Hola</p>"}


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
    config_id, other_config_id = uuid.uuid4(), uuid.uuid4()
    person_id, admin_id = uuid.uuid4(), uuid.uuid4()
    async with factory.begin() as db:
        db.add(Organization(id=org_id, name="Synthetic Org", slug="synthetic-domains"))
        db.add(Organization(id=other_org_id, name="Other Org", slug="synthetic-domains-other"))
        db.add(User(id=person_id, email="persona01@example.com"))
        db.add(User(id=admin_id, email="persona02@example.com", is_admin=True))
        await db.flush()
        db.add(BrandingConfiguration(id=config_id, organization_id=org_id))
        db.add(BrandingConfiguration(id=other_config_id, organization_id=other_org_id))
    yield {
        "factory": factory,
        "org": org_id,
        "other_org": other_org_id,
        "config": config_id,
        "other_config": other_config_id,
        "person": person_id,
        "admin": admin_id,
    }
    await engine.dispose()


@pytest.fixture(scope="module")
def module_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def token_for(monkeypatch, module_key):
    monkeypatch.setattr(jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(jwt_manager, "public_key", module_key.public_key())

    def sign(user_id):
        payload = {
            "iss": jwt_manager.issuer,
            "aud": jwt_manager.audience,
            "iat": int(time()) - 1,
            "exp": int(time()) + 900,
            "type": "access",
            "sub": str(user_id),
        }
        token = jwt.encode(payload, module_key, algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

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


@pytest.fixture
def admin(env, token_for):
    return token_for(env["admin"])


async def create_domain(http, headers, config_id, domain="brand.example.com"):
    return await http.post(
        DOMAINS,
        params={"branding_config_id": str(config_id)},
        json={"domain": domain},
        headers=headers,
    )


async def stored(env, model):
    async with env["factory"]() as db:
        return (await db.execute(select(model))).scalars().all()


def code_of(response):
    return response.json()["detail"]["code"]


# ── Custom domains ─────────────────────────────────────────────────────────


async def test_admin_creates_a_domain_for_the_configuration_org(env, http, admin):
    created = await create_domain(http, admin, env["config"], "Portal.Brand-Name.example.mx")

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["organization_id"] == str(env["org"])
    # Host names are case-insensitive; one spelling is stored.
    assert body["domain"] == "portal.brand-name.example.mx"
    assert body["is_verified"] is False
    assert body["status"] == "pending"
    assert body["ssl_configured"] is False
    assert body["created_at"]

    [row] = await stored(env, CustomDomain)
    assert str(row.id) == body["id"]
    assert row.organization_id == env["org"]
    assert row.domain == "portal.brand-name.example.mx"
    assert row.verified is False


async def test_a_domain_is_registered_once_whatever_its_case(env, http, admin):
    assert (await create_domain(http, admin, env["config"])).status_code == 200

    for config, spelling in (
        (env["config"], "brand.example.com"),
        (env["other_config"], "BRAND.example.COM"),
    ):
        again = await create_domain(http, admin, config, spelling)
        assert again.status_code == 409, again.text
        assert code_of(again) == "custom_domain_exists"

    assert len(await stored(env, CustomDomain)) == 1


@pytest.mark.parametrize("config_id", [uuid.uuid4(), "not-a-uuid"])
async def test_domain_for_a_missing_configuration_is_404(env, http, admin, config_id):
    result = await create_domain(http, admin, config_id)
    assert result.status_code == 404, result.text
    assert code_of(result) == "branding_configuration_not_found"
    assert await stored(env, CustomDomain) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"domain": "not a domain"},
        {"domain": "localhost"},
        {"domain": "-brand.example.com"},
        {"domain": "brand.example.com", "subdomain": "app"},
    ],
)
async def test_domain_request_is_validated(env, http, admin, payload):
    result = await http.post(
        DOMAINS,
        params={"branding_config_id": str(env["config"])},
        json=payload,
        headers=admin,
    )
    assert result.status_code == 422, result.text
    assert await stored(env, CustomDomain) == []


async def test_verify_persists_the_verified_state(env, http, admin):
    domain_id = (await create_domain(http, admin, env["config"])).json()["id"]

    verified = await http.post(f"{DOMAINS}/{domain_id}/verify", headers=admin)
    assert verified.status_code == 200, verified.text
    assert verified.json()["id"] == domain_id
    assert verified.json()["is_verified"] is True
    assert verified.json()["status"] == "verified"

    [row] = await stored(env, CustomDomain)
    assert row.verified is True

    # Verifying again is an answer, not an error.
    again = await http.post(f"{DOMAINS}/{domain_id}/verify", headers=admin)
    assert again.status_code == 200
    assert again.json()["is_verified"] is True


async def test_verify_of_a_domain_stored_outside_the_api_is_persisted(env, http, admin):
    async with env["factory"].begin() as db:
        seeded = CustomDomain(organization_id=env["org"], domain="seeded.example.com")
        db.add(seeded)

    verified = await http.post(f"{DOMAINS}/{seeded.id}/verify", headers=admin)
    assert verified.status_code == 200, verified.text

    [row] = await stored(env, CustomDomain)
    assert row.verified is True


@pytest.mark.parametrize("domain_id", [uuid.uuid4(), "not-a-uuid"])
async def test_verify_of_a_missing_domain_is_404(env, http, admin, domain_id):
    result = await http.post(f"{DOMAINS}/{domain_id}/verify", headers=admin)
    assert result.status_code == 404, result.text
    assert code_of(result) == "custom_domain_not_found"


# ── Email templates ────────────────────────────────────────────────────────


async def test_admin_creates_an_email_template_for_the_configuration_org(env, http, admin):
    created = await http.post(
        TEMPLATES,
        params={"branding_config_id": str(env["config"])},
        json={**TEMPLATE, "text_body": "Hola"},
        headers=admin,
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["organization_id"] == str(env["org"])
    assert body["template_type"] == "welcome"
    assert body["subject"] == "Bienvenida"
    assert body["html_body"] == "<p>Hola</p>"
    assert body["text_body"] == "Hola"
    assert body["is_active"] is True
    assert body["created_at"]

    [row] = await stored(env, EmailTemplate)
    assert str(row.id) == body["id"]
    assert row.organization_id == env["org"]
    assert row.html_content == "<p>Hola</p>"
    assert row.text_content == "Hola"


async def test_one_template_per_type_and_org(env, http, admin):
    first = await http.post(
        TEMPLATES, params={"branding_config_id": str(env["config"])}, json=TEMPLATE, headers=admin
    )
    assert first.status_code == 200

    again = await http.post(
        TEMPLATES, params={"branding_config_id": str(env["config"])}, json=TEMPLATE, headers=admin
    )
    assert again.status_code == 409, again.text
    assert code_of(again) == "email_template_exists"

    # Another organization keeps its own namespace.
    other = await http.post(
        TEMPLATES,
        params={"branding_config_id": str(env["other_config"])},
        json=TEMPLATE,
        headers=admin,
    )
    assert other.status_code == 200, other.text
    assert len(await stored(env, EmailTemplate)) == 2


@pytest.mark.parametrize("config_id", [uuid.uuid4(), "not-a-uuid"])
async def test_template_for_a_missing_configuration_is_404(env, http, admin, config_id):
    result = await http.post(
        TEMPLATES, params={"branding_config_id": str(config_id)}, json=TEMPLATE, headers=admin
    )
    assert result.status_code == 404, result.text
    assert code_of(result) == "branding_configuration_not_found"
    assert await stored(env, EmailTemplate) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"subject": "x" * 256},
        {"template_type": ""},
        {"html_body": ""},
        {"from_email": "sender@example.com"},
        {"locale": "es"},
        {"button_color": "#000000"},
    ],
)
async def test_template_request_is_validated(env, http, admin, changes):
    result = await http.post(
        TEMPLATES,
        params={"branding_config_id": str(env["config"])},
        json={**TEMPLATE, **changes},
        headers=admin,
    )
    assert result.status_code == 422, result.text
    assert await stored(env, EmailTemplate) == []


# ── Authorization is unchanged: platform admins only ───────────────────────


async def test_a_person_who_is_not_an_admin_writes_nothing(env, http, token_for):
    headers = token_for(env["person"])
    async with env["factory"].begin() as db:
        seeded = CustomDomain(organization_id=env["org"], domain="seeded.example.com")
        db.add(seeded)

    results = [
        await create_domain(http, headers, env["config"]),
        await http.post(f"{DOMAINS}/{seeded.id}/verify", headers=headers),
        await http.post(
            TEMPLATES,
            params={"branding_config_id": str(env["config"])},
            json=TEMPLATE,
            headers=headers,
        ),
    ]
    assert [r.status_code for r in results] == [403, 403, 403]
    assert [(d.domain, d.verified) for d in await stored(env, CustomDomain)] == [
        ("seeded.example.com", False)
    ]
    assert await stored(env, EmailTemplate) == []
