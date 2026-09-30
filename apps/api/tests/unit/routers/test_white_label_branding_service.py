"""Branding routes accept an org-bound service token and keep the person path.

Real SQL sessions (sqlite), real RS256-signed tokens, the real router.
"""

import base64
import hashlib
import hmac
import json
import uuid
from time import time

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.models import Base, OAuthClient, Organization, User
from app.models.white_label import BrandingConfiguration, CustomDomain, EmailTemplate
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


def service_claims(org_id, changes=None):
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
    return {k: v for k, v in payload.items() if v is not None}


@pytest.fixture
def service_token(key):
    def sign(org_id, changes=None):
        return jwt.encode(service_claims(org_id, changes), key, algorithm="RS256")

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


# ---------------------------------------------------------------------------
# Boundary tests: who holds the grant, what the token must look like, and what
# a service token can never reach. Real models, real router, no mocks.
# ---------------------------------------------------------------------------

SEEDED_CSS = "body{color:#000}"


def branding_path(org_id):
    return f"/api/v1/white-label/branding/{org_id}"


async def seed_branding(env, **columns):
    async with env["factory"].begin() as db:
        row = BrandingConfiguration(
            organization_id=env["org"],
            brand_name="Seeded",
            logo_url="https://example.com/seeded.svg",
            primary_color="#111111",
            custom_css=SEEDED_CSS,
            **columns,
        )
        db.add(row)
    return row.id


async def stored_branding(env):
    async with env["factory"]() as db:
        return (await db.execute(select(BrandingConfiguration))).scalars().all()


async def attempt_every_branding_call(http, org_id, headers):
    """GET, PUT and POST on one organization's branding, with the same headers."""
    return [
        await http.get(branding_path(org_id), headers=headers),
        await http.put(branding_path(org_id), json={"company_name": "Changed"}, headers=headers),
        await http.post(
            "/api/v1/white-label/branding",
            params={"organization_id": str(org_id)},
            json=BRAND,
            headers=headers,
        ),
    ]


def assert_unchanged(rows):
    assert len(rows) == 1
    assert rows[0].brand_name == "Seeded"
    assert rows[0].logo_url == "https://example.com/seeded.svg"
    assert rows[0].custom_css == SEEDED_CSS


@pytest.mark.parametrize("creator", ["person", "org_owner", "unknown_user"])
async def test_client_not_registered_by_a_platform_admin_grants_nothing(
    env, http, service_token, creator
):
    # A row carrying the reserved audience and scope, bound to the org, but
    # registered by someone who is not a platform admin (or by a user id that
    # resolves to no user at all).
    owner_id = uuid.uuid4()
    async with env["factory"].begin() as db:
        db.add(User(id=owner_id, email="persona03@example.com"))
        await db.flush()
        (await db.get(Organization, env["org"])).owner_id = owner_id
        client = (
            await db.execute(select(OAuthClient).where(OAuthClient.client_id == CLIENT_ID))
        ).scalar_one()
        client.created_by = {
            "person": env["person"],
            "org_owner": owner_id,
            "unknown_user": uuid.uuid4(),
        }[creator]
    await seed_branding(env)

    for result in await attempt_every_branding_call(
        http, env["org"], bearer(service_token(env["org"]))
    ):
        assert result.status_code == 403, result.text
        assert result.json()["detail"]["code"] == "branding_service_grant_unavailable"
    assert_unchanged(await stored_branding(env))


async def test_service_may_not_clear_custom_css_with_null(env, http, service_token):
    await seed_branding(env)
    headers = bearer(service_token(env["org"]))

    cleared = await http.put(branding_path(env["org"]), json={"custom_css": None}, headers=headers)
    assert cleared.status_code == 403
    assert cleared.json()["detail"]["code"] == "branding_service_custom_css_forbidden"
    mixed = await http.put(
        branding_path(env["org"]),
        json={"company_name": "Changed", "custom_css": None},
        headers=headers,
    )
    assert mixed.status_code == 403
    assert_unchanged(await stored_branding(env))

    # The same presence rule on create.
    async with env["factory"].begin() as db:
        await db.execute(delete(BrandingConfiguration))
    created = await http.post(
        "/api/v1/white-label/branding",
        params={"organization_id": str(env["org"])},
        json={**BRAND, "custom_css": None},
        headers=headers,
    )
    assert created.status_code == 403
    assert await stored_branding(env) == []


async def test_row_with_null_columns_reads_as_200(env, http, service_token, person_token):
    # As a row written outside this API may look: only a name, every other
    # nullable column (000_init) NULL, no Python-side defaults applied.
    async with env["factory"].begin() as db:
        await db.execute(
            insert(BrandingConfiguration.__table__).values(
                id=uuid.uuid4(),
                organization_id=env["org"],
                brand_name="Legacy",
                primary_color=None,
                secondary_color=None,
                is_active=None,
                features=None,
                created_at=None,
                updated_at=None,
            )
        )

    for headers in (bearer(service_token(env["org"])), bearer(person_token(env["person"]))):
        read = await http.get(branding_path(env["org"]), headers=headers)
        assert read.status_code == 200, read.text
        body = read.json()
        assert body["company_name"] == "Legacy"
        assert body["primary_color"] == "#1a73e8"
        assert body["secondary_color"] == "#ea4335"
        assert body["accent_color"] == "#34a853"
        assert body["is_enabled"] is None
        assert body["created_at"] is None

    updated = await http.put(
        branding_path(env["org"]),
        json={"accent_color": "#f4a261"},
        headers=bearer(service_token(env["org"])),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["accent_color"] == "#f4a261"

    # Enabled but colourless: the public stylesheet uses the defaults, never "None".
    async with env["factory"].begin() as db:
        (await db.execute(select(BrandingConfiguration))).scalar_one().is_active = True
    css = await http.get(f"/api/v1/white-label/css/{env['org']}")
    assert css.status_code == 200
    assert "--primary-color: #1a73e8" in css.text
    assert "None" not in css.text


def _segment(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")


def _hand_signed(payload, alg, secret=None):
    """A JWT built by hand, because PyJWT refuses to produce these on purpose."""
    signing_input = _segment({"alg": alg, "typ": "JWT"}) + b"." + _segment(payload)
    signature = b""
    if secret is not None:
        digest = hmac.new(secret, signing_input, hashlib.sha256).digest()
        signature = base64.urlsafe_b64encode(digest).rstrip(b"=")
    return (signing_input + b"." + signature).decode()


@pytest.mark.parametrize("forgery", ["alg_none", "hs256_with_public_pem"])
async def test_unsigned_or_algorithm_confused_tokens_are_refused(env, http, key, forgery):
    await seed_branding(env)
    claims = service_claims(env["org"])
    if forgery == "alg_none":
        token = _hand_signed(claims, "none")
    else:
        pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        token = _hand_signed(claims, "HS256", pem)

    for result in await attempt_every_branding_call(http, env["org"], bearer(token)):
        # Not a janua token at all: the person path's 401, never a read.
        assert result.status_code == 401, result.text
    assert_unchanged(await stored_branding(env))


async def test_expired_token_is_refused_and_writes_nothing(env, http, service_token):
    await seed_branding(env)
    token = service_token(env["org"], {"iat": int(time()) - 600, "exp": int(time()) - 60})
    for result in await attempt_every_branding_call(http, env["org"], bearer(token)):
        assert result.status_code == 401, result.text
    assert_unchanged(await stored_branding(env))


@pytest.mark.parametrize(
    "aud,status",
    [
        # Does not verify against the branding audience, nor the platform one.
        ("janua-white-label-x", 401),
        ("xjanua-white-label", 401),
        # Verifies (PyJWT accepts a list containing the audience), then this
        # authority requires the exact single string.
        (["janua-white-label"], 403),
        (["janua-white-label", "__platform__"], 403),
    ],
)
async def test_audience_must_be_exactly_the_branding_audience(
    env, http, service_token, aud, status
):
    await seed_branding(env)
    if isinstance(aud, list):
        aud = [auth.jwt_manager.audience if value == "__platform__" else value for value in aud]
    for result in await attempt_every_branding_call(
        http, env["org"], bearer(service_token(env["org"], {"aud": aud}))
    ):
        assert result.status_code == status, result.text
        if status == 403:
            assert result.json()["detail"]["code"] == "branding_service_unauthorized"
    assert_unchanged(await stored_branding(env))


@pytest.mark.parametrize(
    "scope",
    [
        "white-label:branding-x",
        "xwhite-label:branding",
        "white-label:brandingx openid",
        "white-label",
        "white-label:branding,openid",
    ],
)
async def test_scope_must_contain_the_exact_branding_scope(env, http, service_token, scope):
    await seed_branding(env)
    for result in await attempt_every_branding_call(
        http, env["org"], bearer(service_token(env["org"], {"scope": scope}))
    ):
        assert result.status_code == 403, result.text
        assert result.json()["detail"]["code"] == "branding_service_unauthorized"
    assert_unchanged(await stored_branding(env))


async def test_client_deleted_after_minting_is_refused(env, http, service_token):
    await seed_branding(env)
    token = service_token(env["org"])
    assert (await http.get(branding_path(env["org"]), headers=bearer(token))).status_code == 200
    async with env["factory"].begin() as db:
        await db.execute(delete(OAuthClient).where(OAuthClient.client_id == CLIENT_ID))

    for result in await attempt_every_branding_call(http, env["org"], bearer(token)):
        assert result.status_code == 403, result.text
        assert result.json()["detail"]["code"] == "branding_service_grant_unavailable"
    assert_unchanged(await stored_branding(env))


def _image():
    return {"file": ("mark.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, "image/png")}


async def test_service_token_reaches_no_other_white_label_route(
    env, http, service_token, person_token, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    config_id = await seed_branding(env)
    async with env["factory"].begin() as db:
        domain = CustomDomain(organization_id=env["org"], domain="seeded.example.com")
        db.add(domain)
    org = env["org"]
    calls = [
        ("post", f"/api/v1/white-label/branding/{org}/logo", {"files": _image()}),
        ("post", f"/api/v1/white-label/branding/{org}/logo-dark", {"files": _image()}),
        ("post", f"/api/v1/white-label/branding/{org}/favicon", {"files": _image()}),
        ("delete", f"/api/v1/white-label/branding/{org}/logo", {}),
        ("delete", f"/api/v1/white-label/branding/{org}/logo-dark", {}),
        ("delete", f"/api/v1/white-label/branding/{org}/favicon", {}),
        (
            "post",
            "/api/v1/white-label/domains",
            {
                "params": {"branding_config_id": str(config_id)},
                "json": {"domain": "brand.example.com"},
            },
        ),
        ("post", f"/api/v1/white-label/domains/{domain.id}/verify", {}),
        (
            "post",
            "/api/v1/white-label/email-templates",
            {
                "params": {"branding_config_id": str(config_id)},
                "json": {"template_type": "welcome", "subject": "Hola", "html_body": "<p>x</p>"},
            },
        ),
        ("get", "/api/v1/white-label/theme-presets", {}),
    ]
    headers = bearer(service_token(env["org"]))
    for method, path, kwargs in calls:
        result = await getattr(http, method)(path, headers=headers, **kwargs)
        # These routes know only people; a branding token is not one.
        assert result.status_code == 401, (method, path, result.text)

    assert_unchanged(await stored_branding(env))
    assert list(tmp_path.iterdir()) == []
    async with env["factory"]() as db:
        domains = (await db.execute(select(CustomDomain))).scalars().all()
        assert [(d.domain, d.verified) for d in domains] == [("seeded.example.com", False)]
        assert (await db.execute(select(EmailTemplate))).scalars().all() == []


async def test_person_token_addressed_to_the_branding_audience_is_refused(env, http, key):
    await seed_branding(env)
    # What an interactive client registered with this audience would mint for
    # a person: a user subject, no client_credentials markers. Even for a
    # platform admin it is not a read.
    payload = {
        "iss": auth.jwt_manager.issuer,
        "aud": auth.BRANDING_AUDIENCE,
        "iat": int(time()) - 1,
        "exp": int(time()) + 900,
        "type": "access",
        "sub": str(env["admin"]),
        "client_id": CLIENT_ID,
        "org_id": str(env["org"]),
        "scope": f"openid {auth.BRANDING_SCOPE}",
    }
    token = jwt.encode(payload, key, algorithm="RS256")
    for result in await attempt_every_branding_call(http, env["org"], bearer(token)):
        assert result.status_code == 403, result.text
        assert result.json()["detail"]["code"] == "branding_service_unauthorized"
    assert_unchanged(await stored_branding(env))


async def test_admin_routes_answer_their_own_404_not_500(env, http, person_token):
    headers = bearer(person_token(env["admin"]))
    missing = str(uuid.uuid4())
    domain = await http.post(
        "/api/v1/white-label/domains",
        params={"branding_config_id": missing},
        json={"domain": "brand.example.com"},
        headers=headers,
    )
    assert domain.status_code == 404
    verify = await http.post(f"/api/v1/white-label/domains/{missing}/verify", headers=headers)
    assert verify.status_code == 404
    template = await http.post(
        "/api/v1/white-label/email-templates",
        params={"branding_config_id": missing},
        json={"template_type": "welcome", "subject": "Hola", "html_body": "<p>x</p>"},
        headers=headers,
    )
    assert template.status_code == 404
