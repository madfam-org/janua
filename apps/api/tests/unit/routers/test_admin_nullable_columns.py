"""
Regression tests for admin endpoints that 500'd on legacy data.

Three production bugs (browser-verified for admin@madfam.io on app.janua.dev):

  1. GET /api/v1/admin/users -> 500
     Root cause: User.is_admin / mfa_enabled / email_verified are nullable=True
     in migration 000_init.py. UserAdminResponse declared them as non-Optional
     `bool`, so any legacy NULL row crashed pydantic validation for the whole list.

  2. GET /api/v1/admin/organizations -> 500 (manifested as "Network request failed"
     in the dashboard after the SDK fallback to the non-admin endpoint also failed).
     Root cause: Organization.billing_plan / owner_id are nullable=True; the
     OrganizationAdminResponse and the user-scoped OrganizationResponse both
     required `billing_plan: str` and `owner_id: str`.

  3. GET /api/v1/sessions -> 500 (separate from the SDK 404 that was the primary
     symptom). Router referenced UserSession.last_activity_at, but the model
     column is `last_activity` (per migration 000_init.py).

These tests construct the response models directly with rows containing the
nullable fields set to None and assert no validation error is raised.
"""
from datetime import datetime
from uuid import uuid4

from app.models import Organization, User, UserStatus
from app.routers.v1.admin import OrganizationAdminResponse, UserAdminResponse

# NOTE: `app/routers/v1/organizations.py` (file) is shadowed at import time by
# the `app/routers/v1/organizations/` package. The package's `core.py` is what
# the FastAPI app actually serves. Import the response model from the package
# so the test matches production reality.
from app.routers.v1.organizations.schemas import OrganizationResponse


def _legacy_user_with_nulls() -> User:
    """Simulate a legacy user row predating the boolean defaults backfill."""
    user = User(
        id=uuid4(),
        email="legacy@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
        # All three of these were added later as nullable=True and could be NULL:
        email_verified=None,
        is_admin=None,
        mfa_enabled=None,
        created_at=datetime.utcnow(),
        updated_at=None,
        last_sign_in_at=None,
    )
    return user


def _build_user_admin_response(user: User) -> UserAdminResponse:
    """Mirror the construction logic in admin.list_all_users()."""
    return UserAdminResponse(
        id=str(user.id),
        email=user.email,
        email_verified=bool(user.email_verified),
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status.value if user.status else UserStatus.ACTIVE.value,
        mfa_enabled=bool(user.mfa_enabled),
        is_admin=bool(user.is_admin),
        organizations_count=0,
        sessions_count=0,
        oauth_providers=[],
        passkeys_count=0,
        created_at=user.created_at,
        updated_at=user.updated_at or user.created_at,
        last_sign_in_at=user.last_sign_in_at,
    )


class TestAdminUsersNullableColumns:
    """Regression: GET /api/v1/admin/users no longer 500s on legacy NULL booleans."""

    def test_legacy_user_with_null_booleans_serializes_cleanly(self):
        user = _legacy_user_with_nulls()
        response = _build_user_admin_response(user)

        # Coalesced None -> False (matches column default in the model definition).
        assert response.email_verified is False
        assert response.is_admin is False
        assert response.mfa_enabled is False

        # updated_at falls back to created_at when null.
        assert response.updated_at == user.created_at

        # last_sign_in_at remains Optional and stays None.
        assert response.last_sign_in_at is None

    def test_active_admin_with_all_flags_set(self):
        user = User(
            id=uuid4(),
            email="admin@madfam.io",
            password_hash="hashed",
            status=UserStatus.ACTIVE,
            email_verified=True,
            is_admin=True,
            mfa_enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        response = _build_user_admin_response(user)

        assert response.email_verified is True
        assert response.is_admin is True
        assert response.mfa_enabled is True

    def test_user_with_null_status_falls_back_to_active(self):
        """Defensive: even if the enum read somehow returns None, no crash."""
        user = _legacy_user_with_nulls()
        user.status = None
        response = _build_user_admin_response(user)
        assert response.status == UserStatus.ACTIVE.value


def _build_admin_org_response(org: Organization) -> OrganizationAdminResponse:
    """Mirror admin.list_all_organizations() construction."""
    return OrganizationAdminResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        owner_id=str(org.owner_id) if org.owner_id else "",
        owner_email="unknown",
        billing_plan=org.billing_plan or "free",
        billing_email=org.billing_email,
        members_count=0,
        created_at=org.created_at,
        updated_at=org.updated_at or org.created_at,
    )


class TestAdminOrganizationsNullableColumns:
    """Regression: GET /api/v1/admin/organizations no longer 500s on legacy rows."""

    def test_legacy_org_with_null_billing_plan_serializes(self):
        org = Organization(
            id=uuid4(),
            name="Legacy Org",
            slug="legacy-org",
            owner_id=None,  # Orphaned (FK was nullable in 000_init).
            billing_plan=None,  # Pre-default backfill.
            created_at=datetime.utcnow(),
            updated_at=None,
        )
        response = _build_admin_org_response(org)

        assert response.billing_plan == "free"
        assert response.owner_id == ""
        assert response.updated_at == org.created_at


def _build_user_org_response(org: Organization, owner_email=None, member_count=0) -> OrganizationResponse:
    """Mirror organizations/core.list_organizations() construction (non-admin path)."""
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        billing_email=org.billing_email,
        created_at=org.created_at,
        updated_at=org.updated_at or org.created_at,
        member_count=member_count or 0,
        settings=org.settings or {},
        plan=getattr(org, "subscription_tier", None)
        or getattr(org, "billing_plan", None)
        or "community",
        owner_email=owner_email,
    )


class TestUserOrganizationsNullableColumns:
    """Regression: GET /api/v1/organizations (non-admin) no longer 500s on legacy rows.

    This is the dashboard's fallback when the admin endpoint isn't accessible,
    so it must be hardened too. The user-scoped router lives in
    apps/api/app/routers/v1/organizations/core.py (the package, which shadows
    the legacy organizations.py file with the same name).
    """

    def test_legacy_org_with_null_updated_at(self):
        org = Organization(
            id=uuid4(),
            name="Legacy Org",
            slug="legacy-org",
            owner_id=None,
            billing_plan=None,
            subscription_tier=None,
            description=None,
            logo_url=None,
            settings=None,
            org_metadata=None,
            created_at=datetime.utcnow(),
            updated_at=None,
        )
        response = _build_user_org_response(org, owner_email=None, member_count=None)

        # plan falls back to "community" (the legacy default) when both
        # subscription_tier and billing_plan are NULL.
        assert response.plan == "community"
        # updated_at falls back to created_at to satisfy the required schema field.
        assert response.updated_at == org.created_at
        assert response.member_count == 0
        assert response.settings == {}
        assert response.owner_email is None


class TestSessionsModelColumnFix:
    """Regression: GET /api/v1/sessions referenced UserSession.last_activity_at.

    The model column is `last_activity` (no `_at`). Importing the router with
    the wrong attribute would not crash at import time (SQLAlchemy attributes
    are looked up lazily), but the first request would AttributeError.
    """

    def test_session_model_has_last_activity_not_last_activity_at(self):
        from app.models import Session as UserSession

        # The only column should be `last_activity`. The router previously
        # referenced `last_activity_at` which does not exist on the model.
        assert hasattr(UserSession, "last_activity")
        assert not hasattr(UserSession, "last_activity_at")

    def test_router_uses_correct_column_name(self):
        """The fixed router file should not reference the bad column."""
        import inspect

        from app.routers.v1 import sessions as sessions_router

        source = inspect.getsource(sessions_router)
        # The pydantic *response field* is named last_activity_at (public contract);
        # but every SQLAlchemy access must use .last_activity, not .last_activity_at.
        # We assert that there is no `UserSession.last_activity_at` or
        # `session.last_activity_at` in the source.
        assert "UserSession.last_activity_at" not in source
        assert "session.last_activity_at" not in source
        # Sanity: the correct attribute IS used.
        assert "UserSession.last_activity" in source
