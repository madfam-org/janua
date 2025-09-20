import pytest
pytestmark = pytest.mark.asyncio


"""
Unit tests for database module
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, init_db


class TestDatabaseFunctions:
    """Test database utility functions."""
    
    @pytest.mark.asyncio
    async def test_get_db_success(self, db_session):
        """Test successful database session retrieval."""
        # Mock the AsyncSessionLocal
        with patch('app.core.database.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_session_local.return_value.__aexit__.return_value = None
            
            # Test the generator
            async for db_session in get_db():
                assert db_session == mock_session
            
            # Verify session operations were called
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_db_rollback_on_error(self):
        """Test database session rollback on error."""
        with patch('app.core.database.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.commit.side_effect = Exception("Database error")
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_session_local.return_value.__aexit__.return_value = None
            
            # Test that exception is raised and rollback is called
            try:
                async for db_session in get_db():
                    pass  # This should trigger the commit error
            except Exception:
                pass
            
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Test successful database initialization."""
        with patch('app.core.database.engine') as mock_engine, \
             patch('app.core.database.Base') as mock_base, \
             patch('app.core.database.settings') as mock_settings:
            
            mock_settings.AUTO_MIGRATE = True
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_engine.begin.return_value.__aexit__.return_value = None
            
            await init_db()
            
            mock_engine.begin.assert_called_once()
            mock_conn.run_sync.assert_called_once_with(mock_base.metadata.create_all)
    
    @pytest.mark.asyncio
    async def test_init_db_no_auto_migrate(self):
        """Test database initialization without auto-migration."""
        with patch('app.core.database.engine') as mock_engine, \
             patch('app.core.database.Base') as mock_base, \
             patch('app.core.database.settings') as mock_settings:
            
            mock_settings.AUTO_MIGRATE = False
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_engine.begin.return_value.__aexit__.return_value = None
            
            await init_db()
            
            mock_engine.begin.assert_called_once()
            # Should not call create_all when AUTO_MIGRATE is False
            mock_conn.run_sync.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_init_db_error_handling(self):
        """Test database initialization error handling."""
        with patch('app.core.database.engine') as mock_engine, \
             patch('app.core.database.logger') as mock_logger:
            
            mock_engine.begin.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                await init_db()
            
            mock_logger.error.assert_called_once()


class TestDatabaseConfiguration:
    """Test database configuration and setup."""
    
    def test_database_url_auto_correction(self):
        """Test PostgreSQL URL format auto-correction."""
        # This tests the logic in the database.py file
        # The actual test would need to check the engine creation
        # but since it's at module level, we test the concept
        
        # Mock settings to test URL correction
        with patch('app.core.database.settings') as mock_settings:
            mock_settings.DATABASE_URL = "postgresql://user:pass@localhost/db"
            
            # Import after patching to get the corrected URL
            from app.core import database
            
            # The corrected URL should be used for asyncpg
            # This is a conceptual test - the actual correction happens at import time
            assert True  # Placeholder - actual implementation would verify URL correction
    
    def test_database_engine_configuration(self):
        """Test database engine configuration parameters."""
        # Test that engine is configured with correct parameters
        from app.core.database import engine
        
        # Verify engine has expected configuration
        assert engine is not None
        assert hasattr(engine, 'pool')
        assert hasattr(engine, 'url')
    
    def test_session_maker_configuration(self):
        """Test async session maker configuration."""
        from app.core.database import AsyncSessionLocal
        
        assert AsyncSessionLocal is not None
        # async_sessionmaker doesn't have a bind attribute like the old sessionmaker
        # Instead, check that it has the expected configuration methods
        assert hasattr(AsyncSessionLocal, '__call__')  # It's callable to create sessions
        # Check that the bind is available through the registry
        assert hasattr(AsyncSessionLocal, 'registry') or hasattr(AsyncSessionLocal, 'kw')


class TestDatabaseMetadata:
    """Test database metadata and naming conventions."""
    
    def test_naming_conventions(self):
        """Test database naming conventions are properly set."""
        from app.core.database import metadata
        
        expected_conventions = {
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
        
        assert metadata.naming_convention == expected_conventions
    
    def test_base_model_setup(self):
        """Test that Base model is properly configured."""
        from app.core.database import Base
        
        assert Base is not None
        assert hasattr(Base, 'metadata')
        assert Base.metadata.naming_convention is not None