# Test Patterns and Best Practices

## ✅ Achieving 100% Test Pass Rate

This document outlines the patterns and practices for writing tests that consistently pass in our async FastAPI application.

## 🎯 Core Principles

1. **Always use AsyncMock for async operations**
2. **Mark async tests with @pytest.mark.asyncio**
3. **Use centralized fixtures from tests/fixtures/**
4. **Mock at the service layer, not the database layer**
5. **Ensure proper event loop configuration**

## 📁 Test Structure

```
tests/
├── fixtures/
│   ├── __init__.py
│   ├── async_fixtures.py      # Centralized async mocks
│   └── test_data.py          # Shared test data
├── unit/
│   ├── services/              # Service layer tests
│   ├── routers/              # API endpoint tests
│   └── models/               # Model validation tests
├── integration/
│   └── test_workflows.py     # Full workflow tests
└── conftest.py               # Global configuration
```

## 🔧 Common Patterns

### Pattern 1: Async Service Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from tests.fixtures.async_fixtures import AsyncDatabaseSession, AsyncRedisClient

@pytest.mark.asyncio
class TestServicePattern:
    
    @pytest.fixture(autouse=True)
    async def setup(self, async_db_session, async_redis_client):
        """Setup with proper async mocks"""
        self.db = async_db_session.session
        self.redis = async_redis_client.client
        
    async def test_async_operation(self):
        """Test async service method"""
        from app.services.my_service import MyService
        
        # Create service with mocked dependencies
        service = MyService(self.db, self.redis)
        
        # Mock async method if needed
        service.async_method = AsyncMock(return_value="result")
        
        # Test the operation
        result = await service.async_method()
        assert result == "result"
```

### Pattern 2: API Endpoint Testing

```python
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_api_endpoint():
    """Test API endpoint with proper mocking"""
    
    with patch('app.database.get_db') as mock_db:
        # Setup database mock
        mock_session = AsyncMock()
        mock_db.return_value = mock_session
        
        with patch('app.services.auth_service.AuthService') as mock_service:
            # Setup service mock
            mock_service_instance = AsyncMock()
            mock_service_instance.create_user = AsyncMock(return_value={"id": "123"})
            mock_service.return_value = mock_service_instance
            
            # Test the endpoint
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/api/endpoint", json={"data": "test"})
                
            assert response.status_code == 200
```

### Pattern 3: Database Operation Testing

```python
from tests.fixtures.async_fixtures import AsyncDatabaseSession

@pytest.mark.asyncio
async def test_database_operation(async_db_session):
    """Test database operations with mock session"""
    
    session = async_db_session.session
    
    # Setup query result
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=None)
    session.execute.return_value = mock_result
    
    # Test the operation
    from app.repositories.user_repo import UserRepository
    
    repo = UserRepository(session)
    user = await repo.get_by_email("test@example.com")
    
    assert user is None
    session.execute.assert_called_once()
```

### Pattern 4: Redis Operation Testing

```python
from tests.fixtures.async_fixtures import AsyncRedisClient

@pytest.mark.asyncio
async def test_redis_operation(async_redis_client):
    """Test Redis operations with mock client"""
    
    redis = async_redis_client.client
    
    # Setup Redis responses
    redis.get.return_value = None
    redis.setex.return_value = True
    
    # Test cache service
    from app.services.cache import CacheService
    
    cache = CacheService(redis)
    
    # Test cache miss
    value = await cache.get("key")
    assert value is None
    
    # Test cache set
    success = await cache.set("key", "value", ttl=60)
    assert success is True
```

## ❌ Common Pitfalls to Avoid

### Pitfall 1: Using Mock Instead of AsyncMock
```python
# ❌ WRONG
from unittest.mock import Mock
mock_service = Mock()
mock_service.async_method.return_value = "value"  # Not awaitable!

# ✅ CORRECT
from unittest.mock import AsyncMock
mock_service = AsyncMock()
mock_service.async_method.return_value = "value"  # Properly awaitable
```

### Pitfall 2: Missing @pytest.mark.asyncio
```python
# ❌ WRONG
async def test_something():  # Will be skipped!
    result = await async_function()

# ✅ CORRECT
@pytest.mark.asyncio
async def test_something():  # Will run properly
    result = await async_function()
```

### Pitfall 3: Not Awaiting Async Mocks
```python
# ❌ WRONG
mock.async_method()  # RuntimeWarning: coroutine was never awaited

# ✅ CORRECT
await mock.async_method()  # Properly awaited
```

### Pitfall 4: Incorrect Event Loop Setup
```python
# ❌ WRONG - in conftest.py
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()  # Closes loop for other tests!

# ✅ CORRECT - in conftest.py
@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
```

## 🚀 Quick Fixes for Common Issues

### Issue: "coroutine was never awaited"
**Fix**: Ensure the mock is AsyncMock and the call is awaited

### Issue: "async def functions are not natively supported"
**Fix**: Add @pytest.mark.asyncio decorator

### Issue: "event loop is closed"
**Fix**: Update conftest.py event_loop fixture as shown above

### Issue: "Mock object has no attribute"
**Fix**: Use AsyncMock() instead of Mock() for async methods

## 📋 Testing Checklist

Before committing tests, ensure:

- [ ] All async functions have @pytest.mark.asyncio
- [ ] AsyncMock used for all async operations
- [ ] Fixtures imported from tests/fixtures/
- [ ] No hardcoded database connections
- [ ] No real Redis connections
- [ ] All async calls are awaited
- [ ] Tests run with: `pytest --asyncio-mode=auto`
- [ ] No warnings about unawaited coroutines

## 🔨 Tools and Commands

### Run Tests with Proper Configuration
```bash
# Single test file
ENVIRONMENT=test DATABASE_URL="sqlite+aiosqlite:///:memory:" \
python -m pytest tests/unit/test_file.py --asyncio-mode=auto -v

# All tests with coverage
ENVIRONMENT=test DATABASE_URL="sqlite+aiosqlite:///:memory:" \
python -m pytest tests/ --asyncio-mode=auto --cov=app --cov-report=term-missing

# Quick validation
./scripts/fix-and-run-tests.sh

# Health check
python scripts/validate-test-health.py
```

## 📚 Resources

- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [unittest.mock AsyncMock](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock)