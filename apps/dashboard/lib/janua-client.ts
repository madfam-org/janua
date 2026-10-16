/**
 * Janua SDK Client Configuration for Dashboard
 *
 * Replaces custom auth implementation with official @janua/typescript-sdk
 */

import { JanuaClient } from '@janua/typescript-sdk'
import { lazyConsoleClient, lazyConsoleObject } from '@janua/ui/console-runtime'

// Imports never read credentials, construct an SDK or mutate server state.
export const januaClient = lazyConsoleClient('dashboard', config => new JanuaClient({
  baseURL: config.apiOrigin,
  issuer: config.issuer,
  audience: config.audience,
  tokenStorage: 'localStorage',
  autoRefreshTokens: true,
  // Browser WebSockets attach cookies without a credentials:omit option.
  // Stage uses the existing polling fallback until host isolation is approved.
  wsUrl: config.environment === 'staging' ? undefined : config.apiOrigin.replace(/^http/, 'ws') + '/ws',
  wsAutoConnect: false, // Connect on demand (e.g. audit live feed)
}))

// Export modules for convenience
export const auth = lazyConsoleObject(() => januaClient.auth)
export const users = lazyConsoleObject(() => januaClient.users)
export const sessions = lazyConsoleObject(() => januaClient.sessions)
export const organizations = lazyConsoleObject(() => januaClient.organizations)
export const webhooks = lazyConsoleObject(() => januaClient.webhooks)
export const admin = lazyConsoleObject(() => januaClient.admin)
export const sso = lazyConsoleObject(() => januaClient.sso)
export const invitations = lazyConsoleObject(() => januaClient.invitations)
export const scim = lazyConsoleObject(() => januaClient.scim)

export default januaClient
