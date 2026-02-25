/**
 * Janua SDK Client Configuration for Dashboard
 *
 * Replaces custom auth implementation with official @janua/typescript-sdk
 */

import { JanuaClient } from '@janua/typescript-sdk'

const baseURL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'
const wsURL = process.env.NEXT_PUBLIC_WS_URL || baseURL.replace(/^http/, 'ws') + '/ws'

export const januaClient = new JanuaClient({
  baseURL,
  audience: process.env.NEXT_PUBLIC_JANUA_AUDIENCE || 'janua.dev',
  debug: process.env.NODE_ENV === 'development',
  tokenStorage: 'localStorage',
  autoRefreshTokens: true,
  wsUrl: wsURL,
  wsAutoConnect: false, // Connect on demand (e.g. audit live feed)
} as any)

// Export modules for convenience
export const auth = januaClient.auth
export const users = januaClient.users
export const sessions = januaClient.sessions
export const organizations = januaClient.organizations
export const webhooks = januaClient.webhooks
export const admin = januaClient.admin
export const sso = januaClient.sso
export const invitations = januaClient.invitations
export const scim = januaClient.scim

export default januaClient
