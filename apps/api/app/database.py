# Database configuration and session management
import os
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

# Create async engine for production
if hasattr(settings, "DATABASE_URL") and settings.DATABASE_URL:
    # Convert postgres:// to postgresql:// for SQLAlchemy compatibility
    database_url = settings.DATABASE_URL.replace("postgres://", "postgresql://")

    # For async operations, convert to async URL
    if "postgresql://" in database_url:
        async_database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_database_url = database_url

    # Configure engine parameters based on database type
    engine_kwargs = {
        "echo": settings.DEBUG if hasattr(settings, "DEBUG") else False,
        "pool_pre_ping": True,
    }

    # Add pooling parameters only for non-SQLite databases
    if "sqlite" not in async_database_url:
        engine_kwargs.update(
            {
                "pool_size": 50,  # Increased from 5 to handle concurrent requests
                "max_overflow": 100,  # Increased from 10 for burst capacity
                "pool_recycle": 3600,  # Recycle connections after 1 hour
                "pool_timeout": 30,  # Wait up to 30 seconds for a connection
            }
        )
        # Disable SSL for asyncpg if connecting to PostgreSQL without SSL
        if "asyncpg" in async_database_url:
            engine_kwargs["connect_args"] = {"ssl": False}
    else:
        # Use NullPool for SQLite to avoid connection sharing issues
        engine_kwargs["poolclass"] = NullPool

    # Override poolclass for test environment and remove pool-specific params
    if hasattr(settings, "ENVIRONMENT") and settings.ENVIRONMENT == "test":
        engine_kwargs["poolclass"] = NullPool
        # Remove all pool parameters when using NullPool (incompatible)
        engine_kwargs.pop("pool_size", None)
        engine_kwargs.pop("max_overflow", None)
        engine_kwargs.pop("pool_recycle", None)
        engine_kwargs.pop("pool_timeout", None)

    engine = create_async_engine(async_database_url, **engine_kwargs)

    # Create sync engine for migrations and some operations
    sync_engine = create_engine(
        database_url,
        echo=settings.DEBUG if hasattr(settings, "DEBUG") else False,
        pool_pre_ping=True,
    )
else:
    # Require explicit DATABASE_URL configuration
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable must be set. "
            "Example: postgresql://user:password@localhost:5432/janua"
        )

    # Convert to async URL
    async_database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        async_database_url,
        echo=True,
        pool_pre_ping=True,
        pool_size=50,  # Handle concurrent requests
        max_overflow=100,  # Burst capacity
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_timeout=30,  # Wait up to 30 seconds for a connection
        connect_args={"ssl": False},  # Disable SSL for asyncpg
    )

    sync_engine = create_engine(
        DATABASE_URL,
        echo=True,
        pool_pre_ping=True,
        pool_size=50,
        max_overflow=100,
        pool_recycle=3600,
        pool_timeout=30,
    )

# Create session factories
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


# Dependency for FastAPI routes
async def get_db() -> AsyncSession:
    """
    Dependency that provides a database session for FastAPI routes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Alternative sync version for compatibility
def get_sync_db() -> Session:
    """
    Provides a synchronous database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Context manager for async operations outside of FastAPI
@asynccontextmanager
async def get_async_db():
    """
    Context manager for getting an async database session.
    Usage:
        async with get_async_db() as db:
            # perform database operations
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Initialize database (create tables)
async def init_db():
    """
    Initialize database by creating all tables.
    """
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Close database connections
async def close_db():
    """
    Close database engine and dispose of connection pool.
    """
    await engine.dispose()


# Export commonly used items
__all__ = [
    "engine",
    "sync_engine",
    "AsyncSessionLocal",
    "SessionLocal",
    "get_db",
    "get_sync_db",
    "get_async_db",
    "init_db",
    "close_db",
]
