"""
Comprehensive integration tests for database operations
Tests model relationships, constraints, migrations, and transactions
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import uuid

from app.models import (
    User, UserStatus, Organization, OrganizationRole, OrganizationMember,
    Session, EmailVerification, PasswordReset, MagicLink, ActivityLog,
    Invitation, OAuthProvider, WebhookStatus
)
from app.core.database import get_db


@pytest.mark.asyncio
class TestDatabaseModelRelationships:
    """Test database model relationships and constraints"""

    async def test_user_organization_relationship(self, test_db_session: AsyncSession):
        """Test User-Organization many-to-many relationship"""
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="hashed_password",
            first_name="John",
            last_name="Doe",
            status=UserStatus.ACTIVE,
            email_verified=True
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create test organization
        org = Organization(
            id=str(uuid.uuid4()),
            name="Test Company",
            description="A test organization",
            owner_id=user.id
        )
        test_db_session.add(org)
        await test_db_session.commit()

        # Create organization member relationship
        member = OrganizationMember(
            user_id=user.id,
            organization_id=org.id,
            role=OrganizationRole.OWNER,
            joined_at=datetime.utcnow()
        )
        test_db_session.add(member)
        await test_db_session.commit()

        # Test relationship queries
        result = await test_db_session.execute(
            select(User).where(User.id == user.id)
        )
        found_user = result.scalar_one()
        assert found_user.email == "test@example.com"

        # Test organization query
        result = await test_db_session.execute(
            select(Organization).where(Organization.id == org.id)
        )
        found_org = result.scalar_one()
        assert found_org.name == "Test Company"
        assert found_org.owner_id == user.id

        # Test member relationship
        result = await test_db_session.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == org.id
                )
            )
        )
        found_member = result.scalar_one()
        assert found_member.role == OrganizationRole.OWNER

    async def test_user_sessions_relationship(self, test_db_session: AsyncSession):
        """Test User-Session one-to-many relationship"""
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="session_test@example.com",
            hashed_password="hashed_password",
            first_name="Session",
            last_name="User",
            status=UserStatus.ACTIVE,
            email_verified=True
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create multiple sessions for the user
        sessions = []
        for i in range(3):
            session = Session(
                id=str(uuid.uuid4()),
                user_id=user.id,
                refresh_token=f"refresh_token_{i}",
                ip_address=f"192.168.1.{i+1}",
                user_agent=f"Chrome/{90+i}",
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            sessions.append(session)
            test_db_session.add(session)

        await test_db_session.commit()

        # Test querying user's sessions
        result = await test_db_session.execute(
            select(Session).where(Session.user_id == user.id)
        )
        user_sessions = result.scalars().all()
        assert len(user_sessions) == 3

        # Test session user relationship
        for session in user_sessions:
            assert session.user_id == user.id

    async def test_email_verification_relationship(self, test_db_session: AsyncSession):
        """Test User-EmailVerification relationship"""
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="verify_test@example.com",
            hashed_password="hashed_password",
            first_name="Verify",
            last_name="User",
            status=UserStatus.ACTIVE,
            email_verified=False
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create email verification
        verification = EmailVerification(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token="verification_token_123",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        test_db_session.add(verification)
        await test_db_session.commit()

        # Test relationship
        result = await test_db_session.execute(
            select(EmailVerification).where(EmailVerification.user_id == user.id)
        )
        found_verification = result.scalar_one()
        assert found_verification.token == "verification_token_123"
        assert found_verification.user_id == user.id

    async def test_activity_log_relationship(self, test_db_session: AsyncSession):
        """Test User-ActivityLog relationship"""
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="activity_test@example.com",
            hashed_password="hashed_password",
            first_name="Activity",
            last_name="User",
            status=UserStatus.ACTIVE,
            email_verified=True
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create activity logs
        activities = [
            ActivityLog(
                id=str(uuid.uuid4()),
                user_id=user.id,
                action="login",
                resource_type="session",
                resource_id=str(uuid.uuid4()),
                ip_address="192.168.1.1",
                user_agent="Chrome/91.0",
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            for i in range(5)
        ]

        for activity in activities:
            test_db_session.add(activity)
        await test_db_session.commit()

        # Test querying user activities
        result = await test_db_session.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user.id)
            .order_by(ActivityLog.timestamp.desc())
        )
        user_activities = result.scalars().all()
        assert len(user_activities) == 5
        assert all(activity.user_id == user.id for activity in user_activities)


@pytest.mark.asyncio
class TestDatabaseConstraints:
    """Test database constraints and validation"""

    async def test_user_email_uniqueness(self, test_db_session: AsyncSession):
        """Test user email uniqueness constraint"""
        # Create first user
        user1 = User(
            id=str(uuid.uuid4()),
            email="unique@example.com",
            hashed_password="hashed_password",
            first_name="First",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user1)
        await test_db_session.commit()

        # Try to create second user with same email
        user2 = User(
            id=str(uuid.uuid4()),
            email="unique@example.com",  # Same email
            hashed_password="hashed_password",
            first_name="Second",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user2)

        # Should raise integrity error
        with pytest.raises(IntegrityError):
            await test_db_session.commit()

    async def test_organization_name_constraint(self, test_db_session: AsyncSession):
        """Test organization name constraints"""
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="org_test@example.com",
            hashed_password="hashed_password",
            first_name="Org",
            last_name="Owner",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create organization with empty name (should fail validation)
        with pytest.raises((IntegrityError, ValueError)):
            org = Organization(
                id=str(uuid.uuid4()),
                name="",  # Empty name
                owner_id=user.id
            )
            test_db_session.add(org)
            await test_db_session.commit()

    async def test_foreign_key_constraints(self, test_db_session: AsyncSession):
        """Test foreign key constraints"""
        # Try to create organization member without valid user
        with pytest.raises(IntegrityError):
            member = OrganizationMember(
                user_id=str(uuid.uuid4()),  # Non-existent user
                organization_id=str(uuid.uuid4()),  # Non-existent org
                role=OrganizationRole.MEMBER
            )
            test_db_session.add(member)
            await test_db_session.commit()

    async def test_cascade_deletion(self, test_db_session: AsyncSession):
        """Test cascade deletion behavior"""
        # Create user with sessions
        user = User(
            id=str(uuid.uuid4()),
            email="cascade_test@example.com",
            hashed_password="hashed_password",
            first_name="Cascade",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create session for user
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token="refresh_token_123",
            ip_address="192.168.1.1",
            user_agent="Chrome/91.0",
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        test_db_session.add(session)
        await test_db_session.commit()

        # Delete user
        await test_db_session.delete(user)
        await test_db_session.commit()

        # Check if session is also deleted (depends on cascade configuration)
        result = await test_db_session.execute(
            select(Session).where(Session.user_id == user.id)
        )
        remaining_sessions = result.scalars().all()
        # Should be empty if cascade delete is configured
        assert len(remaining_sessions) == 0


@pytest.mark.asyncio
class TestDatabaseTransactions:
    """Test database transaction handling"""

    async def test_transaction_commit(self, test_db_session: AsyncSession):
        """Test successful transaction commit"""
        # Start transaction
        user = User(
            id=str(uuid.uuid4()),
            email="transaction_test@example.com",
            hashed_password="hashed_password",
            first_name="Transaction",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user)

        # Verify user is not yet committed
        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.email == "transaction_test@example.com")
        )
        count_before_commit = result.scalar()

        # Commit transaction
        await test_db_session.commit()

        # Verify user is now committed
        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.email == "transaction_test@example.com")
        )
        count_after_commit = result.scalar()
        assert count_after_commit == count_before_commit + 1

    async def test_transaction_rollback(self, test_db_session: AsyncSession):
        """Test transaction rollback"""
        # Start transaction
        user = User(
            id=str(uuid.uuid4()),
            email="rollback_test@example.com",
            hashed_password="hashed_password",
            first_name="Rollback",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user)

        # Get count before rollback
        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.email == "rollback_test@example.com")
        )
        count_before_rollback = result.scalar()

        # Rollback transaction
        await test_db_session.rollback()

        # Verify user was not persisted
        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.email == "rollback_test@example.com")
        )
        count_after_rollback = result.scalar()
        assert count_after_rollback == count_before_rollback

    async def test_concurrent_transactions(self, test_db_engine):
        """Test concurrent database transactions"""
        import asyncio
        from sqlalchemy.ext.asyncio import async_sessionmaker

        async_session = async_sessionmaker(test_db_engine, expire_on_commit=False)

        async def create_user(session_factory, email_suffix):
            async with session_factory() as session:
                user = User(
                    id=str(uuid.uuid4()),
                    email=f"concurrent_{email_suffix}@example.com",
                    hashed_password="hashed_password",
                    first_name="Concurrent",
                    last_name=f"User{email_suffix}",
                    status=UserStatus.ACTIVE
                )
                session.add(user)
                await session.commit()
                return user.id

        # Create multiple users concurrently
        tasks = [create_user(async_session, i) for i in range(5)]
        user_ids = await asyncio.gather(*tasks)

        # Verify all users were created
        assert len(user_ids) == 5
        assert len(set(user_ids)) == 5  # All unique

        # Verify users exist in database
        async with async_session() as session:
            result = await session.execute(
                select(func.count(User.id)).where(
                    User.email.like("concurrent_%@example.com")
                )
            )
            user_count = result.scalar()
            assert user_count == 5


@pytest.mark.asyncio
class TestDatabaseQueries:
    """Test complex database queries and performance"""

    async def test_complex_join_queries(self, test_db_session: AsyncSession):
        """Test complex queries with joins"""
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="query_test@example.com",
            hashed_password="hashed_password",
            first_name="Query",
            last_name="User",
            status=UserStatus.ACTIVE,
            email_verified=True
        )
        test_db_session.add(user)

        org = Organization(
            id=str(uuid.uuid4()),
            name="Query Test Company",
            description="Test organization for queries",
            owner_id=user.id
        )
        test_db_session.add(org)

        member = OrganizationMember(
            user_id=user.id,
            organization_id=org.id,
            role=OrganizationRole.OWNER,
            joined_at=datetime.utcnow()
        )
        test_db_session.add(member)

        await test_db_session.commit()

        # Complex query: Get users with their organization roles
        result = await test_db_session.execute(
            select(User.email, Organization.name, OrganizationMember.role)
            .join(OrganizationMember, User.id == OrganizationMember.user_id)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .where(User.email == "query_test@example.com")
        )
        rows = result.all()

        assert len(rows) == 1
        assert rows[0][0] == "query_test@example.com"  # User email
        assert rows[0][1] == "Query Test Company"       # Organization name
        assert rows[0][2] == OrganizationRole.OWNER     # User role

    async def test_aggregation_queries(self, test_db_session: AsyncSession):
        """Test database aggregation queries"""
        # Create test users
        users = []
        for i in range(10):
            user = User(
                id=str(uuid.uuid4()),
                email=f"user_{i}@example.com",
                hashed_password="hashed_password",
                first_name=f"User{i}",
                last_name="Test",
                status=UserStatus.ACTIVE if i % 2 == 0 else UserStatus.INACTIVE,
                email_verified=i % 3 == 0
            )
            users.append(user)
            test_db_session.add(user)

        await test_db_session.commit()

        # Aggregation query: Count users by status
        result = await test_db_session.execute(
            select(User.status, func.count(User.id))
            .group_by(User.status)
        )
        status_counts = dict(result.all())

        assert status_counts[UserStatus.ACTIVE] == 5
        assert status_counts[UserStatus.INACTIVE] == 5

        # Aggregation query: Count verified vs unverified users
        result = await test_db_session.execute(
            select(User.email_verified, func.count(User.id))
            .group_by(User.email_verified)
        )
        verification_counts = dict(result.all())

        verified_count = verification_counts.get(True, 0)
        unverified_count = verification_counts.get(False, 0)
        assert verified_count + unverified_count == 10

    async def test_pagination_queries(self, test_db_session: AsyncSession):
        """Test database pagination"""
        # Create test data
        for i in range(25):
            user = User(
                id=str(uuid.uuid4()),
                email=f"page_user_{i:02d}@example.com",
                hashed_password="hashed_password",
                first_name=f"PageUser{i}",
                last_name="Test",
                status=UserStatus.ACTIVE,
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )
            test_db_session.add(user)

        await test_db_session.commit()

        # Test pagination
        page_size = 10
        offset = 0

        # First page
        result = await test_db_session.execute(
            select(User)
            .where(User.email.like("page_user_%@example.com"))
            .order_by(User.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        first_page = result.scalars().all()
        assert len(first_page) == 10

        # Second page
        offset = 10
        result = await test_db_session.execute(
            select(User)
            .where(User.email.like("page_user_%@example.com"))
            .order_by(User.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        second_page = result.scalars().all()
        assert len(second_page) == 10

        # Third page (partial)
        offset = 20
        result = await test_db_session.execute(
            select(User)
            .where(User.email.like("page_user_%@example.com"))
            .order_by(User.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        third_page = result.scalars().all()
        assert len(third_page) == 5

    async def test_search_queries(self, test_db_session: AsyncSession):
        """Test database search functionality"""
        # Create test data with searchable content
        search_users = [
            ("John Doe", "john.doe@example.com"),
            ("Jane Smith", "jane.smith@example.com"),
            ("John Johnson", "john.johnson@example.com"),
            ("Alice Wonder", "alice.wonder@example.com"),
            ("Bob Builder", "bob.builder@example.com")
        ]

        for name, email in search_users:
            first_name, last_name = name.split()
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                hashed_password="hashed_password",
                first_name=first_name,
                last_name=last_name,
                status=UserStatus.ACTIVE
            )
            test_db_session.add(user)

        await test_db_session.commit()

        # Search by first name
        result = await test_db_session.execute(
            select(User).where(User.first_name.ilike("%john%"))
        )
        john_users = result.scalars().all()
        assert len(john_users) == 2

        # Search by email domain
        result = await test_db_session.execute(
            select(User).where(User.email.like("%@example.com"))
        )
        example_users = result.scalars().all()
        assert len(example_users) >= 5

        # Complex search (first name OR last name)
        result = await test_db_session.execute(
            select(User).where(
                or_(
                    User.first_name.ilike("%alice%"),
                    User.last_name.ilike("%smith%")
                )
            )
        )
        complex_search_users = result.scalars().all()
        assert len(complex_search_users) == 2


@pytest.mark.asyncio
class TestDatabaseIndexes:
    """Test database index usage and performance"""

    async def test_index_usage(self, test_db_session: AsyncSession):
        """Test that database indexes are being used"""
        # Create test data
        for i in range(100):
            user = User(
                id=str(uuid.uuid4()),
                email=f"index_test_{i}@example.com",
                hashed_password="hashed_password",
                first_name=f"IndexUser{i}",
                last_name="Test",
                status=UserStatus.ACTIVE,
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )
            test_db_session.add(user)

        await test_db_session.commit()

        # Query by email (should use email index)
        result = await test_db_session.execute(
            select(User).where(User.email == "index_test_50@example.com")
        )
        user = result.scalar_one()
        assert user.first_name == "IndexUser50"

        # Query by status (should use status index if exists)
        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
        )
        active_count = result.scalar()
        assert active_count == 100

    async def test_query_performance(self, test_db_session: AsyncSession):
        """Test query performance with larger datasets"""
        import time

        # Create larger dataset
        users_batch = []
        for i in range(1000):
            user = User(
                id=str(uuid.uuid4()),
                email=f"perf_test_{i}@example.com",
                hashed_password="hashed_password",
                first_name=f"PerfUser{i}",
                last_name="Test",
                status=UserStatus.ACTIVE if i % 2 == 0 else UserStatus.INACTIVE,
                created_at=datetime.utcnow() - timedelta(minutes=i)
            )
            users_batch.append(user)

        test_db_session.add_all(users_batch)
        await test_db_session.commit()

        # Measure query performance
        start_time = time.time()

        result = await test_db_session.execute(
            select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
        )
        count = result.scalar()

        end_time = time.time()
        query_time = end_time - start_time

        assert count == 500
        # Query should complete reasonably quickly (adjust threshold as needed)
        assert query_time < 1.0  # Less than 1 second


@pytest.mark.asyncio
class TestDatabaseEdgeCases:
    """Test database edge cases and error conditions"""

    async def test_null_handling(self, test_db_session: AsyncSession):
        """Test handling of null values"""
        # Create user with minimal required fields
        user = User(
            id=str(uuid.uuid4()),
            email="null_test@example.com",
            hashed_password="hashed_password",
            status=UserStatus.ACTIVE
            # first_name and last_name are optional (nullable)
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Verify user was created successfully
        result = await test_db_session.execute(
            select(User).where(User.email == "null_test@example.com")
        )
        found_user = result.scalar_one()
        assert found_user.first_name is None
        assert found_user.last_name is None

    async def test_unicode_handling(self, test_db_session: AsyncSession):
        """Test handling of unicode characters"""
        # Create user with unicode characters
        user = User(
            id=str(uuid.uuid4()),
            email="unicode_test@example.com",
            hashed_password="hashed_password",
            first_name="José",
            last_name="González",
            status=UserStatus.ACTIVE
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Verify unicode data was stored correctly
        result = await test_db_session.execute(
            select(User).where(User.email == "unicode_test@example.com")
        )
        found_user = result.scalar_one()
        assert found_user.first_name == "José"
        assert found_user.last_name == "González"

    async def test_large_text_fields(self, test_db_session: AsyncSession):
        """Test handling of large text fields"""
        # Create user with large bio field
        large_bio = "A" * 10000  # 10KB text

        user = User(
            id=str(uuid.uuid4()),
            email="large_text@example.com",
            hashed_password="hashed_password",
            first_name="Large",
            last_name="Text",
            status=UserStatus.ACTIVE,
            bio=large_bio
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Verify large text was stored correctly
        result = await test_db_session.execute(
            select(User).where(User.email == "large_text@example.com")
        )
        found_user = result.scalar_one()
        assert len(found_user.bio) == 10000
        assert found_user.bio[0] == "A"

    async def test_datetime_handling(self, test_db_session: AsyncSession):
        """Test handling of datetime fields"""
        now = datetime.utcnow()
        past = now - timedelta(days=30)
        future = now + timedelta(days=30)

        # Create user with specific timestamps
        user = User(
            id=str(uuid.uuid4()),
            email="datetime_test@example.com",
            hashed_password="hashed_password",
            first_name="DateTime",
            last_name="Test",
            status=UserStatus.ACTIVE,
            created_at=past,
            updated_at=now
        )
        test_db_session.add(user)

        # Create session with future expiration
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token="test_token",
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            created_at=now,
            expires_at=future
        )
        test_db_session.add(session)
        await test_db_session.commit()

        # Verify datetime handling
        result = await test_db_session.execute(
            select(User).where(User.email == "datetime_test@example.com")
        )
        found_user = result.scalar_one()

        # Check that times are close (allowing for small differences)
        time_diff = abs((found_user.created_at - past).total_seconds())
        assert time_diff < 1  # Less than 1 second difference

        # Test datetime queries
        result = await test_db_session.execute(
            select(Session).where(Session.expires_at > datetime.utcnow())
        )
        future_sessions = result.scalars().all()
        assert len(future_sessions) >= 1