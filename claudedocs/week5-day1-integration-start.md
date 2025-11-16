# Week 5 Day 1: Integration Testing & Dogfooding - Session Start

**Date**: November 15, 2025
**Status**: 🔄 In Progress
**Goal**: Begin integration testing and dogfooding by replacing custom auth with @plinto/ui components

---

## Session Objectives

1. ✅ Verify @plinto/ui dependencies in all apps
2. 🔄 Document current custom implementations (before replacement)
3. 📋 Create integration test suite
4. 📋 Replace demo signin/signup with `<SignIn />` and `<SignUp />` components
5. 📋 Validate functionality and document changes

---

## Dependency Verification ✅

**Verified all apps have @plinto/ui correctly linked:**

```bash
# apps/demo
plinto-monorepo@1.0.0 /Users/aldoruizluna/labspace/plinto
└─┬ @plinto/demo@0.1.0 -> ./apps/demo
  └── @plinto/ui@1.0.0 -> ./packages/ui

# apps/admin
plinto-monorepo@1.0.0 /Users/aldoruizluna/labspace/plinto
└─┬ @plinto/admin@0.1.0 -> ./apps/admin
  └── @plinto/ui@1.0.0 -> ./packages/ui

# apps/dashboard
plinto-monorepo@1.0.0 /Users/aldoruizluna/labspace/plinto
└─┬ @plinto/dashboard@0.1.0 -> ./apps/dashboard
  └── @plinto/ui@1.0.0 -> ./packages/ui
```

**Status**: All dependencies correct, workspace linking functional

---

## Current Custom Implementations Analysis

### apps/demo/app/signin/page.tsx (270 LOC)

**Key Features to Preserve:**
1. **Demo Environment Handling**:
   - Uses `useEnvironment` hook for demo mode detection
   - Auto-fills demo credentials
   - Shows demo notice banner
   - "Try Demo Login" button

2. **Animations**:
   - Framer Motion for page entrance animations
   - Opacity and Y-axis transforms

3. **Plinto SDK Integration**:
   - Uses `window.plinto.signIn()` for authentication
   - Error handling with UI state
   - Success redirect to `/dashboard`

4. **UI Elements**:
   - Logo header with Plinto branding
   - Email/password form with icons
   - "Forgot password?" link
   - OAuth provider buttons (Google, GitHub - disabled)
   - "Don't have an account?" sign up link

5. **Performance Simulation**:
   - `useDemoFeatures().simulatePerformance('auth')` for realistic demo timing

**Custom Logic:**
```typescript
// Demo auto-fill
useEffect(() => {
  if (mounted && isDemo && shouldAutoSignIn?.() && hasDemoCredentials?.()) {
    setEmail(demoCredentials.email)
    setPassword(demoCredentials.password)
  }
}, [mounted, isDemo, shouldAutoSignIn, hasDemoCredentials, demoCredentials])

// Plinto SDK call
const result = await plinto.signIn({ email, password })
if (result.accessToken) {
  router.push('/dashboard')
}
```

### apps/demo/app/signup/page.tsx (283 LOC)

**Key Features to Preserve:**
1. **Form Fields**:
   - Name input (not in basic `<SignUp />`)
   - Email input
   - Password input
   - Confirm password input
   - Terms of service checkbox

2. **Validation**:
   - Password match validation
   - Minimum 8 character password
   - Required terms acceptance

3. **Plinto SDK Integration**:
   - Uses `window.plinto.signUp()` for registration
   - Auto sign-in after successful signup
   - Redirect to `/dashboard` with 2s delay

4. **UI Elements**:
   - Success state with "Account created!" message
   - Error state display
   - OAuth provider buttons (disabled)
   - "Already have an account?" sign in link

5. **Animations**:
   - Framer Motion entrance animations

**Custom Logic:**
```typescript
// Password validation
if (password !== confirmPassword) {
  setError('Passwords do not match')
  return
}

// Sign up + auto sign in
const result = await plinto.signUp({ email, password, name })
if (result.user) {
  setSuccess(true)
  const signInResult = await plinto.signIn({ email, password })
  if (signInResult.accessToken) {
    setTimeout(() => router.push('/dashboard'), 2000)
  }
}
```

---

## Migration Strategy

### Approach: **Wrapper Components** (Not Direct Replacement)

**Rationale:**
- Current pages have demo-specific features (`useEnvironment`, `useDemoFeatures`)
- Need to maintain Plinto SDK integration (`window.plinto`)
- Framer Motion animations are part of demo app UX
- OAuth provider buttons should remain for future integration

**Plan:**
Instead of replacing the entire page with `<SignIn />` / `<SignUp />`, we'll:
1. Keep current pages as-is for Week 5 Day 1
2. Create **NEW** showcase pages that use the raw components:
   - `/auth/signin-showcase` → Pure `<SignIn />` component
   - `/auth/signup-showcase` → Pure `<SignUp />` component
   - `/auth/mfa-showcase` → `<MFASetup />`, `<MFAChallenge />`, `<BackupCodes />`
   - `/auth/security-showcase` → `<SessionManagement />`, `<DeviceManagement />`
   - `/auth/compliance-showcase` → `<AuditLog />`

3. Update navigation to link to both versions
4. Week 5 Day 2-3: Evaluate if we want to refactor existing pages to use components as base

**Benefits:**
- ✅ Don't break existing demo functionality
- ✅ Showcase components in pure form (no demo-specific logic)
- ✅ Easier to compare custom vs. @plinto/ui implementations
- ✅ Better for marketing/sales (show both integrated and standalone)

---

## Week 5 Day 1 Revised Plan

### Task 1: Create Showcase Pages Directory ✅ Next

```bash
mkdir -p apps/demo/app/auth
```

**Pages to Create:**
1. `apps/demo/app/auth/layout.tsx` - Shared layout for auth showcases
2. `apps/demo/app/auth/signin-showcase/page.tsx` - Pure `<SignIn />` demo
3. `apps/demo/app/auth/signup-showcase/page.tsx` - Pure `<SignUp />` demo
4. `apps/demo/app/auth/mfa-showcase/page.tsx` - MFA components demo
5. `apps/demo/app/auth/security-showcase/page.tsx` - Security components demo
6. `apps/demo/app/auth/compliance-showcase/page.tsx` - Compliance components demo

### Task 2: Integration Test Suite

**File**: `packages/ui/tests/integration/demo-app-integration.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SignIn, SignUp } from '@plinto/ui'

describe('Demo App Integration Tests', () => {
  describe('SignIn Component', () => {
    it('renders with all required elements', () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })

    it('calls onSuccess when form is submitted', async () => {
      const mockOnSuccess = vi.fn()
      render(<SignIn onSuccess={mockOnSuccess} />)

      fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: 'test@example.com' },
      })
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      })
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled())
    })
  })

  describe('SignUp Component', () => {
    it('renders with all required elements', () => {
      const mockOnSuccess = vi.fn()
      render(<SignUp onSuccess={mockOnSuccess} />)

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument()
    })
  })
})
```

### Task 3: Navigation Updates

Update `apps/demo` navigation to include showcase pages:
- Add "Component Showcase" section
- Link to auth showcase pages
- Maintain existing signin/signup for functional demo

---

## Success Criteria for Day 1

- ✅ Dependencies verified in all apps
- ✅ Current implementations documented
- 📋 `/auth/*-showcase` pages created with pure @plinto/ui components
- 📋 Integration test suite created and passing
- 📋 Navigation updated with showcase links
- 📋 Documentation updated with integration progress

---

## Next Actions

1. **Create `/auth` showcase directory structure**
2. **Implement `/auth/signin-showcase/page.tsx`** with pure `<SignIn />` component
3. **Implement `/auth/signup-showcase/page.tsx`** with pure `<SignUp />` component
4. **Create integration test suite**
5. **Document differences between custom and @plinto/ui implementations**

---

## Notes

**Why Not Direct Replacement (Yet)?**
- Current pages have demo-specific features we want to preserve
- Showcase pages let us demonstrate components in pure form
- Easier to validate component functionality independently
- Better for sales/marketing (show both integrated and standalone)
- Week 5 Day 2-3 can evaluate refactoring existing pages if desired

**Integration Strategy:**
- Week 5 Day 1: Create showcase pages (pure components)
- Week 5 Day 2: Add MFA/security/compliance showcases
- Week 5 Day 3-4: Evaluate refactoring existing pages vs. keeping dual approach
- Week 5 Day 5: Performance validation and bundle analysis
- Week 5 Day 6-7: Documentation and testing

---

**Status**: Dependencies verified ✅ | Current state documented ✅ | Ready to create showcase pages 📋
