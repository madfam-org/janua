"""
Shared test fixtures for service unit tests.

This module provides properly configured async mocks for database sessions,
services, and other dependencies used across service tests.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_db_session():
    """
    Properly configured async database session mock.

    Returns an AsyncMock that simulates SQLAlchemy AsyncSession behavior:
    - execute() chain: execute() → scalars() → first()
    - Transaction methods: commit(), rollback(), close()
    - Context manager support

    Usage:
        async def test_example(mock_db_session):
            # Configure return value
            mock_user = User(id=uuid4(), email="test@example.com")
            mock_result = AsyncMock()
            mock_result.scalars.return_value.first.return_value = mock_user
            mock_db_session.execute.return_value = mock_result

            # Use in service
            service = AuthService(mock_db_session)
            user = await service.get_user_by_email("test@example.com")
            assert user.email == "test@example.com"
    """
    session = AsyncMock()

    # Configure execute chain for SELECT queries
    mock_result = AsyncMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    # Configure transaction methods
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    # Configure add/delete operations
    session.add = MagicMock()
    session.delete = AsyncMock()

    return session


@pytest.fixture
def mock_jwt_service():
    """
    Mock JWT service for token operations.

    Returns an AsyncMock configured for common JWT operations:
    - create_access_token(): Returns mock access token
    - create_refresh_token(): Returns mock refresh token
    - decode_token(): Returns mock payload
    - verify_token(): Returns True for valid tokens

    Usage:
        async def test_example(mock_jwt_service):
            token = await mock_jwt_service.create_access_token(user_id="123")
            assert token == "mock_access_token"
    """
    service = AsyncMock()

    # Configure token generation
    service.create_access_token.return_value = "mock_access_token"
    service.create_refresh_token.return_value = "mock_refresh_token"

    # Configure token validation
    service.decode_token.return_value = {
        "user_id": str(uuid4()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        "type": "access",
    }
    service.verify_token.return_value = True

    return service


@pytest.fixture
def mock_email_service():
    """
    Mock email service for sending emails.

    Returns an AsyncMock configured for common email operations:
    - send_verification_email(): Returns True
    - send_password_reset_email(): Returns True
    - send_welcome_email(): Returns True

    Usage:
        async def test_example(mock_email_service):
            result = await mock_email_service.send_verification_email(
                email="test@example.com",
                token="verification_token"
            )
            assert result is True
    """
    service = AsyncMock()

    # Configure email sending operations
    service.send_verification_email.return_value = True
    service.send_password_reset_email.return_value = True
    service.send_welcome_email.return_value = True
    service.send_mfa_code.return_value = True

    return service


@pytest.fixture
def mock_session_service():
    """
    Mock session service for session management.

    Returns an AsyncMock configured for session operations:
    - create_session(): Returns mock session
    - refresh_session(): Returns new mock session
    - revoke_session(): Returns True
    - get_active_sessions(): Returns list of mock sessions

    Usage:
        async def test_example(mock_session_service):
            session = await mock_session_service.create_session(user_id="123")
            assert session.user_id == "123"
    """
    service = AsyncMock()

    # Configure session operations
    mock_session = MagicMock()
    mock_session.id = uuid4()
    mock_session.user_id = uuid4()
    mock_session.created_at = datetime.utcnow()
    mock_session.expires_at = datetime.utcnow() + timedelta(days=7)

    service.create_session.return_value = mock_session
    service.refresh_session.return_value = mock_session
    service.revoke_session.return_value = True
    service.get_active_sessions.return_value = [mock_session]

    return service


@pytest.fixture
def sample_user():
    """
    Sample user object for testing.

    Returns a mock User object with realistic data.
    """
    from app.models import User

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    user.hashed_password = (
        "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqYj5qJ7.C"  # "TestPassword123!"
    )
    user.is_active = True
    user.is_verified = False
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()

    return user


@pytest.fixture
def sample_session():
    """
    Sample session object for testing.

    Returns a mock Session object with realistic data.
    """
    from app.models import Session

    session = MagicMock(spec=Session)
    session.id = uuid4()
    session.user_id = uuid4()
    session.token = "sample_session_token"
    session.refresh_token = "sample_refresh_token"
    session.created_at = datetime.utcnow()
    session.expires_at = datetime.utcnow() + timedelta(days=7)
    session.is_active = True

    return session


@pytest.fixture
def sample_organization():
    """
    Sample organization object for testing.

    Returns a mock Organization object with realistic data.
    """
    from app.models import Organization

    org = MagicMock(spec=Organization)
    org.id = uuid4()
    org.name = "Test Organization"
    org.slug = "test-org"
    org.created_at = datetime.utcnow()
    org.updated_at = datetime.utcnow()

    return org
