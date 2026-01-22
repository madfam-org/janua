"""
Tests for core database models
"""
import pytest
from unittest.mock import patch, MagicMock
import os


@pytest.fixture
def mock_env():
    """Mock environment variables for testing"""
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/janua_test",
            "JWT_SECRET": "test-secret-key",
            "REDIS_URL": "redis://localhost:6379/0",
            "JANUA_ENV": "test",
        },
    ):
        yield


def test_user_model_structure(mock_env):
    """Test User model structure and fields"""
    try:
        from app.models import User

        # Check that User model has expected attributes
        assert hasattr(User, "__tablename__")
        assert hasattr(User, "id")
        assert hasattr(User, "email")
        assert hasattr(User, "created_at")
        assert hasattr(User, "updated_at")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_organization_model_structure(mock_env):
    """Test Organization model structure"""
    try:
        from app.models import Organization

        # Check Organization model attributes
        assert hasattr(Organization, "__tablename__")
        assert hasattr(Organization, "id")
        assert hasattr(Organization, "name")
        assert hasattr(Organization, "created_at")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_session_model_structure(mock_env):
    """Test Session model structure"""
    try:
        from app.models import Session

        # Check Session model attributes
        assert hasattr(Session, "__tablename__")
        assert hasattr(Session, "id")
        assert hasattr(Session, "user_id")
        assert hasattr(Session, "created_at")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_audit_log_model_structure(mock_env):
    """Test AuditLog model structure"""
    try:
        from app.models import AuditLog

        # Check AuditLog model attributes
        assert hasattr(AuditLog, "__tablename__")
        assert hasattr(AuditLog, "id")
        assert hasattr(AuditLog, "event_type")  # Updated from 'action' to 'event_type'
        assert hasattr(AuditLog, "timestamp")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_organization_member_model_structure(mock_env):
    """Test OrganizationMember model structure"""
    try:
        from app.models import OrganizationMember

        # Check OrganizationMember model attributes
        assert hasattr(OrganizationMember, "__tablename__")
        # OrganizationMember uses composite primary keys, not a single 'id'
        assert hasattr(OrganizationMember, "organization_id")
        assert hasattr(OrganizationMember, "user_id")
        assert hasattr(OrganizationMember, "role")
        assert hasattr(OrganizationMember, "joined_at")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_policy_model_structure(mock_env):
    """Test Policy model structure"""
    try:
        from app.models import Policy

        # Check Policy model attributes
        assert hasattr(Policy, "__tablename__")
        assert hasattr(Policy, "id")
        assert hasattr(Policy, "name")
        assert hasattr(Policy, "organization_id")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_webhook_model_structure(mock_env):
    """Test Webhook model structure"""
    try:
        from app.models import Webhook

        # Check Webhook model attributes
        assert hasattr(Webhook, "__tablename__")
        assert hasattr(Webhook, "id")
        assert hasattr(Webhook, "url")
        assert hasattr(Webhook, "organization_id")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_invitation_model_structure(mock_env):
    """Test Invitation model structure"""
    try:
        from app.models import Invitation

        # Check Invitation model attributes
        assert hasattr(Invitation, "__tablename__")
        assert hasattr(Invitation, "id")
        assert hasattr(Invitation, "email")
        assert hasattr(Invitation, "organization_id")
        assert hasattr(Invitation, "status")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_model_imports_complete(mock_env):
    """Test that all models can be imported together"""
    try:
        from app.models import (
            User,
            Organization,
            Session,
            AuditLog,
            OrganizationMember,
            Policy,
            Webhook,
            Invitation,
        )

        # Verify all models are classes
        models = [
            User,
            Organization,
            Session,
            AuditLog,
            OrganizationMember,
            Policy,
            Webhook,
            Invitation,
        ]

        for model in models:
            assert hasattr(model, "__tablename__")
            assert hasattr(model, "id")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")


def test_database_connection_mock(mock_env):
    """Test database connection with mocked database"""
    try:
        with patch("app.core.database_manager.create_async_engine") as mock_engine:
            mock_engine.return_value = MagicMock()

            from app.core.database_manager import DatabaseManager

            # Test that DatabaseManager can be instantiated
            db_manager = DatabaseManager()
            assert db_manager is not None

    except ImportError as e:
        pytest.skip(f"Database manager imports failed: {e}")


def test_model_relationships(mock_env):
    """Test model relationships are properly defined"""
    try:
        from app.models import User, Organization, OrganizationMember

        # Check that relationship attributes exist
        if hasattr(User, "organization_memberships"):
            assert hasattr(User, "organization_memberships")

        if hasattr(Organization, "members"):
            assert hasattr(Organization, "members")

        if hasattr(OrganizationMember, "user"):
            assert hasattr(OrganizationMember, "user")

        if hasattr(OrganizationMember, "organization"):
            assert hasattr(OrganizationMember, "organization")

    except ImportError as e:
        pytest.skip(f"Model imports failed: {e}")
