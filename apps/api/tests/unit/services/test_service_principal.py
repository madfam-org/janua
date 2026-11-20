"""Service principals — a technical login must not render as a person.

`User` distinguished `status`, `is_active`, `is_admin` and `tenant_id`, and none
of those answer "is this row a human being?". So every multi-app tenant's
technical logins — a development access account, an importer, an integration
principal — appeared in rosters, assignee pickers and document-signature fields
as colleagues. crea-map's own domain doc declined, correctly, to invent a local
boolean for a single row: the fact belongs to identity, so it lives here.

These tests pin:
  * the flag, and its tolerance of objects that predate the column;
  * the claim, which is stamped ONLY when true — so a person's token shape is
    byte-identical to what it was before this existed;
  * both mint paths (session and OIDC) carrying it;
  * the API surfaces (`/users/me`, the org roster, internal provisioning)
    reporting it, since that is how an app that binds to a `sub` reads it;
  * the rule that provisioning never RE-flags a live identity.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.services.auth_service import AuthService
from app.services.service_principal import (
    SERVICE_ACCOUNT_CLAIM,
    is_service_principal,
    service_principal_claims,
)


def _decode(token: str) -> dict:
    return pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])


def _user(is_service_account=False):
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        tenant_id=uuid4(),
        is_admin=False,
        is_active=True,
        is_service_account=is_service_account,
    )


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------


def test_flag_true_identifies_a_service_principal():
    assert is_service_principal(_user(is_service_account=True)) is True


def test_flag_false_is_a_person():
    assert is_service_principal(_user(is_service_account=False)) is False


def test_missing_attribute_defaults_to_person():
    """An object predating the column (or a test double) reads as a person —
    the same answer migration 015's NOT NULL DEFAULT FALSE gives every
    pre-existing row.

    The default direction is deliberate and is the opposite of the
    fail-closed default used for authorization elsewhere: mistaking a service
    account for a person shows an operator one extra roster row, while
    mistaking a person for a service account would erase a real colleague from
    the UI they work in.
    """
    assert is_service_principal(SimpleNamespace(id=uuid4())) is False
    assert is_service_principal(None) is False


# ---------------------------------------------------------------------------
# The claim shape
# ---------------------------------------------------------------------------


def test_claim_is_stamped_only_for_service_principals():
    assert service_principal_claims(_user(is_service_account=True)) == {SERVICE_ACCOUNT_CLAIM: True}


def test_person_gets_no_claim_key_at_all():
    """Absent, not `false` — so every person's token is byte-identical to what
    it was before this feature existed and no consumer's parsing changes."""
    assert service_principal_claims(_user(is_service_account=False)) == {}


# ---------------------------------------------------------------------------
# The mint paths
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
async def test_session_token_of_a_service_principal_carries_the_claim():
    assert (await _mint_session(_user(is_service_account=True)))[SERVICE_ACCOUNT_CLAIM] is True


@pytest.mark.asyncio
async def test_session_token_of_a_person_carries_no_such_key():
    assert SERVICE_ACCOUNT_CLAIM not in await _mint_session(_user(is_service_account=False))


def test_oidc_mint_paths_stamp_the_claim_too():
    """Both OIDC seams (auth-code and refresh) must carry it, or a technical
    login looks like a person to any app that arrives by OIDC rather than by
    magic link."""
    import importlib
    import inspect

    from app.routers.v1 import oauth_provider

    # The OAuth provider is several modules since the 2026-11-19 split.
    source = "".join(
        inspect.getsource(importlib.import_module(f"app.routers.v1.{m}"))
        for m in oauth_provider.MODULES
    )
    assert source.count("service_principal_claims(user)") == 2


# ---------------------------------------------------------------------------
# Model + migration
# ---------------------------------------------------------------------------


def test_user_model_declares_the_column_not_nullable_defaulting_false():
    from app.models import User

    column = User.__table__.columns["is_service_account"]
    assert column.nullable is False
    assert column.default.arg is False


def test_migration_015_is_additive_and_reentrant():
    """Additive: one new column with a safe default, nothing altered or dropped.

    Re-entrant: environments that ran `Base.metadata.create_all` already carry
    the column while `alembic_version` reads older, and an unguarded add_column
    there raises DuplicateColumn and rolls back the WHOLE chain.
    """
    from pathlib import Path

    source = Path(
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "015_user_is_service_account.py"
    ).read_text()

    assert 'down_revision = "014_capability_links"' in source
    assert 'if "is_service_account" not in existing:' in source
    assert "server_default=sa.false()" in source
    # Nothing destructive in the forward direction.
    for destructive in ("drop_table", "alter_column", "drop_index"):
        assert destructive not in source
    # The only drop_column is in downgrade(), and it is guarded.
    assert source.count("drop_column") == 1
    assert source.index("def downgrade") < source.index("drop_column")


def test_migration_revision_id_fits_the_version_column():
    """`alembic_version.version_num` is VARCHAR(32); a longer id fails the stamp
    write and rolls back the upgrade it just performed."""
    assert len("015_user_is_service_acct") <= 32


# ---------------------------------------------------------------------------
# API surfaces
# ---------------------------------------------------------------------------


def test_user_response_reports_the_flag():
    from app.routers.v1.users import UserResponse

    assert UserResponse.model_fields["is_service_account"].default is False


def test_member_response_reports_the_flag():
    """The roster surface — the one that decides whether a technical login is
    drawn as a teammate."""
    from app.routers.v1.organization_members import MemberResponse

    assert MemberResponse.model_fields["is_service_account"].default is False


def test_provisioning_request_defaults_to_provisioning_a_person():
    from app.schemas.internal import ProvisionUserRequest

    assert ProvisionUserRequest.model_fields["is_service_account"].default is False


def test_provisioning_response_echoes_the_flag():
    from app.schemas.internal import ProvisionUserResponse

    assert ProvisionUserResponse.model_fields["is_service_account"].default is False


def test_provisioning_never_reflags_an_existing_identity():
    """Provisioning is not synchronization. Flipping a live identity between
    "person" and "service" is roster- and signature-visible, so it must not
    happen as a side effect of a roster app's retry: the existing-row branch
    reports the STORED value and writes nothing.
    """
    import inspect

    from app.routers.v1 import internal_users

    source = inspect.getsource(internal_users.provision_user)
    existing_branch = source[
        source.index("if existing is not None:") : source.index("user = User(")
    ]
    assert 'getattr(existing, "is_service_account", False)' in existing_branch
    # No assignment onto the existing row anywhere in that branch.
    assert "existing.is_service_account =" not in existing_branch


@pytest.mark.asyncio
async def test_roster_enrichment_degrades_to_person_when_identities_cannot_be_read():
    """A roster read must never fail — or silently empty — on this enrichment."""
    from app.routers.v1.organization_members import _with_service_principal_flags

    member = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        role="member",
        status="active",
        joined_at="2026-09-02T00:00:00Z",
        metadata=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    responses = await _with_service_principal_flags([member], db)

    assert len(responses) == 1
    assert responses[0].is_service_account is False
