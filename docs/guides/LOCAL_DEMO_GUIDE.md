# Local Demo Guide - Test Everything

**Complete step-by-step guide to run and test the entire Janua platform locally**

**Time Required**: 10-15 minutes for complete setup and demo

---

## Prerequisites Check

Before starting, verify you have:

```bash
# Check Node.js (should be v18+)
node --version

# Check Python (should be 3.11+)
python --version

# Check Docker (optional but recommended)
docker --version
docker-compose --version

# Check current directory
pwd  # Should be: /Users/aldoruizluna/labspace/janua
```

---

## 🚀 Quick Start (3 Steps)

### Step 1: Start Backend Services (PostgreSQL + Redis)

**Option A: Using Docker (Recommended)**
```bash
# Start database and cache
cd apps/api
docker-compose up -d postgres redis

# Verify services are running
docker-compose ps

# Expected output:
# postgres    running    0.0.0.0:5432->5432/tcp
# redis       running    0.0.0.0:6379->6379/tcp
```

**Option B: Using Local Services**
```bash
# Start PostgreSQL (if installed locally)
brew services start postgresql@15

# Start Redis (if installed locally)
brew services start redis

# Create database
createdb janua_db
```

### Step 2: Start FastAPI Backend

```bash
# Open new terminal window
cd apps/api

# Install Python dependencies (first time only)
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

**Verify API is running**:
```bash
# In another terminal
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","database":"connected","redis":"connected"}
```

### Step 3: Start Demo Application

```bash
# Open new terminal window
cd apps/demo

# Install dependencies (first time only)
npm install

# Start demo app
npm run dev

# Expected output:
# ▲ Next.js 14.2.5
# - Local:        http://localhost:3002
# ✓ Ready in 2.3s
```

---

## 🎯 Test the Demo (Interactive Walkthrough)

### Part 1: API Documentation & Testing

**1. Open API Docs** → http://localhost:8000/docs

**What you'll see**:
- Interactive Swagger/OpenAPI interface
- All authentication endpoints organized by category
- Try-it-now functionality

**Test Authentication Flow**:

```bash
# Test 1: Health check
curl http://localhost:8000/health

# Test 2: Create a test user
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@janua.dev",
    "password": "SecurePass123!",
    "first_name": "Demo",
    "last_name": "User"
  }'

# Expected response (JWT tokens):
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",
#   "user": { ... }
# }

# Test 3: Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@janua.dev",
    "password": "SecurePass123!"
  }'

# Test 4: Get current user (use access_token from above)
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Available API Sections**:
- ✅ `/api/v1/auth/*` - Authentication (signup, login, logout, refresh)
- ✅ `/api/v1/mfa/*` - Multi-factor authentication (TOTP, backup codes)
- ✅ `/api/v1/passkeys/*` - WebAuthn/FIDO2 passkeys
- ✅ `/api/v1/oauth/*` - Social OAuth (Google, GitHub, Microsoft)
- ✅ `/api/v1/sso/*` - Enterprise SSO (SAML, OIDC)
- ✅ `/api/v1/organizations/*` - Multi-tenancy
- ✅ `/api/v1/users/*` - User management
- ✅ `/api/v1/sessions/*` - Session management
- ✅ `/api/v1/admin/*` - Admin endpoints

### Part 2: Demo Application Showcases

**1. Open Demo App** → http://localhost:3002

**Home Page Features**:
- Hero section with value proposition
- Feature grid showcasing capabilities
- Code examples for quick start
- Pricing comparison
- Framework support badges

**2. Authentication Showcases** → http://localhost:3002/auth

**Available Showcase Pages**:

1. **Sign In Showcase** → http://localhost:3002/auth/signin-showcase
   - Email/password authentication
   - Social OAuth buttons (Google, GitHub, Microsoft, Apple)
   - Remember me checkbox
   - Password visibility toggle
   - Error handling demo
   - Success redirect flow

2. **Sign Up Showcase** → http://localhost:3002/auth/signup-showcase
   - User registration form
   - Password strength indicator
   - Email validation
   - Terms acceptance
   - Success flow with verification

3. **Email Verification Showcase** → http://localhost:3002/auth/verification-showcase
   - Email verification code entry
   - Resend code functionality
   - Auto-submit on 6-digit completion
   - Timer for resend cooldown

4. **Password Reset Showcase** → http://localhost:3002/auth/password-reset-showcase
   - Forgot password flow
   - Email verification
   - New password entry
   - Strength requirements display

5. **MFA Setup Showcase** → http://localhost:3002/auth/mfa-showcase
   - TOTP setup with QR code
   - Manual secret key entry
   - Backup codes generation
   - MFA verification challenge
   - Device trust options

**Interactive Testing**:

Each showcase page includes:
- ✅ **Live component preview** - Fully functional UI
- ✅ **Props customization** - Toggle options to see variations
- ✅ **Theme switcher** - Light/dark mode testing
- ✅ **Code snippets** - Copy-paste integration code
- ✅ **API integration** - Real backend connections

**Example: Test Sign In Flow**

1. Navigate to http://localhost:3002/auth/signin-showcase
2. Enter credentials:
   - Email: `demo@janua.dev`
   - Password: `SecurePass123!`
3. Click "Sign In"
4. Observe:
   - Loading state animation
   - Success/error messages
   - Redirect behavior
   - JWT token storage

### Part 3: Component Library Testing

**UI Component Showcase** → http://localhost:3002/components

**Available Components**:

1. **Auth Components** (15 components)
   - SignIn, SignUp, UserProfile
   - MFASetup, MFAChallenge, BackupCodes
   - EmailVerification, PhoneVerification
   - PasswordReset, UserButton
   - SessionManagement, DeviceManagement
   - OrganizationProfile, OrganizationSwitcher
   - AuditLog

2. **Enterprise Components** (8 components)
   - SSOProviderForm, SSOProviderList
   - SSOTestConnection, SAMLConfigForm
   - InviteUserForm, InvitationList
   - InvitationAccept, BulkInviteUpload

3. **SCIM Components** (2 components)
   - SCIMConfigWizard, SCIMSyncStatus

4. **RBAC Components** (1 component)
   - RoleManager

5. **Compliance Components** (3 components)
   - ConsentManager, PrivacySettings
   - DataSubjectRequest

6. **Payment Components** (5 components)
   - SubscriptionPlans, SubscriptionManagement
   - PaymentMethodForm, InvoiceList
   - BillingPortal

**Testing Each Component**:

```typescript
// Example: Test SignIn component
import { SignIn } from '@janua/ui'

<SignIn
  redirectUrl="/dashboard"
  signUpUrl="/signup"
  socialProviders={{
    google: true,
    github: true,
    microsoft: true,
    apple: true
  }}
  appearance={{
    theme: 'light',
    variables: {
      colorPrimary: '#3B82F6'
    }
  }}
  showRememberMe={true}
/>
```

### Part 4: End-to-End Testing (Playwright)

**Run E2E Tests**:

```bash
# In apps/demo directory
npm run e2e

# Run specific test suite
npm run e2e -- auth-signin.spec.ts

# Run in headed mode (see browser)
npm run e2e:headed

# Run in UI mode (interactive)
npm run e2e:ui

# Debug mode
npm run e2e:debug
```

**Available E2E Test Suites** (94+ scenarios):

1. **Authentication Flow** (10 tests)
   - Complete sign-up flow with email verification
   - Sign-in with valid credentials
   - Sign-in with invalid credentials
   - Password reset flow
   - Session persistence after page reload

2. **Password Reset Flow** (9 tests)
   - Request password reset email
   - Verify reset code
   - Update password
   - Login with new password

3. **MFA Setup & Verification** (10 tests)
   - Enable TOTP MFA
   - Generate backup codes
   - Verify MFA challenge
   - Use backup code
   - Disable MFA

4. **Organization Management** (8 tests)
   - Create new organization
   - Switch between organizations
   - Invite team members
   - Manage member roles

5. **Session & Device Management** (12 tests)
   - View active sessions
   - Revoke session
   - Trust device
   - View audit log

**Expected Test Results**:
```
✓ 94 tests passed (11 suites)
✓ Test duration: ~3-5 minutes
✓ All critical user journeys validated
```

### Part 5: Performance Testing

**Run Lighthouse Audit**:

```bash
# In apps/demo directory
npm run build
npm run start

# In another terminal, run Lighthouse
npx lighthouse http://localhost:3002 \
  --output html \
  --output-path ./lighthouse-report.html \
  --chrome-flags="--headless"

# Open report
open lighthouse-report.html
```

**Expected Performance**:
- **Performance**: 84/100
- **Accessibility**: 95/100
- **Best Practices**: 95/100
- **SEO**: 100/100

**Performance Metrics**:
- First Contentful Paint: <1.5s
- Largest Contentful Paint: <2.5s
- Time to Interactive: <3.5s
- Cumulative Layout Shift: <0.1

### Part 6: Backend Testing

**Run Python Tests**:

```bash
# In apps/api directory
ENVIRONMENT=test DATABASE_URL="sqlite+aiosqlite:///:memory:" \
python -m pytest tests/test_100_coverage.py -v --tb=short

# Run all tests with coverage
ENVIRONMENT=test DATABASE_URL="sqlite+aiosqlite:///:memory:" \
python -m pytest tests/ --cov=app --cov-report=term-missing --tb=no -q
```

**Expected Results**:
- ✅ 3,784+ test cases passing
- ✅ 75-85% test coverage
- ✅ Zero critical failures

**Test Categories**:
- Authentication service tests
- JWT service tests  
- MFA service tests
- SSO service tests
- Organization service tests
- RBAC engine tests
- Billing service tests
- Compliance service tests

---

## 📊 Demo Script (15-Minute Walkthrough)

Use this script to demonstrate Janua's capabilities:

### Minute 0-2: Platform Overview

**Open**: http://localhost:3002

**Talking Points**:
- "Janua is an enterprise authentication platform that combines Better-Auth's data control with Clerk's developer experience"
- "Everything you see is 100% free and open source - including enterprise SSO, SCIM, MFA, and multi-tenancy"
- "Let me show you how it works..."

### Minute 2-5: API Capabilities

**Open**: http://localhost:8000/docs

**Demonstrate**:
1. **Health Check**:
   ```bash
   curl http://localhost:8000/health
   ```
   - Show database and Redis connectivity

2. **User Registration**:
   - Navigate to `/api/v1/auth/signup` in Swagger UI
   - Click "Try it out"
   - Use sample data:
     ```json
     {
       "email": "demo@company.com",
       "password": "SecurePass123!",
       "first_name": "Demo",
       "last_name": "User"
     }
     ```
   - Execute and show JWT tokens returned

3. **Authentication**:
   - Navigate to `/api/v1/auth/login`
   - Login with same credentials
   - Show access token and refresh token

**Talking Points**:
- "Direct database writes - no webhooks, no sync failures"
- "Full REST API with OpenAPI documentation"
- "Production-ready with comprehensive error handling"

### Minute 5-8: UI Components

**Open**: http://localhost:3002/auth/signin-showcase

**Demonstrate**:
1. **Sign In Component**:
   - Show customization options (theme, social providers)
   - Enter credentials and sign in
   - Show success flow

2. **Switch to Sign Up**:
   - Navigate to http://localhost:3002/auth/signup-showcase
   - Show password strength indicator
   - Show validation feedback

3. **MFA Setup**:
   - Navigate to http://localhost:3002/auth/mfa-showcase
   - Show TOTP QR code generation
   - Show backup codes
   - Show MFA challenge flow

**Talking Points**:
- "40+ production-ready UI components"
- "Fully customizable - theme, colors, logos"
- "10-minute integration from npm install to working auth flow"

### Minute 8-11: Enterprise Features (All Free)

**Open**: http://localhost:8000/docs

**Demonstrate**:

1. **SSO Configuration**:
   - Navigate to `/api/v1/sso/configurations`
   - Show SAML and OIDC support
   - Show metadata endpoints

2. **Organization Management**:
   - Navigate to `/api/v1/organizations`
   - Show multi-tenancy support
   - Show member management

3. **SCIM Provisioning**:
   - Navigate to `/api/v1/scim/v2/Users`
   - Show SCIM 2.0 endpoints
   - Show automatic user provisioning

**Talking Points**:
- "These features cost $2,000-5,000/month in Auth0"
- "Clerk charges $1,000+/month for SSO"
- "In Janua? Free forever in our AGPL v3-licensed OSS"
- "We charge for managed hosting convenience, not capabilities"

### Minute 11-13: Migration Path (Anti-Lock-In)

**Open**: `docs/migration/cloud-to-self-hosted.md`

**Demonstrate**:
- Show 132-line migration guide
- Show export API endpoints
- Show import script
- Show zero-downtime cutover strategy

**Talking Points**:
- "Complete data portability - no vendor lock-in"
- "2-4 hour migration from our cloud to self-hosted"
- "Your data is always in your database"
- "No competitor offers this level of portability"

### Minute 13-15: Framework Support & SDK

**Open**: http://localhost:3002

**Demonstrate**:
- Show framework badges (React, Vue, Next.js, React Native)
- Show code examples
- Show SDK documentation

**Talking Points**:
- "Framework-agnostic unlike Clerk's React-only focus"
- "TypeScript SDKs for React, Vue, Next.js, React Native"
- "Coming Q1 2026: Svelte, Astro, Solid, Angular, Flutter"
- "One authentication platform for all your apps"

**Close**:
- "Production-ready today"
- "100% free and open source"
- "No vendor lock-in, complete data control"
- "Questions?"

---

## 🐛 Troubleshooting

### Issue: Port Already in Use

**Symptom**: `Error: listen EADDRINUSE: address already in use :::8000`

**Solution**:
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 PID

# Or use different port
uvicorn main:app --port 8001
```

### Issue: Database Connection Failed

**Symptom**: `sqlalchemy.exc.OperationalError: could not connect to server`

**Solution**:
```bash
# Check PostgreSQL is running
docker-compose ps

# Restart PostgreSQL
docker-compose restart postgres

# Check connection
psql -U janua -h localhost -d janua_db
```

### Issue: Redis Connection Failed

**Symptom**: `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution**:
```bash
# Check Redis is running
docker-compose ps

# Restart Redis
docker-compose restart redis

# Test connection
redis-cli ping  # Should return PONG
```

### Issue: Module Not Found (Python)

**Symptom**: `ModuleNotFoundError: No module named 'fastapi'

**Solution**:
```bash
# Install dependencies
cd apps/api
pip install -r requirements.txt

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Module Not Found (Node.js)

**Symptom**: `Error: Cannot find module '@janua/ui'

**Solution**:
```bash
# Install dependencies
cd apps/demo
npm install

# Build local packages (if needed)
cd ../..
npm run build
```

### Issue: Database Migration Failed

**Symptom**: `alembic.util.exc.CommandError: Can't locate revision`

**Solution**:
```bash
# Reset migrations
cd apps/api
alembic stamp head
alembic upgrade head

# Or recreate database
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

### Issue: E2E Tests Failing

**Symptom**: `Error: Navigation timeout of 30000ms exceeded`

**Solution**:
```bash
# Ensure services are running
curl http://localhost:3002  # Demo app
curl http://localhost:8000/health  # API

# Install Playwright browsers (first time)
npx playwright install

# Run tests with timeout increased
npm run e2e -- --timeout=60000
```

---

## 🎯 Quick Commands Reference

```bash
# Start everything
cd apps/api && docker-compose up -d postgres redis
cd apps/api && uvicorn main:app --reload
cd apps/demo && npm run dev

# Stop everything
# Ctrl+C in terminals, then:
cd apps/api && docker-compose down

# Run tests
cd apps/api && ENVIRONMENT=test DATABASE_URL="sqlite+aiosqlite:///:memory:" python -m pytest
cd apps/demo && npm run e2e

# View logs
cd apps/api && docker-compose logs -f postgres
cd apps/api && docker-compose logs -f redis

# Database operations
cd apps/api && alembic upgrade head  # Run migrations
cd apps/api && alembic downgrade -1  # Rollback one migration
psql -U janua -h localhost -d janua_db  # Connect to DB

# Clean slate
cd apps/api && docker-compose down -v  # Remove volumes
cd apps/api && alembic upgrade head    # Recreate schema
```

---

## 📈 Performance Benchmarks

**Expected local performance**:

| Metric | Target | Actual |
|--------|--------|--------|
| API Response Time (p95) | <200ms | ~50-150ms |
| Database Query Time (p95) | <50ms | ~10-30ms |
| Redis Cache Hit Rate | >80% | ~90% |
| Frontend First Load | <2s | ~1.2-1.8s |
| Frontend Navigation | <500ms | ~100-300ms |
| E2E Test Suite | <5min | ~3-4min |

**Load Testing** (optional):
```bash
# Install k6
brew install k6

# Run load test (100 virtual users, 30 seconds)
k6 run scripts/load-test.js

# Expected throughput: 500-1000 req/sec on local machine
```

---

## ✅ Verification Checklist

After completing the demo, verify:

**Backend**:
- [ ] API health endpoint responds with `{"status":"healthy"}`
- [ ] PostgreSQL accepting connections
- [ ] Redis accepting connections
- [ ] User registration works
- [ ] User login works
- [ ] JWT tokens issued correctly
- [ ] MFA endpoints accessible
- [ ] SSO endpoints accessible
- [ ] Organization endpoints accessible

**Frontend**:
- [ ] Demo app loads at http://localhost:3002
- [ ] All showcase pages accessible
- [ ] Sign in component renders
- [ ] Sign up component renders
- [ ] MFA setup component renders
- [ ] Theme switching works
- [ ] Props customization works
- [ ] Code snippets copy to clipboard

**Testing**:
- [ ] Python unit tests pass (3,784+ tests)
- [ ] E2E tests pass (94 tests)
- [ ] Lighthouse score >80
- [ ] No console errors in browser
- [ ] No errors in API logs

**Documentation**:
- [ ] API docs render at http://localhost:8000/docs
- [ ] Swagger UI interactive features work
- [ ] README displays correctly
- [ ] Migration guide accessible

---

## 🚀 Next Steps

After completing local testing:

1. **Publish SDKs to npm** (when ready)
   ```bash
   cd packages/react-sdk && npm publish
   cd packages/vue-sdk && npm publish
   cd packages/nextjs-sdk && npm publish
   ```

2. **Deploy API to production**
   - Follow `docs/DEPLOYMENT.md`
   - Configure production environment
   - Set up monitoring and logging

3. **Deploy demo app**
   - Vercel: `vercel deploy`
   - Railway: `railway up`
   - Custom: `npm run build && npm start`

4. **Launch Janua Cloud** (Q1 2026)
   - Managed hosting platform
   - Zero-config deployment
   - Git integration
   - Auto-scaling

---

**Questions or Issues?**
- GitHub Discussions: https://github.com/madfam-org/janua/discussions
- Discord: https://discord.gg/janua
- Email: support@janua.dev
