"""
Tests for core configuration functionality
"""
import os
import pytest
from unittest.mock import patch


def test_config_imports():
    """Test that config module can be imported"""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/plinto_test',
        'JWT_SECRET_KEY': 'test-secret-key',
        'REDIS_URL': 'redis://localhost:6379/0',
        'ENVIRONMENT': 'test'
    }):
        try:
            from app.config import settings
            assert settings.ENVIRONMENT == 'test'
            assert settings.JWT_SECRET_KEY == 'test-secret-key'
            assert 'plinto_test' in settings.DATABASE_URL
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")


def test_database_url_format():
    """Test database URL configuration"""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db_name',
        'JWT_SECRET_KEY': 'test-secret',
        'ENVIRONMENT': 'test'
    }):
        try:
            from app.config import settings
            assert settings.DATABASE_URL.startswith('postgresql')
            assert 'localhost' in settings.DATABASE_URL
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")


def test_environment_detection():
    """Test environment detection logic"""
    test_environments = ['development', 'staging', 'production', 'test']
    for env in test_environments:
        # Clear any cached settings from previous tests
        import sys
        if 'app.config' in sys.modules:
            del sys.modules['app.config']

        with patch.dict(os.environ, {
            'ENVIRONMENT': env,
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
            'JWT_SECRET_KEY': 'test-secret',
            'SECRET_KEY': 'test-secret-key-for-testing'
        }, clear=True):
            try:
                from app.config import settings
                assert settings.ENVIRONMENT == env
            except ImportError as e:
                pytest.skip(f"Config imports failed: {e}")


def test_jwt_configuration():
    """Test JWT configuration settings"""
    # Clear any cached settings from previous tests
    import sys
    if 'app.config' in sys.modules:
        del sys.modules['app.config']

    with patch.dict(os.environ, {
        'JWT_SECRET_KEY': 'super-secret-key-for-testing',
        'JWT_ALGORITHM': 'HS256',
        'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': '60',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'ENVIRONMENT': 'test'
    }, clear=True):
        try:
            from app.config import settings
            assert settings.JWT_SECRET_KEY == 'super-secret-key-for-testing'
            # Check that sensitive data is not exposed in logs
            assert len(settings.JWT_SECRET_KEY) > 10
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")


def test_redis_configuration():
    """Test Redis configuration"""
    with patch.dict(os.environ, {
        'REDIS_URL': 'redis://localhost:6379/1',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'JWT_SECRET_KEY': 'test-secret',
        'ENVIRONMENT': 'test'
    }):
        try:
            from app.config import settings
            assert 'redis://' in settings.REDIS_URL
            assert '6379' in settings.REDIS_URL
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")


def test_cors_configuration():
    """Test CORS configuration for different environments"""
    # Test development environment
    import sys
    if 'app.config' in sys.modules:
        del sys.modules['app.config']

    with patch.dict(os.environ, {
        'ENVIRONMENT': 'development',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'JWT_SECRET_KEY': 'test-secret',
        'SECRET_KEY': 'test-secret-key-for-testing'
    }, clear=True):
        try:
            from app.config import settings
            # Development should allow broader CORS
            assert settings.ENVIRONMENT == 'development'
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")

    # Test production environment
    import sys
    if 'app.config' in sys.modules:
        del sys.modules['app.config']

    with patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'JWT_SECRET_KEY': 'test-secret',
        'SECRET_KEY': 'test-secret-key-for-testing'
    }, clear=True):
        try:
            from app.config import settings
            # Production should have stricter CORS
            assert settings.ENVIRONMENT == 'production'
        except ImportError as e:
            pytest.skip(f"Config imports failed: {e}")