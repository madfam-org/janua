/**
 * Admin panel timing constants
 *
 * Centralizes magic numbers for auto-dismiss timeouts, polling intervals,
 * and other timing values used across admin components.
 */

// Vault secret reveal auto-hide interval (milliseconds)
export const VAULT_POLL_INTERVAL_MS = 30_000

// Error-context auto-dismiss timeouts by severity (milliseconds)
export const AUTO_DISMISS_MS = {
  error: null, // Never auto-dismiss errors
  warning: 10_000,
  info: 5_000,
  success: 3_000,
} as const
