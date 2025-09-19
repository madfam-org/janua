"""
Configuration and fixtures for integration tests
Provides realistic test data, database setup, and service mocking
"""

import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import uuid
import json

# Set test environment variables before any imports
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/1",
    "SECRET_KEY": "test-secret-key-for-integration-tests",
    "JWT_SECRET_KEY": "test-jwt-secret-key-for-integration-tests",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "EMAIL_ENABLED": "false",
    "REDIS_ENABLED": "false",
    "RATE_LIMITING_ENABLED": "false"
})

from app.main import app
from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.models import User, UserStatus, Organization, OrganizationRole, OrganizationMember


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback."""
    async_session = async_sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def mock_redis():
    """Create a comprehensive mock Redis client for testing."""
    mock_redis = AsyncMock()

    # Basic operations
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    mock_redis.expire.return_value = True

    # Counter operations
    mock_redis.incr.return_value = 1
    mock_redis.decr.return_value = 1

    # Hash operations
    mock_redis.hget.return_value = None
    mock_redis.hset.return_value = True
    mock_redis.hdel.return_value = 1
    mock_redis.hgetall.return_value = {}

    # List operations
    mock_redis.lpush.return_value = 1
    mock_redis.rpush.return_value = 1
    mock_redis.lpop.return_value = None
    mock_redis.rpop.return_value = None
    mock_redis.llen.return_value = 0

    # Set operations
    mock_redis.sadd.return_value = 1
    mock_redis.srem.return_value = 1
    mock_redis.smembers.return_value = set()
    mock_redis.sismember.return_value = False

    return mock_redis


@pytest_asyncio.fixture
async def test_client(test_db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden dependencies."""

    async def override_get_db():
        yield test_db_session

    async def override_get_redis():
        return mock_redis

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Generate sample user data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "password": "TestPassword123!",
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "status": UserStatus.ACTIVE.value,
        "email_verified": True
    }


@pytest.fixture
def sample_organization_data() -> Dict[str, Any]:
    """Generate sample organization data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Company",
        "description": "A test organization for integration testing",
        "website": "https://testcompany.com",
        "industry": "Technology",
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_signin_data() -> Dict[str, str]:
    """Generate sample signin data for testing."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Generate sample authorization headers for testing."""
    return {
        "Authorization": "Bearer test_access_token_123",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_jwt_service():
    """Mock JWT service for testing."""
    mock_service = MagicMock()

    # Token creation
    mock_service.create_access_token.return_value = "mock_access_token_123"
    mock_service.create_refresh_token.return_value = "mock_refresh_token_123"

    # Token verification
    mock_service.verify_token.return_value = {
        "user_id": str(uuid.uuid4()),
        "email": "test@example.com",
        "token_type": "access",
        "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()
    }

    # Token refresh
    mock_service.refresh_access_token.return_value = "new_mock_access_token_456"

    return mock_service


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    mock_service = AsyncMock()

    # Email sending methods (matching actual EmailService methods)
    mock_service.send_verification_email.return_value = True
    mock_service.send_password_reset_email.return_value = True
    mock_service.send_welcome_email.return_value = True
    mock_service._send_email.return_value = True

    # Template rendering
    mock_service._render_template.return_value = "<html>Rendered email template</html>"

    # Token verification
    mock_service.verify_email_token.return_value = {
        "user_id": str(uuid.uuid4()),
        "valid": True,
        "expired": False
    }

    return mock_service


@pytest.fixture
def mock_auth_service():
    """Mock authentication service for testing."""
    mock_service = AsyncMock()

    # User creation
    mock_user = MagicMock()
    mock_user.id = str(uuid.uuid4())
    mock_user.email = "test@example.com"
    mock_user.first_name = "John"
    mock_user.last_name = "Doe"
    mock_user.username = "johndoe"
    mock_user.status = UserStatus.ACTIVE
    mock_user.email_verified = True
    mock_user.created_at = datetime.utcnow()
    mock_user.updated_at = datetime.utcnow()

    mock_service.create_user.return_value = mock_user
    mock_service.authenticate_user.return_value = mock_user
    mock_service.get_user_by_id.return_value = mock_user
    mock_service.get_user_by_email.return_value = mock_user

    # Session management
    mock_service.create_session.return_value = (
        "mock_access_token_123",
        "mock_refresh_token_123",
        {"id": str(uuid.uuid4()), "expires_at": datetime.utcnow() + timedelta(hours=1)}
    )

    # Password operations
    mock_service.verify_password.return_value = True
    mock_service.change_password.return_value = True
    mock_service.reset_password.return_value = True

    # Email verification
    mock_service.verify_email.return_value = True
    mock_service.send_verification_email.return_value = True

    # Magic link
    mock_service.create_magic_link.return_value = "magic_token_123"
    mock_service.verify_magic_link.return_value = mock_user

    return mock_service


@pytest.fixture
def mock_organization_service():
    """Mock organization service for testing."""
    mock_service = AsyncMock()

    # Organization creation
    mock_org = MagicMock()
    mock_org.id = str(uuid.uuid4())
    mock_org.name = "Test Company"
    mock_org.description = "A test organization"
    mock_org.website = "https://testcompany.com"
    mock_org.industry = "Technology"
    mock_org.created_at = datetime.utcnow()
    mock_org.member_count = 1

    mock_service.create_organization.return_value = mock_org
    mock_service.get_organization.return_value = mock_org
    mock_service.update_organization.return_value = mock_org
    mock_service.delete_organization.return_value = True

    # Member management
    mock_service.get_user_role.return_value = OrganizationRole.ADMIN
    mock_service.add_member.return_value = True
    mock_service.remove_member.return_value = True
    mock_service.update_member_role.return_value = True

    # Organization listing
    mock_service.get_user_organizations.return_value = [
        {
            "id": mock_org.id,
            "name": mock_org.name,
            "role": OrganizationRole.ADMIN.value,
            "member_count": 1,
            "created_at": mock_org.created_at.isoformat()
        }
    ]

    # Member listing
    mock_service.get_organization_members.return_value = [
        {
            "id": str(uuid.uuid4()),
            "email": "member@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "role": OrganizationRole.MEMBER.value,
            "joined_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat()
        }
    ]

    return mock_service


@pytest.fixture
def sample_test_data():
    """Comprehensive test data for various scenarios."""
    return {
        "users": [
            {
                "id": str(uuid.uuid4()),
                "email": "user1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "status": UserStatus.ACTIVE.value
            },
            {
                "id": str(uuid.uuid4()),
                "email": "user2@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "status": UserStatus.ACTIVE.value
            },
            {
                "id": str(uuid.uuid4()),
                "email": "inactive@example.com",
                "first_name": "Inactive",
                "last_name": "User",
                "status": UserStatus.INACTIVE.value
            }
        ],
        "organizations": [
            {
                "id": str(uuid.uuid4()),
                "name": "Tech Company",
                "description": "A technology company",
                "industry": "Technology"
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Marketing Agency",
                "description": "A marketing and advertising agency",
                "industry": "Marketing"
            }
        ],
        "invitations": [
            {
                "id": str(uuid.uuid4()),
                "email": "invite1@example.com",
                "role": OrganizationRole.MEMBER.value,
                "token": "invitation_token_1",
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "email": "invite2@example.com",
                "role": OrganizationRole.ADMIN.value,
                "token": "invitation_token_2",
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
            }
        ]
    }


@pytest.fixture
def security_test_payloads():
    """Security test payloads for various attack vectors."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "admin'; DROP TABLE sessions; --"
        ],
        "xss": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src='x' onerror='alert(1)'>",
            "';alert(String.fromCharCode(88,83,83))//'"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ],
        "command_injection": [
            "; ls -la",
            "| cat /etc/passwd",
            "& dir",
            "`whoami`"
        ]
    }


# Helper functions for test data generation
def generate_user_data(override: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate realistic user data with optional overrides."""
    base_data = {
        "id": str(uuid.uuid4()),
        "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
        "password": "GeneratedPassword123!",
        "first_name": "Generated",
        "last_name": "User",
        "username": f"user_{uuid.uuid4().hex[:8]}",
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    if override:
        base_data.update(override)

    return base_data


def generate_organization_data(owner_id: str = None, override: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate realistic organization data with optional overrides."""
    base_data = {
        "id": str(uuid.uuid4()),
        "name": f"Company {uuid.uuid4().hex[:8]}",
        "description": "An automatically generated test organization",
        "website": f"https://{uuid.uuid4().hex[:8]}.com",
        "industry": "Technology",
        "owner_id": owner_id or str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    if override:
        base_data.update(override)

    return base_data


async def create_test_user(session: AsyncSession, user_data: Dict[str, Any] = None) -> User:
    """Create a test user in the database."""
    if user_data is None:
        user_data = generate_user_data()

    user = User(
        id=user_data["id"],
        email=user_data["email"],
        hashed_password="hashed_" + user_data.get("password", "password"),
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        username=user_data.get("username"),
        status=UserStatus(user_data["status"]),
        email_verified=user_data.get("email_verified", True),
        created_at=datetime.fromisoformat(user_data["created_at"].replace("Z", "+00:00")) if isinstance(user_data["created_at"], str) else user_data["created_at"],
        updated_at=datetime.fromisoformat(user_data["updated_at"].replace("Z", "+00:00")) if isinstance(user_data["updated_at"], str) else user_data["updated_at"]
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def create_test_organization(session: AsyncSession, org_data: Dict[str, Any] = None) -> Organization:
    """Create a test organization in the database."""
    if org_data is None:
        org_data = generate_organization_data()

    org = Organization(
        id=org_data["id"],
        name=org_data["name"],
        description=org_data["description"],
        website=org_data.get("website"),
        industry=org_data.get("industry"),
        owner_id=org_data["owner_id"],
        created_at=datetime.fromisoformat(org_data["created_at"].replace("Z", "+00:00")) if isinstance(org_data["created_at"], str) else org_data["created_at"],
        updated_at=datetime.fromisoformat(org_data["updated_at"].replace("Z", "+00:00")) if isinstance(org_data["updated_at"], str) else org_data["updated_at"]
    )

    session.add(org)
    await session.commit()
    await session.refresh(org)

    return org