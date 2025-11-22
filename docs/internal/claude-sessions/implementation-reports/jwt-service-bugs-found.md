# JWT Service Critical Bugs Found

**Date**: 2025-11-17  
**Status**: 🚨 Blocking 95%+ test coverage  
**Current Coverage**: 70% (113/161 lines)  
**Target Coverage**: 95%+ (152+/161 lines)

## Executive Summary

During comprehensive testing implementation for JWT Service, discovered **critical runtime bugs** where the service attempts to instantiate SQLAlchemy database models as Pydantic response models. These bugs will cause runtime failures in production.

## Critical Bugs

### Bug 1: TokenPair Model Misuse
**Location**: `app/services/jwt_service.py:273-278`  
**Severity**: 🔴 Critical - Runtime Error

```python
# Current code (BROKEN):
return TokenPair(
    access_token=access_token,
    refresh_token=refresh_token,
    expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    token_type="Bearer",
)
```

**Problem**:
- `TokenPair` is a SQLAlchemy model: `class TokenPair(Base)` 
- Database model has fields: `id`, `access_token`, `refresh_token`, `user_id`, `created_at`, `expires_at`
- Service tries to create with: `access_token`, `refresh_token`, `expires_in`, `token_type`
- **Result**: `TypeError: 'expires_in' is an invalid keyword argument for TokenPair`

**Fix Required**:
Create Pydantic response model:
```python
class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
```

### Bug 2: TokenClaims Model Misuse
**Location**: `app/services/jwt_service.py:313`  
**Severity**: 🔴 Critical - Runtime Error

```python
# Current code (BROKEN):
return TokenClaims(**claims)
```

**Problem**:
- `TokenClaims` is a SQLAlchemy model with fields: `id`, `user_id`, `claims` (JSONB), `created_at`, `expires_at`
- Service tries to create with JWT claim fields: `sub`, `tid`, `oid`, `exp`, `jti`, `type`, etc.
- **Result**: `TypeError: 'sub' is an invalid keyword argument for TokenClaims`

**Fix Required**:
Return the decoded claims dictionary directly or create Pydantic response model:
```python
# Option 1: Return dict
return claims

# Option 2: Create response model
class TokenClaimsResponse(BaseModel):
    sub: str
    tid: Optional[str]
    oid: Optional[str]
    exp: datetime
    jti: str
    type: str
    # ... other JWT claims
```

### Bug 3: Wrong Exception Type
**Location**: `app/services/jwt_service.py:383`  
**Severity**: 🟡 Medium - Runtime Error on Exception Path

```python
# Current code (BROKEN):
except jwt.InvalidTokenError as e:
    raise TokenError(f"Invalid refresh token: {str(e)}")
```

**Problem**:
- `jose.jwt` module doesn't have `InvalidTokenError`
- Valid exceptions: `JWTError`, `ExpiredSignatureError`, `JWTClaimsError`, `JWSError`
- **Result**: `AttributeError: module 'jose.jwt' has no attribute 'InvalidTokenError'`

**Fix Required**:
```python
except JWTError as e:
    raise TokenError(f"Invalid refresh token: {str(e)}")
```

### Bug 4: Redis Mock Comparison
**Location**: `app/services/jwt_service.py:354`  
**Severity**: 🟡 Medium - Test Infrastructure

```python
# Current code:
return await self.redis.exists(f"blacklist:{jti}") > 0
```

**Problem**:
- In tests, `AsyncMock().exists()` returns `AsyncMock` object
- Can't compare `AsyncMock > 0`
- **Result**: `TypeError: '>' not supported between instances of 'AsyncMock' and 'int'`

**Fix Required**:
```python
# More explicit boolean conversion
result = await self.redis.exists(f"blacklist:{jti}")
return bool(result) if result is not None else False
```

## Impact Assessment

### Current State
- ✅ **21 tests passing** - Basic token creation and simple operations
- ❌ **5 tests failing** - Verification, refresh, and advanced operations
- 🚫 **Cannot test verification flow** - Service crashes on `verify_token()`
- 🚫 **Cannot test refresh flow** - Service crashes on `refresh_tokens()`
- 📊 **Coverage stuck at 70%** - Cannot test lines 273-313 (core functionality)

### Production Risk
- 🔴 **HIGH**: Token verification will fail with TypeError in production
- 🔴 **HIGH**: Token refresh will fail with TypeError in production  
- 🔴 **HIGH**: Any endpoint using JWT verification is broken
- 🟡 **MEDIUM**: Error handling paths have wrong exception types

## Recommended Action Plan

### Phase 1: Critical Fixes (Immediate)
1. Create `TokenPairResponse` Pydantic model
2. Create `TokenClaimsResponse` Pydantic model or return dict
3. Update `create_tokens()` to return `TokenPairResponse`
4. Update `verify_token()` to return claims dict or response model
5. Fix exception types (`jwt.InvalidTokenError` → `JWTError`)

### Phase 2: Testing (After Fixes)
1. Update test expectations to match new response types
2. Run comprehensive test suite
3. Achieve 95%+ coverage target
4. Validate all JWT flows work end-to-end

### Phase 3: Integration Validation
1. Test authentication endpoints
2. Test token refresh endpoints
3. Verify protected routes work
4. Load testing with real JWT flows

## Coverage Analysis

### Lines Currently Covered (70%)
- Token creation (basic methods)
- Key loading and generation
- JWKS endpoint
- Basic helper methods

### Lines Missing Coverage (30%)
- **Lines 273-278**: TokenPair creation ← **BLOCKED BY BUG 1**
- **Lines 280-313**: Token verification ← **BLOCKED BY BUG 2**
- **Lines 324-360**: Token refresh ← **BLOCKED BY BUGS 1 & 2**
- **Lines 362-384**: Refresh token verification ← **BLOCKED BY BUGS 2 & 3**
- **Lines 386-420**: Token revocation flows

## Test Results Summary

### Enhanced Test Suite Results
- **Total Tests**: 32
- **Passing**: 13 (40.6%)
- **Failing**: 19 (59.4%)

### Failure Categories
1. **Model instantiation failures**: 10 tests (TokenPair/TokenClaims bugs)
2. **Exception type failures**: 4 tests (InvalidTokenError bug)
3. **Method signature mismatches**: 5 tests (different API than expected)

### Existing Test Suite Results  
- **Total Tests**: 26
- **Passing**: 21 (80.8%)
- **Failing**: 5 (19.2%)

## Files Affected

### Service Files
- `apps/api/app/services/jwt_service.py` (161 lines) - **NEEDS FIXES**

### Model Files
- `apps/api/app/models/__init__.py` - TokenPair and TokenClaims definitions
- **MISSING**: Response model schemas (need to create)

### Test Files
- `apps/api/tests/unit/services/test_jwt_service_complete.py` - 21/26 passing
- `apps/api/tests/unit/services/test_jwt_service_enhanced.py` - 13/32 passing (created)

## Next Steps

1. ✅ **Document bugs found** (this file)
2. ⏭️ **Create Pydantic response models**
3. ⏭️ **Fix JWT service to use response models**
4. ⏭️ **Update all tests to match fixed service**
5. ⏭️ **Achieve 95%+ coverage**
6. ⏭️ **Integration testing**

## Conclusion

Cannot achieve 95%+ test coverage until critical service bugs are fixed. The JWT service has fundamental design issues where it confuses database models with API response models. These bugs will cause runtime failures in production and must be addressed before comprehensive testing can proceed.

**Recommendation**: Fix the service bugs first, then resume testing to 95%+ coverage.
