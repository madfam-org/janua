/**
 * Janua SDK Client Configuration for Admin App
 */

import { JanuaClient } from '@janua/typescript-sdk'

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'
const apiBasePath = process.env.NEXT_PUBLIC_API_BASE_PATH || '/api/v1'

// Construct the full base URL for the SDK
const baseURL = `${apiUrl}${apiBasePath}`

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
