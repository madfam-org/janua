/**
 * Janua SDK Client Configuration for Admin App
 */

import { JanuaClient } from '@janua/typescript-sdk'

// SDK methods already include /api/v1 prefix in their paths,
// so baseURL should be the API root without the base path
const baseURL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

export const januaClient = new JanuaClient({
  baseURL,
  debug: process.env.NODE_ENV === 'development',
  tokenStorage: 'localStorage',
  autoRefreshTokens: true,
  timeout: 30000,
})

export const auth = januaClient.auth
export const users = januaClient.users
export const organizations = januaClient.organizations

export default januaClient
