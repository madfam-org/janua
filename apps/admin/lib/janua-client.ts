/**
 * Janua SDK Client Configuration for Admin App
 */

import { JanuaClient } from '@janua/typescript-sdk'
import { lazyConsoleClient, lazyConsoleObject } from '@janua/ui/console-runtime'

// SDK methods already include /api/v1 prefix in their paths,
// so baseURL should be the API root without the base path
export const januaClient = lazyConsoleClient('admin', config => new JanuaClient({
  baseURL: config.apiOrigin,
  issuer: config.issuer,
  audience: config.audience,
  tokenStorage: 'localStorage',
  autoRefreshTokens: true,
  timeout: 30000,
}))

export const auth = lazyConsoleObject(() => januaClient.auth)
export const users = lazyConsoleObject(() => januaClient.users)
export const organizations = lazyConsoleObject(() => januaClient.organizations)

export default januaClient
