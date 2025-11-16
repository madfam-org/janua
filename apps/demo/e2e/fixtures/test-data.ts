/**
 * Test data fixtures for E2E tests
 */

export const TEST_USERS = {
  validUser: {
    email: 'valid.user@plinto.dev',
    password: 'ValidPass123!',
    firstName: 'Valid',
    lastName: 'User',
  },
  weakPassword: {
    email: 'weak@plinto.dev',
    password: '123',
    firstName: 'Weak',
    lastName: 'Password',
  },
  existingUser: {
    email: 'existing@plinto.dev',
    password: 'ExistingPass123!',
    firstName: 'Existing',
    lastName: 'User',
  },
}

export const TEST_ORGANIZATIONS = {
  techCorp: {
    name: 'Tech Corp',
    slug: 'tech-corp',
  },
  startupInc: {
    name: 'Startup Inc',
    slug: 'startup-inc',
  },
}

export const VERIFICATION_CODES = {
  valid: '123456',
  invalid: '000000',
  expired: '999999',
}

export const MFA_CODES = {
  validTOTP: '123456',
  validSMS: '654321',
  backupCode: 'BACKUP-CODE-1234',
}

export const TEST_DEVICES = {
  chrome: {
    name: 'Chrome on MacOS',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
  },
  mobile: {
    name: 'iPhone Safari',
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
  },
}
