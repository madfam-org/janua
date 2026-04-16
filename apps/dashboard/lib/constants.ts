/**
 * Dashboard timing constants
 *
 * Centralizes magic numbers for toast dismiss durations, polling intervals,
 * and auto-dismiss timeouts used across settings pages and error handling.
 */

// Toast / success-message auto-dismiss (milliseconds)
export const TOAST_DISMISS_MS = 3_000

// Vault secret reveal auto-hide interval (milliseconds)
export const VAULT_POLL_INTERVAL_MS = 30_000

// Error-context auto-dismiss timeouts by severity (milliseconds)
export const AUTO_DISMISS_MS = {
  error: null, // Never auto-dismiss errors
  warning: 10_000,
  info: 5_000,
  success: 3_000,
} as const
