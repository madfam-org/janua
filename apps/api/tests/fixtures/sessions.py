"""
Test Fixtures - Session Models
Created: January 13, 2025
Purpose: Reusable session fixtures for authentication testing

Usage:
    @pytest.mark.asyncio
    async def test_example(test_session, test_user):
        assert test_session.user_id == test_user.id
        assert test_session.is_active
"""

import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, User


def _create_test_token(user_id: str, token_type: str = "access") -> str:
    """Generate a simple test token string"""
    return f"test_{token_type}_token_{user_id}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def test_session(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[Session, None]:
    """
    Create valid active session for test_user

    Properties:
    - User: test_user
    - Status: Active
    - Tokens: Valid access + refresh tokens
    - Device: Test device
    """
    access_token = _create_test_token(str(test_user.id), "access")
    refresh_token = _create_test_token(str(test_user.id), "refresh")

    session = Session(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token=access_token,
        refresh_token=refresh_token,
        access_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        refresh_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0 (Test Browser)",
        device_name="Test Desktop",
        is_active=True,
        created_at=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )

    async_session.add(session)
    await async_session.commit()
    await async_session.refresh(session)

    yield session

    # Cleanup
    await async_session.delete(session)
    await async_session.commit()


@pytest.fixture
async def test_session_expired(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[Session, None]:
    """
    Create expired session for testing expiration handling

    Properties:
    - User: test_user
    - Status: Expired (1 hour ago)
    - Tokens: Expired
    """
    access_token = _create_test_token(str(test_user.id), "access")
    refresh_token = _create_test_token(str(test_user.id), "refresh")

    session = Session(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token=access_token,
        refresh_token=refresh_token,
        access_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        refresh_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0 (Test Browser)",
        device_name="Test Desktop",
        is_active=True,
        created_at=datetime.utcnow() - timedelta(days=2),
        last_activity=datetime.utcnow() - timedelta(hours=2),
        expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
    )

    async_session.add(session)
    await async_session.commit()
    await async_session.refresh(session)

    yield session

    await async_session.delete(session)
    await async_session.commit()


@pytest.fixture
async def test_session_revoked(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[Session, None]:
    """
    Create revoked session for testing revocation handling

    Properties:
    - User: test_user
    - Status: REVOKED (manually invalidated)
    - Tokens: Invalid
    """
    access_token = _create_test_token(str(test_user.id), "access")
    refresh_token = _create_test_token(str(test_user.id), "refresh")

    session = Session(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token=access_token,
        refresh_token=refresh_token,
        access_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        refresh_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0 (Test Browser)",
        device_name="Test Desktop",
        is_active=False,  # Revoked
        revoked_at=datetime.utcnow(),
        created_at=datetime.utcnow() - timedelta(hours=2),
        last_activity=datetime.utcnow() - timedelta(minutes=30),
        expires_at=datetime.utcnow() + timedelta(hours=22),  # Would be valid if not revoked
    )

    async_session.add(session)
    await async_session.commit()
    await async_session.refresh(session)

    yield session

    await async_session.delete(session)
    await async_session.commit()


# Helper function for creating custom sessions
async def create_test_session(
    async_session: AsyncSession,
    user: User,
    ip_address: str = "127.0.0.1",
    user_agent: str = "Test Browser",
    device_name: str = "desktop",
    is_active: bool = True,
    expires_in_hours: int = 24,
) -> Session:
    """
    Factory function for creating custom test sessions

    Usage:
        session = await create_test_session(
            async_session,
            user=test_user,
            device_name="mobile",
            expires_in_hours=1
        )
    """
    access_token = _create_test_token(str(user.id), "access")
    refresh_token = _create_test_token(str(user.id), "refresh")

    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        access_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        refresh_token_jti=f"jti_{uuid.uuid4().hex[:16]}",
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=device_name,
        is_active=is_active,
        created_at=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
    )

    async_session.add(session)
    await async_session.commit()
    await async_session.refresh(session)

    return session
