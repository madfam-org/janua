# Week 5: Integration Testing & Dogfooding Implementation Plan

**Timeline**: Week 5 (Post Week 4 Completion)
**Goal**: Validate all 15 components in real applications and begin dogfooding strategy
**Status**: 📋 Ready to Execute

## Overview

Week 4 delivered 15 production-ready authentication components. Week 5 focuses on:
1. **Integration Testing**: Validate components work correctly in consuming applications
2. **Dogfooding Implementation**: Replace custom code with @plinto/ui in demo/admin/dashboard apps
3. **Real-World Validation**: Ensure components meet actual usage requirements
4. **Performance Verification**: Validate bundle size and runtime performance

## Phase 1: Integration Testing Setup (Days 1-2)

### Task 1.1: Configure Test Infrastructure

**apps/demo Integration:**
```bash
# Verify @plinto/ui dependency
cd apps/demo
npm ls @plinto/ui

# Run build to verify tree-shaking
npm run build
npm run build:demo

# Check bundle size
ls -lh .next/static/chunks/*.js | head -20
```

**Expected Outcome:**
- ✅ @plinto/ui resolves correctly
- ✅ Build succeeds without errors
- ✅ Bundle size <500KB total for demo app
- ✅ Tree-shaking eliminates unused components

### Task 1.2: Create Integration Test Suite

**File**: `packages/ui/tests/integration/component-integration.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  SignIn,
  SignUp,
  UserButton,
  MFASetup,
  SessionManagement,
  DeviceManagement,
  AuditLog
} from '@plinto/ui'

describe('Component Integration Tests', () => {
  describe('Authentication Flow Components', () => {
    it('SignIn renders with required props', () => {
      render(<SignIn onSuccess={() => {}} />)
      expect(screen.getByRole('form')).toBeInTheDocument()
    })

    it('SignUp renders with validation', () => {
      render(<SignUp onSuccess={() => {}} />)
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    })
  })

  describe('Security Components', () => {
    it('SessionManagement renders with sessions', () => {
      const sessions = [
        {
          id: 'session-1',
          device: { type: 'desktop', name: 'Test Device' },
          createdAt: new Date(),
          lastActiveAt: new Date(),
        },
      ]
      render(<SessionManagement sessions={sessions} currentSessionId="session-1" />)
      expect(screen.getByText(/Test Device/i)).toBeInTheDocument()
    })
  })

  describe('Compliance Components', () => {
    it('AuditLog renders with events', () => {
      const events = [
        {
          id: 'evt-1',
          type: 'auth.login',
          category: 'auth',
          actor: { id: 'user-1', email: 'test@example.com' },
          timestamp: new Date(),
        },
      ]
      render(<AuditLog events={events} />)
      expect(screen.getByText(/test@example.com/i)).toBeInTheDocument()
    })
  })
})
```

**Run Tests:**
```bash
cd packages/ui
npm run test
npm run test:coverage
```

**Expected Coverage:**
- ✅ All 15 components render without errors
- ✅ Props validation works correctly
- ✅ Accessibility attributes present
- ✅ No console errors or warnings

## Phase 2: Dogfooding Implementation (Days 3-4)

### Task 2.1: Replace apps/demo Authentication Pages

**Current State:**
```typescript
// apps/demo/app/signin/page.tsx (BEFORE)
'use client'
import { Button, Input, Card } from '@plinto/ui'

export default function SignInPage() {
  return (
    <Card>
      <form>{/* Custom form implementation */}</form>
    </Card>
  )
}
```

**Target State:**
```typescript
// apps/demo/app/signin/page.tsx (AFTER)
'use client'
import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  const handleSuccess = (data) => {
    console.log('Login successful:', data)
    window.location.href = '/dashboard'
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn
        onSuccess={handleSuccess}
        onError={(error) => console.error('Login error:', error)}
        logoUrl="/logo.svg"
      />
    </div>
  )
}
```

**Files to Update:**

| File | Current Implementation | Replace With |
|------|------------------------|--------------|
| `apps/demo/app/signin/page.tsx` | Custom form | `<SignIn />` |
| `apps/demo/app/signup/page.tsx` | Custom form | `<SignUp />` |
| `apps/demo/app/dashboard/page.tsx` | Custom layout | `<UserButton />` |

**Validation:**
```bash
cd apps/demo
npm run dev
# Navigate to http://localhost:3002/signin
# Verify SignIn component renders and functions correctly
```

### Task 2.2: Add Component Showcase Pages

**New Pages to Create:**

1. **MFA Showcase** (`apps/demo/app/mfa/page.tsx`):
```typescript
'use client'
import { MFASetup, MFAChallenge, BackupCodes } from '@plinto/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@plinto/ui'

export default function MFAShowcase() {
  return (
    <div className="container mx-auto py-12">
      <h1 className="text-3xl font-bold mb-8">Multi-Factor Authentication</h1>
      <Tabs defaultValue="setup">
        <TabsList>
          <TabsTrigger value="setup">Setup</TabsTrigger>
          <TabsTrigger value="challenge">Challenge</TabsTrigger>
          <TabsTrigger value="backup">Backup Codes</TabsTrigger>
        </TabsList>
        <TabsContent value="setup">
          <MFASetup onComplete={(secret, qrCode) => console.log('MFA enabled')} />
        </TabsContent>
        <TabsContent value="challenge">
          <MFAChallenge onSuccess={() => console.log('MFA verified')} />
        </TabsContent>
        <TabsContent value="backup">
          <BackupCodes codes={['CODE1', 'CODE2', 'CODE3']} onDownload={() => {}} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

2. **Security Showcase** (`apps/demo/app/security/page.tsx`):
```typescript
'use client'
import { SessionManagement, DeviceManagement } from '@plinto/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@plinto/ui'

export default function SecurityShowcase() {
  const sessions = [/* sample session data */]
  const devices = [/* sample device data */]

  return (
    <div className="container mx-auto py-12">
      <h1 className="text-3xl font-bold mb-8">Security Management</h1>
      <Tabs defaultValue="sessions">
        <TabsList>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="devices">Devices</TabsTrigger>
        </TabsList>
        <TabsContent value="sessions">
          <SessionManagement
            sessions={sessions}
            currentSessionId="current"
            onRevokeSession={async (id) => console.log('Revoke:', id)}
          />
        </TabsContent>
        <TabsContent value="devices">
          <DeviceManagement
            devices={devices}
            currentDeviceId="current"
            onTrustDevice={async (id) => console.log('Trust:', id)}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

3. **Compliance Showcase** (`apps/demo/app/compliance/page.tsx`):
```typescript
'use client'
import { AuditLog } from '@plinto/ui'

export default function ComplianceShowcase() {
  const events = [/* sample audit events */]

  return (
    <div className="container mx-auto py-12">
      <h1 className="text-3xl font-bold mb-8">Compliance & Audit Logs</h1>
      <AuditLog
        events={events}
        showExport={true}
        showFilters={true}
        onExport={async (format) => console.log('Export:', format)}
      />
    </div>
  )
}
```

### Task 2.3: apps/admin Security Dashboard

**File**: `apps/admin/app/security/page.tsx`

```typescript
'use client'
import { SessionManagement, DeviceManagement, AuditLog } from '@plinto/ui'
import { Card, CardHeader, CardTitle, CardContent } from '@plinto/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@plinto/ui'

export default function SecurityDashboard() {
  // Fetch real data from API
  const sessions = [] // TODO: Fetch from /api/admin/sessions
  const devices = [] // TODO: Fetch from /api/admin/devices
  const events = [] // TODO: Fetch from /api/admin/audit-logs

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-8">Security Dashboard</h1>

      <Tabs defaultValue="sessions" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="sessions">Active Sessions</TabsTrigger>
          <TabsTrigger value="devices">Trusted Devices</TabsTrigger>
          <TabsTrigger value="audit">Audit Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="sessions" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Active Sessions Management</CardTitle>
            </CardHeader>
            <CardContent>
              <SessionManagement
                sessions={sessions}
                currentSessionId="admin-session"
                onRevokeSession={async (id) => {
                  await fetch(`/api/admin/sessions/${id}`, { method: 'DELETE' })
                }}
                onRevokeAllOthers={async () => {
                  await fetch('/api/admin/sessions/revoke-all', { method: 'POST' })
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="devices" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Trusted Device Management</CardTitle>
            </CardHeader>
            <CardContent>
              <DeviceManagement
                devices={devices}
                currentDeviceId="admin-device"
                onTrustDevice={async (id) => {
                  await fetch(`/api/admin/devices/${id}/trust`, { method: 'POST' })
                }}
                onRevokeDevice={async (id) => {
                  await fetch(`/api/admin/devices/${id}/revoke`, { method: 'POST' })
                }}
                onRemoveDevice={async (id) => {
                  await fetch(`/api/admin/devices/${id}`, { method: 'DELETE' })
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Audit Logs</CardTitle>
            </CardHeader>
            <CardContent>
              <AuditLog
                events={events}
                showExport={true}
                showFilters={true}
                onExport={async (format, filters) => {
                  const response = await fetch('/api/admin/audit-logs/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ format, filters }),
                  })
                  const blob = await response.blob()
                  // Download file logic
                }}
                onLoadMore={async () => {
                  // Pagination logic
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

## Phase 3: Performance Validation (Day 5)

### Task 3.1: Bundle Size Analysis

**Run in each app:**
```bash
# apps/demo
cd apps/demo
npm run build
npx @next/bundle-analyzer

# apps/admin
cd apps/admin
npm run build
npx @next/bundle-analyzer

# apps/dashboard
cd apps/dashboard
npm run build
npx @next/bundle-analyzer
```

**Success Criteria:**
- ✅ @plinto/ui contributes <100KB gzipped to each app
- ✅ Unused components not included in bundles
- ✅ Radix UI primitives properly tree-shaken
- ✅ lucide-react icons individually imported

### Task 3.2: Runtime Performance Testing

**File**: `packages/ui/tests/performance/render-performance.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { SignIn, SessionManagement, AuditLog } from '@plinto/ui'

describe('Render Performance', () => {
  it('SignIn renders in <50ms', () => {
    const start = performance.now()
    render(<SignIn onSuccess={() => {}} />)
    const duration = performance.now() - start
    expect(duration).toBeLessThan(50)
  })

  it('SessionManagement renders 100 sessions in <100ms', () => {
    const sessions = Array.from({ length: 100 }, (_, i) => ({
      id: `session-${i}`,
      device: { type: 'desktop', name: `Device ${i}` },
      createdAt: new Date(),
      lastActiveAt: new Date(),
    }))

    const start = performance.now()
    render(<SessionManagement sessions={sessions} currentSessionId="session-0" />)
    const duration = performance.now() - start
    expect(duration).toBeLessThan(100)
  })
})
```

**Run Performance Tests:**
```bash
cd packages/ui
npm run test -- performance
```

### Task 3.3: Lighthouse Audit

**Run on demo app:**
```bash
cd apps/demo
npm run build
npm run start

# In separate terminal
npx lighthouse http://localhost:3002/signin --view
npx lighthouse http://localhost:3002/mfa --view
npx lighthouse http://localhost:3002/security --view
```

**Success Criteria:**
- ✅ Performance score: >90
- ✅ Accessibility score: >95
- ✅ Best Practices score: >90
- ✅ First Contentful Paint: <1.5s
- ✅ Time to Interactive: <3.0s

## Phase 4: Documentation & Validation (Day 6-7)

### Task 4.1: Create Integration Examples

**File**: `packages/ui/examples/next-js-integration.md`

```markdown
# Next.js Integration Example

## Installation

\`\`\`bash
npm install @plinto/ui
\`\`\`

## Configuration

\`\`\`typescript
// next.config.js
module.exports = {
  transpilePackages: ['@plinto/ui'],
}
\`\`\`

## Usage Examples

### Basic Authentication Flow

\`\`\`typescript
// app/signin/page.tsx
import { SignIn } from '@plinto/ui'

export default function SignInPage() {
  return (
    <SignIn
      onSuccess={(data) => {
        // Handle successful login
        window.location.href = '/dashboard'
      }}
    />
  )
}
\`\`\`

[... more examples ...]
```

### Task 4.2: Week 4 Completion Summary

**File**: `packages/ui/WEEK4_COMPLETION.md`

```markdown
# Week 4 Completion Summary

**Date**: November 15, 2025
**Status**: ✅ Complete

## Achievements

### Components Delivered (15 total)

**Week 1 (3 components):**
- ✅ SignIn
- ✅ SignUp
- ✅ UserButton

**Week 2 (5 components):**
- ✅ MFASetup
- ✅ MFAChallenge
- ✅ BackupCodes
- ✅ OrganizationSwitcher
- ✅ OrganizationProfile

**Week 3 (4 components):**
- ✅ UserProfile
- ✅ PasswordReset
- ✅ EmailVerification
- ✅ PhoneVerification

**Week 4 (3 components):**
- ✅ SessionManagement (~420 LOC)
- ✅ DeviceManagement (~470 LOC)
- ✅ AuditLog (~550 LOC)

### Infrastructure

- ✅ Storybook 8.6.14 setup with 85+ stories
- ✅ Vitest + React Testing Library
- ✅ Performance optimization (source-only distribution)
- ✅ Bundle analysis and tree-shaking validation
- ✅ Comprehensive documentation

### Metrics

- **Total LOC**: 6,348
- **Components**: 27 files (15 auth + 10 UI primitives + 2 utilities)
- **Test Coverage**: Setup complete (Week 5 target: 80%+)
- **Bundle Size**: <100KB gzipped for typical usage
- **Storybook Stories**: 85+ interactive examples

## Next Steps (Week 5)

1. Integration testing with apps/demo, apps/admin, apps/dashboard
2. Dogfooding implementation (replace custom code with @plinto/ui)
3. Real-world performance validation
4. Component API refinement based on usage
5. Comprehensive test coverage (target: 80%+)
```

## Success Metrics

### Week 5 Completion Criteria

- ✅ All 15 components tested in real applications
- ✅ apps/demo showcases all components with working examples
- ✅ apps/admin uses security/compliance components
- ✅ apps/dashboard uses authentication flow components
- ✅ Bundle size validated (<100KB gzipped for typical usage)
- ✅ Performance benchmarks met (render <50ms, interactive <100ms)
- ✅ Lighthouse scores >90 (performance, accessibility, best practices)
- ✅ Integration documentation complete
- ✅ Week 4 completion documented

## Timeline

| Day | Phase | Tasks | Status |
|-----|-------|-------|--------|
| Day 1 | Integration Setup | Configure test infrastructure, verify dependencies | 📋 Planned |
| Day 2 | Integration Tests | Create test suite, validate all components | 📋 Planned |
| Day 3-4 | Dogfooding | Replace custom code in demo/admin/dashboard | 📋 Planned |
| Day 5 | Performance | Bundle analysis, runtime testing, Lighthouse audit | 📋 Planned |
| Day 6-7 | Documentation | Integration examples, Week 4 summary | 📋 Planned |

---

**Ready to Execute**: All prerequisites met, Week 4 components complete and optimized.
