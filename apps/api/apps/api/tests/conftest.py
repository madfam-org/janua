"""
Pytest configuration and fixtures for enterprise testing
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.config import settings
from app.models import User, Organization, UserStatus
from app.core.jwt_manager import jwt_manager
from app.services.auth_service import AuthService


# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from app.services.auth_service import AuthService

    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email="test@example.com",
        password="TestPassword123!",
        first_name="Test",
        last_name="User"
    )
    return user


@pytest.fixture
async def enterprise_user(db_session: AsyncSession) -> User:
    """Create an enterprise test user."""
    from app.services.auth_service import AuthService

    auth_service = AuthService(db_session)
    user = await auth_service.create_user(
        email="enterprise@example.com",
        password="EnterprisePassword123!",
        first_name="Enterprise",
        last_name="User"
    )
    return user


@pytest.fixture
async def test_organization(db_session: AsyncSession, test_user: User) -> Organization:
    """Create a test organization."""
    from app.services.organization_service import OrganizationService

    org_service = OrganizationService(db_session)
    organization = await org_service.create_organization(
        name="Test Organization",
        slug="test-org",
        owner_id=test_user.id
    )
    return organization


@pytest.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    access_token = jwt_manager.create_access_token(
        user_id=str(test_user.id),
        email=test_user.email
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def enterprise_auth_headers(enterprise_user: User) -> dict:
    """Create authentication headers for enterprise user."""
    access_token = jwt_manager.create_access_token(
        user_id=str(enterprise_user.id),
        email=enterprise_user.email
    )
    return {"Authorization": f"Bearer {access_token}"}


# Test data fixtures
@pytest.fixture
def valid_signup_data():
    """Valid signup data for testing."""
    return {
        "email": "newuser@example.com",
        "password": "NewUserPassword123!",
        "first_name": "New",
        "last_name": "User"
    }


@pytest.fixture
def valid_signin_data():
    """Valid signin data for testing."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }


@pytest.fixture
def enterprise_sso_config():
    """Enterprise SSO configuration for testing."""
    return {
        "provider": "saml",
        "entity_id": "https://test.example.com",
        "sso_url": "https://sso.example.com/saml",
        "certificate": "-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----",
        "enabled": True
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "enterprise: marks tests as enterprise feature tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-focused tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


# Async test configuration
pytest_asyncio.main.pytest_configure = pytest_configure