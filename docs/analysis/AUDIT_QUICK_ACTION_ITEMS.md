# Plinto Audit - Quick Action Items

## 🚨 IMMEDIATE ACTION REQUIRED (This Week)

### Critical Security Fixes
- [ ] **Update Next.js** - Multiple critical CVEs (SSRF, cache poisoning, DoS)
  ```bash
  npm update next@latest
  npm audit fix --force
  ```

- [ ] **Fix CORS Configuration** - `apps/api/app/main.py:439-440`
  ```python
  # Change from:
  allow_methods=["*"], allow_headers=["*"]
  # To:
  allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
  allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-API-Key"]
  ```

- [ ] **Remove Hardcoded Database Credentials** - `apps/api/app/database.py:57`
  ```python
  if not os.getenv("DATABASE_URL"):
      raise RuntimeError("DATABASE_URL environment variable must be set")
  ```

- [ ] **Enforce Secret Key Validation** - `apps/api/app/config.py:63`
  ```python
  @field_validator("SECRET_KEY")
  def validate_secret_key(cls, v):
      if not v or (len(v) < 32 and settings.ENVIRONMENT == "production"):
          raise ValueError("SECRET_KEY must be set and at least 32 characters")
      return v
  ```

- [ ] **Add OAuth Redirect Validation** - `apps/api/app/routers/v1/oauth.py`
  - Implement URL validation against allowlist
  - Prevent open redirect vulnerability

### Critical Architecture Fixes
- [ ] **Scale Database Connection Pool** - `apps/api/app/database.py`
  ```python
  # Change from:
  pool_size=5, max_overflow=10
  # To:
  pool_size=50, max_overflow=100
  ```

- [ ] **Fix Memory Leak** - `packages/typescript-sdk/src/services/session-manager.service.ts`
  - Add timer cleanup in destroy/unmount methods

- [ ] **Remove Hardcoded Secrets** - `packages/typescript-sdk/src/config/config.service.ts`
  - Remove fallback values for jwt-secret, encryption-key, session-secret
  - Fail fast if not provided in production

---

## 🔥 HIGH PRIORITY (This Month)

### Security
- [ ] Update vulnerable dependencies: glob, esbuild, vite, wrangler
- [ ] Increase bcrypt rounds to 12 in mock API
- [ ] Remove hardcoded JWT secrets from mock API
- [ ] Fix X-Forwarded-For header trust logic
- [ ] Enforce HTTPS for OIDC in production
- [ ] Add authorization checks to user endpoints

### Architecture
- [ ] **Consolidate Duplicate Services** (12+ files)
  - 3x AuthService → 1
  - 2x CacheService → 1
  - 3x EmailService → 1
  - 2x ComplianceService → 1

- [ ] **Implement Dependency Injection**
  - Convert all service instantiations to use FastAPI Depends()

- [ ] **Add Redis Circuit Breaker**
  - Implement fallback for sessions, rate limiting, caching

### Code Quality
- [ ] Add logging to 20+ silent error handlers
- [ ] Fix incomplete TypeScript types (uncomment types/index.ts)
- [ ] Extract duplicated code from HttpClient implementations
- [ ] Add environment variable validation

---

## 📊 METRICS TO TRACK

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Critical CVEs | 4 | 0 | 🔴 |
| Test Coverage | ~35% | 80%+ | 🔴 |
| Duplicate Services | 12 files | 0 | 🔴 |
| DB Pool Size | 5 | 50 | 🔴 |
| Silent Error Handlers | 20+ | 0 | 🔴 |
| God Objects (>1000 lines) | 5 files | 0 | 🟡 |
| Response Time (p95) | Unknown | <200ms | 🟡 |

---

## 📁 KEY FILES TO REVIEW

### Security
1. `apps/api/app/main.py` - CORS configuration
2. `apps/api/app/config.py` - Secret key validation
3. `apps/api/app/database.py` - Database credentials
4. `apps/api/app/routers/v1/oauth.py` - OAuth redirect validation
5. `packages/mock-api/src/middleware/auth.ts` - JWT secrets

### Architecture
1. `apps/api/app/services/auth*.py` - Duplicate AuthService implementations
2. `apps/api/app/database.py` - Connection pool settings
3. `packages/typescript-sdk/src/services/session-manager.service.ts` - Memory leak

### Code Quality
1. `packages/typescript-sdk/src/services/analytics.service.ts` - 1,296 lines (god object)
2. `packages/typescript-sdk/src/services/billing.service.ts` - 1,192 lines (god object)
3. `packages/typescript-sdk/src/config/config.service.ts` - Hardcoded secrets

---

## 🎯 SUCCESS CRITERIA

### Week 1
- ✅ All critical security CVEs patched
- ✅ No hardcoded credentials in codebase
- ✅ CORS configuration secured
- ✅ Database pool scaled appropriately

### Month 1
- ✅ Zero duplicate service implementations
- ✅ Dependency injection implemented
- ✅ Redis resilience added
- ✅ Test coverage > 60%
- ✅ All error handlers have logging

### Month 3
- ✅ Test coverage > 80%
- ✅ All god objects refactored
- ✅ Observability stack implemented
- ✅ API response time p95 < 200ms
- ✅ Zero high-severity security issues

---

## 📞 ESCALATION

**If you encounter blockers:**
1. Review full audit report: `CODEBASE_AUDIT_REPORT.md`
2. Check detailed analysis:
   - Code Quality: `/tmp/audit_report.md`
   - Architecture: `/tmp/ARCHITECTURAL_REVIEW_SUMMARY.md`
3. Consult team for prioritization decisions

**Estimated Total Effort**: 35-47 days (1.5-2 months) with 3-4 developers

---

Last Updated: November 19, 2025
