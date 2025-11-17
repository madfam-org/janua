/**
 * Plinto SDK Client Configuration
 *
 * This file initializes and exports the Plinto SDK client for use throughout the demo app.
 * The client connects to the production FastAPI backend and provides authentication,
 * user management, and other Plinto features.
 */

import { PlintoClient } from '@plinto/typescript-sdk'

// Get API URL from environment variables
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const apiBasePath = process.env.NEXT_PUBLIC_API_BASE_PATH || '/api/v1'

// Initialize Plinto client
export const plintoClient = new PlintoClient({
  baseURL: apiUrl + apiBasePath,
  // Enable debug logging in development
  debug: process.env.NODE_ENV === 'development',
  // Token storage configuration
  tokenStorage: 'localStorage', // Use localStorage for web apps
})

// Export individual modules for convenience
export const auth = plintoClient.auth
export const users = plintoClient.users
export const sessions = plintoClient.sessions
export const organizations = plintoClient.organizations
export const sso = plintoClient.sso
export const invitations = plintoClient.invitations

// Export default client
export default plintoClient
