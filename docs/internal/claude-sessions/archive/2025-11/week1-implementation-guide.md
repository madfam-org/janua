# Week 1 Foundation Sprint - Implementation Guide

**Created**: January 13, 2025
**Target**: Testing Foundation & Authentication Coverage (24% → 40%)
**Duration**: 5 working days
**Team Required**: 2-3 FTE (QA Engineer + Backend Developer + Frontend Developer)

---

## 🎯 Week 1 Goals

### Coverage Target
- **Starting**: 24.1% test coverage
- **Target**: 40% test coverage (+16 points)
- **Stretch**: 50% test coverage (+26 points)

### Deliverables
✅ CI/CD pipeline with automated testing
✅ Coverage reporting integrated (Codecov)
✅ 50+ new authentication integration tests
✅ E2E test suite for auth flows
✅ Test fixtures and factories
✅ Admin Dashboard MVP (optional if frontend dev available)

---

## 📋 Day-by-Day Implementation Plan

### Day 1-2: Testing Infrastructure (QA Engineer)

#### Tasks Completed ✅
- [x] GitHub Actions CI/CD workflow created (`.github/workflows/tests.yml`)
- [x] Codecov integration configured
- [x] Coverage reporting in PRs enabled
- [x] Test templates created

#### Tasks Remaining 🚧
- [ ] **Set up Codecov account** and get `CODECOV_TOKEN`
  - Sign up at https://codecov.io
  - Connect GitHub repository
  - Copy token to GitHub Secrets (`Settings → Secrets → Actions`)

- [ ] **Configure pre-commit hooks**:
  ```bash
  # apps/api/.pre-commit-config.yaml
  repos:
    - repo: local
      hooks:
        - id: pytest
          name: pytest
          entry: pytest
          language: system
          pass_filenames: false
          always_run: true
          args: ['-m', 'not slow', '--tb=short']
  ```

- [ ] **Create test data fixtures** (`apps/api/tests/fixtures/`):
  ```python
  # fixtures/users.py
  @pytest.fixture
  async def test_user(async_session):
      """Create test user with known password"""
      user = User(
          email="test@example.com",
          hashed_password=get_password_hash("TestPassword123!"),
          full_name="Test User",
          is_verified=True,
          is_active=True
      )
      async_session.add(user)
      await async_session.commit()
      await async_session.refresh(user)
      return user

  @pytest.fixture
  async def test_organization(async_session, test_user):
      """Create test organization owned by test_user"""
      org = Organization(
          name="Test Organization",
          owner_id=test_user.id
      )
      async_session.add(org)
      await async_session.commit()
      await async_session.refresh(org)
      return org
  ```

- [ ] **Set up parallel test execution**:
  ```bash
  # Install pytest-xdist
  pip install pytest-xdist

  # Run tests in parallel (4 workers)
  pytest -n 4
  ```

- [ ] **Configure test database isolation**:
  ```python
  # conftest.py - ensure each test gets fresh database
  @pytest.fixture(scope="function")
  async def async_session():
      async with async_session_maker() as session:
          async with session.begin():
              yield session
              await session.rollback()  # Rollback after each test
  ```

**Hours**: 12-16 hours
**Owner**: QA Engineer

---

### Day 3-5: Authentication Testing (QA + Backend Dev)

#### Templates Created ✅
- [x] `test_auth_registration.py` (2 example tests + 8 TODOs)
- [x] `test_auth_login.py` (2 example tests + 10 TODOs)
- [x] E2E auth flows template (`auth-flows.spec.ts`)

#### Implementation Checklist 🚧

**Registration Tests** (15 tests total):
- [ ] test_user_signup_success ✅ (template provided)
- [ ] test_user_signup_duplicate_email ✅ (template provided)
- [ ] test_user_signup_weak_password
- [ ] test_user_signup_invalid_email
- [ ] test_email_verification_flow
- [ ] test_signup_rate_limiting
- [ ] test_signup_missing_required_fields
- [ ] test_signup_with_organization_creation
- [ ] test_signup_password_complexity_enforcement
- [ ] test_signup_email_normalization (lowercase, trim)
- [ ] test_signup_profanity_filter (if implemented)
- [ ] test_signup_disposable_email_blocking (if implemented)
- [ ] test_signup_concurrent_requests_same_email
- [ ] test_signup_xss_prevention (malicious input)
- [ ] test_signup_sql_injection_prevention

**Login Tests** (12 tests total):
- [ ] test_login_success ✅ (template provided)
- [ ] test_login_invalid_credentials ✅ (template provided)
- [ ] test_login_locked_account
- [ ] test_login_unverified_email
- [ ] test_login_session_creation
- [ ] test_login_rate_limiting
- [ ] test_login_nonexistent_email
- [ ] test_login_case_insensitive_email
- [ ] test_login_with_whitespace_handling
- [ ] test_login_missing_fields
- [ ] test_concurrent_sessions_allowed
- [ ] test_session_expiration

**Token Management Tests** (8 tests - create `test_tokens.py`):
- [ ] test_access_token_generation
- [ ] test_refresh_token_rotation
- [ ] test_token_expiration
- [ ] test_token_revocation
- [ ] test_invalid_token_handling
- [ ] test_token_format_validation
- [ ] test_token_claims_verification
- [ ] test_token_signature_validation

**MFA Tests** (10 tests - create `test_mfa.py`):
- [ ] test_totp_setup
- [ ] test_totp_verification
- [ ] test_backup_codes_generation
- [ ] test_backup_codes_usage
- [ ] test_sms_mfa_flow (if SMS implemented)
- [ ] test_mfa_enrollment_flow
- [ ] test_mfa_disable_flow
- [ ] test_mfa_recovery_flow
- [ ] test_mfa_rate_limiting
- [ ] test_invalid_mfa_code_handling

**Password Reset Tests** (8 tests - create `test_password_reset.py`):
- [ ] test_password_reset_request
- [ ] test_password_reset_token_generation
- [ ] test_password_reset_token_expiration
- [ ] test_password_reset_with_valid_token
- [ ] test_password_reset_with_expired_token
- [ ] test_password_reset_rate_limiting
- [ ] test_password_reset_email_not_found
- [ ] test_password_cannot_reuse_old_password

**Total**: 53 integration tests (target: 50+)

**Hours**: 20-24 hours
**Owner**: QA Engineer (15hrs) + Backend Developer (5-9hrs for edge cases)

---

### Day 3-5 (Parallel): E2E Authentication Tests

#### Tasks 🚧
- [ ] **Set up test user creation script**:
  ```bash
  # scripts/create-test-user.sh
  curl -X POST http://localhost:8000/api/v1/auth/signup \
    -H "Content-Type: application/json" \
    -d '{
      "email": "e2e-test@example.com",
      "password": "E2ETestPassword123!",
      "full_name": "E2E Test User"
    }'
  ```

- [ ] **Configure Playwright for API testing**:
  ```typescript
  // playwright.config.ts - add API base URL
  use: {
    baseURL: 'http://localhost:3000',
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
  },
  ```

- [ ] **Implement E2E tests from template**:
  - [ ] User registration and email verification flow
  - [ ] Login flow with valid credentials ✅ (template provided)
  - [ ] Login with invalid credentials
  - [ ] Password reset complete journey
  - [ ] MFA enrollment and login flow
  - [ ] Session persistence across refreshes
  - [ ] Logout clears session
  - [ ] Protected route auth guards
  - [ ] Social login (if OAuth ready)
  - [ ] Account lockout after failed attempts

**Hours**: 12-16 hours
**Owner**: QA Engineer

---

### Day 3-5 (Optional): Admin Dashboard MVP

**Only if Frontend Developer available**

#### Features to Implement

**User Management** (`apps/dashboard-admin/src/pages/users/`):
- [ ] User list page with data table
  - Columns: Name, Email, Status, Created, Actions
  - Pagination (20 per page)
  - Search by email/name
  - Filter by status (active/suspended/deleted)
- [ ] User detail page
  - View user profile
  - View sessions
  - View activity log
- [ ] User actions
  - Suspend/unsuspend user
  - Trigger password reset
  - Delete user (soft delete)

**Organization Management** (`apps/dashboard-admin/src/pages/organizations/`):
- [ ] Organization list
- [ ] Organization creation form
- [ ] Organization detail view
- [ ] Member management

**Analytics Dashboard** (`apps/dashboard-admin/src/pages/dashboard/`):
- [ ] User growth chart (daily/weekly/monthly)
- [ ] Authentication events timeline
- [ ] API usage metrics
- [ ] Error rate monitoring

**Hours**: 20-24 hours
**Owner**: Frontend Developer

---

## 🧪 Running Tests

### API Tests (Python/pytest)

```bash
# Navigate to API directory
cd apps/api

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run only integration tests
pytest -m integration

# Run only auth tests
pytest -m auth

# Run fast tests (exclude slow)
pytest -m "not slow"

# Run specific test file
pytest tests/integration/test_auth_registration.py

# Run specific test
pytest tests/integration/test_auth_registration.py::TestUserRegistration::test_user_signup_success

# Run in parallel (4 workers)
pytest -n 4

# Watch mode (auto-rerun on file changes)
pytest-watch
```

### E2E Tests (Playwright)

```bash
# From project root

# Run all E2E tests
npx playwright test

# Run with UI mode (interactive)
npx playwright test --ui

# Run specific test file
npx playwright test tests-e2e/auth-flows.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Debug mode
npx playwright test --debug

# Generate code (record actions)
npx playwright codegen http://localhost:3000
```

---

## 📊 Monitoring Progress

### Coverage Tracking

```bash
# Generate HTML coverage report
cd apps/api
pytest --cov=app --cov-report=html

# Open coverage report in browser
open htmlcov/index.html

# Check coverage percentage
pytest --cov=app --cov-report=term | grep "TOTAL"
```

### CI/CD Monitoring

- **GitHub Actions**: Check workflow runs at `https://github.com/{org}/janua/actions`
- **Codecov Dashboard**: View coverage trends at `https://app.codecov.io/gh/{org}/janua`
- **PR Comments**: Coverage diff automatically commented on PRs

---

## ✅ Definition of Done

### Week 1 Success Criteria

- [ ] **Testing Coverage**: ≥40% (stretch: ≥50%)
- [ ] **CI/CD Pipeline**: All tests passing on main branch
- [ ] **Integration Tests**: ≥50 new tests added
- [ ] **E2E Tests**: ≥10 auth flow scenarios covered
- [ ] **Code Quality**: All new code passes linting (ruff, black, mypy)
- [ ] **Documentation**: Test patterns documented in `TEST_PATTERNS.md`
- [ ] **Admin Dashboard**: MVP complete (if frontend dev available)

### Quality Gates

All PRs must pass:
- ✅ All tests passing (100% pass rate)
- ✅ No decrease in coverage percentage
- ✅ No linting errors
- ✅ No type checking errors
- ✅ E2E tests passing

---

## 🚨 Common Issues & Solutions

### Issue: Tests fail with database connection errors
**Solution**: Ensure PostgreSQL and Redis are running:
```bash
# Start with Docker Compose
cd apps/api
docker-compose up -d

# Verify services healthy
docker-compose ps
```

### Issue: Codecov token not working
**Solution**: Regenerate token and update GitHub Secret:
1. Go to Codecov project settings
2. Click "Regenerate token"
3. Update in GitHub: `Settings → Secrets → Actions → CODECOV_TOKEN`

### Issue: Tests are slow
**Solution**: Use parallel execution and optimize database setup:
```bash
# Run in parallel
pytest -n 4

# Use in-memory database for unit tests
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
```

### Issue: E2E tests timing out
**Solution**: Increase timeout in playwright.config.ts:
```typescript
use: {
  actionTimeout: 10000,  // Increase to 10s
  navigationTimeout: 30000,  // Increase to 30s
}
```

---

## 📈 Next Steps (Week 2)

After completing Week 1:

1. **Expand to 50% coverage** (Week 2 goal)
   - Enterprise features testing (SSO, SCIM)
   - Organization management tests
   - Webhook delivery tests

2. **Performance testing baseline**
   - Load testing with k6 or Artillery
   - Database query optimization
   - API response time benchmarks

3. **Security testing**
   - OWASP ZAP scan
   - Dependency vulnerability scan
   - Penetration testing preparation

---

## 🤝 Team Coordination

### Daily Standup (15 min)
- What did you complete yesterday?
- What are you working on today?
- Any blockers?

### End of Day (5 min)
- Update GitHub issue/project board
- Push code to branch (don't leave uncommitted work)
- Note coverage percentage change

### End of Week Review (30 min)
- Demo completed tests
- Review coverage report
- Discuss challenges and lessons learned
- Plan Week 2 priorities

---

## 📚 Resources

**Testing Documentation**:
- pytest: https://docs.pytest.org
- pytest-asyncio: https://pytest-asyncio.readthedocs.io
- Playwright: https://playwright.dev

**Coverage Tools**:
- pytest-cov: https://pytest-cov.readthedocs.io
- Codecov: https://docs.codecov.com

**Internal Docs**:
- `apps/api/tests/TEST_PATTERNS.md` - Testing patterns and conventions
- `apps/api/tests/conftest.py` - Test fixtures and configuration

---

**Status**: Foundation complete ✅
**Next Action**: QA Engineer to configure Codecov and begin test implementation
**Timeline**: 5 working days (January 13-17, 2025)
