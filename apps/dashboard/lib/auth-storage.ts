/**
 * Canonical auth storage keys for the dashboard.
 *
 * WHY THIS FILE EXISTS: these names were previously hand-written at five call
 * sites, and they drifted. The login page wrote the session cookie as
 * `janua_access_token` (matching middleware.ts, which gates every route), while
 * app/page.tsx and components/layout/dashboard-layout.tsx read `janua_token`
 * and the logout handlers cleared `janua_token`.
 *
 * The result was an infinite redirect loop that presented as a frozen loading
 * screen after a SUCCESSFUL login: middleware saw a valid `janua_access_token`
 * and admitted the user to `/`; the page looked for `janua_token`, found
 * nothing, and sent them to `/login`; middleware saw the valid cookie again and
 * bounced them back to `/`. Neither side believed it had failed, so nothing was
 * logged and no error surfaced. Logout was broken by the same typo — it cleared
 * a cookie that did not exist, leaving the real session intact.
 *
 * Import these constants. Do not re-type the strings.
 */

import { browserConsoleConfig, consoleCookieDomain, consoleSessionCookie } from '@janua/ui/console-runtime'

// Re-exported so callers have one import site for keys AND helpers.
export {
  AUTH_COOKIE,
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  TOKEN_EXPIRES_AT_KEY,
  USER_KEY,
} from './auth-keys'

/** Read a cookie value by name; returns null on the server or when absent. */
export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() || null
  }
  return null
}

/** The session token as middleware sees it. */
export function getAuthToken(): string | null {
  if (typeof document === 'undefined') return null
  return getCookie(consoleSessionCookie(browserConsoleConfig('dashboard')))
}

/**
 * Persist the session cookie. Scoped to .janua.dev in production so the
 * dashboard, admin and website share one session; host-only elsewhere
 * (localhost, preview hosts) where a domain attribute would be rejected.
 */
export function setAuthCookie(token: string): void {
  if (typeof document === 'undefined') return
  const config = browserConsoleConfig('dashboard')
  document.cookie = `${consoleSessionCookie(config)}=${token}; path=/${consoleCookieDomain(config)}; secure; samesite=lax`
}

/**
 * Clear the session everywhere it could live. Both the host-only and
 * domain-scoped forms are expired, because a cookie set with a domain
 * attribute is NOT removed by expiring the host-only one — that asymmetry is
 * how a "logged out" user stayed logged in.
 */
export function clearAuthCookie(): void {
  if (typeof document === 'undefined') return
  const expired = 'expires=Thu, 01 Jan 1970 00:00:01 GMT'
  const config = browserConsoleConfig('dashboard')
  const name = consoleSessionCookie(config)
  document.cookie = `${name}=; path=/; ${expired}; secure; samesite=lax`
  if (consoleCookieDomain(config)) document.cookie = `${name}=; path=/${consoleCookieDomain(config)}; ${expired}; secure; samesite=lax`
}
