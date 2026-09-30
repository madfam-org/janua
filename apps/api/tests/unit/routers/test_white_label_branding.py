"""White-label branding: the API contract against the real ORM model.

Until this fix, `routers/v1/white_label.py` used the API field names
(`company_name`, `is_enabled`, `accent_color`, ...) as attributes of
`BrandingConfiguration`, an alias of `WhiteLabelConfiguration`, whose columns
are `brand_name`, `is_active`, ... POST raised on the constructor keyword, GET
and PUT raised AttributeError building the response, and every handler's
`except Exception` turned that, and its own 404, into a 500. Nothing noticed
because nothing exercised the handlers against the real model.

These tests do: real `WhiteLabelConfiguration` rows in an in-memory database,
the real router, the real `require_admin`. Only the authenticated principal is
injected (and, for the refusal cases, not even that).

The response and request field names are the wire contract nauta#331 reads
(nauta `packages/integrations/src/janua-branding.ts`); CONTRACT_FIELDS pins it.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Base, Organization, User
from app.models.white_label import WhiteLabelConfiguration
from app.routers.v1 import white_label

pytestmark = pytest.mark.asyncio

_TABLES = ["users", "organizations", "white_label_configurations"]

BASE = "/api/v1/white-label/branding"

# The exact response keys nauta's `januaBrandingSchema` declares in snake_case.
CONTRACT_FIELDS = {
    "id",
    "organization_id",
    "is_enabled",
    "branding_level",
    "company_name",
    "company_logo_url",
    "company_logo_dark_url",
    "company_favicon_url",
    "company_website",
    "theme_mode",
    "primary_color",
    "secondary_color",
    "accent_color",
    "background_color",
    "surface_color",
    "text_color",
    "font_family",
    "border_radius",
    "created_at",
    "updated_at",
}

# What nauta's `upsertBranding` may send (`BRANDING_WIRE_FIELD` values).
NAUTA_WRITE_FIELDS = {
    "company_name",
    "company_logo_url",
    "company_logo_dark_url",
    "company_favicon_url",
    "company_website",
    "primary_color",
    "secondary_color",
    "accent_color",
    "background_color",
    "surface_color",
    "text_color",
    "font_family",
    "border_radius",
}

# nauta's JANUA_BRANDING_DEFAULTS: it reads a value equal to one of these as unset.
NAUTA_KNOWN_DEFAULTS = {
    "primary_color": "#1a73e8",
    "secondary_color": "#ea4335",
    "accent_color": "#34a853",
    "font_family": "Inter, system-ui, sans-serif",
    "border_radius": "8px",
}


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    tables = [Base.metadata.tables[name] for name in _TABLES]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def orgs(session_factory):
    """Two organizations: `branded` has a row as 000_init's columns hold it, `bare` has none."""
    branded, bare = uuid.uuid4(), uuid.uuid4()
    async with session_factory() as db:
        db.add_all(
            [
                Organization(id=branded, name="Branded", slug=f"branded-{branded.hex[:6]}"),
                Organization(id=bare, name="Bare", slug=f"bare-{bare.hex[:6]}"),
            ]
        )
        await db.flush()
        db.add(
            WhiteLabelConfiguration(
                organization_id=branded,
                brand_name="Org A",
                logo_url="https://cdn.example.test/logo.png",
                favicon_url="https://cdn.example.test/icon.png",
                primary_color="#2d2f86",
                secondary_color="#ffcc00",
                custom_css=".x { color: red; }",
            )
        )
        await db.commit()
    return SimpleNamespace(branded=branded, bare=bare)


def _principal(is_admin: bool) -> User:
    return User(id=uuid.uuid4(), email=f"p-{uuid.uuid4().hex[:6]}@example.test", is_admin=is_admin)


def _app(session_factory, principal=None) -> FastAPI:
    app = FastAPI()
    app.include_router(white_label.router, prefix="/api/v1")

    async def override_get_db():
        async with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    # get_current_user resolves Redis before it reads the token; never reached
    # for a refused token, but it must not try to connect.
    app.dependency_overrides[get_redis] = lambda: AsyncMock(get=AsyncMock(return_value=None))
    if principal is not None:
        app.dependency_overrides[get_current_user] = lambda: principal
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _row(session_factory, org_id) -> WhiteLabelConfiguration:
    async with session_factory() as db:
        result = await db.execute(
            select(WhiteLabelConfiguration).where(WhiteLabelConfiguration.organization_id == org_id)
        )
        return result.scalar_one_or_none()


# --- the mapping itself ------------------------------------------------------


def test_every_mapped_column_exists_on_the_table():
    """The regression guard: an API field may only map onto a real column."""
    columns = set(WhiteLabelConfiguration.__table__.columns.keys())
    missing = set(white_label.BRANDING_FIELD_COLUMNS.values()) - columns
    assert missing == set()


def test_every_request_and_response_field_is_mapped():
    mapped = set(white_label.BRANDING_FIELD_COLUMNS)
    for model in (
        white_label.BrandingConfigurationCreate,
        white_label.BrandingConfigurationUpdate,
    ):
        assert set(model.model_fields) <= mapped, model.__name__
    response_fields = set(white_label.BrandingConfigurationResponse.model_fields)
    assert response_fields - {"id", "organization_id", "created_at", "updated_at"} <= mapped


def test_contract_matches_nauta():
    assert set(white_label.BrandingConfigurationResponse.model_fields) == CONTRACT_FIELDS
    assert NAUTA_WRITE_FIELDS <= set(white_label.BrandingConfigurationCreate.model_fields)
    assert NAUTA_WRITE_FIELDS <= set(white_label.BrandingConfigurationUpdate.model_fields)
    for field, value in NAUTA_KNOWN_DEFAULTS.items():
        assert white_label.DEFAULT_THEME[field] == value
        assert white_label.BrandingConfigurationCreate.model_fields[field].default == value


# --- GET ----------------------------------------------------------------------


async def test_get_maps_existing_columns_onto_the_contract(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=False))) as client:
        response = await client.get(f"{BASE}/{orgs.branded}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == CONTRACT_FIELDS
    assert body["organization_id"] == str(orgs.branded)
    assert body["company_name"] == "Org A"
    assert body["company_logo_url"] == "https://cdn.example.test/logo.png"
    assert body["company_favicon_url"] == "https://cdn.example.test/icon.png"
    assert body["primary_color"] == "#2d2f86"
    assert body["secondary_color"] == "#ffcc00"
    assert body["is_enabled"] is True
    # Never chosen: null, not an invented default.
    for field in (
        "branding_level",
        "theme_mode",
        "company_logo_dark_url",
        "company_website",
        "accent_color",
        "background_color",
        "surface_color",
        "text_color",
        "font_family",
        "border_radius",
    ):
        assert body[field] is None, field
    assert body["created_at"] and body["updated_at"]


async def test_get_without_a_record_is_404_not_500(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=False))) as client:
        missing = await client.get(f"{BASE}/{orgs.bare}")
        malformed = await client.get(f"{BASE}/not-a-uuid")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Branding configuration not found"}
    assert malformed.status_code == 404


# --- PUT ----------------------------------------------------------------------


async def test_put_is_a_partial_update_onto_the_real_columns(session_factory, orgs):
    payload = {
        "company_name": "Org A Renamed",
        "company_logo_dark_url": "https://cdn.example.test/logo-dark.png",
        "company_website": "https://org-a.example.test",
        "accent_color": "#00AA55",
        "font_family": "Aileron, sans-serif",
        "border_radius": "12px",
        "theme_mode": "dark",
    }
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        response = await client.put(f"{BASE}/{orgs.branded}", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    for field, value in payload.items():
        assert body[field] == value, field
    # Not sent, so unchanged.
    assert body["primary_color"] == "#2d2f86"
    assert body["company_logo_url"] == "https://cdn.example.test/logo.png"
    assert body["is_enabled"] is True

    row = await _row(session_factory, orgs.branded)
    assert row.brand_name == "Org A Renamed"
    assert row.logo_dark_url == "https://cdn.example.test/logo-dark.png"
    assert row.website_url == "https://org-a.example.test"
    assert row.accent_color == "#00AA55"
    assert row.font_family == "Aileron, sans-serif"
    assert row.border_radius == "12px"
    assert row.theme_mode == "dark"
    assert row.primary_color == "#2d2f86"
    assert row.custom_css == ".x { color: red; }"


async def test_put_disables_and_clears(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        response = await client.put(
            f"{BASE}/{orgs.branded}", json={"is_enabled": False, "company_favicon_url": None}
        )

    assert response.status_code == 200, response.text
    assert response.json()["is_enabled"] is False
    assert response.json()["company_favicon_url"] is None
    row = await _row(session_factory, orgs.branded)
    assert row.is_active is False
    assert row.favicon_url is None


async def test_put_without_a_record_is_404(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        response = await client.put(f"{BASE}/{orgs.bare}", json={"company_name": "x"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Branding configuration not found"}
    assert await _row(session_factory, orgs.bare) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"primary_color": "rgb(1, 2, 3)"},
        {"accent_color": "#12345"},
        {"company_logo_url": "https://example.test/" + "a" * 500},
        {"border_radius": "x" * 21},
        {"is_enabled": None},
    ],
)
async def test_put_refuses_values_the_columns_cannot_hold(session_factory, orgs, payload):
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        response = await client.put(f"{BASE}/{orgs.branded}", json=payload)

    assert response.status_code == 422, response.text
    row = await _row(session_factory, orgs.branded)
    assert row.primary_color == "#2d2f86"
    assert row.is_active is True


# --- POST ---------------------------------------------------------------------


async def test_post_creates_and_get_reads_it_back(session_factory, orgs):
    payload = {
        "branding_level": "advanced",
        "company_name": "Org B",
        "company_logo_url": "https://cdn.example.test/b.png",
        "company_favicon_url": "https://cdn.example.test/b.ico",
        "primary_color": "#2d2f86",
        "accent_color": "#f5a623",
    }
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        created = await client.post(BASE, params={"organization_id": str(orgs.bare)}, json=payload)
        read = await client.get(f"{BASE}/{orgs.bare}")

    assert created.status_code == 200, created.text
    body = created.json()
    assert set(body) == CONTRACT_FIELDS
    for field, value in payload.items():
        assert body[field] == value, field
    assert body["is_enabled"] is True
    assert body["theme_mode"] == "light"
    # Fields left out get Janua's defaults, which nauta reads as "not chosen".
    assert body["secondary_color"] == "#ea4335"
    assert body["font_family"] == "Inter, system-ui, sans-serif"
    assert body["border_radius"] == "8px"
    assert body["company_logo_dark_url"] is None

    assert read.status_code == 200
    assert read.json() == body

    row = await _row(session_factory, orgs.bare)
    assert row.brand_name == "Org B"
    assert row.logo_url == "https://cdn.example.test/b.png"
    assert row.favicon_url == "https://cdn.example.test/b.ico"
    assert row.branding_level == "advanced"
    assert row.theme_mode == "light"
    assert row.is_active is True


async def test_post_for_an_existing_record_is_400(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        response = await client.post(
            BASE, params={"organization_id": str(orgs.branded)}, json={"company_name": "dup"}
        )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    assert (await _row(session_factory, orgs.branded)).brand_name == "Org A"


async def test_post_for_an_unknown_organization_is_404(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=True))) as client:
        unknown = await client.post(
            BASE, params={"organization_id": str(uuid.uuid4())}, json={"company_name": "x"}
        )
        malformed = await client.post(
            BASE, params={"organization_id": "nope"}, json={"company_name": "x"}
        )

    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Organization not found"}
    assert malformed.status_code == 404


# --- auth (unchanged by this fix) -----------------------------------------------


async def test_writes_refuse_a_non_admin(session_factory, orgs):
    async with _client(_app(session_factory, _principal(is_admin=False))) as client:
        put = await client.put(f"{BASE}/{orgs.branded}", json={"company_name": "x"})
        post = await client.post(
            BASE, params={"organization_id": str(orgs.bare)}, json={"company_name": "x"}
        )

    assert put.status_code == 403
    assert post.status_code == 403
    assert put.json() == {"detail": "Admin privileges required"}
    assert (await _row(session_factory, orgs.branded)).brand_name == "Org A"
    assert await _row(session_factory, orgs.bare) is None


async def test_every_endpoint_refuses_an_anonymous_or_invalid_caller(session_factory, orgs):
    """No principal is injected here: the real get_current_user decides."""
    app = _app(session_factory)
    bad = {"Authorization": "Bearer not-a-jwt"}
    async with _client(app) as client:
        anonymous = [
            await client.get(f"{BASE}/{orgs.branded}"),
            await client.put(f"{BASE}/{orgs.branded}", json={"company_name": "x"}),
            await client.post(
                BASE, params={"organization_id": str(orgs.bare)}, json={"company_name": "x"}
            ),
        ]
        invalid = [
            await client.get(f"{BASE}/{orgs.branded}", headers=bad),
            await client.put(f"{BASE}/{orgs.branded}", json={"company_name": "x"}, headers=bad),
            await client.post(
                BASE,
                params={"organization_id": str(orgs.bare)},
                json={"company_name": "x"},
                headers=bad,
            ),
        ]

    # HTTPBearer's refusal for a missing header (401 or 403 by FastAPI version).
    assert {r.status_code for r in anonymous} <= {401, 403}
    assert [r.status_code for r in invalid] == [401, 401, 401]
    assert (await _row(session_factory, orgs.branded)).brand_name == "Org A"
    assert await _row(session_factory, orgs.bare) is None


# --- the other handlers that touch the same columns -------------------------------


async def test_css_reads_enabled_branding_and_falls_back_per_column(session_factory, orgs):
    async with _client(_app(session_factory)) as client:
        branded = await client.get(f"/api/v1/white-label/css/{orgs.branded}")
        bare = await client.get(f"/api/v1/white-label/css/{orgs.bare}")

    assert branded.status_code == 200
    assert "--primary-color: #2d2f86;" in branded.text
    assert "--accent-color: #34a853;" in branded.text  # NULL column -> default
    assert ".x { color: red; }" in branded.text
    assert bare.status_code == 200
    assert "--primary-color: #1a73e8;" in bare.text

    async with session_factory() as db:
        row = (
            await db.execute(
                select(WhiteLabelConfiguration).where(
                    WhiteLabelConfiguration.organization_id == orgs.branded
                )
            )
        ).scalar_one()
        row.is_active = False
        await db.commit()
    async with _client(_app(session_factory)) as client:
        disabled = await client.get(f"/api/v1/white-label/css/{orgs.branded}")
    assert "--primary-color: #1a73e8;" in disabled.text


async def test_logo_upload_and_delete_write_the_logo_url_column(
    session_factory, orgs, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    app = _app(session_factory, _principal(is_admin=True))
    async with _client(app) as client:
        uploaded = await client.post(
            f"{BASE}/{orgs.branded}/logo-dark",
            files={"file": ("dark.png", b"\x89PNG fake", "image/png")},
        )
        read = await client.get(f"{BASE}/{orgs.branded}")
        deleted = await client.delete(f"{BASE}/{orgs.branded}/logo-dark")
        missing = await client.delete(f"{BASE}/{orgs.bare}/logo")

    assert uploaded.status_code == 200, uploaded.text
    url = uploaded.json()["company_logo_dark_url"]
    assert url.startswith("/uploads/branding/")
    assert read.json()["company_logo_dark_url"] == url
    assert deleted.status_code == 200
    assert (await _row(session_factory, orgs.branded)).logo_dark_url is None
    assert missing.status_code == 404
