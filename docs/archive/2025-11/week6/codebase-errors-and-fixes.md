# Codebase Errors and Fixes Report

**Date**: November 16, 2025  
**Status**: In Progress  
**Total Errors Found**: 150+

---

## Executive Summary

Comprehensive TypeScript error scan revealed 150+ errors across the codebase, categorized into 7 main types. These errors are preventing successful builds and need systematic resolution.

### Error Categories

| Category | Count | Severity | Priority |
|----------|-------|----------|----------|
| **Syntax Errors** | 1 | Critical | P0 |
| **Missing Dependencies** | 3 apps | Critical | P0 |
| **TypeScript SDK Event Types** | ~15 | High | P1 |
| **Readonly Array Type Errors** | ~15 | High | P1 |
| **Missing Type Exports** | ~30 | High | P1 |
| **Test Type Errors** | ~50 | Medium | P2 |
| **Type Re-export Errors** | ~20 | Medium | P2 |

---

## P0: Critical Errors (Block Build)

### 1. Admin App Syntax Error ✅ FIXED

**File**: `apps/admin/app/error.tsx:44`

**Error**:
```
error TS1135: Argument expression expected.
```

**Code**:
```typescript
}).catch(// Error logged to Sentry in production
```

**Fix Applied**:
```typescript
}).catch(() => {
  // Error logged to Sentry in production
})
```

**Status**: ✅ Fixed

---

### 2. Missing @plinto/feature-flags Package

**Affected Apps**: Demo, Dashboard, Admin

**Error**:
```typescript
error TS2307: Cannot find module '@plinto/feature-flags' or its corresponding type declarations.
```

**Files Affected**:
- `apps/demo/components/providers.tsx`
- `apps/dashboard/app/layout.tsx`
- `apps/admin/app/layout.tsx` (implicit via import)

**Root Cause**: Feature-flags package created but not built/published

**Fix Required**:
```bash
# Build feature-flags package
cd packages/feature-flags
npm install
npm run build

# Or temporarily remove imports until package is ready
```

**Status**: ⚠️ Requires package build or temporary removal

**Recommendation**: Since feature-flags is new (just created), either:
1. **Option A** (Recommended): Build the package:
   ```bash
   cd packages/feature-flags
   npm install
   npm run build
   ```

2. **Option B** (Quick fix): Temporarily remove feature flag imports and wrap with conditional checks:
   ```typescript
   // apps/demo/components/providers.tsx
   import { PlintoProvider } from './providers/plinto-provider'
   
   // TODO: Re-enable after building @plinto/feature-flags
   // import { FeatureFlagProvider } from '@plinto/feature-flags'
   
   export function Providers({ children }: { children: React.ReactNode }) {
     return (
       <PlintoProvider>
         {children}
       </PlintoProvider>
     )
   }
   ```

---

## P1: High Priority Errors (Type Safety)

### 3. TypeScript SDK Event Type Errors

**Count**: 15 occurrences  
**Severity**: High

**Files Affected**:
- `apps/demo/components/providers/plinto-provider.tsx`
- `apps/dashboard/lib/auth.tsx`
- `apps/admin/lib/auth.tsx` (will have same issue)

**Error 1**: Event name type mismatch
```typescript
error TS2345: Argument of type '"signIn"' is not assignable to parameter of type 'keyof SdkEventMap'.
error TS2345: Argument of type '"signOut"' is not assignable to parameter of type 'keyof SdkEventMap'.
error TS2345: Argument of type '"tokenRefreshed"' is not assignable to parameter of type 'keyof SdkEventMap'.
```

**Code**:
```typescript
plintoClient.on('signIn', handleSignIn)
plintoClient.on('signOut', handleSignOut)
plintoClient.on('tokenRefreshed', handleTokenRefresh)
```

**Error 2**: Event listener argument count
```typescript
error TS2554: Expected 0-1 arguments, but got 2.
```

**Code**:
```typescript
plintoClient.off('signIn', handleSignIn)
plintoClient.off('signOut', handleSignOut)
plintoClient.off('tokenRefreshed', handleTokenRefresh)
```

**Root Cause**: `@plinto/typescript-sdk` type definitions don't match implemented API

**Fix Options**:

**Option A** (Update SDK types):
```typescript
// packages/typescript-sdk/src/types.ts
export interface SdkEventMap {
  signIn: (user: User) => void
  signOut: () => void
  tokenRefreshed: () => void
}

export class PlintoClient extends EventEmitter<SdkEventMap> {
  // ...
}
```

**Option B** (Cast types in apps):
```typescript
// Temporary workaround
plintoClient.on('signIn' as any, handleSignIn)
plintoClient.on('signOut' as any, handleSignOut)
plintoClient.on('tokenRefreshed' as any, handleTokenRefresh)
```

**Recommended**: Option A - Fix SDK types to match implementation

---

### 4. Dashboard Auth SDK Method Errors

**File**: `apps/dashboard/lib/auth.tsx`

**Error**:
```typescript
error TS2339: Property 'getAccessToken' does not exist on type 'Auth'.
```

**Code**:
```typescript
const token = await plintoClient.auth.getAccessToken()
```

**Root Cause**: Method name mismatch in SDK

**Fix**: Check actual SDK method name:
```typescript
// Likely should be:
const token = await plintoClient.auth.getToken()
// or
const token = plintoClient.getAccessToken()
```

---

### 5. Dashboard Token Storage Type Error

**File**: `apps/dashboard/lib/plinto-client.ts:16`

**Error**:
```typescript
error TS2322: Type '{ type: string; key: string; }' is not assignable to type '"localStorage" | "sessionStorage" | "memory" | "custom" | undefined'.
```

**Code**:
```typescript
tokenStorage: {
  type: 'localStorage',
  key: 'plinto_auth_token',
},
```

**Fix**:
```typescript
tokenStorage: {
  type: 'localStorage' as const, // Add 'as const' assertion
  key: 'plinto_auth_token',
},
```

---

### 6. UI Package Readonly Array Errors

**Count**: 15 occurrences  
**Severity**: High

**Files Affected**:
- `packages/ui/src/components/auth/password-reset.tsx`
- `packages/ui/src/components/auth/sign-up.tsx`
- `packages/ui/src/lib/error-messages.ts`

**Error**:
```typescript
error TS2345: Argument of type '{ readonly title: "...", readonly message: "...", readonly actions: readonly [...] }' is not assignable to parameter of type 'ActionableError'.
  Types of property 'actions' are incompatible.
    The type 'readonly [...]' is 'readonly' and cannot be assigned to the mutable type 'string[]'.
```

**Code**:
```typescript
setError({
  title: "Passwords don't match",
  message: "The passwords you entered don't match.",
  actions: ["Re-enter both passwords", "Ensure they match exactly", "Check Caps Lock is off"],
})
```

**Root Cause**: `ActionableError` type expects mutable `string[]` but getting readonly array literal

**Fix Option A** (Update type definition):
```typescript
// packages/ui/src/types/error.ts
export interface ActionableError {
  title: string
  message: string
  actions: readonly string[] // Change to readonly
}
```

**Fix Option B** (Cast in usage):
```typescript
setError({
  title: "Passwords don't match",
  message: "The passwords you entered don't match.",
  actions: ["Re-enter both passwords", "Ensure they match exactly", "Check Caps Lock is off"] as string[],
})
```

**Recommended**: Option A - Update type to readonly (more type-safe)

---

### 7. Missing Type Exports

**Count**: 30 occurrences  
**Severity**: High

**Files Affected**:
- `packages/ui/src/components/auth/index.ts`
- `packages/ui/src/index.ts`

**Error**:
```typescript
error TS1205: Re-exporting a type when 'isolatedModules' is enabled requires using 'export type'.
error TS2305: Module '"./components/auth"' has no exported member 'SSOProviderCreate'.
error TS2305: Module '"./components/auth"' has no exported member 'SSOProviderResponse'.
error TS2305: Module '"./components/auth"' has no exported member 'SAMLConfigUpdate'.
error TS2724: '"./components/auth"' has no exported member named 'InvitationResponse'. Did you mean 'InvitationListResponse'?
```

**Code**:
```typescript
export {
  SSOProviderCreate,
  SSOProviderResponse,
  SAMLConfigUpdate,
  InvitationResponse, // Should be InvitationListResponse
  // ... many more
} from './components/auth'
```

**Fix Required**:
```typescript
// For type-only exports with isolatedModules
export type {
  SSOProviderCreate,
  SSOProviderResponse,
  SAMLConfigUpdate,
} from './components/auth'

// Fix incorrect export name
export type {
  InvitationListResponse, // Changed from InvitationResponse
} from './components/auth'
```

---

### 8. Demo App Showcase Errors

**Count**: 20 occurrences  
**Severity**: High

**Files Affected**:
- `apps/demo/app/auth/invitations-showcase/page.tsx`
- `apps/demo/app/auth/sso-showcase/page.tsx`

**Errors**:

**8a. Missing/Incorrect Imports**:
```typescript
error TS2724: '"@plinto/ui/components/auth"' has no exported member named 'InvitationResponse'. Did you mean 'InvitationListResponse'?
error TS2724: '"@/lib/plinto-client"' has no exported member named 'PlintoClient'. Did you mean 'plintoClient'?
error TS2305: Module '"@plinto/ui/components/auth"' has no exported member 'SSOProviderCreate'.
```

**Fix**:
```typescript
// apps/demo/app/auth/invitations-showcase/page.tsx
import { 
  InvitationListResponse, // Changed from InvitationResponse
} from '@plinto/ui/components/auth'
import { plintoClient } from '@/lib/plinto-client' // Changed from PlintoClient

// apps/demo/app/auth/sso-showcase/page.tsx
// Remove missing imports or create placeholder types
```

**8b. Type Mismatches in Event Handlers**:
```typescript
error TS2322: Type '(invitation: string) => void' is not assignable to type '(invitationId: string) => Promise<void>'.
```

**Fix**:
```typescript
// Change from:
const handleAccept = (invitation: string) => {
  console.log('Accepting invitation:', invitation.id)
}

// To:
const handleAccept = async (invitationId: string) => {
  console.log('Accepting invitation:', invitationId)
}
```

---

## P2: Medium Priority (Tests & Non-blocking)

### 9. Demo App Test Errors

**Count**: 50+ occurrences  
**Severity**: Medium (tests only)

**Error Types**:
1. **Implicit `any` types in mock props** (30 errors)
2. **Null check errors** (10 errors)
3. **Delete operator on readonly** (5 errors)
4. **Testing library matcher types** (5 errors)

**Examples**:

**9a. Implicit any in mocks**:
```typescript
error TS7006: Parameter 'props' implicitly has an 'any' type.

// Fix:
jest.mock('@plinto/ui', () => ({
  Button: (props: any) => <button {...props} />,
}))
```

**9b. Null safety**:
```typescript
error TS2345: Argument of type 'HTMLButtonElement | null' is not assignable to parameter of type 'Element | Node | Window | Document'.

// Fix:
const button = screen.getByRole('button')
if (button) {
  fireEvent.click(button)
}
```

**9c. Delete operator**:
```typescript
error TS2790: The operand of a 'delete' operator must be optional.

// Fix:
// Change from:
delete process.env.NEXT_PUBLIC_API_URL

// To:
const originalEnv = process.env.NEXT_PUBLIC_API_URL
process.env.NEXT_PUBLIC_API_URL = undefined
// ... test ...
process.env.NEXT_PUBLIC_API_URL = originalEnv
```

---

### 10. Dashboard Test Errors

**Count**: 40+ occurrences  
**Severity**: Medium (tests only)

**Similar issues to demo app tests, plus**:

**Testing library type extensions**:
```typescript
error TS2339: Property 'toBeInTheDocument' does not exist on type 'JestMatchers<HTMLElement>'.
```

**Fix**: Add to test setup:
```typescript
// jest.setup.ts
import '@testing-library/jest-dom'
```

---

### 11. Component Import Errors

**Files Affected**:
- `apps/demo/app/dashboard/page.test.tsx`
- `apps/demo/app/layout.test.tsx`
- `apps/demo/app/signin/page.test.tsx`
- `apps/demo/app/signup/page.test.tsx`
- `apps/demo/components/providers.test.tsx`

**Error**:
```typescript
error TS2614: Module '"./page"' has no exported member 'page'. Did you mean to use 'import page from "./page"' instead?
```

**Fix**:
```typescript
// Change from:
import { page } from './page'

// To:
import page from './page'
```

---

### 12. Demo App User Type Errors

**File**: `apps/demo/components/providers.tsx`

**Errors**:
```typescript
error TS2339: Property 'organizationId' does not exist on type 'User'.
error TS2339: Property 'organization' does not exist on type 'User'.
```

**Fix**: Add properties to User type or use optional chaining:
```typescript
// Option A: Use optional chaining (safer)
organizationId: (user as any)?.organizationId,
plan: (user as any)?.organization?.plan || 'free',

// Option B: Update User type in SDK
export interface User {
  id: string
  email?: string
  organizationId?: string
  organization?: {
    plan?: string
  }
}
```

---

## P3: Low Priority (Can defer)

### 13. E2E Test Playwright Errors

**File**: `apps/demo/e2e/error-messages.spec.ts`

**Errors**:
```typescript
error TS2554: Expected 2 arguments, but got 1.
error TS2339: Property 'match' does not exist on type 'void'.
```

**Note**: These are likely due to Playwright version or API changes. Can be fixed when running E2E tests.

---

## Summary of Fixes Applied

### ✅ Completed

1. **Admin app syntax error** - Fixed catch block
   - File: `apps/admin/app/error.tsx`
   - Change: Added proper error handler function

### ⏳ In Progress

2. **Feature flags package** - Needs build or temporary removal
3. **TypeScript SDK event types** - Needs SDK type updates
4. **UI package readonly arrays** - Needs type definition updates
5. **Missing type exports** - Needs export corrections

### 📋 Pending

6. **Dashboard SDK method calls** - Verify correct method names
7. **Demo showcase errors** - Fix import and type issues
8. **Test type errors** - Add proper types and null checks
9. **Test setup** - Configure jest-dom types

---

## Recommended Fix Priority

### Phase 1: Critical (Today)
1. ✅ Fix admin syntax error
2. ⏳ Build feature-flags package OR temporarily remove imports
3. ⏳ Fix TypeScript SDK event types in @plinto/typescript-sdk

### Phase 2: High Priority (This Week)
4. Fix UI package readonly array type definitions
5. Fix missing type exports in @plinto/ui
6. Fix demo app showcase import errors
7. Fix dashboard SDK method calls

### Phase 3: Medium Priority (Next Sprint)
8. Fix all test type errors
9. Add proper test setup with jest-dom
10. Fix component import patterns

### Phase 4: Low Priority (When Needed)
11. Fix E2E Playwright test errors when running E2E suite

---

## Automated Fix Script

```bash
#!/bin/bash
# fix-errors.sh - Automated error fixes

echo "Phase 1: Critical Fixes"

# 1. Admin syntax error - DONE
echo "✅ Admin syntax error fixed"

# 2. Build feature-flags
echo "Building feature-flags package..."
cd packages/feature-flags
npm install
npm run build
cd ../..

# 3. Fix TypeScript SDK events
echo "Updating SDK event types..."
# (Would need specific SDK changes)

echo "Phase 2: High Priority Fixes"

# 4-7 would require specific file edits

echo "Run typechecks to verify..."
npm run typecheck
```

---

## Testing After Fixes

```bash
# Test each app individually
cd apps/demo && npm run typecheck
cd apps/dashboard && npm run typecheck
cd apps/admin && npm run typecheck

# Test packages
cd packages/ui && npm run typecheck
cd packages/typescript-sdk && npm run typecheck
cd packages/feature-flags && npm run typecheck

# Run all tests
npm test
```

---

**Report Status**: Initial scan complete  
**Next Action**: Execute Phase 1 critical fixes  
**Estimated Fix Time**: 2-4 hours for all high-priority errors
