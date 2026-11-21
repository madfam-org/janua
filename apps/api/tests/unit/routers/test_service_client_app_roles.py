"""Unit tests for application roles on org-bound service (client_credentials) clients.

The gap these pin: symbiosis-hcm authorizes ONLY on namespaced application roles
read from the token's `roles` claim (`hcm:hr`, `hcm:admin`, `employee` —
`symbiosis-hcm/apps/api/core/permissions.py`). For a PERSON, janua emits those
from `organization_member_app_roles` (migration 016). For a SERVICE client it
emitted `["service_account"]` plus `admin` plus the UNDERSCORE forms of
`*:admin` scopes — so `hcm:admin` arrived as `hcm_admin`, with the wrong
separator, and `hcm:hr` was never emitted at all. An org-bound service client
(nauta's, kalya's manager) could therefore never satisfy HCM.

The rule under test: the grant for a service client is its `allowed_scopes`.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.routers.v1 import oauth_provider_grants
from app.routers.v1.oauth_provider import (
    _get_client_credentials_claims,
    _service_client_app_roles,
)
from app.services.org_claims_service import ORG_ROLES_CLAIM

pytestmark = pytest.mark.asyncio


def _client(
    *,
    allowed_scopes: list[str],
    organization_id=None,
    client_id: str = "jnc_nauta",
    name: str = "nauta",
):
    client = MagicMock()
    client.client_id = client_id
    client.name = name
    client.allowed_scopes = allowed_scopes
    client.audience = "symbiosis-hcm"
    client.is_confidential = True
    client.organization_id = organization_id
    return client


def _db_returning_org(org):
    """An AsyncSession mock whose single SELECT resolves to `org`."""
    from unittest.mock import AsyncMock

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=org)))
    db.commit = AsyncMock()
    return db


def _org(org_id, slug="crea"):
    org = MagicMock()
    org.id = org_id
    org.slug = slug
    org.subscription_tier = "madfam"
    org.product_tiers = {}
    return org


# ------------------------------------------------------------------ the rule


class TestServiceClientAppRolesPredicate:
    """`_service_client_app_roles` — the four conditions, one test each."""

    async def test_org_bound_allowed_and_requested_scope_is_emitted_verbatim(self):
        """The headline case: nauta requesting `hcm:hr` gets `hcm:hr`, colon kept."""
        client = _client(
            allowed_scopes=["openid", "hcm:hr"],
            organization_id=uuid.uuid4(),
        )
        assert _service_client_app_roles(client, {"openid", "hcm:hr"}) == ["hcm:hr"]

    async def test_scope_not_requested_is_absent(self):
        """Least privilege: allowed but not asked for means not carried."""
        client = _client(
            allowed_scopes=["openid", "hcm:hr"],
            organization_id=uuid.uuid4(),
        )
        assert _service_client_app_roles(client, {"openid"}) == []

    async def test_scope_not_allowed_is_absent(self):
        """Belt-and-braces with `_parse_requested_scopes`: never read an ungranted string."""
        client = _client(allowed_scopes=["openid"], organization_id=uuid.uuid4())
        assert _service_client_app_roles(client, {"openid", "hcm:hr"}) == []

    async def test_client_without_organization_gets_no_app_roles(self):
        """A service with no tenant must not carry tenant authority."""
        client = _client(allowed_scopes=["openid", "hcm:hr"], organization_id=None)
        assert _service_client_app_roles(client, {"openid", "hcm:hr"}) == []

    @pytest.mark.parametrize("org_role", ["owner", "admin", "member"])
    async def test_organization_membership_roles_are_never_emitted(self, org_role):
        """`admin` in a bare `roles` list is the payroll leak the namespace prevents."""
        client = _client(
            allowed_scopes=["openid", org_role],
            organization_id=uuid.uuid4(),
        )
        assert _service_client_app_roles(client, {"openid", org_role}) == []

    async def test_legacy_star_admin_alias_is_not_emitted_with_a_colon(self):
        """`hcm:admin` keeps ONLY its established underscore form; see the caller."""
        client = _client(
            allowed_scopes=["openid", "hcm:admin"],
            organization_id=uuid.uuid4(),
        )
        assert _service_client_app_roles(client, {"openid", "hcm:admin"}) == []

    @pytest.mark.parametrize(
        "scope",
        [
            "openid",  # no namespace
            "hcm_hr",  # underscore, not the app-role shape
            "HCM:HR",  # uppercase
            "hcm:",  # empty role half
            ":hr",  # empty app half
            "hcm:hr:extra",  # two separators
            "1hcm:hr",  # app must start with a letter
            "hcm:1hr",  # role must start with a letter
            "data-api",  # an ordinary scope that is not a role
        ],
    )
    async def test_non_app_role_shapes_are_ignored(self, scope):
        """Shape, not meaning — but a malformed shape is never authority."""
        client = _client(allowed_scopes=[scope], organization_id=uuid.uuid4())
        assert _service_client_app_roles(client, {scope}) == []

    async def test_multiple_roles_are_sorted_and_deduplicated(self):
        """Stable claim across mints: a reordering role list is a meaningless diff."""
        client = _client(
            allowed_scopes=["kalya:manage", "hcm:hr", "hcm:employee"],
            organization_id=uuid.uuid4(),
        )
        assert _service_client_app_roles(client, {"kalya:manage", "hcm:hr", "hcm:employee"}) == [
            "hcm:employee",
            "hcm:hr",
            "kalya:manage",
        ]


# ------------------------------------------------------------- claims builder


class TestClientCredentialsClaims:
    """`_get_client_credentials_claims` — what actually lands in the token."""

    async def test_nauta_requesting_hcm_hr_gets_the_claim_hcm_reads(self):
        org_id = uuid.uuid4()
        client = _client(
            allowed_scopes=["openid", "hcm:hr"],
            organization_id=org_id,
        )

        claims = await _get_client_credentials_claims(
            client, "hcm:hr openid", _db_returning_org(_org(org_id))
        )

        assert claims["roles"] == ["hcm:hr", "service_account"]
        assert claims["org_id"] == str(org_id)
        assert claims["tenant_id"] == str(org_id)
        assert claims["org_slug"] == "crea"
        assert claims["is_admin"] is False

    async def test_org_roles_claim_carries_only_service_account(self):
        """Application roles go ONLY in `roles`; `madfam_org_roles` says what it is.

        A machine principal holds no organization MEMBERSHIP, so putting an app
        role here would tell a consumer the janua ACCOUNT granted it — exactly
        the conflation the namespace exists to stop.
        """
        org_id = uuid.uuid4()
        client = _client(allowed_scopes=["hcm:hr"], organization_id=org_id)

        claims = await _get_client_credentials_claims(
            client, "hcm:hr", _db_returning_org(_org(org_id))
        )

        assert claims[ORG_ROLES_CLAIM] == ["service_account"]
        assert "hcm:hr" not in claims[ORG_ROLES_CLAIM]

    async def test_legacy_underscore_form_is_preserved_alongside(self):
        """Additive, never a replacement: every existing string still ships."""
        org_id = uuid.uuid4()
        client = _client(
            allowed_scopes=["admin", "hcm:admin", "hcm:hr"],
            organization_id=org_id,
        )

        claims = await _get_client_credentials_claims(
            client, "admin hcm:admin hcm:hr", _db_returning_org(_org(org_id))
        )

        assert claims["roles"] == ["admin", "hcm:hr", "hcm_admin", "service_account"]
        assert claims["is_admin"] is True

    async def test_client_without_org_keeps_todays_exact_shape(self):
        """No org, no app roles — and the rest of the claim is byte-for-byte as before."""
        client = _client(
            allowed_scopes=["openid", "hcm:hr", "hcm:admin"],
            organization_id=None,
        )
        from unittest.mock import AsyncMock

        claims = await _get_client_credentials_claims(
            client, "openid hcm:hr hcm:admin", AsyncMock()
        )

        assert claims["roles"] == ["hcm_admin", "service_account"]
        assert "org_id" not in claims
        assert claims[ORG_ROLES_CLAIM] == ["service_account"]


# --------------------------------------------------------- full grant handler


class TestClientCredentialsGrantHandler:
    """`_handle_client_credentials_grant` — end to end through the token mint."""

    async def test_minted_token_carries_the_app_role(self):
        from unittest.mock import patch

        import app.routers.v1.oauth_provider as oauth_provider_module
        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        org_id = uuid.uuid4()
        client = _client(
            allowed_scopes=["openid", "hcm:hr"],
            organization_id=org_id,
        )
        db = _db_returning_org(_org(org_id))

        with patch.object(
            oauth_provider_module.jwt_manager,
            "create_access_token",
            return_value=("encoded_access_token", "jti", None),
        ) as mock_create:
            response = await _handle_client_credentials_grant(
                client=client,
                requested_scope="openid hcm:hr",
                db=db,
            )

        assert response.access_token == "encoded_access_token"
        assert response.refresh_token is None
        assert response.scope == "hcm:hr openid"
        db.commit.assert_called_once()

        _, kwargs = mock_create.call_args
        assert kwargs["user_id"] == "service-account:jnc_nauta"
        claims = kwargs["additional_claims"]
        assert claims["roles"] == ["hcm:hr", "service_account"]
        assert claims["org_id"] == str(org_id)
        assert claims["token_use"] == "client_credentials"
        assert claims["actor_type"] == "service_account"

    async def test_audit_row_is_written_when_app_roles_are_minted(self):
        """A machine reading payroll leaves a durable record of the USE."""
        from unittest.mock import AsyncMock, patch

        import app.routers.v1.oauth_provider as oauth_provider_module
        from app.routers.v1.oauth_provider import _handle_client_credentials_grant
        from app.services.audit_logger import AuditEventType

        org_id = uuid.uuid4()
        client = _client(allowed_scopes=["hcm:hr"], organization_id=org_id)
        db = _db_returning_org(_org(org_id))

        audit_logger = AsyncMock()
        with (
            patch.object(
                oauth_provider_module.jwt_manager,
                "create_access_token",
                return_value=("t", "jti", None),
            ),
            patch.object(oauth_provider_grants, "AuditLogger", return_value=audit_logger),
        ):
            await _handle_client_credentials_grant(client=client, requested_scope="hcm:hr", db=db)

        audit_logger.log.assert_awaited_once()
        kwargs = audit_logger.log.await_args.kwargs
        assert kwargs["event_type"] is AuditEventType.SERVICE_TOKEN_APP_ROLES
        assert kwargs["details"]["client_id"] == "jnc_nauta"
        assert kwargs["details"]["org_id"] == str(org_id)
        assert kwargs["details"]["app_roles"] == ["hcm:hr"]
        # The secret never reaches the trail.
        assert "client_secret" not in kwargs["details"]

    async def test_no_audit_row_for_an_ordinary_service_token(self):
        """An ordinary mint writes nothing; its cost is unchanged."""
        from unittest.mock import AsyncMock, patch

        import app.routers.v1.oauth_provider as oauth_provider_module
        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        client = _client(allowed_scopes=["openid"], organization_id=None)
        db = AsyncMock()
        db.commit = AsyncMock()

        audit_logger = AsyncMock()
        with (
            patch.object(
                oauth_provider_module.jwt_manager,
                "create_access_token",
                return_value=("t", "jti", None),
            ),
            patch.object(oauth_provider_grants, "AuditLogger", return_value=audit_logger),
        ):
            await _handle_client_credentials_grant(client=client, requested_scope="openid", db=db)

        audit_logger.log.assert_not_awaited()

    async def test_ungranted_scope_still_fails_the_way_it_fails_today(self):
        """Scopes requested but not allowed keep failing closed."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.routers.v1.oauth_provider import _handle_client_credentials_grant

        client = _client(allowed_scopes=["openid"], organization_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            await _handle_client_credentials_grant(
                client=client, requested_scope="openid hcm:hr", db=AsyncMock()
            )

        assert exc_info.value.status_code == 400
        assert "invalid_scope" in exc_info.value.detail
