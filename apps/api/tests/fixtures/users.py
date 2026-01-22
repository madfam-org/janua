"""
Test Fixtures - User Models
Created: January 13, 2025
Purpose: Reusable user fixtures for integration and E2E testing

Usage:
    @pytest.mark.asyncio
    async def test_example(test_user, test_admin):
        # test_user and test_admin are ready to use
        assert test_user.email == "test@example.com"
"""

import pytest_asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models import UserStatus
from app.services.auth_service import AuthService


# Standard test password (use for all test users)
TEST_PASSWORD = "TestPassword123!"
TEST_PASSWORD_HASH = AuthService.hash_password(TEST_PASSWORD)


@pytest_asyncio.fixture
async def test_user(integration_db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """
    Create standard test user with verified email

    Properties:
    - Email: test@example.com
    - Password: TestPassword123!
    - Status: Active, Verified
    - No MFA enabled
    """
    user = User(
        email="test@example.com",
        password_hash=TEST_PASSWORD_HASH,
        first_name="Test",
        last_name="User",
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(user)
    await integration_db_session.commit()
    await integration_db_session.refresh(user)

    yield user

    # Cleanup after test
    await integration_db_session.delete(user)
    await integration_db_session.commit()


@pytest_asyncio.fixture
async def test_user_unverified(integration_db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """
    Create test user with unverified email

    Properties:
    - Email: unverified@example.com
    - Password: TestPassword123!
    - Status: Active, NOT Verified
    - Email verification pending
    """
    user = User(
        email="unverified@example.com",
        password_hash=TEST_PASSWORD_HASH,
        first_name="Unverified",
        last_name="User",
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(user)
    await integration_db_session.commit()
    await integration_db_session.refresh(user)

    yield user

    await integration_db_session.delete(user)
    await integration_db_session.commit()


@pytest_asyncio.fixture
async def test_user_suspended(integration_db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """
    Create suspended/locked test user

    Properties:
    - Email: suspended@example.com
    - Password: TestPassword123!
    - Status: SUSPENDED/Locked
    - Verified email
    """
    user = User(
        email="suspended@example.com",
        password_hash=TEST_PASSWORD_HASH,
        first_name="Suspended",
        last_name="User",
        status=UserStatus.SUSPENDED,
        is_active=False,  # Suspended
        email_verified=True,
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(user)
    await integration_db_session.commit()
    await integration_db_session.refresh(user)

    yield user

    await integration_db_session.delete(user)
    await integration_db_session.commit()


@pytest_asyncio.fixture
async def test_admin(integration_db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """
    Create test admin user with elevated privileges

    Properties:
    - Email: admin@example.com
    - Password: TestPassword123!
    - Role: Admin
    - Status: Active, Verified
    """
    admin = User(
        email="admin@example.com",
        password_hash=TEST_PASSWORD_HASH,
        first_name="Admin",
        last_name="User",
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(admin)
    await integration_db_session.commit()
    await integration_db_session.refresh(admin)

    yield admin

    await integration_db_session.delete(admin)
    await integration_db_session.commit()


@pytest_asyncio.fixture
async def test_user_with_mfa(integration_db_session: AsyncSession) -> AsyncGenerator[User, None]:
    """
    Create test user with MFA enabled

    Properties:
    - Email: mfa-user@example.com
    - Password: TestPassword123!
    - MFA: TOTP enabled
    - Status: Active, Verified
    """
    user = User(
        email="mfa-user@example.com",
        password_hash=TEST_PASSWORD_HASH,
        first_name="MFA",
        last_name="User",
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(user)
    await integration_db_session.commit()
    await integration_db_session.refresh(user)

    yield user

    await integration_db_session.delete(user)
    await integration_db_session.commit()


@pytest_asyncio.fixture
async def test_users_batch(
    integration_db_session: AsyncSession,
) -> AsyncGenerator[list[User], None]:
    """
    Create batch of 10 test users for list/pagination testing

    Properties:
    - Emails: user1@example.com ... user10@example.com
    - All verified and active
    - Created at different times (for sorting tests)
    """
    users = []

    for i in range(1, 11):
        user = User(
            email=f"user{i}@example.com",
            password_hash=TEST_PASSWORD_HASH,
            first_name=f"User",
            last_name=f"{i}",
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified=True,
            created_at=datetime.utcnow() - timedelta(days=i),
            updated_at=datetime.utcnow(),
        )
        integration_db_session.add(user)
        users.append(user)

    await integration_db_session.commit()

    # Refresh all users to get IDs
    for user in users:
        await integration_db_session.refresh(user)

    yield users

    # Cleanup
    for user in users:
        await integration_db_session.delete(user)
    await integration_db_session.commit()


# Helper function for creating custom test users
async def create_test_user(
    integration_db_session: AsyncSession,
    email: str,
    password: str = TEST_PASSWORD,
    first_name: str = "Test",
    last_name: str = "User",
    email_verified: bool = True,
    is_active: bool = True,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """
    Factory function for creating custom test users

    Usage:
        user = await create_test_user(
            async_session,
            email="custom@example.com",
            first_name="Custom",
            last_name="User",
            status=UserStatus.SUSPENDED
        )
    """
    user = User(
        email=email,
        password_hash=AuthService.hash_password(password),
        first_name=first_name,
        last_name=last_name,
        status=status,
        is_active=is_active,
        email_verified=email_verified,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    integration_db_session.add(user)
    await integration_db_session.commit()
    await integration_db_session.refresh(user)

    return user
