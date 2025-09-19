# Test Coverage Action Plan: Path to 100%

## Immediate Quick Wins (Priority 1 - Next 24 Hours)

### 1. Fix RBAC Engine Async Mock Issues (4 tests)
**File**: `tests/unit/core/test_rbac_engine.py`
**Issue**: `'coroutine' object has no attribute 'status'`
**Solution**: Fix async mocking pattern for database calls

```python
# Current broken pattern:
mock_db_session.query().filter().first.return_value = mock_membership

# Fixed pattern:
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

**Impact**: Immediately raises RBAC pass rate from 83% to 100%

### 2. Complete High-Coverage Modules
**Target Files with Missing Lines**:

#### A. `app/routers/v1/organizations/schemas.py` (99% -> 100%)
- **Missing**: 1 line at line 39
- **Action**: Add test for missing validation case

#### B. `app/config.py` (95% -> 100%)
- **Missing**: Lines 205, 214, 218-221, 232
- **Action**: Add tests for configuration edge cases and error handling

#### C. `app/core/logging.py` (88% -> 100%)
- **Missing**: Lines 40, 74, 103, 130
- **Action**: Add tests for logging configuration and error scenarios

#### D. `app/core/database.py` (78% -> 100%)
- **Missing**: Lines 10-12, 31, 37, 42, 66-69
- **Action**: Test database initialization error cases

**Estimated Time**: 4-6 hours
**Coverage Gain**: +3-5%

## Strategic Module Completion (Priority 2 - Week 1)

### 1. Health Router Complete Coverage
**File**: `app/routers/v1/health.py` (62% -> 100%)
**Missing**: 10 lines (22-27, 32, 44, 51-59, 67)
**Strategy**: Test all health check endpoints and error conditions

### 2. Organization Members Router
**File**: `app/routers/v1/organization_members.py` (59% -> 100%)
**Missing**: 39 lines across CRUD operations
**Strategy**: Test member management endpoints with proper auth mocking

### 3. RBAC Router
**File**: `app/routers/v1/rbac.py` (52% -> 100%)
**Missing**: 51 lines across permission management
**Strategy**: Test role and permission assignment endpoints

### 4. Auth Service Core
**File**: `app/services/auth.py` (53% -> 100%)
**Missing**: 36 lines in authentication logic
**Strategy**: Test token validation and user authentication flows

**Estimated Time**: 2-3 weeks
**Coverage Gain**: +15-20%

## High-Impact Router Coverage (Priority 3 - Week 2-3)

### 1. Authentication Router
**File**: `app/routers/v1/auth.py` (43% -> 90%+)
**Missing**: 136 lines across login, logout, registration
**Strategy**: Focus on core auth flows, defer complex edge cases

### 2. Main Application
**File**: `app/main.py` (40% -> 80%+)
**Missing**: 200 lines in app initialization and middleware setup
**Strategy**: Test app startup, middleware configuration, route registration

### 3. Webhooks Router
**File**: `app/routers/v1/webhooks.py` (62% -> 90%+)
**Missing**: 56 lines in webhook management
**Strategy**: Test webhook CRUD operations and delivery mechanisms

**Estimated Time**: 2-3 weeks
**Coverage Gain**: +25-30%

## Service Layer Foundation (Priority 4 - Week 4-6)

### Critical Services (0% -> 80%+)
1. **Authentication Services**
   - `app/services/auth_service.py` (224 lines)
   - `app/services/jwt_service.py` (161 lines)

2. **Authorization Services**
   - `app/services/rbac_service.py` (162 lines, currently 27%)
   - `app/services/policy_engine.py` (163 lines)

3. **Organization Management**
   - `app/services/organization_member_service.py` (127 lines, currently 16%)

4. **Monitoring & Observability**
   - `app/services/monitoring.py` (339 lines, currently 29%)
   - `app/services/audit_logger.py` (248 lines, currently 47%)

**Strategy**: Focus on core business logic, mock external dependencies
**Estimated Time**: 3-4 weeks
**Coverage Gain**: +40-50%

## Testing Patterns & Best Practices

### 1. Async Testing Pattern (for RBAC fixes)
```python
@pytest.mark.asyncio
async def test_async_operation():
    with patch('app.core.database.get_db') as mock_get_db:
        mock_session = AsyncMock()
        mock_get_db.return_value = mock_session

        # Setup async mock returns
        mock_session.query().filter().first = AsyncMock(return_value=mock_data)

        result = await async_function()
        assert result == expected
```

### 2. Router Testing Pattern
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### 3. Service Mocking Pattern
```python
@patch('app.services.external_service.ExternalAPI')
def test_service_method(mock_external):
    mock_external.return_value.method.return_value = mock_response

    result = service.process_data(input_data)
    assert result == expected_output
    mock_external.return_value.method.assert_called_once_with(input_data)
```

## Execution Commands

### Run Working Tests for Baseline
```bash
# Core foundation tests (should all pass)
python -m pytest tests/unit/test_core_config.py tests/unit/core/test_database.py tests/unit/test_core_models.py --cov=app --cov-report=term-missing

# Test specific modules after fixes
python -m pytest tests/unit/core/test_rbac_engine.py -v

# Full coverage report after each phase
python -m pytest tests/unit/ --cov=app --cov-report=html:htmlcov --cov-report=term-missing
```

### Track Progress
```bash
# Quick pass rate check
python -m pytest tests/unit/ --tb=no -q | tail -1

# Coverage summary
python -m pytest tests/unit/ --cov=app --cov-report=term | grep "TOTAL"
```

## Success Metrics

### Phase Completion Targets
- **Week 1**: 35% coverage, 450+ passing tests
- **Week 2**: 50% coverage, 550+ passing tests
- **Week 3**: 70% coverage, 650+ passing tests
- **Week 4-6**: 90%+ coverage, 750+ passing tests

### Quality Gates
- **No regressions**: Existing passing tests must continue to pass
- **Error handling**: Each module must test both success and failure paths
- **Mock isolation**: Tests should not depend on external services
- **Performance**: Test suite should complete in under 30 seconds

## Risk Mitigation

### High-Risk Areas Requiring Careful Testing
1. **Database transactions**: Ensure proper session handling and rollback
2. **Authentication flows**: Security implications of auth logic
3. **Permission checks**: Authorization bypass vulnerabilities
4. **External integrations**: Proper mocking of third-party services

### Rollback Strategy
- Maintain working test baseline in separate branch
- Run full regression suite before merging coverage improvements
- Document test patterns for future maintainability

## Final Notes

This plan prioritizes **working code over perfect coverage**. The goal is to:
1. Fix immediate failures in RBAC engine
2. Complete nearly-finished modules for quick wins
3. Systematically cover core business logic
4. Achieve sustainable 90%+ coverage with quality tests

**Expected Timeline**: 4-6 weeks to 90%+ coverage
**Resource Requirement**: 1 developer, 20-30 hours/week
**Risk Level**: Low (building on existing working foundation)