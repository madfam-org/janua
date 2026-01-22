"""
Integration tests for database operations
"""

import asyncio
import time
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from unittest.mock import patch, AsyncMock

from app.core.database import init_db

pytestmark = pytest.mark.asyncio


class TestDatabaseIntegration:
    """Test database integration scenarios."""

    async def test_database_connection_lifecycle(self):
        """Test complete database connection lifecycle."""
        # Test initialization
        with patch("app.core.database.engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.connect.return_value.__aenter__.return_value = mock_conn
            mock_conn.execute.return_value = None

            await init_db()

            mock_engine.connect.assert_called_once()
            mock_conn.execute.assert_called_once()

    async def test_session_dependency_injection(self, test_db_session: AsyncSession):
        """Test database session dependency injection."""
        # Test that we can get a session
        session = test_db_session
        assert session is not None

        # Test basic database operation
        result = await session.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        assert row.test == 1

    async def test_transaction_rollback(self, test_db_session: AsyncSession):
        """Test transaction rollback behavior."""
        # Start a transaction
        await test_db_session.begin()

        try:
            # Execute some operation
            await test_db_session.execute(text("SELECT 1"))

            # Simulate error to trigger rollback
            raise Exception("Test error")

        except Exception:
            # Rollback should work
            await test_db_session.rollback()

        # Session should still be usable after rollback
        result = await test_db_session.execute(text("SELECT 2 as test"))
        row = result.fetchone()
        assert row.test == 2

    async def test_concurrent_database_access(self, test_db_session: AsyncSession):
        """Test concurrent database access."""

        async def db_operation(session: AsyncSession, value: int):
            result = await session.execute(text(f"SELECT {value} as test"))
            row = result.fetchone()
            return row.test

        # Create multiple concurrent database operations
        tasks = [db_operation(test_db_session, i) for i in range(1, 6)]

        results = await asyncio.gather(*tasks)

        # All operations should complete successfully
        assert results == [1, 2, 3, 4, 5]


class TestDatabaseErrorHandling:
    """Test database error handling scenarios."""

    async def test_connection_error_handling(self):
        """Test database connection error handling."""
        with patch("app.core.database.engine") as mock_engine:
            mock_engine.connect.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await init_db()

    async def test_query_error_handling(self, test_db_session: AsyncSession):
        """Test database query error handling."""
        with pytest.raises(Exception):
            # This should raise an error due to invalid SQL
            await test_db_session.execute(text("INVALID SQL QUERY"))

    async def test_session_cleanup_on_error(self, test_db_session: AsyncSession):
        """Test that sessions are properly cleaned up after errors."""
        try:
            # Execute invalid operation
            await test_db_session.execute(text("INVALID SQL"))
        except Exception:
            pass  # Intentionally ignoring - invalid SQL execution is expected to fail

        # Session should still be in a usable state for cleanup
        # (This tests that the session doesn't get permanently corrupted)
        try:
            await test_db_session.rollback()
        except Exception:
            pass  # Intentionally ignoring - rollback may fail after invalid SQL, which is OK

        # We should be able to execute a simple query after cleanup
        result = await test_db_session.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        assert row.test == 1


class TestDatabasePerformance:
    """Test database performance scenarios."""

    async def test_query_performance(self, test_db_session: AsyncSession):
        """Test basic query performance."""
        start_time = time.time()

        # Execute a simple query
        result = await test_db_session.execute(text("SELECT 1 as test"))
        row = result.fetchone()

        end_time = time.time()

        assert row.test == 1
        assert (end_time - start_time) < 1.0  # Should complete within 1 second

    async def test_multiple_queries_performance(self, test_db_session: AsyncSession):
        """Test performance of multiple sequential queries."""
        start_time = time.time()

        # Execute multiple queries
        for i in range(10):
            result = await test_db_session.execute(text(f"SELECT {i} as test"))
            row = result.fetchone()
            assert row.test == i

        end_time = time.time()

        # 10 simple queries should complete quickly
        assert (end_time - start_time) < 5.0  # Should complete within 5 seconds


class TestDatabaseConfiguration:
    """Test database configuration scenarios."""

    async def test_database_settings_integration(self):
        """Test database settings integration."""
        from app.config import get_settings

        settings = get_settings()

        # Validate database URL format
        assert settings.DATABASE_URL is not None
        assert isinstance(settings.DATABASE_URL, str)

        # For testing, should be using test database
        assert "test" in settings.DATABASE_URL.lower() or "sqlite" in settings.DATABASE_URL.lower()

    async def test_engine_configuration(self):
        """Test database engine configuration."""
        from app.core.database import engine

        # Engine should be configured
        assert engine is not None

        # Engine should have proper configuration
        assert hasattr(engine, "url")
        assert hasattr(engine, "pool")


class TestDatabaseMigrations:
    """Test database migration scenarios."""

    async def test_schema_creation(self, test_db_session: AsyncSession):
        """Test basic schema operations."""
        # Test creating a temporary table
        await test_db_session.execute(
            text(
                """
            CREATE TEMPORARY TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """
            )
        )

        # Test inserting data
        await test_db_session.execute(
            text(
                """
            INSERT INTO test_table (id, name) VALUES (1, 'test')
        """
            )
        )

        # Test querying data
        result = await test_db_session.execute(
            text(
                """
            SELECT id, name FROM test_table WHERE id = 1
        """
            )
        )

        row = result.fetchone()
        assert row.id == 1
        assert row.name == "test"

        await test_db_session.commit()

    async def test_data_types_support(self, test_db_session: AsyncSession):
        """Test support for various data types."""
        # Create temporary table with various data types
        await test_db_session.execute(
            text(
                """
            CREATE TEMPORARY TABLE type_test (
                id INTEGER,
                text_field TEXT,
                bool_field BOOLEAN,
                timestamp_field TIMESTAMP
            )
        """
            )
        )

        # Insert data with various types
        await test_db_session.execute(
            text(
                """
            INSERT INTO type_test (id, text_field, bool_field, timestamp_field)
            VALUES (1, 'test_text', true, datetime('now'))
        """
            )
        )

        # Query and validate data types
        result = await test_db_session.execute(
            text(
                """
            SELECT * FROM type_test WHERE id = 1
        """
            )
        )

        row = result.fetchone()
        assert row.id == 1
        assert row.text_field == "test_text"
        assert row.bool_field is True
        assert row.timestamp_field is not None

        await test_db_session.commit()


class TestDatabaseSecurity:
    """Test database security scenarios."""

    async def test_sql_injection_protection(self, test_db_session: AsyncSession):
        """Test protection against SQL injection."""
        # Create temporary table
        await test_db_session.execute(
            text(
                """
            CREATE TEMPORARY TABLE security_test (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """
            )
        )

        # Insert safe data
        await test_db_session.execute(
            text("INSERT INTO security_test (id, data) VALUES (:id, :data)"),
            {"id": 1, "data": "safe_data"},
        )

        # Try to insert potentially malicious data (should be safe with parameterized queries)
        malicious_data = "'; DROP TABLE security_test; --"
        await test_db_session.execute(
            text("INSERT INTO security_test (id, data) VALUES (:id, :data)"),
            {"id": 2, "data": malicious_data},
        )

        # Table should still exist and contain both records
        result = await test_db_session.execute(text("SELECT COUNT(*) as count FROM security_test"))
        row = result.fetchone()
        assert row.count == 2

        # Malicious data should be stored as literal text, not executed
        result = await test_db_session.execute(text("SELECT data FROM security_test WHERE id = 2"))
        row = result.fetchone()
        assert row.data == malicious_data

        await test_db_session.commit()

    async def test_connection_string_security(self):
        """Test that connection strings don't expose sensitive information."""
        from app.core.database import engine

        # Engine URL should not contain plaintext passwords in logs
        url_str = str(engine.url)

        # If there's a password, it should be hidden
        if "@" in url_str:  # Indicates user:password@host format
            # Password should be replaced with '***' in string representation
            assert "***" in url_str or "password" not in url_str.lower()
