"""
Comprehensive test suite to boost code coverage to 80%+
Targets modules with 0% or low coverage
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from datetime import datetime, timedelta
import json
import jwt
from httpx import AsyncClient
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from typing import Dict, Any, Optional

pytestmark = pytest.mark.asyncio


class TestMainApplication:
    """Test app/main.py to increase coverage from 43%"""

    @pytest.mark.asyncio
    async def test_app_initialization(self):
        """Test FastAPI app initialization and configuration"""
        from app.main import app

        assert app.title == "Plinto API"
        assert app.version == "3.0.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    @pytest.mark.asyncio
    async def test_cors_configuration(self):
        """Test CORS middleware configuration"""
        from app.main import app

        # Check that CORS middleware is added
        middlewares = [m for m in app.user_middleware]
        cors_middleware = [m for m in middlewares if "CORSMiddleware" in str(m)]
        assert len(cors_middleware) > 0

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_startup_event(self):
        """Test startup event handler"""
        with patch('app.main.logger') as mock_logger:
            from app.main import startup_event

            await startup_event()
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_event(self):
        """Test shutdown event handler"""
        with patch('app.main.logger') as mock_logger:
            from app.main import shutdown_event

            await shutdown_event()
            mock_logger.info.assert_called()


class TestDatabaseModule:
    """Test app/database.py to increase coverage from 53%"""

    @pytest.mark.asyncio
    async def test_get_db(self):
        """Test database session creation"""
        from app.database import get_db

        # Mock the SessionLocal
        mock_session = AsyncMock()
        with patch('app.database.SessionLocal', return_value=mock_session):
            gen = get_db()
            session = await anext(gen)
            assert session == mock_session

            # Clean up
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

            mock_session.close.assert_called()

    @pytest.mark.asyncio
    async def test_init_db(self):
        """Test database initialization"""
        from app.database import init_db

        mock_engine = AsyncMock()
        with patch('app.database.engine', mock_engine):
            with patch('app.database.Base') as mock_base:
                mock_base.metadata.create_all = AsyncMock()

                await init_db()
                mock_base.metadata.create_all.assert_called_once()


class TestDependencies:
    """Test app/dependencies.py to increase coverage from 34%"""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test getting current user with valid token"""
        from app.dependencies import get_current_user

        mock_request = Mock()
        mock_request.headers = {"authorization": "Bearer valid_token"}

        mock_db = AsyncMock()
        mock_user = Mock()
        mock_user.id = "user123"

        with patch('app.dependencies.JWTService.verify_token', return_value={"sub": "user123"}):
            with patch('app.dependencies.get_user_by_id', return_value=mock_user):
                user = await get_current_user(mock_request, mock_db)
                assert user.id == "user123"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token"""
        from app.dependencies import get_current_user
        from app.exceptions import AuthenticationError

        mock_request = Mock()
        mock_request.headers = {"authorization": "Bearer invalid_token"}

        mock_db = AsyncMock()

        with patch('app.dependencies.JWTService.verify_token', side_effect=jwt.InvalidTokenError):
            with pytest.raises(AuthenticationError):
                await get_current_user(mock_request, mock_db)

    @pytest.mark.asyncio
    async def test_require_admin_role(self):
        """Test admin role requirement"""
        from app.dependencies import require_admin
        from app.exceptions import AuthorizationError

        # Test with admin user
        admin_user = Mock()
        admin_user.role = "admin"
        result = await require_admin(admin_user)
        assert result == admin_user

        # Test with non-admin user
        regular_user = Mock()
        regular_user.role = "user"
        with pytest.raises(AuthorizationError):
            await require_admin(regular_user)


class TestCoreDatabase:
    """Test app/core/database.py to increase coverage from 43%"""

    @pytest.mark.asyncio
    async def test_database_manager_init(self):
        """Test DatabaseManager initialization"""
        from app.core.database import DatabaseManager

        manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
        assert manager.database_url == "sqlite+aiosqlite:///:memory:"
        assert manager._engine is None
        assert manager._session_factory is None

    @pytest.mark.asyncio
    async def test_database_manager_connect(self):
        """Test DatabaseManager connection"""
        from app.core.database import DatabaseManager

        manager = DatabaseManager("sqlite+aiosqlite:///:memory:")

        with patch('app.core.database.create_async_engine') as mock_create_engine:
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            await manager.connect()

            mock_create_engine.assert_called_once()
            assert manager._engine == mock_engine

    @pytest.mark.asyncio
    async def test_database_manager_disconnect(self):
        """Test DatabaseManager disconnection"""
        from app.core.database import DatabaseManager

        manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
        manager._engine = AsyncMock()

        await manager.disconnect()

        manager._engine.dispose.assert_called_once()
        assert manager._engine is None


class TestCoreRedis:
    """Test app/core/redis.py to increase coverage from 32%"""

    @pytest.mark.asyncio
    async def test_redis_manager_init(self):
        """Test RedisManager initialization"""
        from app.core.redis import RedisManager

        manager = RedisManager("redis://localhost:6379")
        assert manager.redis_url == "redis://localhost:6379"
        assert manager._redis is None

    @pytest.mark.asyncio
    async def test_redis_manager_connect(self):
        """Test RedisManager connection"""
        from app.core.redis import RedisManager

        manager = RedisManager("redis://localhost:6379")

        with patch('app.core.redis.aioredis.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await manager.connect()

            mock_from_url.assert_called_once_with(
                "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True
            )
            assert manager._redis == mock_redis

    @pytest.mark.asyncio
    async def test_redis_manager_disconnect(self):
        """Test RedisManager disconnection"""
        from app.core.redis import RedisManager

        manager = RedisManager("redis://localhost:6379")
        manager._redis = AsyncMock()

        await manager.disconnect()

        manager._redis.close.assert_called_once()
        assert manager._redis is None

    @pytest.mark.asyncio
    async def test_get_redis(self):
        """Test get_redis dependency"""
        from app.core.redis import get_redis

        mock_redis = AsyncMock()
        with patch('app.core.redis.redis_manager._redis', mock_redis):
            result = await get_redis()
            assert result == mock_redis


class TestMiddlewareRateLimit:
    """Test app/middleware/rate_limit.py to increase coverage from 68%"""

    @pytest.mark.asyncio
    async def test_rate_limiter_init(self):
        """Test RateLimiter initialization"""
        from app.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)
        assert limiter.requests_per_minute == 60
        assert limiter.window_size == 60

    @pytest.mark.asyncio
    async def test_rate_limiter_allow_request(self):
        """Test rate limiting allows requests within limit"""
        from app.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "10"  # Below limit
        mock_redis.incr = AsyncMock(return_value=11)
        mock_redis.expire = AsyncMock()

        allowed = await limiter.allow_request("test_key", mock_redis)
        assert allowed is True
        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiter_deny_request(self):
        """Test rate limiting denies requests over limit"""
        from app.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "60"  # At limit

        allowed = await limiter.allow_request("test_key", mock_redis)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_middleware(self):
        """Test RateLimitMiddleware"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = Mock()
        middleware = RateLimitMiddleware(app)

        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/test"

        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_call_next.return_value = mock_response

        with patch('app.middleware.rate_limit.get_redis', return_value=AsyncMock()):
            response = await middleware.dispatch(mock_request, mock_call_next)
            assert response == mock_response


class TestServicesCache:
    """Test app/services/cache.py to increase coverage from 27%"""

    @pytest.mark.asyncio
    async def test_cache_service_get(self):
        """Test CacheService get operation"""
        from app.services.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"key": "value"}'

        service = CacheService(mock_redis)
        result = await service.get("test_key")

        assert result == {"key": "value"}
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_service_set(self):
        """Test CacheService set operation"""
        from app.services.cache import CacheService

        mock_redis = AsyncMock()

        service = CacheService(mock_redis)
        await service.set("test_key", {"key": "value"}, ttl=3600)

        mock_redis.setex.assert_called_once_with(
            "test_key",
            3600,
            '{"key": "value"}'
        )

    @pytest.mark.asyncio
    async def test_cache_service_delete(self):
        """Test CacheService delete operation"""
        from app.services.cache import CacheService

        mock_redis = AsyncMock()

        service = CacheService(mock_redis)
        await service.delete("test_key")

        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_service_clear_pattern(self):
        """Test CacheService clear pattern"""
        from app.services.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["key1", "key2", "key3"]

        service = CacheService(mock_redis)
        await service.clear_pattern("test:*")

        mock_redis.keys.assert_called_once_with("test:*")
        assert mock_redis.delete.call_count == 3


class TestServicesMigration:
    """Test app/services/migration_service.py to increase coverage from 60%"""

    @pytest.mark.asyncio
    async def test_migration_service_init(self):
        """Test MigrationService initialization"""
        from app.services.migration_service import MigrationService

        mock_db = AsyncMock()
        service = MigrationService(mock_db)
        assert service.db == mock_db

    @pytest.mark.asyncio
    async def test_migration_service_migrate_users(self):
        """Test user migration"""
        from app.services.migration_service import MigrationService

        mock_db = AsyncMock()
        mock_old_users = [
            {"id": 1, "email": "user1@test.com", "name": "User 1"},
            {"id": 2, "email": "user2@test.com", "name": "User 2"}
        ]

        service = MigrationService(mock_db)

        with patch.object(service, '_get_old_users', return_value=mock_old_users):
            with patch.object(service, '_create_new_user', return_value=None) as mock_create:
                result = await service.migrate_users()

                assert result["migrated"] == 2
                assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_migration_service_rollback(self):
        """Test migration rollback"""
        from app.services.migration_service import MigrationService

        mock_db = AsyncMock()
        service = MigrationService(mock_db)

        await service.rollback("migration_123")

        mock_db.execute.assert_called()
        mock_db.commit.assert_called()


class TestCoreErrorHandling:
    """Test app/core/error_handling.py to increase coverage from 59%"""

    @pytest.mark.asyncio
    async def test_error_handler_init(self):
        """Test ErrorHandler initialization"""
        from app.core.error_handling import ErrorHandler

        handler = ErrorHandler()
        assert handler.logger is not None

    @pytest.mark.asyncio
    async def test_handle_validation_error(self):
        """Test validation error handling"""
        from app.core.error_handling import ErrorHandler
        from app.exceptions import ValidationError

        handler = ErrorHandler()
        error = ValidationError("Invalid input")

        response = await handler.handle_error(error)
        assert response["error"] == "validation_error"
        assert response["message"] == "Invalid input"

    @pytest.mark.asyncio
    async def test_handle_authentication_error(self):
        """Test authentication error handling"""
        from app.core.error_handling import ErrorHandler
        from app.exceptions import AuthenticationError

        handler = ErrorHandler()
        error = AuthenticationError("Invalid credentials")

        response = await handler.handle_error(error)
        assert response["error"] == "authentication_error"
        assert response["message"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_handle_generic_error(self):
        """Test generic error handling"""
        from app.core.error_handling import ErrorHandler

        handler = ErrorHandler()
        error = Exception("Something went wrong")

        response = await handler.handle_error(error)
        assert response["error"] == "internal_error"
        assert "Internal server error" in response["message"]


class TestCorePerformance:
    """Test app/core/performance.py to increase coverage from 39%"""

    @pytest.mark.asyncio
    async def test_performance_monitor_init(self):
        """Test PerformanceMonitor initialization"""
        from app.core.performance import PerformanceMonitor

        monitor = PerformanceMonitor()
        assert monitor.metrics == {}

    @pytest.mark.asyncio
    async def test_performance_monitor_start_timer(self):
        """Test starting a performance timer"""
        from app.core.performance import PerformanceMonitor
        import time

        monitor = PerformanceMonitor()
        monitor.start_timer("test_operation")

        assert "test_operation" in monitor.timers
        assert isinstance(monitor.timers["test_operation"], float)

    @pytest.mark.asyncio
    async def test_performance_monitor_end_timer(self):
        """Test ending a performance timer"""
        from app.core.performance import PerformanceMonitor
        import time

        monitor = PerformanceMonitor()
        monitor.start_timer("test_operation")
        await asyncio.sleep(0.1)
        duration = monitor.end_timer("test_operation")

        assert duration >= 0.1
        assert "test_operation" not in monitor.timers

    @pytest.mark.asyncio
    async def test_performance_monitor_record_metric(self):
        """Test recording performance metrics"""
        from app.core.performance import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_metric("request_count", 100)
        monitor.record_metric("response_time", 0.5)

        assert monitor.metrics["request_count"] == 100
        assert monitor.metrics["response_time"] == 0.5

    @pytest.mark.asyncio
    async def test_performance_monitor_get_metrics(self):
        """Test getting performance metrics"""
        from app.core.performance import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_metric("test_metric", 42)

        metrics = monitor.get_metrics()
        assert metrics["test_metric"] == 42


class TestCoreEvents:
    """Test app/core/events.py to increase coverage from 23%"""

    @pytest.mark.asyncio
    async def test_event_dispatcher_init(self):
        """Test EventDispatcher initialization"""
        from app.core.events import EventDispatcher

        dispatcher = EventDispatcher()
        assert dispatcher.handlers == {}

    @pytest.mark.asyncio
    async def test_event_dispatcher_register(self):
        """Test registering event handlers"""
        from app.core.events import EventDispatcher

        dispatcher = EventDispatcher()

        async def handler(event):
            pass

        dispatcher.register("user.created", handler)
        assert "user.created" in dispatcher.handlers
        assert handler in dispatcher.handlers["user.created"]

    @pytest.mark.asyncio
    async def test_event_dispatcher_emit(self):
        """Test emitting events"""
        from app.core.events import EventDispatcher

        dispatcher = EventDispatcher()

        handler_called = False
        async def handler(event):
            nonlocal handler_called
            handler_called = True

        dispatcher.register("test.event", handler)
        await dispatcher.emit("test.event", {"data": "test"})

        assert handler_called is True

    @pytest.mark.asyncio
    async def test_event_dispatcher_unregister(self):
        """Test unregistering event handlers"""
        from app.core.events import EventDispatcher

        dispatcher = EventDispatcher()

        async def handler(event):
            pass

        dispatcher.register("test.event", handler)
        dispatcher.unregister("test.event", handler)

        assert handler not in dispatcher.handlers.get("test.event", [])


# Add more test classes for other modules with 0% coverage...

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app", "--cov-report=term-missing"])