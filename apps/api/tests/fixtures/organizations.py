"""
Test Fixtures - Organization Models
Created: January 13, 2025
Purpose: Reusable organization fixtures for multi-tenancy testing

Usage:
    @pytest.mark.asyncio
    async def test_example(test_organization, test_user):
        assert test_organization.owner_id == test_user.id
"""

import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, OrganizationMember, OrganizationRole

# Alias for backward compatibility with existing tests
MemberRole = OrganizationRole


@pytest.fixture
async def test_organization(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[Organization, None]:
    """
    Create test organization owned by test_user

    Properties:
    - Name: Test Organization
    - Owner: test_user
    - Status: Active
    - No seat limits
    """
    org = Organization(
        name="Test Organization",
        slug="test-organization",
        owner_id=test_user.id,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    # Add owner as admin member
    member = OrganizationMember(
        organization_id=org.id,
        user_id=test_user.id,
        role=MemberRole.OWNER,
        joined_at=datetime.utcnow(),
    )
    async_session.add(member)
    await async_session.commit()

    yield org

    # Cleanup
    await async_session.delete(member)
    await async_session.delete(org)
    await async_session.commit()


@pytest.fixture
async def test_organization_with_members(
    async_session: AsyncSession, test_user: User, test_users_batch: list[User]
) -> AsyncGenerator[Organization, None]:
    """
    Create organization with multiple members at different roles

    Properties:
    - Owner: test_user (OWNER role)
    - 3 Admins (from test_users_batch)
    - 4 Members (from test_users_batch)
    - 3 Viewers (from test_users_batch)
    """
    org = Organization(
        name="Multi-Member Organization",
        slug="multi-member-org",
        owner_id=test_user.id,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    # Add owner
    owner_member = OrganizationMember(
        organization_id=org.id,
        user_id=test_user.id,
        role=MemberRole.OWNER,
        joined_at=datetime.utcnow(),
    )
    async_session.add(owner_member)

    members_to_cleanup = [owner_member]

    # Add 3 admins
    for i in range(3):
        member = OrganizationMember(
            organization_id=org.id,
            user_id=test_users_batch[i].id,
            role=MemberRole.ADMIN,
            joined_at=datetime.utcnow() - timedelta(days=i + 1),
        )
        async_session.add(member)
        members_to_cleanup.append(member)

    # Add 4 members
    for i in range(3, 7):
        member = OrganizationMember(
            organization_id=org.id,
            user_id=test_users_batch[i].id,
            role=MemberRole.MEMBER,
            joined_at=datetime.utcnow() - timedelta(days=i + 1),
        )
        async_session.add(member)
        members_to_cleanup.append(member)

    # Add 3 viewers
    for i in range(7, 10):
        member = OrganizationMember(
            organization_id=org.id,
            user_id=test_users_batch[i].id,
            role=MemberRole.VIEWER,
            joined_at=datetime.utcnow() - timedelta(days=i + 1),
        )
        async_session.add(member)
        members_to_cleanup.append(member)

    await async_session.commit()

    yield org

    # Cleanup
    for member in members_to_cleanup:
        await async_session.delete(member)
    await async_session.delete(org)
    await async_session.commit()


@pytest.fixture
async def test_organization_suspended(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[Organization, None]:
    """
    Create suspended organization for testing access restrictions

    Properties:
    - Status: SUSPENDED
    - Owner: test_user
    - Access should be restricted
    """
    org = Organization(
        name="Suspended Organization",
        slug="suspended-org",
        owner_id=test_user.id,
        is_active=False,  # Suspended
        suspended_at=datetime.utcnow(),
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow(),
    )

    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    yield org

    await async_session.delete(org)
    await async_session.commit()


@pytest.fixture
async def test_organizations_batch(
    async_session: AsyncSession, test_user: User
) -> AsyncGenerator[list[Organization], None]:
    """
    Create batch of 5 organizations for list/pagination testing

    Properties:
    - All owned by test_user
    - All active
    - Created at different times (for sorting)
    """
    orgs = []

    for i in range(1, 6):
        org = Organization(
            name=f"Test Organization {i}",
            slug=f"test-org-{i}",
            owner_id=test_user.id,
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=i),
            updated_at=datetime.utcnow(),
        )
        async_session.add(org)
        orgs.append(org)

    await async_session.commit()

    for org in orgs:
        await async_session.refresh(org)

    yield orgs

    # Cleanup
    for org in orgs:
        await async_session.delete(org)
    await async_session.commit()


# Helper function for creating custom organizations
async def create_test_organization(
    async_session: AsyncSession,
    name: str,
    owner: User,
    slug: str = None,
    is_active: bool = True,
    members: list[tuple[User, MemberRole]] = None,
) -> Organization:
    """
    Factory function for creating custom test organizations

    Usage:
        org = await create_test_organization(
            async_session,
            name="Custom Org",
            owner=test_user,
            members=[
                (user1, MemberRole.ADMIN),
                (user2, MemberRole.MEMBER),
            ]
        )
    """
    if not slug:
        slug = name.lower().replace(" ", "-")

    org = Organization(
        name=name,
        slug=slug,
        owner_id=owner.id,
        is_active=is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    # Add owner as OWNER role
    owner_member = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role=MemberRole.OWNER,
        joined_at=datetime.utcnow(),
    )
    async_session.add(owner_member)

    # Add additional members
    if members:
        for user, role in members:
            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=role,
                joined_at=datetime.utcnow(),
            )
            async_session.add(member)

    await async_session.commit()

    return org
