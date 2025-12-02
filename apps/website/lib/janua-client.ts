/**
 * Janua SDK Client Configuration
 *
 * This file initializes and exports the Janua SDK client for use throughout the demo app.
 * The client connects to the production FastAPI backend and provides authentication,
 * user management, and other Janua features.
 */

import { JanuaClient } from '@janua/typescript-sdk'

// Get API URL from environment variables
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const apiBasePath = process.env.NEXT_PUBLIC_API_BASE_PATH || '/api/v1'

// Initialize Janua client
export const januaClient = new JanuaClient({
  baseURL: apiUrl + apiBasePath,
  // Enable debug logging in development
  debug: process.env.NODE_ENV === 'development',
  // Token storage configuration
  tokenStorage: 'localStorage', // Use localStorage for web apps
})

// Export individual modules for convenience
export const auth = januaClient.auth
export const users = januaClient.users
export const sessions = januaClient.sessions
export const organizations = januaClient.organizations
export const sso = januaClient.sso
export const invitations = januaClient.invitations

// Export default client
export default januaClient
