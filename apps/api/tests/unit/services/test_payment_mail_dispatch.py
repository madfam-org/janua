"""Real SQL sessions, signed service tokens; provider calls stay in process."""

import uuid
from datetime import datetime, timedelta
from time import time
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, OAuthClient, Organization, PaymentMailDispatch, User
from app.routers.v1.payment_notices import router
from app.services import payment_mail_auth as auth
from app.services import payment_mail_dispatch as mail

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def mail_env(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    org_id, user_id, client_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with factory.begin() as db:
        db.add(Organization(id=org_id, name="Synthetic Org", slug="synthetic-mail"))
        db.add(User(id=user_id, email="persona01@example.com"))
        await db.flush()
        db.add(
            OAuthClient(
                id=client_id,
                organization_id=org_id,
                created_by=user_id,
                client_id="fixture-map-mail",
                client_secret_hash="fixture-not-a-secret",
                client_secret_prefix="fixture",
                name="Fixture mail",
                redirect_uris=[],
                audience=auth.MAIL_AUDIENCE,
                allowed_scopes=[auth.PAYMENT_MAIL_SCOPE],
                grant_types=["client_credentials"],
                is_active=True,
                is_confidential=True,
            )
        )
    principal = auth.PaymentMailPrincipal("fixture-map-mail", org_id)
    intent = mail.PaymentNoticeIntent(
        command_id=uuid.uuid4(), recipient="persona02@example.com", year=2026, month=9, sessions=4
    )
    envelope = AsyncMock(
        return_value=(
            {"subject": "fixture", "to": [str(intent.recipient)]},
            "fixture-key",
            "a" * 64,
            "b" * 64,
        )
    )
    provider = Mock(return_value={"id": "fixture-provider-id"})
    monkeypatch.setattr(mail, "_envelope", envelope)
    monkeypatch.setattr(mail, "send_on_account", provider)
    yield factory, principal, intent, envelope, provider, client_id
    await engine.dispose()


async def dispatch(env, intent=None):
    factory, principal, original, *_ = env
    async with factory() as db:
        return await mail.dispatch_payment_notice(db, principal, intent or original)


async def stored(env):
    async with env[0]() as db:
        return (await db.execute(select(PaymentMailDispatch))).scalar_one()


async def make_due(env, **changes):
    async with env[0].begin() as db:
        row = (await db.execute(select(PaymentMailDispatch))).scalar_one()
        row.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        for name, value in changes.items():
            setattr(row, name, value)


async def test_acceptance_replay_works_during_credential_outage(mail_env):
    first = await dispatch(mail_env)
    mail_env[3].side_effect = RuntimeError("credential service offline")
    second = await dispatch(mail_env)
    assert first == second
    assert first.delivery_status == "accepted" and first.message_id == "fixture-provider-id"
    assert mail_env[4].call_count == mail_env[3].call_count == 1
    row = await stored(mail_env)
    assert row.attempts == 1 and row.accepted_at
    assert "recipient" not in PaymentMailDispatch.__table__.columns


async def test_changed_command_refuses_even_after_acceptance(mail_env):
    await dispatch(mail_env)
    changed = mail_env[2].model_copy(update={"month": 10})
    with pytest.raises(HTTPException) as error:
        await dispatch(mail_env, changed)
    assert error.value.status_code == 409
    assert mail_env[4].call_count == 1


@pytest.mark.parametrize(
    "response", [{}, {"id": ""}, {"id": " "}, {"id": None}, None, {"id": "x" * 256}]
)
async def test_missing_receipt_remains_pending(mail_env, response):
    mail_env[4].return_value = response
    result = await dispatch(mail_env)
    assert result.delivery_status == "pending" and not result.message_id
    assert result.issue == "provider_outcome_unknown" and result.retry_after
    assert result.retry_after.utcoffset().total_seconds() == 0


async def test_ambiguous_outcome_retries_same_key_and_envelope_after_backoff(mail_env):
    mail_env[4].side_effect = [
        TimeoutError("accepted then response lost"),
        {"id": "fixture-provider-id"},
    ]
    first = await dispatch(mail_env)
    assert (await dispatch(mail_env)) == first  # backoff: no provider call
    assert mail_env[4].call_count == 1
    await make_due(mail_env)
    final = await dispatch(mail_env)
    assert final.delivery_status == "accepted"
    before, after = mail_env[4].call_args_list
    assert before == after  # includes immutable deadline and opaque provider key
    assert (await stored(mail_env)).attempts == 2


@pytest.mark.parametrize("change", ["envelope", "binding", "credential"])
async def test_configuration_drift_requires_review_before_retry(mail_env, change):
    mail_env[4].side_effect = TimeoutError()
    await dispatch(mail_env)
    await make_due(mail_env)
    values = list(mail_env[3].return_value)
    if change == "envelope":
        values[0] = {"subject": "changed template"}
    else:
        values[2 if change == "binding" else 3] = "c" * 64
    mail_env[3].return_value = tuple(values)
    result = await dispatch(mail_env)
    assert result.delivery_status == "review"
    assert (await dispatch(mail_env)) == result
    assert mail_env[4].call_count == 1


async def test_expired_window_stops_without_loading_credentials(mail_env):
    mail_env[4].side_effect = TimeoutError()
    await dispatch(mail_env)
    await make_due(mail_env, first_attempt_at=datetime.utcnow() - timedelta(hours=23))
    result = await dispatch(mail_env)
    assert result.delivery_status == "review" and result.issue == "provider_key_window_expired"
    assert mail_env[3].call_count == mail_env[4].call_count == 1


async def test_last_active_attempt_is_not_prematurely_marked_review(mail_env):
    mail_env[4].side_effect = TimeoutError()
    await dispatch(mail_env)
    await make_due(
        mail_env, state="sending", attempts=10, lease_until=datetime.utcnow() + timedelta(minutes=1)
    )
    assert (await dispatch(mail_env)).delivery_status == "pending"
    await make_due(mail_env, lease_until=datetime.utcnow() - timedelta(seconds=1))
    result = await dispatch(mail_env)
    assert result.delivery_status == "review" and result.issue == "attempt_limit_reached"
    assert mail_env[4].call_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"is_active": False},
        {"is_confidential": False},
        {"allowed_scopes": []},
        {"grant_types": ["authorization_code"]},
        {"audience": "other-api"},
        {"organization_id": uuid.uuid4()},
    ],
)
async def test_native_grant_is_checked_even_for_accepted_replay(mail_env, changes):
    await dispatch(mail_env)
    async with mail_env[0].begin() as db:
        client = await db.get(OAuthClient, mail_env[5])
        for name, value in changes.items():
            setattr(client, name, value)
    with pytest.raises(HTTPException) as error:
        await dispatch(mail_env)
    assert error.value.status_code == 403
    assert mail_env[4].call_count == 1


async def test_preflight_failure_does_not_create_claim(mail_env):
    mail_env[3].side_effect = HTTPException(503, "fixture unavailable")
    with pytest.raises(HTTPException):
        await dispatch(mail_env)
    async with mail_env[0]() as db:
        assert (await db.execute(select(PaymentMailDispatch))).scalar_one_or_none() is None
    mail_env[4].assert_not_called()


@pytest.fixture
def signer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth.jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(auth.jwt_manager, "public_key", key.public_key())

    def sign(org_id, changes=None):
        payload = {
            "iss": auth.jwt_manager.issuer,
            "aud": auth.MAIL_AUDIENCE,
            "iat": int(time()) - 1,
            "exp": int(time()) + 3599,
            "type": "access",
            "token_use": "client_credentials",
            "actor_type": "service_account",
            "sub": "service-account:fixture-map-mail",
            "client_id": "fixture-map-mail",
            "org_id": str(org_id),
            "scope": auth.PAYMENT_MAIL_SCOPE,
        }
        payload.update(changes or {})
        payload = {k: v for k, v in payload.items() if v is not None}
        return jwt.encode(payload, key, algorithm="RS256")

    return sign


@pytest_asyncio.fixture
async def http(mail_env):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def database():
        async with mail_env[0]() as db:
            yield db

    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app), base_url="http://fixture") as client:
        yield client


async def test_real_signed_machine_token_and_strict_body(mail_env, http, signer):
    token = signer(mail_env[1].org_id)
    body = mail_env[2].model_dump(mode="json")
    headers = {"Authorization": f"Bearer {token}"}
    result = await http.post("/api/v1/email/payment-notices", json=body, headers=headers)
    assert result.status_code == 200 and result.json()["delivery_status"] == "accepted"
    body["org_id"] = str(uuid.uuid4())
    assert (
        await http.post("/api/v1/email/payment-notices", json=body, headers=headers)
    ).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "other-api"},
        {"aud": [auth.MAIL_AUDIENCE, "other-api"]},
        {"aud": None},
        {"iss": "other-issuer"},
        {"iss": None},
        {"exp": None},
        {"iat": None},
        {"exp": int(time()) - 1},
        {"exp": int(time()) + 7200},
        {"iat": int(time()) + 300},
        {"type": "refresh"},
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
async def test_invalid_signed_claims_cannot_dispatch(mail_env, http, signer, changes):
    result = await http.post(
        "/api/v1/email/payment-notices",
        json=mail_env[2].model_dump(mode="json"),
        headers={"Authorization": f"Bearer {signer(mail_env[1].org_id, changes)}"},
    )
    assert result.status_code == 403
    mail_env[4].assert_not_called()


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-API-Key": "fixture-shared-key"}, {"Authorization": "Bearer invalid"}],
)
async def test_shared_key_or_missing_token_is_not_authority(mail_env, http, headers):
    result = await http.post(
        "/api/v1/email/payment-notices", headers=headers, json=mail_env[2].model_dump(mode="json")
    )
    assert result.status_code == 403
    mail_env[4].assert_not_called()


async def test_symmetric_runtime_fallback_is_refused(mail_env, http, signer, monkeypatch):
    token = signer(mail_env[1].org_id)
    monkeypatch.setattr(auth.jwt_manager, "algorithm", "HS256")
    result = await http.post(
        "/api/v1/email/payment-notices",
        json=mail_env[2].model_dump(mode="json"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 403
    mail_env[4].assert_not_called()
