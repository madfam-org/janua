# Manual Error Message Testing Checklist

**Purpose**: Validate error message quality, actionability, and user experience across all authentication flows.

**Date Created**: November 16, 2025  
**Status**: Ready for execution  
**Estimated Time**: 1-2 hours comprehensive testing

---

## Testing Environment Setup

### Prerequisites
- [ ] FastAPI backend running on http://localhost:8000
- [ ] Demo app running on http://localhost:3000
- [ ] PostgreSQL database healthy and accessible
- [ ] Redis cache connected
- [ ] Browser DevTools open (Network tab for status codes)
- [ ] Screen reader available for accessibility testing (optional)

### Preparation
- [ ] Clear browser cache and cookies
- [ ] Open browser in private/incognito mode
- [ ] Note test user credentials if using existing accounts
- [ ] Have test email account accessible for verification codes

---

## 1. Sign-In Error Messages

### Test 1.1: Invalid Credentials
**Steps**:
1. Navigate to http://localhost:3000/auth/signin-showcase
2. Enter email: `wrong@example.com`
3. Enter password: `WrongPassword123!`
4. Click "Sign In"

**Expected Error Message**:
```
Invalid credentials: The email or password you entered is incorrect.

What to do:
1. Double-check your email and password
2. Use "Forgot password?" to reset your password
3. Ensure Caps Lock is off
```

**Validation**:
- [ ] Error appears within 2 seconds
- [ ] Title is "Invalid credentials"
- [ ] Message explains what went wrong
- [ ] 3+ actionable recovery steps listed
- [ ] Error is dismissible or disappears after re-attempt
- [ ] HTTP 401 status code in Network tab

---

### Test 1.2: Account Not Verified
**Steps**:
1. Create new account via `/auth/signup-showcase`
2. Do NOT verify email
3. Attempt to sign in with those credentials

**Expected Error Message**:
```
Email not verified: Please verify your email address before signing in.

What to do:
1. Check your inbox for the verification email
2. Click "Resend verification email" if you didn't receive it
3. Check your spam folder
```

**Validation**:
- [ ] Error title is "Email not verified"
- [ ] Explains email verification requirement
- [ ] Provides resend option guidance
- [ ] HTTP 401 with "not verified" message
- [ ] Email shown in error message for context

---

### Test 1.3: Account Locked (Rate Limiting)
**Steps**:
1. Attempt sign-in with wrong password 5+ times rapidly
2. Observe rate limiting error

**Expected Error Message**:
```
Too many attempts: You've made too many requests. Please slow down.

What to do:
1. Wait 5 minutes before trying again
2. Avoid rapid repeated attempts
3. Contact support if you need immediate access
```

**Validation**:
- [ ] Error appears after multiple failed attempts
- [ ] Title is "Too many attempts"
- [ ] Specific wait time mentioned (e.g., "5 minutes")
- [ ] HTTP 429 status code in Network tab
- [ ] Retry-After header present in response

---

### Test 1.4: Network Error
**Steps**:
1. Open DevTools → Network tab
2. Enable "Offline" mode in DevTools
3. Attempt to sign in

**Expected Error Message**:
```
Connection error: Unable to connect to the authentication server.

What to do:
1. Check your internet connection
2. Try again in a few moments
3. Refresh the page
4. Contact support if the issue persists
```

**Validation**:
- [ ] Error appears when network is offline
- [ ] Title is "Connection error"
- [ ] Mentions connectivity issue
- [ ] Provides retry suggestions
- [ ] No HTTP status code (network failure)

---

## 2. Sign-Up Error Messages

### Test 2.1: Weak Password
**Steps**:
1. Navigate to `/auth/signup-showcase`
2. Enter email: `newuser@example.com`
3. Enter password: `weak` (intentionally weak)
4. Click "Sign Up"

**Expected Error Message**:
```
Password too weak: Your password doesn't meet the security requirements.

What to do:
1. Use at least 8 characters
2. Include uppercase and lowercase letters
3. Add at least one number
4. Add a special character (!@#$%^&*)
```

**Validation**:
- [ ] Error appears before API call (client-side validation)
- [ ] Title is "Password too weak"
- [ ] Lists all 4 password requirements
- [ ] Numbered action items (1-4)
- [ ] Password strength indicator shows weak

---

### Test 2.2: Invalid Email Format
**Steps**:
1. Navigate to `/auth/signup-showcase`
2. Enter email: `not-an-email` (no @ symbol)
3. Enter valid password
4. Click "Sign Up"

**Expected Error Message**:
```
Invalid email address: The email address format is not valid.

What to do:
1. Check for typos in your email
2. Ensure format is: name@example.com
3. Remove any extra spaces
```

**Validation**:
- [ ] Error appears (client or server-side)
- [ ] Title is "Invalid email address"
- [ ] Provides correct email format example
- [ ] 3 recovery steps listed
- [ ] Email input field highlighted/focused

---

### Test 2.3: Email Already Exists
**Steps**:
1. Sign up with email: `existing@example.com` (use real email from previous test)
2. Complete sign-up
3. Sign out
4. Attempt to sign up again with same email

**Expected Error Message**:
```
Email already registered: An account with this email address already exists.

What to do:
1. Try signing in instead
2. Use "Forgot password?" if you don't remember your password
3. Use a different email address
```

**Validation**:
- [ ] Error appears after API call
- [ ] Title is "Email already registered"
- [ ] Provides sign-in alternative
- [ ] HTTP 409 status code (Conflict)
- [ ] Forgot password option mentioned

---

## 3. Password Reset Error Messages

### Test 3.1: Passwords Don't Match
**Steps**:
1. Navigate to `/auth/password-reset-showcase`
2. Request password reset email
3. Click reset link in email (or use test token)
4. Enter new password: `NewPassword123!`
5. Enter confirm password: `DifferentPassword123!`
6. Click "Reset Password"

**Expected Error Message**:
```
Passwords don't match: The passwords you entered don't match.

What to do:
1. Re-enter both passwords
2. Ensure they match exactly
3. Check Caps Lock is off
```

**Validation**:
- [ ] Error appears after form submission
- [ ] Title is "Passwords don't match"
- [ ] Clear mismatch explanation
- [ ] 3 recovery steps
- [ ] Password fields cleared or highlighted

---

### Test 3.2: Reset Token Expired
**Steps**:
1. Request password reset
2. Wait for token to expire (1 hour default, or use old token)
3. Attempt to use expired reset link

**Expected Error Message**:
```
Reset link expired: This password reset link has expired. Reset links are valid for 1 hour.

What to do:
1. Request a new password reset email
2. Use the latest email you received
3. Complete the reset process within 1 hour
```

**Validation**:
- [ ] Error appears when using expired token
- [ ] Title is "Reset link expired"
- [ ] Expiration time mentioned (1 hour)
- [ ] Provides request new link action
- [ ] HTTP 400 or 422 status code

---

### Test 3.3: Reset Token Invalid/Used
**Steps**:
1. Request password reset
2. Use reset link successfully
3. Attempt to use the same link again

**Expected Error Message**:
```
Invalid reset link: This password reset link is invalid or has already been used.

What to do:
1. Request a new password reset email
2. Copy the entire link from your email
3. Ensure you're clicking the latest reset link
```

**Validation**:
- [ ] Error appears for reused/invalid token
- [ ] Title is "Invalid reset link"
- [ ] Mentions already used possibility
- [ ] Provides request new link action

---

## 4. MFA Error Messages

### Test 4.1: Invalid MFA Code
**Steps**:
1. Navigate to `/auth/mfa-showcase`
2. Set up TOTP MFA (or use existing account)
3. Enter verification code: `000000` (invalid)
4. Click "Verify"

**Expected Error Message**:
```
Invalid verification code: The verification code you entered is incorrect or has expired.

What to do:
1. Enter the current 6-digit code from your authenticator app
2. Wait for a new code if the current one expired
3. Ensure your device time is synced correctly
4. Try using a backup code if available
```

**Validation**:
- [ ] Error appears after invalid code submission
- [ ] Title is "Invalid verification code"
- [ ] Explains code might be expired
- [ ] 4 recovery steps including backup codes
- [ ] HTTP 400 or 422 status code

---

### Test 4.2: MFA Already Enabled
**Steps**:
1. Enable MFA on an account
2. Attempt to enable MFA again on the same account

**Expected Error Message**:
```
MFA already enabled: Multi-factor authentication is already set up for your account.

What to do:
1. Use your existing authenticator app
2. Disable MFA first if you want to reconfigure
3. Contact support if you lost access to your authenticator
```

**Validation**:
- [ ] Error appears when MFA already active
- [ ] Title is "MFA already enabled"
- [ ] Provides disable/reconfigure option
- [ ] Support contact for lost access

---

## 5. Phone Verification Error Messages

### Test 5.1: Invalid Phone Number
**Steps**:
1. Navigate to `/auth/phone-verify-showcase` (if available)
2. Enter invalid phone: `123` (too short)
3. Click "Send Code"

**Expected Error Message**:
```
Invalid format: Phone number format is invalid.

What to do:
1. Ensure phone number is in format: +1234567890
2. Remove any extra spaces
3. Check for typos
```

**Validation**:
- [ ] Error appears for invalid phone format
- [ ] Title is "Invalid format"
- [ ] Provides correct format example
- [ ] 3 recovery steps

---

### Test 5.2: SMS Delivery Failure
**Steps**:
1. Enter valid phone number
2. Simulate SMS failure (or use number that fails)

**Expected Error Message**:
```
[Appropriate error based on failure type - connection error or service error]
```

**Validation**:
- [ ] Error appears when SMS fails
- [ ] Explains delivery failure
- [ ] Provides retry option
- [ ] Contact support option for persistent issues

---

## 6. Server & System Error Messages

### Test 6.1: 500 Internal Server Error
**Steps**:
1. Use browser DevTools to intercept and mock 500 response
2. Attempt any auth action (sign-in, sign-up, etc.)

**Expected Error Message**:
```
Server error: Something went wrong on our end. This is not your fault.

What to do:
1. Try again in a few moments
2. Refresh the page
3. Contact support if the issue persists
4. Our team has been notified
```

**Validation**:
- [ ] Error appears for 500 responses
- [ ] Title is "Server error"
- [ ] Reassures user it's not their fault
- [ ] Mentions team notification
- [ ] 4 recovery steps
- [ ] HTTP 500 status code

---

### Test 6.2: Request Timeout
**Steps**:
1. Simulate slow network (DevTools → Network → Throttling)
2. Set very high latency or offline
3. Attempt auth action that times out

**Expected Error Message**:
```
Request timeout: The request took too long to complete.

What to do:
1. Check your internet connection
2. Try again with a faster connection
3. Reduce the size of uploaded files if applicable
```

**Validation**:
- [ ] Error appears after timeout
- [ ] Title is "Request timeout"
- [ ] Mentions connection speed
- [ ] 3 recovery steps

---

## 7. Error Message Quality Standards

### Visual Presentation
- [ ] **Visibility**: Errors are prominently displayed
- [ ] **Color**: Red or warning color used for errors
- [ ] **Icons**: Error icon (⚠️ or ❌) present
- [ ] **Position**: Error appears near form or at top of page
- [ ] **Persistence**: Error remains visible until dismissed or form resubmitted

### Content Quality
- [ ] **Title**: Clear, concise error title (2-5 words)
- [ ] **Message**: Explains what went wrong (1-2 sentences)
- [ ] **Actions**: Lists 2-4 specific recovery steps
- [ ] **Tone**: Professional, helpful, non-blaming
- [ ] **Technical Details**: Hidden by default, available for developers

### Accessibility
- [ ] **ARIA Role**: Error has `role="alert"` attribute
- [ ] **Screen Reader**: Error is announced to screen readers
- [ ] **Focus**: Focus moves to error or error field
- [ ] **Color Contrast**: Error text meets WCAG AA contrast ratio (4.5:1)
- [ ] **Keyboard**: Error dismissible via keyboard (Esc key)

### Consistency
- [ ] **Format**: All errors follow "Title: Message\n\nWhat to do:\n1. Action" format
- [ ] **Numbering**: Recovery steps use numbered lists (1. 2. 3.)
- [ ] **Language**: Consistent terminology across all errors
- [ ] **Action Verbs**: Start action items with verbs (Check, Try, Ensure, etc.)

---

## 8. Cross-Component Error Testing

### Test 8.1: Error Persistence Across Navigation
**Steps**:
1. Trigger error on sign-in page
2. Navigate to sign-up page
3. Return to sign-in page

**Validation**:
- [ ] Previous error is cleared when navigating away
- [ ] No error persists incorrectly on new page
- [ ] Form state is reset appropriately

---

### Test 8.2: Multiple Errors in Sequence
**Steps**:
1. Trigger invalid email error on sign-up
2. Fix email
3. Trigger weak password error
4. Fix password
5. Trigger network error (go offline)

**Validation**:
- [ ] Each error replaces previous error (not accumulating)
- [ ] Error messages are specific to current issue
- [ ] No conflicting error messages shown simultaneously

---

## 9. Beta User Feedback Collection

### During Testing, Note:
- [ ] **Clarity**: Is error message immediately understandable?
- [ ] **Actionability**: Can user resolve issue from error message alone?
- [ ] **Frustration Level**: Does error reduce or increase user frustration?
- [ ] **Support Need**: Would user contact support or self-resolve?
- [ ] **Language**: Is terminology clear to non-technical users?

### Metrics to Track:
- [ ] **Time to Resolution**: How long to fix error and retry?
- [ ] **Retry Success Rate**: Did error message help user succeed on retry?
- [ ] **Support Ticket Avoidance**: Would error prevent support contact?

---

## 10. Regression Testing

### Before Deploying Updates:
- [ ] All existing E2E tests pass (`npm run e2e`)
- [ ] Error message E2E tests pass (`npx playwright test error-messages.spec.ts`)
- [ ] Manual testing checklist completed
- [ ] Accessibility audit passes (axe-core or Lighthouse)
- [ ] No console errors in browser DevTools

---

## Test Results Template

**Tester**: _______________  
**Date**: _______________  
**Environment**: Development / Staging / Production  
**Browser**: _______________  

### Summary
- **Total Tests**: _____ / _____
- **Passed**: _____
- **Failed**: _____
- **Blockers**: _____

### Critical Issues Found:
1. 
2. 
3. 

### Recommendations:
1. 
2. 
3. 

### Next Steps:
- [ ] File bugs for failed tests
- [ ] Update error message utility if needed
- [ ] Retest after fixes
- [ ] Approve for beta deployment

---

**Testing Complete**: ☐ Ready for Beta | ☐ Needs Fixes | ☐ Blocked
