# MFA API Mapping - Documentation to Implementation

**Purpose**: Map documented MFA API calls to actual SDK implementation  
**Date**: November 14, 2025  
**Status**: Reference for MFA guide rewrite

---

## API Namespace Change

**DOCUMENTED** (WRONG):
```typescript
plinto.auth.mfa.*  // Nested namespace - DOES NOT EXIST
```

**ACTUAL** (CORRECT):
```typescript
plinto.auth.*  // Flat namespace - ALL MFA methods are directly on auth
```

---

## Method Mapping Table

| Documented Method | Actual Method | Parameter Changes | Notes |
|-------------------|---------------|-------------------|-------|
| `plinto.auth.mfa.setup()` | `plinto.auth.enableMFA()` | method param required | Renamed: setup → enableMFA |
| `plinto.auth.mfa.verify()` | `plinto.auth.verifyMFA()` | code param required | Renamed: verify → verifyMFA |
| `plinto.auth.mfa.getStatus()` | `plinto.auth.getMFAStatus()` | No userId param | No parameters needed |
| `plinto.auth.mfa.disable()` | `plinto.auth.disableMFA()` | password param required | No confirmationCode |
| `plinto.auth.mfa.generateBackupCodes()` | `plinto.auth.regenerateMFABackupCodes()` | password param required | Renamed: generate → regenerate |
| `plinto.auth.mfa.challenge()` | NOT EXISTS | - | Remove from documentation |
| `plinto.auth.mfa.verifySetup()` | USE `verifyMFA()` | - | Combined into verifyMFA |
| `plinto.auth.mfa.requestNewCode()` | NOT EXISTS | - | Remove from documentation |
| `plinto.auth.mfa.webauthn.*` | USE passkey methods | See below | Wrong namespace |

---

## Detailed Method Replacements

### 1. Setup/Enable MFA

**DOCUMENTED**:
```typescript
const mfaSetup = await plinto.auth.mfa.setup({
  userId: user.id,
  method: 'totp',
  phoneNumber: '+1234567890',  // For SMS
  label: 'My Account'
});
```

**ACTUAL**:
```typescript
const mfaSetup = await plinto.auth.enableMFA('totp');
// Returns: { qr_code, secret, backup_codes }
// No userId needed (uses authenticated user)
// No phoneNumber support yet
// No label parameter
```

### 2. Verify MFA Code

**DOCUMENTED**:
```typescript
const result = await plinto.auth.mfa.verify({
  sessionId: session.id,
  method: 'totp',
  code: '123456'
});
```

**ACTUAL**:
```typescript
const result = await plinto.auth.verifyMFA({
  code: '123456'
});
// Returns: AuthResponse with tokens
// No sessionId needed
// No method parameter (inferred from setup)
```

### 3. Get MFA Status

**DOCUMENTED**:
```typescript
const status = await plinto.auth.mfa.getStatus({
  userId: user.id
});
```

**ACTUAL**:
```typescript
const status = await plinto.auth.getMFAStatus();
// No parameters needed (uses authenticated user)
// Returns: { enabled, method, backup_codes_remaining }
```

### 4. Disable MFA

**DOCUMENTED**:
```typescript
await plinto.auth.mfa.disable({
  userId: user.id,
  password: 'userPassword',
  confirmationCode: '123456'
});
```

**ACTUAL**:
```typescript
await plinto.auth.disableMFA('userPassword');
// Only password needed for confirmation
// No userId or confirmationCode parameters
```

### 5. Generate/Regenerate Backup Codes

**DOCUMENTED**:
```typescript
const backupCodes = await plinto.auth.mfa.generateBackupCodes({
  userId: user.id,
  count: 10
});
```

**ACTUAL**:
```typescript
const backupCodes = await plinto.auth.regenerateMFABackupCodes('userPassword');
// Returns fixed number of codes (usually 8-10)
// Requires password for security
// No count parameter
```

### 6. WebAuthn/Passkey Methods

**DOCUMENTED** (WRONG):
```typescript
// Documented as nested under mfa.webauthn:
const challenge = await plinto.auth.mfa.webauthn.generateChallenge({
  userId: user.id,
  type: 'platform'
});

const verification = await plinto.auth.mfa.webauthn.verify({
  challengeId: challenge.id,
  credential: publicKeyCredential
});
```

**ACTUAL** (CORRECT):
```typescript
// Passkey methods are directly on auth:
const options = await plinto.auth.getPasskeyRegistrationOptions({
  authenticator_attachment: 'platform'  // optional
});

const verified = await plinto.auth.verifyPasskeyRegistration(
  credential,
  'My Passkey'  // optional name
);

// For authentication:
const authOptions = await plinto.auth.getPasskeyAuthenticationOptions(email);
const authResult = await plinto.auth.verifyPasskeyAuthentication(
  credential,
  challenge,
  email
);
```

---

## Additional Methods (Not Documented but Available)

These bonus methods exist in the SDK but aren't documented:

```typescript
// MFA Recovery
await plinto.auth.validateMFACode(code);
await plinto.auth.getMFARecoveryOptions(email);
await plinto.auth.initiateMFARecovery(email);

// Passkey Management
await plinto.auth.checkPasskeyAvailability();
await plinto.auth.listPasskeys();
await plinto.auth.updatePasskey(passkeyId, newName);
await plinto.auth.deletePasskey(passkeyId, password);
await plinto.auth.regeneratePasskeySecret(passkeyId);
```

---

## Search & Replace Guide

For updating the MFA guide, use these regex patterns:

### Pattern 1: Basic namespace change
```regex
plinto\.auth\.mfa\.
→
plinto.auth.
```

### Pattern 2: Method renames
```regex
plinto\.auth\.mfa\.setup\(
→
plinto.auth.enableMFA(

plinto\.auth\.mfa\.verify\(
→
plinto.auth.verifyMFA(

plinto\.auth\.mfa\.getStatus\(
→
plinto.auth.getMFAStatus(

plinto\.auth\.mfa\.disable\(
→
plinto.auth.disableMFA(

plinto\.auth\.mfa\.generateBackupCodes\(
→
plinto.auth.regenerateMFABackupCodes(
```

### Pattern 3: Remove userId parameters
```regex
\{\s*userId:\s*[^,}]+,\s*
→
{

\{\s*userId:\s*[^}]+\}
→
()
```

### Pattern 4: WebAuthn namespace
```regex
plinto\.auth\.mfa\.webauthn\.
→
plinto.auth.
```

---

## Parameter Structure Changes

### Old Structure (Documented)
Most methods used object parameters with explicit userId:
```typescript
{ userId, method, code }
```

### New Structure (Actual)
Methods use authenticated user context, simpler params:
```typescript
(method)  // for enableMFA
{ code }  // for verifyMFA
()        // for getMFAStatus
(password) // for disableMFA
```

---

## Testing Changes

After updating documentation, verify:

1. ✅ All code examples compile without TypeScript errors
2. ✅ Method signatures match SDK implementation
3. ✅ No references to non-existent methods (challenge, requestNewCode, verifySetup)
4. ✅ No nested mfa.* or mfa.webauthn.* namespaces remain
5. ✅ Parameter structures match actual SDK requirements

---

**Status**: Ready for MFA guide rewrite  
**Next Step**: Apply systematic replacements to apps/docs/content/guides/authentication/mfa.md
