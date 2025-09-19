# Immediate Test Fixes for Maximum Coverage Gain

## Critical RBAC Engine Fix (Highest Priority)

### Problem: 4 failing tests due to async mock issues
**Files**: `tests/unit/core/test_rbac_engine.py` lines 168, 199, 230, 409
**Error**: `'coroutine' object has no attribute 'status'`

### Root Cause Analysis
The mock objects for database sessions are not properly configured for async operations. The tests are trying to call async methods on sync mocks.

### Solution Pattern
Replace sync mocks with proper async mocks for database operations:

```python
# Before (broken):
mock_membership = Mock()
mock_membership.status = "active"
mock_db_session.query().filter().first.return_value = mock_membership

# After (working):
mock_membership = Mock()
mock_membership.status = "active"
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

### Specific Fixes Required

#### Test 1: `test_check_permission_exact_match` (line 168)
```python
# Line ~160, fix the mock setup:
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

#### Test 2: `test_check_permission_wildcard_match` (line 199)
```python
# Line ~190, fix the mock setup:
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

#### Test 3: `test_check_permission_admin_override` (line 230)
```python
# Line ~220, fix the mock setup:
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

#### Test 4: `test_admin_user_scenario` (line 409)
```python
# Line ~400, fix the mock setup:
mock_db_session.query().filter().first = AsyncMock(return_value=mock_membership)
```

**Impact**: Immediately improves RBAC from 83% to 100% pass rate

## Quick Coverage Wins (Next 2-4 hours)

### 1. Complete Organizations Schema (1 line missing)
**File**: `app/routers/v1/organizations/schemas.py`
**Current**: 99% coverage (1 line missing at line 39)
**Action**: Add test case for the missing validation scenario

### 2. Complete Config Module (7 lines missing)
**File**: `app/config.py`
**Current**: 95% coverage
**Missing lines**: 205, 214, 218-221, 232
**Action**: Add tests for configuration error cases and environment validation

### 3. Complete Logging Module (4 lines missing)
**File**: `app/core/logging.py`
**Current**: 88% coverage
**Missing lines**: 40, 74, 103, 130
**Action**: Add tests for logging setup error conditions

### 4. Improve Database Module (10 lines missing)
**File**: `app/core/database.py`
**Current**: 78% coverage
**Missing lines**: 10-12, 31, 37, 42, 66-69
**Action**: Add tests for database connection error handling

## Running Commands for Validation

### Step 1: Fix RBAC Tests
```bash
# Test RBAC specifically after fixes
python -m pytest tests/unit/core/test_rbac_engine.py -v --tb=short

# Should show 23 passed, 0 failed
```

### Step 2: Verify Core Foundation
```bash
# Run all core tests together
python -m pytest tests/unit/test_core_config.py tests/unit/core/test_database.py tests/unit/test_core_models.py tests/unit/core/test_rbac_engine.py -v --cov=app.core --cov-report=term-missing

# Should show 50+ passed tests with high core coverage
```

### Step 3: Baseline Working Tests
```bash
# Run subset of known working tests for baseline
python -m pytest \
  tests/unit/test_core_config.py \
  tests/unit/core/test_database.py \
  tests/unit/test_core_models.py \
  tests/unit/core/test_rbac_engine.py \
  tests/unit/test_routers_health.py \
  --cov=app --cov-report=term-missing --tb=no

# Target: 50+ passed tests, 25-30% coverage
```

### Step 4: Full Coverage Report
```bash
# Generate HTML coverage report after fixes
python -m pytest tests/unit/ --cov=app --cov-report=html:htmlcov --cov-report=term-missing --tb=no

# Open htmlcov/index.html to see detailed coverage by file
```

## Expected Results After Immediate Fixes

### Test Pass Rate Improvement
- **Before**: 415 passed / 769 total (54%)
- **After**: 430+ passed / 769 total (56%+)
- **RBAC**: 100% pass rate (up from 83%)

### Coverage Improvement
- **Before**: 22% overall coverage
- **After**: 28-32% overall coverage
- **Core modules**: 85%+ coverage

### Modules at 100% Coverage
1. `app/models/__init__.py` ✅
2. `app/models/compliance.py` ✅
3. `app/models/enterprise.py` ✅
4. `app/routers/v1/organizations/schemas.py` ✅ (after fix)
5. `app/core/rbac_engine.py` ✅ (after async mock fix)

## Validation Checklist

### ✅ Success Criteria
- [ ] RBAC engine shows 23/23 tests passing
- [ ] Core config shows 6/6 tests passing
- [ ] Core database shows 10/10 tests passing
- [ ] Core models shows 11/11 tests passing
- [ ] Overall pass rate > 55%
- [ ] Overall coverage > 28%
- [ ] No new test failures introduced

### ⚠️ Risk Monitoring
- [ ] No existing working tests broken
- [ ] No import errors in core modules
- [ ] No performance regression in test suite
- [ ] Coverage report generates without errors

## Next Steps After Immediate Fixes

1. **Validate baseline**: Confirm all immediate fixes work
2. **Document patterns**: Record successful async mock patterns for reuse
3. **Identify next targets**: Use coverage report to prioritize next modules
4. **Strategic planning**: Move to Phase 2 of comprehensive coverage plan

**Time Investment**: 2-4 hours for immediate fixes
**Coverage Gain**: +6-10% overall coverage
**Foundation**: Establishes stable base for systematic coverage improvement