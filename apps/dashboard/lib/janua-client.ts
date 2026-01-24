/**
 * Janua SDK Client Configuration for Dashboard
 *
 * Replaces custom auth implementation with official @janua/typescript-sdk
 */

import { JanuaClient } from '@janua/typescript-sdk'

const baseURL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

export const januaClient = new JanuaClient({
  baseURL,
  debug: process.env.NODE_ENV === 'development',
  tokenStorage: 'localStorage',
  autoRefreshTokens: true,
})

// Export modules for convenience
export const auth = januaClient.auth
export const users = januaClient.users
export const sessions = januaClient.sessions
export const organizations = januaClient.organizations

export default januaClient
