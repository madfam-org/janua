/**
 * Comprehensive Error Message Utilities
 *
 * Provides actionable, user-friendly error messages with recovery suggestions
 * for all Plinto authentication components.
 */

export interface ErrorContext {
  /** HTTP status code if available */
  status?: number
  /** Error code from API */
  code?: string
  /** Original error message */
  message?: string
  /** Additional context */
  details?: Record<string, any>
}

export interface ActionableError {
  /** User-friendly title */
  title: string
  /** Detailed explanation */
  message: string
  /** Suggested actions to resolve */
  actions: readonly string[]
  /** Technical details (optional, for developers) */
  technical?: string
}

/**
 * Authentication Error Messages
 */
export const AUTH_ERRORS = {
  // Sign In Errors
  INVALID_CREDENTIALS: {
    title: 'Invalid credentials',
    message: 'The email or password you entered is incorrect.',
    actions: [
      'Double-check your email and password',
      'Use "Forgot password?" to reset your password',
      'Ensure Caps Lock is off',
    ],
  },
  ACCOUNT_LOCKED: {
    title: 'Account locked',
    message: 'Your account has been temporarily locked due to multiple failed login attempts.',
    actions: [
      'Wait 15 minutes and try again',
      'Use "Forgot password?" to reset your password',
      'Contact support if you need immediate access',
    ],
  },
  ACCOUNT_NOT_VERIFIED: {
    title: 'Email not verified',
    message: 'Please verify your email address before signing in.',
    actions: [
      'Check your inbox for the verification email',
      'Click "Resend verification email" if you didn\'t receive it',
      'Check your spam folder',
    ],
  },

  // Sign Up Errors
  EMAIL_ALREADY_EXISTS: {
    title: 'Email already registered',
    message: 'An account with this email address already exists.',
    actions: [
      'Try signing in instead',
      'Use "Forgot password?" if you don\'t remember your password',
      'Use a different email address',
    ],
  },
  WEAK_PASSWORD: {
    title: 'Password too weak',
    message: 'Your password doesn\'t meet the security requirements.',
    actions: [
      'Use at least 8 characters',
      'Include uppercase and lowercase letters',
      'Add at least one number',
      'Add a special character (!@#$%^&*)',
    ],
  },
  INVALID_EMAIL: {
    title: 'Invalid email address',
    message: 'The email address format is not valid.',
    actions: [
      'Check for typos in your email',
      'Ensure format is: name@example.com',
      'Remove any extra spaces',
    ],
  },

  // Password Reset Errors
  RESET_TOKEN_EXPIRED: {
    title: 'Reset link expired',
    message: 'This password reset link has expired. Reset links are valid for 1 hour.',
    actions: [
      'Request a new password reset email',
      'Use the latest email you received',
      'Complete the reset process within 1 hour',
    ],
  },
  RESET_TOKEN_INVALID: {
    title: 'Invalid reset link',
    message: 'This password reset link is invalid or has already been used.',
    actions: [
      'Request a new password reset email',
      'Copy the entire link from your email',
      'Ensure you\'re clicking the latest reset link',
    ],
  },
  PASSWORDS_DONT_MATCH: {
    title: 'Passwords don\'t match',
    message: 'The passwords you entered don\'t match.',
    actions: [
      'Re-enter both passwords',
      'Ensure they match exactly',
      'Check Caps Lock is off',
    ],
  },

  // MFA Errors
  INVALID_MFA_CODE: {
    title: 'Invalid verification code',
    message: 'The verification code you entered is incorrect or has expired.',
    actions: [
      'Enter the current 6-digit code from your authenticator app',
      'Wait for a new code if the current one expired',
      'Ensure your device time is synced correctly',
      'Try using a backup code if available',
    ],
  },
  MFA_ALREADY_ENABLED: {
    title: 'MFA already enabled',
    message: 'Multi-factor authentication is already set up for your account.',
    actions: [
      'Use your existing authenticator app',
      'Disable MFA first if you want to reconfigure',
      'Contact support if you lost access to your authenticator',
    ],
  },

  // Organization Errors
  ORG_NAME_TAKEN: {
    title: 'Organization name unavailable',
    message: 'An organization with this name or slug already exists.',
    actions: [
      'Try a different organization name',
      'Add a unique identifier to the name',
      'Contact support if this is your organization',
    ],
  },
  INSUFFICIENT_PERMISSIONS: {
    title: 'Permission denied',
    message: 'You don\'t have permission to perform this action.',
    actions: [
      'Contact your organization admin for access',
      'Verify you\'re in the correct organization',
      'Check your role permissions',
    ],
  },

  // Session Errors
  SESSION_EXPIRED: {
    title: 'Session expired',
    message: 'Your session has expired for security reasons.',
    actions: [
      'Sign in again to continue',
      'Enable "Remember me" for longer sessions',
      'Ensure cookies are enabled',
    ],
  },
  SESSION_INVALID: {
    title: 'Invalid session',
    message: 'Your session is no longer valid.',
    actions: [
      'Sign in again',
      'Clear your browser cookies and try again',
      'Contact support if the issue persists',
    ],
  },

  // Network/System Errors
  NETWORK_ERROR: {
    title: 'Connection error',
    message: 'Unable to connect to the authentication server.',
    actions: [
      'Check your internet connection',
      'Try again in a few moments',
      'Refresh the page',
      'Contact support if the issue persists',
    ],
  },
  RATE_LIMIT_EXCEEDED: {
    title: 'Too many attempts',
    message: 'You\'ve made too many requests. Please slow down.',
    actions: (waitTime?: number) => [
      `Wait ${waitTime || 5} minutes before trying again`,
      'Avoid rapid repeated attempts',
      'Contact support if you need immediate access',
    ],
  },
  SERVER_ERROR: {
    title: 'Server error',
    message: 'Something went wrong on our end. This is not your fault.',
    actions: [
      'Try again in a few moments',
      'Refresh the page',
      'Contact support if the issue persists',
      'Our team has been notified',
    ],
  },
  TIMEOUT_ERROR: {
    title: 'Request timeout',
    message: 'The request took too long to complete.',
    actions: [
      'Check your internet connection',
      'Try again with a faster connection',
      'Reduce the size of uploaded files if applicable',
    ],
  },

  // Validation Errors
  REQUIRED_FIELD: (fieldName: string) => ({
    title: 'Required field',
    message: `${fieldName} is required.`,
    actions: [
      `Enter your ${fieldName.toLowerCase()}`,
      'Fill in all required fields',
    ],
  }),
  INVALID_FORMAT: (fieldName: string, format: string) => ({
    title: 'Invalid format',
    message: `${fieldName} format is invalid.`,
    actions: [
      `Ensure ${fieldName.toLowerCase()} is in format: ${format}`,
      'Remove any extra spaces',
      'Check for typos',
    ],
  }),
} as const

/**
 * Parse API error response and return actionable error
 */
export function parseApiError(error: any, context?: ErrorContext): ActionableError {
  // Extract error information
  const status = context?.status || error?.response?.status || error?.status
  const code = context?.code || error?.code || error?.response?.data?.code
  const message = context?.message || error?.message || error?.response?.data?.message

  // Map HTTP status codes to error types
  if (status === 401) {
    if (message?.toLowerCase().includes('not verified')) {
      return AUTH_ERRORS.ACCOUNT_NOT_VERIFIED
    }
    if (message?.toLowerCase().includes('locked')) {
      return AUTH_ERRORS.ACCOUNT_LOCKED
    }
    return AUTH_ERRORS.INVALID_CREDENTIALS
  }

  if (status === 403) {
    return AUTH_ERRORS.INSUFFICIENT_PERMISSIONS
  }

  if (status === 409) {
    if (message?.toLowerCase().includes('email')) {
      return AUTH_ERRORS.EMAIL_ALREADY_EXISTS
    }
    if (message?.toLowerCase().includes('organization')) {
      return AUTH_ERRORS.ORG_NAME_TAKEN
    }
  }

  if (status === 422 || status === 400) {
    if (message?.toLowerCase().includes('password')) {
      if (message.toLowerCase().includes('weak') || message.toLowerCase().includes('strength')) {
        return AUTH_ERRORS.WEAK_PASSWORD
      }
      if (message.toLowerCase().includes('match')) {
        return AUTH_ERRORS.PASSWORDS_DONT_MATCH
      }
    }
    if (message?.toLowerCase().includes('email')) {
      return AUTH_ERRORS.INVALID_EMAIL
    }
    if (message?.toLowerCase().includes('token') || message?.toLowerCase().includes('expired')) {
      return AUTH_ERRORS.RESET_TOKEN_EXPIRED
    }
    if (message?.toLowerCase().includes('code')) {
      return AUTH_ERRORS.INVALID_MFA_CODE
    }
  }

  if (status === 429) {
    // Extract retry-after from headers if available
    const retryAfter = error?.response?.headers?.['retry-after']
    const waitMinutes = retryAfter ? Math.ceil(parseInt(retryAfter) / 60) : 5
    return {
      ...AUTH_ERRORS.RATE_LIMIT_EXCEEDED,
      actions: typeof AUTH_ERRORS.RATE_LIMIT_EXCEEDED.actions === 'function'
        ? AUTH_ERRORS.RATE_LIMIT_EXCEEDED.actions(waitMinutes)
        : AUTH_ERRORS.RATE_LIMIT_EXCEEDED.actions,
    }
  }

  if (status && status >= 500) {
    return AUTH_ERRORS.SERVER_ERROR
  }

  // Network errors
  if (error?.message?.toLowerCase().includes('network') ||
      error?.message?.toLowerCase().includes('fetch') ||
      !status) {
    return AUTH_ERRORS.NETWORK_ERROR
  }

  if (error?.message?.toLowerCase().includes('timeout')) {
    return AUTH_ERRORS.TIMEOUT_ERROR
  }

  // Generic fallback
  return {
    title: 'An error occurred',
    message: message || 'Something went wrong. Please try again.',
    actions: [
      'Try again',
      'Refresh the page',
      'Contact support if the issue persists',
    ],
    technical: error?.message || JSON.stringify(error),
  }
}

/**
 * Format actionable error for display
 */
export function formatErrorMessage(error: ActionableError, showActions = true): string {
  let message = `${error.title}: ${error.message}`

  if (showActions && error.actions.length > 0) {
    message += '\n\nWhat to do:\n' + error.actions.map((action, i) => `${i + 1}. ${action}`).join('\n')
  }

  return message
}

/**
 * Get user-friendly error message from any error
 */
export function getErrorMessage(error: any, context?: ErrorContext): string {
  const actionableError = parseApiError(error, context)
  return formatErrorMessage(actionableError, true)
}

/**
 * Get brief error message (title + message only, no actions)
 */
export function getBriefErrorMessage(error: any, context?: ErrorContext): string {
  const actionableError = parseApiError(error, context)
  return `${actionableError.title}: ${actionableError.message}`
}

/**
 * Check if error is recoverable (user can fix it)
 */
export function isRecoverableError(error: any): boolean {
  const parsed = parseApiError(error)

  // Network and server errors are usually temporary
  const temporaryErrors = [
    AUTH_ERRORS.NETWORK_ERROR.title,
    AUTH_ERRORS.SERVER_ERROR.title,
    AUTH_ERRORS.TIMEOUT_ERROR.title,
  ] as const

  return (temporaryErrors as readonly string[]).includes(parsed.title)
}

/**
 * Get retry delay in milliseconds for recoverable errors
 */
export function getRetryDelay(error: any, attempt: number = 0): number {
  if (!isRecoverableError(error)) {
    return 0
  }

  // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
  return Math.min(1000 * Math.pow(2, attempt), 30000)
}
