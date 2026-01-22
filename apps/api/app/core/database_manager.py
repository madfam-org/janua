"""
Unified Database Manager for Janua API
Standardizes on async SQLAlchemy with comprehensive health monitoring
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings

logger = structlog.get_logger()


class DatabaseManager:
    """Centralized database connection and health management"""

    def __init__(self):
        self._engine = None
        self._async_session_local = None
        self._initialized = False
        self._health_status = {"healthy": False, "last_check": 0}

    async def initialize(self) -> None:
        """Initialize database connections with environment-specific configuration"""
        if self._initialized:
            return

        # Environment-specific engine configuration
        engine_kwargs = {
            "echo": settings.DEBUG,
            "echo_pool": settings.DEBUG,
            "pool_pre_ping": True,  # Verify connections before use
            "pool_recycle": 3600,  # Recycle connections hourly
        }

        if settings.ENVIRONMENT == "test":
            # In-memory SQLite for tests
            database_url = "sqlite+aiosqlite:///:memory:"
            engine_kwargs.update(
                {
                    "poolclass": StaticPool,
                    "connect_args": {"check_same_thread": False},
                }
            )
        else:
            # PostgreSQL for development/production
            # Convert DATABASE_URL to use asyncpg driver for async operations
            database_url = settings.DATABASE_URL
            if database_url.startswith("postgresql://"):
                # Replace postgresql:// with postgresql+asyncpg://
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("postgres://"):
                # Handle legacy postgres:// URLs
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

            # Only add pool settings for PostgreSQL (not SQLite)
            if not database_url.startswith("sqlite"):
                engine_kwargs.update(
                    {
                        "pool_size": settings.DATABASE_POOL_SIZE,
                        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
                    }
                )

                # Disable SSL for asyncpg connections when DATABASE_SSL_MODE is 'disable'
                ssl_mode = getattr(settings, "DATABASE_SSL_MODE", "disable")
                if ssl_mode == "disable" and "asyncpg" in database_url:
                    engine_kwargs["connect_args"] = {"ssl": False}

                # Production-specific optimizations
                if settings.ENVIRONMENT == "production":
                    engine_kwargs["pool_reset_on_return"] = "rollback"
                    engine_kwargs["isolation_level"] = "READ_COMMITTED"

        try:
            self._engine = create_async_engine(database_url, **engine_kwargs)
            self._async_session_local = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            # Verify connection
            await self._verify_connection()
            self._initialized = True
            logger.info("Database manager initialized", environment=settings.ENVIRONMENT)

        except Exception as e:
            logger.error("Failed to initialize database manager", error=str(e))
            raise

    async def _verify_connection(self) -> None:
        """Verify database connection is working and create tables if needed"""
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

                # Create tables if AUTO_MIGRATE is enabled
                if settings.AUTO_MIGRATE:
                    # Import models and use their Base (which has User and other models registered)
                    from app.models import Base

                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("Database tables created")

            logger.info("Database connection verified")
        except Exception as e:
            logger.error("Database connection verification failed", error=str(e))
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup and error handling"""
        if not self._initialized:
            await self.initialize()

        session = self._async_session_local()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database session error, rolling back", error=str(e))
            raise
        except Exception as e:
            await session.rollback()
            logger.error("Unexpected error in database session", error=str(e))
            raise
        finally:
            await session.close()

    async def health_check(self) -> dict:
        """Comprehensive database health check with metrics"""
        if not self._initialized:
            return {"healthy": False, "error": "Database manager not initialized"}

        start_time = time.time()
        health_info = {
            "healthy": False,
            "response_time_ms": 0,
            "pool_status": {},
            "last_check": start_time,
        }

        try:
            # Basic connectivity test
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))

            response_time = (time.time() - start_time) * 1000
            health_info.update(
                {
                    "healthy": True,
                    "response_time_ms": round(response_time, 2),
                    "pool_status": self._get_pool_status(),
                }
            )

            # Cache health status
            self._health_status = {
                "healthy": True,
                "last_check": start_time,
                "response_time_ms": response_time,
            }

        except Exception as e:
            health_info["error"] = str(e)
            self._health_status = {
                "healthy": False,
                "last_check": start_time,
                "error": str(e),
            }
            logger.error("Database health check failed", error=str(e))

        return health_info

    def _get_pool_status(self) -> dict:
        """Get current connection pool statistics"""
        if not self._engine:
            return {}

        pool = self._engine.pool

        # StaticPool (used in tests) doesn't have pool metrics
        if isinstance(pool, StaticPool):
            return {"pool_type": "StaticPool", "info": "In-memory test database"}

        # For async pools with metrics
        try:
            stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

            # The 'invalid' method doesn't exist on async pools
            # Use 'total' instead which gives total connections
            if hasattr(pool, "invalid"):
                stats["invalid"] = pool.invalid()
            else:
                stats["total"] = pool.size() + pool.overflow()

            return stats
        except AttributeError as e:
            # Fallback for pools without these metrics
            return {"pool_type": type(pool).__name__, "metrics_unavailable": str(e)}

    async def close(self) -> None:
        """Clean shutdown of database connections"""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")

    @property
    def is_healthy(self) -> bool:
        """Quick health status check without database query"""
        # Consider stale if last check was more than 5 minutes ago
        if time.time() - self._health_status.get("last_check", 0) > 300:
            return False
        return self._health_status.get("healthy", False)


# Global database manager instance
db_manager = DatabaseManager()


# Convenience function for FastAPI dependency injection
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    async with db_manager.get_session() as session:
        yield session


# Health check endpoint helper
async def get_database_health() -> dict:
    """Get database health status for monitoring endpoints"""
    return await db_manager.health_check()


# Application lifecycle helpers
async def init_database() -> None:
    """Initialize database connections on startup"""
    await db_manager.initialize()


async def close_database() -> None:
    """Close database connections on shutdown"""
    await db_manager.close()


# Alias for backward compatibility
get_db = get_db_session
