"""`app/services/spanish_formality.py` — the write rule and the read surfaces.

The HTTP writers are covered in tests/unit/routers/test_spanish_formality_endpoints.py.
This file pins the parts every surface shares:

  * the strict write vocabulary is exactly the register set email_i18n renders;
  * `record_spanish_formality` refuses NULL, is idempotent, and stages ONE audit
    row carrying old -> new on the caller's session (no commit of its own);
  * the claim is stamped only once the person has answered, on every mint path
    (session, OIDC access, ID token), and `/oauth/userinfo` reports it under the
    profile scope;
  * discovery advertises it.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.models import AuditLog
from app.services.audit_logger import AuditEventType
from app.services.email_i18n import (
    SPANISH_FORMALITIES,
    SpanishFormality,
    resolve_formality_for_request,
)
from app.services.spanish_formality import (
    AUDIT_ACTION,
    SPANISH_FORMALITY_CLAIM,
    record_spanish_formality,
    spanish_formality_claims,
    stored_formality,
)


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


def _person(spanish_formality=None):
    return SimpleNamespace(
        id=uuid4(),
        email="persona@example.com",
        tenant_id=uuid4(),
        is_admin=False,
        is_active=True,
        is_service_account=False,
        email_verified=True,
        name="Persona Sintetica",
        spanish_formality=spanish_formality,
    )


def _db():
    db = MagicMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


def test_write_vocabulary_is_exactly_the_rendered_register_set():
    """A write must never accept a register the templates cannot render, and
    every register they render must be writable."""
    assert set(get_args(SpanishFormality)) == set(SPANISH_FORMALITIES) == {"tu", "usted"}


def test_audit_action_is_the_user_update_event():
    assert AUDIT_ACTION == AuditEventType.USER_UPDATE.value == "user.update"


# ---------------------------------------------------------------------------
# Reading the stored value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stored, expected",
    [(None, None), ("tu", "tu"), ("usted", "usted"), ("vosotros", None), ("", None)],
)
def test_stored_formality(stored, expected):
    assert stored_formality(_person(stored)) == expected


def test_stored_formality_tolerates_objects_without_the_column():
    assert stored_formality(SimpleNamespace(id=uuid4())) is None
    assert stored_formality(None) is None
    # A MagicMock attribute is not a string: read as "not answered".
    assert stored_formality(MagicMock()) is None


def test_claim_only_once_answered():
    assert spanish_formality_claims(_person("tu")) == {SPANISH_FORMALITY_CLAIM: "tu"}
    assert spanish_formality_claims(_person("usted")) == {SPANISH_FORMALITY_CLAIM: "usted"}
    # Absent, not null: an unanswered person's token shape is unchanged.
    assert spanish_formality_claims(_person(None)) == {}


# ---------------------------------------------------------------------------
# The write
# ---------------------------------------------------------------------------


def _write(db, user, value, **kw):
    params = {
        "actor_user_id": user.id,
        "actor": "self",
        "actor_type": "user",
        "source": "self",
        "via": "test",
    }
    params.update(kw)
    return record_spanish_formality(db, user, value, **params)


def test_write_sets_the_value_and_stages_one_audit_row():
    db, user = _db(), _person(None)

    change = _write(db, user, "tu", ip_address="203.0.113.7", user_agent="ua/1")

    assert user.spanish_formality == "tu"
    assert (change.previous, change.current, change.changed) == (None, "tu", True)
    db.add.assert_called_once()
    (row,) = db.add.call_args.args
    assert isinstance(row, AuditLog)
    assert row.action == "user.update"
    assert row.resource_type == "user"
    assert row.resource_id == user.id
    assert row.user_id == user.id
    assert row.ip_address == "203.0.113.7"
    assert row.user_agent == "ua/1"
    assert row.details["field"] == "spanish_formality"
    assert (row.details["old"], row.details["new"]) == (None, "tu")


def test_write_never_commits_on_its_own():
    """The caller commits, so the value and its audit row land together."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    _write(db, _person(None), "usted")
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_rewriting_the_stored_value_changes_nothing_and_audits_nothing():
    db, user = _db(), _person("usted")
    change = _write(db, user, "usted")
    assert change.changed is False
    assert change.previous == "usted"
    db.add.assert_not_called()


def test_a_service_write_records_the_product():
    db, user = _db(), _person("tu")
    _write(
        db,
        user,
        "usted",
        actor_user_id=None,
        actor="internal-api-key",
        actor_type="service",
        source="product",
        source_app="nauta",
        organization_id="org-1",
    )
    (row,) = db.add.call_args.args
    assert row.user_id is None
    assert row.details["source_app"] == "nauta"
    assert row.details["organization_id"] == "org-1"
    assert (row.details["old"], row.details["new"]) == ("tu", "usted")


@pytest.mark.parametrize("value", [None, "", "tú", "TU", "vosotros", 1])
def test_write_refuses_anything_but_tu_or_usted(value):
    db, user = _db(), _person("tu")
    with pytest.raises(ValueError):
        _write(db, user, value)
    assert user.spanish_formality == "tu"
    db.add.assert_not_called()


def test_a_non_ip_client_host_is_dropped_not_written():
    """`request.client.host` is not always an IP literal; a non-address would
    fail Postgres' INET cast and roll back the write it records."""
    db, user = _db(), _person(None)
    _write(db, user, "tu", ip_address="testclient")
    (row,) = db.add.call_args.args
    assert row.ip_address is None


def test_after_a_write_the_mailer_picks_the_stored_value():
    db, user = _db(), _person(None)
    assert resolve_formality_for_request(user=user, client_default="usted") == "usted"
    _write(db, user, "tu")
    assert resolve_formality_for_request(user=user, client_default="usted") == "tu"


# ---------------------------------------------------------------------------
# Mint paths
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


async def _mint_session(user):
    from app.services.auth_service import AuthService

    with (
        patch(
            "app.services.entitlements_service.get_user_entitlements",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.org_claims_service.get_user_org_claims_safe",
            AsyncMock(return_value={}),
        ),
        patch("app.services.auth_service.get_redis", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth_service.SessionStore", return_value=AsyncMock()),
    ):
        access_token, _refresh, _session = await AuthService.create_session(
            db=_session_db(), user=user, enforce_session_limit=False
        )
    return _decode(access_token)


@pytest.mark.asyncio
async def test_session_token_carries_the_answer():
    assert (await _mint_session(_person("tu")))[SPANISH_FORMALITY_CLAIM] == "tu"


@pytest.mark.asyncio
async def test_session_token_of_an_unanswered_person_has_no_such_key():
    assert SPANISH_FORMALITY_CLAIM not in await _mint_session(_person(None))


def test_session_refresh_restamps_the_claim():
    from app.services.auth_service import AuthService

    source = inspect.getsource(AuthService.refresh_tokens)
    assert "**spanish_formality_claims(user)" in source


def test_oidc_access_token_paths_stamp_the_claim():
    """Both OIDC access-token seams (auth-code and refresh) plus the ID token."""
    from app.routers.v1 import oauth_provider

    source = inspect.getsource(oauth_provider)
    assert source.count("**spanish_formality_claims(user)") == 2
    assert "claims.update(spanish_formality_claims(user))" in inspect.getsource(
        oauth_provider._generate_id_token
    )


def test_id_token_carries_the_answer_only_once_given():
    from app.routers.v1.oauth_provider import _generate_id_token

    answered = _decode(_generate_id_token(user=_person("usted"), client_id="client-x"))
    unanswered = _decode(_generate_id_token(user=_person(None), client_id="client-x"))

    assert answered[SPANISH_FORMALITY_CLAIM] == "usted"
    assert SPANISH_FORMALITY_CLAIM not in unanswered


# ---------------------------------------------------------------------------
# userinfo + discovery
# ---------------------------------------------------------------------------


async def _userinfo(user, scope: str):
    from app.routers.v1.oauth_provider import userinfo

    request = MagicMock()
    request.headers = {"Authorization": "Bearer access-token"}
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    payload = {"sub": str(user.id), "scope": scope}
    redis = AsyncMock()
    with (
        patch(
            "app.routers.v1.oauth_provider._verify_oauth_token",
            new=AsyncMock(return_value=payload),
        ),
        patch(
            "app.routers.v1.oauth_provider.token_revocation.is_revoked",
            new=AsyncMock(return_value=False),
        ),
    ):
        return await userinfo(request, db, redis)


def _userinfo_user(spanish_formality):
    user = _person(spanish_formality)
    user.first_name = "Persona"
    user.last_name = "Sintetica"
    user.avatar_url = None
    user.profile_image_url = None
    user.updated_at = None
    return user


@pytest.mark.asyncio
async def test_userinfo_reports_the_answer_under_the_profile_scope():
    response = await _userinfo(_userinfo_user("tu"), "openid profile email")
    assert response.spanish_formality == "tu"


@pytest.mark.asyncio
async def test_userinfo_reports_null_until_answered():
    response = await _userinfo(_userinfo_user(None), "openid profile email")
    assert response.spanish_formality is None
    assert "spanish_formality" in response.model_dump()


@pytest.mark.asyncio
async def test_userinfo_without_a_profile_scope_does_not_report_it():
    response = await _userinfo(_userinfo_user("tu"), "email")
    assert response.spanish_formality is None


def test_discovery_advertises_the_claim():
    from app.core.oauth_metadata import authorization_server_metadata

    assert "spanish_formality" in authorization_server_metadata()["claims_supported"]
