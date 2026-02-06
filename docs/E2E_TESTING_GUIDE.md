# E2E Testing Guide

**Last Updated**: November 14, 2025

Quick guide for running Playwright E2E tests locally and in CI/CD.

---

## Quick Start

### Run All E2E Tests
```bash
# Complete test suite (setup → test → teardown)
npm run test:journeys

# This command:
# 1. Starts all services via docker-compose.test.yml
# 2. Waits for health checks
# 3. Runs Playwright tests
# 4. Cleans up containers and volumes
```

### Run Tests Manually (Advanced)
```bash
# 1. Start services
npm run test:journeys:setup

# 2. Run tests (keeps services running)
npx playwright test

# 3. View test report
npx playwright show-report

# 4. Cleanup when done
npm run test:journeys:teardown
```

---

## Test Organization

```
tests/e2e/
├── api-integration.spec.ts       # API endpoint tests (11 tests)
├── auth-flows.spec.ts            # Authentication flows (2 tests)
└── simple-functionality-test.spec.ts  # Marketing site (3 tests)
```

**Total**: 27 tests across 3 suites

---

## Services Required

E2E tests require these services running:

| Service | Port | Health Check |
|---------|------|--------------|
| API Backend | 8000 | `curl http://localhost:8000/health` |
| Landing Page | 3000 | `curl http://localhost:3000` |
| Test App | 3001 | `curl http://localhost:3001` |
| Dashboard | 3002 | `curl http://localhost:3002` |
| PostgreSQL | 5432 | `pg_isready -U test_user` |
| Redis | 6379 | `redis-cli ping` |

All managed by `docker-compose.test.yml`.

---

## Troubleshooting

### "Connection refused" errors

**Cause**: Services not running

**Fix**:
```bash
# Check if services are up
docker-compose -f docker-compose.test.yml ps

# Restart services
npm run test:journeys:teardown
npm run test:journeys:setup
```

### "Port already in use"

**Cause**: Services from previous run still active

**Fix**:
```bash
# Stop all test services
docker-compose -f docker-compose.test.yml down -v

# OR kill specific port
lsof -i :8000  # Find PID
kill -9 <PID>
```

### "Service unhealthy" timeouts

**Cause**: Service taking too long to start

**Fix**:
```bash
# Check service logs
docker-compose -f docker-compose.test.yml logs api

# Increase timeout in docker-compose.test.yml
# Edit healthcheck.start_period: 60s
```

### Tests fail but services are healthy

**Cause**: Test assertions failing (expected behavior during development)

**Fix**: This is normal - fix the test or application code, not the infrastructure.

---

## CI/CD Integration

### GitHub Actions

E2E tests run automatically on:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Workflow**: `.github/workflows/e2e-tests.yml`

### View Results

1. Go to repository **Actions** tab
2. Select **E2E Tests** workflow
3. Click on specific run
4. Download artifacts:
   - `playwright-report` - Full HTML report
   - `test-results` - Screenshots, videos, traces

---

## Local Development Tips

### Run Specific Test File
```bash
# Start services first
npm run test:journeys:setup

# Run single test file
npx playwright test api-integration.spec.ts

# Run with UI mode (headed browser)
npx playwright test --headed

# Debug specific test
npx playwright test --debug
```

### Watch Mode
```bash
# Start services
npm run test:journeys:setup

# Run tests in watch mode
npx playwright test --watch
```

### Interactive Mode
```bash
# Playwright UI (best for development)
npx playwright test --ui
```

---

## Configuration

### Playwright Config

**File**: `playwright.config.ts`

```typescript
{
  testDir: './tests/e2e',
  baseURL: 'http://localhost:3000',
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined
}
```

### Test Environment

**File**: `docker-compose.test.yml`

Test environment uses:
- Isolated test database (`janua_test`)
- Separate Redis instance
- Test-specific environment variables
- Health checks for reliability

---

## Best Practices

### Writing E2E Tests

1. **Use beforeEach for common setup**
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('http://localhost:3000');
});
```

2. **Test user journeys, not implementation**
```typescript
// ✅ Good - tests user behavior
test('User can register', async ({ page }) => {
  await page.fill('[name="email"]', 'test@example.com');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/dashboard/);
});

// ❌ Bad - tests implementation details
test('Register button calls API', async ({ page }) => {
  // Don't test API calls in E2E tests
});
```

3. **Use API tests for backend, E2E for flows**
```typescript
// API tests: Fast, focused on endpoints
test('Health endpoint returns 200', async ({ request }) => {
  const response = await request.get('/health');
  expect(response.status()).toBe(200);
});

// E2E tests: Slow, focused on user journeys
test('User registration flow', async ({ page }) => {
  // Full browser interaction
});
```

---

## Performance Tips

### Speed Up Tests

1. **Use API context for non-UI tests**
```typescript
// Faster - no browser needed
test('API returns data', async ({ request }) => {
  const response = await request.get('/api/users');
  expect(response.ok()).toBeTruthy();
});
```

2. **Parallelize independent tests**
```typescript
// Tests in different describe blocks run in parallel
test.describe.configure({ mode: 'parallel' });
```

3. **Use beforeAll for expensive setup**
```typescript
test.beforeAll(async () => {
  // Expensive one-time setup
});
```

---

## Common Commands Reference

```bash
# Full test suite
npm run test:journeys

# Setup only
npm run test:journeys:setup

# Wait for services
npm run test:journeys:wait

# Teardown only
npm run test:journeys:teardown

# Run tests (services must be running)
npx playwright test

# Run specific test
npx playwright test api-integration

# Debug mode
npx playwright test --debug

# UI mode
npx playwright test --ui

# View last test report
npx playwright show-report

# Update snapshots
npx playwright test --update-snapshots
```

---

## Getting Help

1. **Check service logs**:
   ```bash
   docker-compose -f docker-compose.test.yml logs -f
   ```

2. **Verify service health**:
   ```bash
   docker-compose -f docker-compose.test.yml ps
   ```

3. **View Playwright trace**:
   ```bash
   npx playwright show-trace test-results/trace.zip
   ```

4. **Documentation**:
   - [Playwright Docs](https://playwright.dev)
   - [`docs/PLAYWRIGHT_E2E_TEST_FAILURES.md`](./PLAYWRIGHT_E2E_TEST_FAILURES.md) - Troubleshooting guide

---

## Summary

- **Run tests**: `npm run test:journeys`
- **Local dev**: `npm run test:journeys:setup` → `npx playwright test --ui`
- **CI/CD**: Automatic on push/PR via GitHub Actions
- **Troubleshoot**: Check service logs and health endpoints

E2E tests validate complete user journeys across API, frontend apps, and data layer. Keep them focused on user behavior, not implementation details.
