# Database configuration and session management
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import os

from app.config import settings

# Create async engine for production
if hasattr(settings, 'DATABASE_URL') and settings.DATABASE_URL:
    # Convert postgres:// to postgresql:// for SQLAlchemy compatibility
    database_url = settings.DATABASE_URL.replace("postgres://", "postgresql://")

    # For async operations, convert to async URL
    if "postgresql://" in database_url:
        async_database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_database_url = database_url

    engine = create_async_engine(
        async_database_url,
        echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
        poolclass=NullPool if hasattr(settings, 'ENVIRONMENT') and settings.ENVIRONMENT == "test" else None,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Create sync engine for migrations and some operations
    sync_engine = create_engine(
        database_url,
        echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
        pool_pre_ping=True,
    )
else:
    # Fallback for local development
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://plinto:plinto@localhost/plinto"
    )

    # Convert to async URL
    async_database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        async_database_url,
        echo=True,
        pool_pre_ping=True,
    )

    sync_engine = create_engine(
        DATABASE_URL,
        echo=True,
        pool_pre_ping=True,
    )

# Create session factories
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

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
