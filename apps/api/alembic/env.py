"""Alembic environment configuration for Janua API"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add the parent directory to the path so we can import our app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application components
# Import all models to register them with SQLAlchemy metadata for Alembic migrations
# Note: This import has a side effect of registering models with Base.metadata
from app import models  # noqa: F401 - Side effect import for SQLAlchemy metadata registration
from app.config import settings
from app.core.database import Base
from app.core.database_ssl import asyncpg_options

# Reference to prevent unused import warning (models must be imported for Alembic)
__all__ = ["models"]

# Alembic Config object
config = context.config

# Override sqlalchemy.url with our DATABASE_URL
# Convert to async driver for async migrations
# Migrations keep a DIRECT postgres connection when the runtime routes
# through pgbouncer (transaction pooling breaks DDL session semantics).
# DIRECT_DATABASE_URL is optional; unset => DATABASE_URL (unchanged).
database_url = getattr(settings, "DIRECT_DATABASE_URL", None) or settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
# ConfigParser treats percent signs as interpolation syntax. Preserve URL-
# escaped managed credentials; online transport uses the original typed URL.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    By skipping Engine creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    migration_url, connect_args = asyncpg_options(database_url, settings)
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = migration_url
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
