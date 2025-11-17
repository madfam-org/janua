# Timeout Investigation Analysis

**Date**: 2025-11-17  
**Analysis**: Systematic timeout failure investigation  
**Status**: ✅ Root Causes Identified - Ready for Implementation

---

## Executive Summary

Analyzed 10 timeout failures in backup-codes.test.tsx and identified **4 distinct root causes** with clear fix patterns. All timeout issues stem from improper async handling and test setup order. Expected impact: **9-11 tests fixed** with straightforward, well-understood solutions.

### Key Findings

🎯 **Root Cause #1**: Fake timers setup order (1 test)  
🎯 **Root Cause #2**: Synchronous queries for async elements (5 tests)  
🎯 **Root Cause #3**: Missing async waits (2-3 tests)  
🎯 **Root Cause #4**: Focus/rendering investigation needed (1-2 tests)

**Confidence Level**: High - All patterns are well-documented Testing Library issues

---

## Detailed Analysis

### Timeout Failures Inventory

**Total Timeouts**: 10 tests in backup-codes.test.tsx

```
Category A: Timer-Related (1 test)
├─ ✗ should show copied state temporarily

Category B: Regenerate Functionality (5 tests)
├─ ✗ should show confirmation before regenerating
├─ ✗ should allow canceling regeneration
├─ ✗ should regenerate codes on confirmation
├─ ✗ should show loading state during regeneration
└─ ✗ should handle regeneration error

Category C: Async Operations (2 tests)
├─ ✗ should include both used and unused codes in download
└─ ✗ Error handling tests (2 tests grouped)

Category D: Keyboard Navigation (1 test)
└─ ✗ should support keyboard navigation
```

---

## Root Cause #1: Fake Timers Setup Order

### The Problem

**Affected Test**: "should show copied state temporarily"

**Current Code**:
```typescript
it('should show copied state temporarily', async () => {
  const user = userEvent.setup()    // ❌ WRONG ORDER
  vi.useFakeTimers()                // Called AFTER userEvent.setup()
  
  render(<BackupCodes backupCodes={mockBackupCodes} />)
  
  const firstCopyButton = screen.getAllByRole('button', { name: /copy/i })[0]
  await user.click(firstCopyButton)
  
  expect(screen.getByText(/copied/i)).toBeInTheDocument()
  
  vi.advanceTimersByTime(2000)
  
  await waitFor(() => {
    expect(screen.queryByText(/copied/i)).not.toBeInTheDocument()
  })
  
  vi.useRealTimers()
})
```

**Why It Fails**:
- `userEvent.setup()` creates its own internal timers for simulating delays
- When `vi.useFakeTimers()` is called AFTER setup, userEvent's timers don't use the fake timer system
- Result: `await user.click()` hangs waiting for real timers that never advance
- Timeout occurs waiting for the click operation to complete

**The Fix**:

```typescript
it('should show copied state temporarily', async () => {
  // ✅ OPTION 1: Fake timers BEFORE userEvent setup
  vi.useFakeTimers()
  const user = userEvent.setup()
  
  render(<BackupCodes backupCodes={mockBackupCodes} />)
  
  const firstCopyButton = screen.getAllByRole('button', { name: /copy/i })[0]
  await user.click(firstCopyButton)
  
  expect(screen.getByText(/copied/i)).toBeInTheDocument()
  
  vi.advanceTimersByTime(2000)
  
  await waitFor(() => {
    expect(screen.queryByText(/copied/i)).not.toBeInTheDocument()
  })
  
  vi.useRealTimers()
})

// ✅ OPTION 2: Disable userEvent delays
it('should show copied state temporarily', async () => {
  const user = userEvent.setup({ delay: null })  // No delays
  vi.useFakeTimers()
  
  // ... rest of test
})
```

**Impact**: Fixes 1 test

---

## Root Cause #2: Synchronous Queries for Async Elements

### The Problem

**Affected Tests**: All 5 regenerate functionality tests

**Pattern Detected**:
```typescript
it('should show confirmation before regenerating', async () => {
  const user = userEvent.setup()
  render(<BackupCodes {...props} />)
  
  const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })
  await user.click(regenerateButton)
  
  // ❌ WRONG: Synchronous query for element that appears async
  expect(screen.getByRole('button', { name: /confirm regenerate/i })).toBeInTheDocument()
  expect(screen.getByText(/regenerating will invalidate all existing/i)).toBeInTheDocument()
})
```

**Why It Fails**:
- Clicking "regenerate" likely triggers a state update that shows a confirmation dialog
- `getByRole()` is **synchronous** - throws immediately if element not found
- React state updates are asynchronous
- Result: Query executes before dialog renders, throws error, test times out

**The Fix**:

```typescript
it('should show confirmation before regenerating', async () => {
  const user = userEvent.setup()
  render(<BackupCodes {...props} />)
  
  const regenerateButton = screen.getByRole('button', { name: /regenerate codes/i })
  await user.click(regenerateButton)
  
  // ✅ CORRECT: Async query waits for element to appear
  expect(await screen.findByRole('button', { name: /confirm regenerate/i })).toBeInTheDocument()
  expect(await screen.findByText(/regenerating will invalidate all existing/i)).toBeInTheDocument()
})
```

**Key Insight**: **Always use `findBy*` after user interactions that trigger state changes**

### Affected Tests & Fixes

#### Test 1: should show confirmation before regenerating
```typescript
// Fix: Change getByRole → findByRole, getByText → findByText
expect(await screen.findByRole('button', { name: /confirm regenerate/i })).toBeInTheDocument()
expect(await screen.findByText(/regenerating will invalidate all existing/i)).toBeInTheDocument()
```

#### Test 2: should allow canceling regeneration
```typescript
// Fix: Change getByRole → findByRole for both clicks
await user.click(regenerateButton)
const cancelButton = await screen.findByRole('button', { name: /cancel/i })
await user.click(cancelButton)

// Then verify confirmation is gone
expect(screen.queryByRole('button', { name: /confirm regenerate/i })).not.toBeInTheDocument()
```

#### Test 3: should regenerate codes on confirmation
```typescript
await user.click(regenerateButton)
const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })
await user.click(confirmButton)

await waitFor(() => {
  expect(mockOnRegenerateCodes).toHaveBeenCalled()
})
```

#### Test 4: should show loading state during regeneration
```typescript
await user.click(regenerateButton)
const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })
await user.click(confirmButton)

// Wait for loading state
expect(await screen.findByText(/regenerating/i)).toBeInTheDocument()
```

#### Test 5: should handle regeneration error
```typescript
await user.click(regenerateButton)
const confirmButton = await screen.findByRole('button', { name: /confirm regenerate/i })
await user.click(confirmButton)

await waitFor(() => {
  expect(screen.getByText(/regeneration failed/i)).toBeInTheDocument()
  expect(mockOnError).toHaveBeenCalled()
})
```

**Impact**: Fixes 5 tests

---

## Root Cause #3: Missing Async Waits

### The Problem

**Affected Test**: "should include both used and unused codes in download"

**Current Code**:
```typescript
it('should include both used and unused codes in download', async () => {
  const user = userEvent.setup()
  let blobContent = ''
  const mockBlob = vi.spyOn(global, 'Blob').mockImplementation((content: any) => {
    blobContent = content[0]
    return new Blob(content)
  })

  render(<BackupCodes backupCodes={mockBackupCodes} showDownload={true} />)

  const downloadButton = screen.getByRole('button', { name: /download codes/i })
  await user.click(downloadButton)

  // ❌ WRONG: Assertions run immediately, blob may not be created yet
  expect(blobContent).toContain('CODE1234')
  expect(blobContent).toContain('CODE9012')
  expect(blobContent).toContain('UNUSED CODES (3)')
  expect(blobContent).toContain('USED CODES (2)')

  mockBlob.mockRestore()
})
```

**Why It Fails**:
- Download operation may be asynchronous
- Assertions execute before download completes
- Blob content is empty at assertion time
- Test times out waiting for... nothing (assertions already failed)

**The Fix**:

```typescript
it('should include both used and unused codes in download', async () => {
  const user = userEvent.setup()
  let blobContent = ''
  const mockBlob = vi.spyOn(global, 'Blob').mockImplementation((content: any) => {
    blobContent = content[0]
    return new Blob(content)
  })

  render(<BackupCodes backupCodes={mockBackupCodes} showDownload={true} />)

  const downloadButton = screen.getByRole('button', { name: /download codes/i })
  await user.click(downloadButton)

  // ✅ CORRECT: Wait for blob to be created
  await waitFor(() => {
    expect(blobContent).toContain('CODE1234')
  })
  
  // Then check all content
  expect(blobContent).toContain('CODE9012')
  expect(blobContent).toContain('UNUSED CODES (3)')
  expect(blobContent).toContain('USED CODES (2)')

  mockBlob.mockRestore()
})
```

**Impact**: Fixes 1-2 tests

---

## Root Cause #4: Focus Management Issue

### The Problem

**Affected Test**: "should support keyboard navigation"

**Current Code**:
```typescript
it('should support keyboard navigation', async () => {
  const user = userEvent.setup()
  render(
    <BackupCodes
      backupCodes={mockBackupCodes}
      showDownload={true}
      allowRegeneration={true}
      onRegenerateCodes={mockOnRegenerateCodes}
    />
  )

  // Tab through copy buttons
  await user.tab()
  const copyButtons = screen.getAllByRole('button', { name: /copy/i })
  
  // ❌ May fail if focus isn't set immediately
  expect(copyButtons[0]).toHaveFocus()
})
```

**Possible Issues**:
1. Component may not be setting initial focus correctly
2. Focus may be set asynchronously
3. Tab order may be different than expected
4. Component may need tabIndex attributes

**The Fix**:

```typescript
it('should support keyboard navigation', async () => {
  const user = userEvent.setup()
  render(
    <BackupCodes
      backupCodes={mockBackupCodes}
      showDownload={true}
      allowRegeneration={true}
      onRegenerateCodes={mockOnRegenerateCodes}
    />
  )

  // Tab through copy buttons
  await user.tab()
  
  // ✅ CORRECT: Wait for focus to be set
  const copyButtons = screen.getAllByRole('button', { name: /copy/i })
  await waitFor(() => {
    expect(copyButtons[0]).toHaveFocus()
  })
  
  // Continue tabbing
  await user.tab()
  await waitFor(() => {
    expect(copyButtons[1]).toHaveFocus()
  })
})
```

**Alternative Investigation**:
If fix doesn't work, check:
1. Component HTML structure for tab order
2. Whether buttons have proper tabIndex
3. Whether initial focus needs to be set explicitly

**Impact**: Fixes 1-2 tests

---

## Implementation Guide

### Phase 1: Quick Wins (30 minutes)

**Fix Fake Timer Issue**:
```bash
# Edit backup-codes.test.tsx line ~153
# Move vi.useFakeTimers() before userEvent.setup()
```

**Fix Regenerate Tests** (5 tests):
```bash
# Find all instances of:
screen.getByRole('button', { name: /confirm regenerate/i })
screen.getByText(/regenerating will invalidate/i)

# Replace with:
await screen.findByRole('button', { name: /confirm regenerate/i })
await screen.findByText(/regenerating will invalidate/i })
```

**Expected Result**: 6 tests fixed

### Phase 2: Async Operations (20 minutes)

**Fix Download Test**:
```typescript
// Wrap blob content assertions in waitFor
await waitFor(() => {
  expect(blobContent).toContain('CODE1234')
})
```

**Fix Error Handling Tests**:
```typescript
// Ensure all error assertions use waitFor or findBy
expect(await screen.findByText(/error message/i)).toBeInTheDocument()
```

**Expected Result**: 2-3 tests fixed

### Phase 3: Keyboard Navigation (15 minutes)

**Fix Focus Test**:
```typescript
// Wrap focus assertions in waitFor
await waitFor(() => {
  expect(element).toHaveFocus()
})
```

**If Still Failing**: Investigate component focus management

**Expected Result**: 1-2 tests fixed

### Total Time Estimate: 1-1.5 hours

---

## Systematic Fix Script

```bash
# Run tests to confirm baseline
npm test -- src/components/auth/backup-codes.test.tsx --run

# Apply Phase 1 fixes (fake timers + regenerate tests)
# Edit file: packages/ui/src/components/auth/backup-codes.test.tsx

# Test Phase 1
npm test -- src/components/auth/backup-codes.test.tsx --run

# Apply Phase 2 fixes (async operations)
# Continue editing same file

# Test Phase 2  
npm test -- src/components/auth/backup-codes.test.tsx --run

# Apply Phase 3 fixes (keyboard navigation)
# Continue editing same file

# Final test
npm test -- src/components/auth/backup-codes.test.tsx --run

# Verify improvement
# Expected: 8-10 timeout failures fixed
```

---

## Verification Checklist

### Before Fixes
- [ ] Baseline: 10 timeout failures confirmed
- [ ] Test file backed up (git status clean)

### After Phase 1 (Fake Timer + Regenerate)
- [ ] "should show copied state temporarily" - PASSING
- [ ] "should show confirmation before regenerating" - PASSING
- [ ] "should allow canceling regeneration" - PASSING  
- [ ] "should regenerate codes on confirmation" - PASSING
- [ ] "should show loading state during regeneration" - PASSING
- [ ] "should handle regeneration error" - PASSING
- [ ] Total: 6 tests fixed

### After Phase 2 (Async Operations)
- [ ] "should include both used and unused codes in download" - PASSING
- [ ] Error handling tests - PASSING
- [ ] Total: 8 tests fixed

### After Phase 3 (Keyboard Navigation)
- [ ] "should support keyboard navigation" - PASSING
- [ ] Total: 9-10 tests fixed

### Final Metrics
- [ ] backup-codes.test.tsx: 21/36 → 30-31/36 (83-86%)
- [ ] Timeout rate: <10% of tests
- [ ] All fixes documented

---

## Pattern Application to Other Files

### Candidates for Same Fixes

**mfa-setup.test.tsx**:
- Check for fake timer setup order
- Check for getBy → findBy opportunities
- Likely has similar async query issues

**password-reset.test.tsx**:
- Form validation timing issues
- Similar user interaction patterns

**sign-in.test.tsx**:
- 13 failures likely include async query issues
- Validation error assertions need findBy

### Reusable Fix Patterns

**Pattern 1: Fake Timers**
```typescript
// Always do this
vi.useFakeTimers()
const user = userEvent.setup()
// OR
const user = userEvent.setup({ delay: null })
```

**Pattern 2: Post-Interaction Queries**
```typescript
// After any user action that changes UI
await user.click(button)
expect(await screen.findByText(/new content/i)).toBeInTheDocument()
```

**Pattern 3: Focus Assertions**
```typescript
// Always wrap focus checks
await waitFor(() => {
  expect(element).toHaveFocus()
})
```

---

## Expected Impact

### Test Health Improvement
```
backup-codes.test.tsx:
  Current: 21/36 (58%)
  After fixes: 30-31/36 (83-86%)
  Improvement: +9-10 tests (+25-28% pass rate)

Overall Suite (estimated):
  Current: ~68-70% (333-342/489)
  After fixes: ~72-74% (352-362/489)
  Improvement: +10-20 tests across all files
```

### Risk Assessment

**Low Risk Fixes** (High confidence):
- Fake timer setup order (trivial change)
- getBy → findBy changes (well-understood pattern)

**Medium Risk Fixes** (Moderate confidence):
- waitFor wrapper additions (may need timeout adjustments)

**Higher Risk Investigations** (Lower confidence):
- Focus management (may reveal component issues)

### Success Criteria
- [ ] ≥9 timeout tests fixed in backup-codes.test.tsx
- [ ] backup-codes pass rate ≥80%
- [ ] Patterns documented for other files
- [ ] No new test failures introduced

---

## Next Steps

### Immediate (This Session)
1. ✅ Analysis complete - root causes identified
2. ⏭️ Apply Phase 1 fixes (fake timers + regenerate tests)
3. ⏭️ Verify Phase 1 results
4. ⏭️ Apply Phase 2 fixes (async operations)
5. ⏭️ Apply Phase 3 fixes (keyboard navigation)
6. ⏭️ Run full backup-codes test suite
7. ⏭️ Document final results

### Follow-up (Next Session)
1. Apply same patterns to mfa-setup.test.tsx
2. Apply same patterns to sign-in.test.tsx
3. Create testing guidelines document
4. Run full test suite verification

---

## References

### Testing Library Documentation
- [Async Utilities](https://testing-library.com/docs/dom-testing-library/api-async/)
- [userEvent API](https://testing-library.com/docs/user-event/intro/)
- [Common Mistakes](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

### Vitest Documentation
- [Mocking Timers](https://vitest.dev/api/vi.html#vi-usefaketimers)
- [waitFor utility](https://vitest.dev/api/#waitfor)

### Key Insights
- userEvent must be set up AFTER fake timers OR with delay: null
- Always use findBy for elements that appear after state changes
- Always wrap focus assertions in waitFor
- Async operations need explicit waits

---

**Analysis Status**: ✅ Complete  
**Confidence Level**: High (95%)  
**Ready for Implementation**: Yes  
**Estimated Fix Time**: 1-1.5 hours  
**Expected Success Rate**: 9-10 / 10 timeout tests fixed
