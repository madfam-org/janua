# OAuth 2.0 Social Login

Implement social authentication with major OAuth providers including Google, GitHub, Microsoft, Apple, Discord, Twitter, and LinkedIn.

## Overview

OAuth 2.0 social login allows users to authenticate using their existing accounts from popular services. Plinto supports all major providers with a unified interface and automatic profile synchronization.

## Supported Providers

| Provider | Status | Features | Required Scopes |
|----------|--------|----------|-----------------|
| **Google** | ✅ Ready | Email, Profile, Photos | `openid email profile` |
| **GitHub** | ✅ Ready | Email, Profile, Repos | `user:email read:user` |
| **Microsoft** | ✅ Ready | Email, Profile, Azure AD | `openid email profile` |
| **Apple** | ✅ Ready | Email, Name, Sign in with Apple | `email name` |
| **Discord** | ✅ Ready | Email, Profile, Guilds | `identify email` |
| **Twitter** | ✅ Ready | Email, Profile, Timeline | `users.read tweet.read` |
| **LinkedIn** | ✅ Ready | Email, Profile, Connections | `r_emailaddress r_liteprofile` |

## Quick Start

### 1. Configure Provider

```typescript
// Initialize OAuth provider
const plinto = new Plinto({
  providers: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      redirectUri: 'https://app.example.com/auth/google/callback',
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID,
      clientSecret: process.env.GITHUB_CLIENT_SECRET,
      redirectUri: 'https://app.example.com/auth/github/callback',
    },
    // ... other providers
  }
})
```

### 2. Initiate OAuth Flow

```typescript
// Generate OAuth URL
const authUrl = await plinto.auth.oauth.getAuthorizationUrl({
  provider: 'google',
  state: generateState(), // CSRF protection
  scopes: ['email', 'profile'], // Optional custom scopes
})

// Redirect user
redirect(authUrl)
```

### 3. Handle Callback

```typescript
// In callback route
const { user, session, isNewUser } = await plinto.auth.oauth.callback({
  provider: 'google',
  code: request.query.code,
  state: request.query.state,
})

if (session) {
  // User authenticated
  setCookie('session', session.token)
  redirect(isNewUser ? '/onboarding' : '/dashboard')
}
```

## Provider Setup Guides

### Google OAuth

#### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable Google+ API
4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID

#### 2. Configure OAuth Consent Screen

```javascript
// Required scopes for Google
const GOOGLE_SCOPES = [
  'openid',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
]

// Optional scopes
const OPTIONAL_SCOPES = [
  'https://www.googleapis.com/auth/drive.readonly', // Google Drive
  'https://www.googleapis.com/auth/calendar.readonly', // Calendar
]
```

#### 3. Implementation

```typescript
// app/api/auth/google/route.ts
import { plinto } from '@/lib/auth'

export async function GET() {
  const authUrl = await plinto.auth.oauth.getAuthorizationUrl({
    provider: 'google',
    scopes: ['openid', 'email', 'profile'],
    prompt: 'select_account', // Force account selection
    accessType: 'offline', // Get refresh token
  })

  return Response.redirect(authUrl)
}

// app/api/auth/google/callback/route.ts
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const state = searchParams.get('state')

  try {
    const result = await plinto.auth.oauth.callback({
      provider: 'google',
      code,
      state,
    })

    // Handle successful authentication
    return Response.redirect('/dashboard')
  } catch (error) {
    return Response.redirect('/login?error=oauth_failed')
  }
}
```

### GitHub OAuth

#### 1. Register OAuth App

1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Click "New OAuth App"
3. Fill in application details
4. Copy Client ID and generate Client Secret

#### 2. Configuration

```typescript
const GITHUB_CONFIG = {
  clientId: process.env.GITHUB_CLIENT_ID,
  clientSecret: process.env.GITHUB_CLIENT_SECRET,
  redirectUri: 'https://app.example.com/auth/github/callback',
  scopes: [
    'user:email', // Read email addresses
    'read:user', // Read user profile
    'read:org', // Read organization membership (optional)
  ],
}
```

#### 3. Advanced GitHub Integration

```typescript
// Get additional GitHub data
const { user, githubData } = await plinto.auth.oauth.callback({
  provider: 'github',
  code,
  enrichProfile: true, // Fetch additional data
})

// githubData includes:
// - repos: User's public repositories
// - organizations: User's organizations
// - followers: Follower count
// - following: Following count
```

### Microsoft / Azure AD

#### 1. Register Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to Azure Active Directory → App registrations
3. Click "New registration"
4. Configure redirect URIs

#### 2. Multi-Tenant Support

```typescript
const MICROSOFT_CONFIG = {
  clientId: process.env.MICROSOFT_CLIENT_ID,
  clientSecret: process.env.MICROSOFT_CLIENT_SECRET,
  tenant: 'common', // Multi-tenant
  // Or specific tenant: 'contoso.onmicrosoft.com'
  redirectUri: 'https://app.example.com/auth/microsoft/callback',
}
```

#### 3. Enterprise Integration

```typescript
// Azure AD with organization validation
const result = await plinto.auth.oauth.callback({
  provider: 'microsoft',
  code,
  validateDomain: 'contoso.com', // Restrict to domain
  mapGroups: true, // Map AD groups to roles
})
```

### Apple Sign In

#### 1. Configure Sign in with Apple

1. Enable Sign in with Apple in App ID configuration
2. Create Service ID for web authentication
3. Configure domains and redirect URLs
4. Generate private key

#### 2. Implementation

```typescript
// Apple requires special handling
const APPLE_CONFIG = {
  clientId: process.env.APPLE_SERVICE_ID, // Service ID, not App ID
  teamId: process.env.APPLE_TEAM_ID,
  keyId: process.env.APPLE_KEY_ID,
  privateKey: process.env.APPLE_PRIVATE_KEY, // .p8 key content
  redirectUri: 'https://app.example.com/auth/apple/callback',
}

// Apple-specific options
const authUrl = await plinto.auth.oauth.getAuthorizationUrl({
  provider: 'apple',
  responseMode: 'form_post', // Apple uses POST
  scope: 'email name',
})
```

#### 3. Handle Apple's POST Callback

```typescript
// Apple sends POST request
app.post('/auth/apple/callback', async (req, res) => {
  const { code, state, user } = req.body

  // Apple provides user info only on first sign-in
  if (user) {
    const userData = JSON.parse(user)
    // Store user data as Apple won't send it again
  }

  const result = await plinto.auth.oauth.callback({
    provider: 'apple',
    code,
    state,
  })
})
```

## Advanced OAuth Features

### Custom Scopes

```typescript
// Request additional permissions
const authUrl = await plinto.auth.oauth.getAuthorizationUrl({
  provider: 'google',
  scopes: [
    'email',
    'profile',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar.events',
  ],
})
```

### State Management

```typescript
// Generate secure state for CSRF protection
import { randomBytes } from 'crypto'

function generateState() {
  const state = randomBytes(32).toString('hex')

  // Store in session or database
  session.oauthState = state
  session.oauthTimestamp = Date.now()

  return state
}

// Verify state in callback
function verifyState(receivedState: string): boolean {
  const { oauthState, oauthTimestamp } = session

  // Check state matches
  if (receivedState !== oauthState) {
    return false
  }

  // Check not expired (5 minutes)
  if (Date.now() - oauthTimestamp > 5 * 60 * 1000) {
    return false
  }

  return true
}
```

### Account Linking

```typescript
// Link OAuth account to existing user
const result = await plinto.auth.oauth.callback({
  provider: 'github',
  code,
  linkToUser: currentUser.id, // Link to authenticated user
})

// Handle multiple OAuth accounts
const linkedAccounts = await plinto.users.getLinkedAccounts(userId)
// Returns: [
//   { provider: 'google', email: 'user@gmail.com' },
//   { provider: 'github', username: 'user' }
// ]
```

### Profile Enrichment

```typescript
// Automatically fetch and merge profile data
const { user } = await plinto.auth.oauth.callback({
  provider: 'linkedin',
  code,
  enrichProfile: {
    fetchAvatar: true, // Download profile picture
    fetchMetadata: true, // Get additional profile data
    mergeStrategy: 'override', // How to handle conflicts
  },
})
```

## React Components

### OAuth Button Component

```jsx
import { usePlinto } from '@plinto/react-sdk'

function OAuthButton({ provider, children }) {
  const { initiateOAuth } = usePlinto()

  const handleClick = async () => {
    try {
      await initiateOAuth(provider)
    } catch (error) {
      console.error(`${provider} OAuth failed:`, error)
    }
  }

  return (
    <button
      onClick={handleClick}
      className={`oauth-button oauth-${provider}`}
    >
      {children || `Sign in with ${provider}`}
    </button>
  )
}

// Usage
<div className="oauth-buttons">
  <OAuthButton provider="google">
    <GoogleIcon /> Continue with Google
  </OAuthButton>
  <OAuthButton provider="github">
    <GitHubIcon /> Continue with GitHub
  </OAuthButton>
  <OAuthButton provider="microsoft">
    <MicrosoftIcon /> Continue with Microsoft
  </OAuthButton>
</div>
```

### OAuth Provider Selector

```jsx
function OAuthProviderSelector() {
  const providers = [
    { id: 'google', name: 'Google', icon: GoogleIcon },
    { id: 'github', name: 'GitHub', icon: GitHubIcon },
    { id: 'microsoft', name: 'Microsoft', icon: MicrosoftIcon },
    { id: 'apple', name: 'Apple', icon: AppleIcon },
    { id: 'discord', name: 'Discord', icon: DiscordIcon },
  ]

  return (
    <div className="provider-grid">
      {providers.map(provider => (
        <OAuthButton
          key={provider.id}
          provider={provider.id}
        >
          <provider.icon className="w-5 h-5" />
          <span>{provider.name}</span>
        </OAuthButton>
      ))}
    </div>
  )
}
```

## Security Best Practices

### 1. CSRF Protection

```typescript
// Always use state parameter
const state = crypto.randomBytes(32).toString('hex')
storeInSession('oauth_state', state)

const authUrl = await plinto.auth.oauth.getAuthorizationUrl({
  provider: 'google',
  state, // Required for security
})

// Verify in callback
if (request.query.state !== getFromSession('oauth_state')) {
  throw new Error('Invalid state - possible CSRF attack')
}
```

### 2. Scope Minimization

```typescript
// Request only necessary scopes
const MINIMAL_SCOPES = {
  google: ['openid', 'email'], // Just email
  github: ['user:email'], // Just email
  microsoft: ['openid', 'email'], // Just email
}

// Avoid over-permissioning
const AVOID_SCOPES = {
  google: ['https://www.googleapis.com/auth/gmail.send'], // Don't request email sending
  github: ['delete_repo'], // Don't request destructive permissions
}
```

### 3. Token Security

```typescript
// Secure token storage
const storeTokens = async (tokens) => {
  // Encrypt sensitive tokens
  const encrypted = await encrypt(tokens.refreshToken)

  await db.oauthTokens.create({
    userId: user.id,
    provider: 'google',
    accessToken: tokens.accessToken, // Short-lived, less sensitive
    refreshToken: encrypted, // Encrypted long-lived token
    expiresAt: tokens.expiresAt,
  })
}
```

### 4. Provider Validation

```typescript
// Validate provider configuration
function validateProvider(provider: string) {
  const ALLOWED_PROVIDERS = ['google', 'github', 'microsoft', 'apple']

  if (!ALLOWED_PROVIDERS.includes(provider)) {
    throw new Error('Invalid OAuth provider')
  }

  // Check provider is configured
  if (!process.env[`${provider.toUpperCase()}_CLIENT_ID`]) {
    throw new Error(`${provider} OAuth not configured`)
  }
}
```

## Error Handling

### Common OAuth Errors

| Error | Description | Solution |
|-------|-------------|----------|
| `invalid_client` | Invalid client credentials | Check client ID/secret |
| `invalid_grant` | Invalid authorization code | Code expired or already used |
| `access_denied` | User denied permission | Handle gracefully |
| `invalid_scope` | Requested scope not allowed | Check provider configuration |
| `server_error` | Provider server error | Retry with backoff |

### Error Handler Implementation

```typescript
try {
  const result = await plinto.auth.oauth.callback({
    provider,
    code,
  })
} catch (error) {
  switch (error.code) {
    case 'oauth_access_denied':
      // User cancelled OAuth flow
      return redirect('/login?message=oauth_cancelled')

    case 'oauth_email_unverified':
      // Email not verified with provider
      return redirect('/verify-email')

    case 'oauth_account_exists':
      // Account already linked to another user
      return redirect('/login?error=account_linked')

    case 'oauth_provider_error':
      // Provider-side error
      logger.error('OAuth provider error:', error)
      return redirect('/login?error=provider_error')

    default:
      // Generic error
      return redirect('/login?error=oauth_failed')
  }
}
```

## Testing OAuth

### Mock OAuth Provider

```typescript
// test/mocks/oauth.ts
export class MockOAuthProvider {
  async getAuthorizationUrl({ state }) {
    return `http://localhost:3000/mock-oauth/authorize?state=${state}`
  }

  async callback({ code }) {
    if (code === 'valid_code') {
      return {
        user: {
          id: 'mock_user_123',
          email: 'test@example.com',
          name: 'Test User',
        },
        tokens: {
          accessToken: 'mock_access_token',
          refreshToken: 'mock_refresh_token',
        },
      }
    }
    throw new Error('Invalid code')
  }
}
```

### E2E OAuth Test

```typescript
test('complete OAuth flow', async ({ page }) => {
  // Start OAuth flow
  await page.goto('/login')
  await page.click('button:has-text("Continue with Google")')

  // Mock Google OAuth page
  await page.waitForURL(/accounts\.google\.com/)
  await page.fill('input[type="email"]', 'test@gmail.com')
  await page.click('button:has-text("Next")')

  // Complete OAuth and return
  await page.waitForURL('/dashboard')
  await expect(page.locator('text=Welcome')).toBeVisible()
})
```

## Migration from Other Providers

### From Auth0

```typescript
// Auth0
const auth0 = new Auth0({
  domain: 'tenant.auth0.com',
  clientId: 'client_id',
})
auth0.authorize({
  connection: 'google-oauth2',
})

// Plinto equivalent
await plinto.auth.oauth.getAuthorizationUrl({
  provider: 'google',
})
```

### From Firebase

```typescript
// Firebase
const provider = new firebase.auth.GoogleAuthProvider()
firebase.auth().signInWithPopup(provider)

// Plinto equivalent
await plinto.auth.oauth.initiateFlow({
  provider: 'google',
  mode: 'popup', // or 'redirect'
})
```

## Troubleshooting

### Redirect URI Mismatch

1. Exact match required (including trailing slash)
2. Check protocol (http vs https)
3. Verify port number in development
4. Check provider's allowed redirect URIs

### Missing Email

Some providers don't always provide email:
- GitHub: User may have private email
- Apple: User can choose to hide email
- Twitter: Email not always available

Solution:
```typescript
if (!user.email) {
  // Prompt user to provide email
  return redirect('/complete-profile')
}
```

### Token Expiration

```typescript
// Implement token refresh
async function refreshOAuthToken(userId: string, provider: string) {
  const tokens = await getStoredTokens(userId, provider)

  if (isExpired(tokens.accessToken)) {
    const newTokens = await plinto.auth.oauth.refreshToken({
      provider,
      refreshToken: tokens.refreshToken,
    })

    await updateStoredTokens(userId, provider, newTokens)
    return newTokens
  }

  return tokens
}
```

## API Reference

### `getAuthorizationUrl(options)`

Generate OAuth authorization URL.

**Parameters:**
- `provider` (string): OAuth provider name
- `state` (string): CSRF protection state
- `scopes` (string[]): Requested permissions
- `prompt` (string): UI behavior (e.g., 'select_account')

**Returns:**
- `url` (string): Authorization URL to redirect to

### `callback(options)`

Handle OAuth callback and create session.

**Parameters:**
- `provider` (string): OAuth provider name
- `code` (string): Authorization code
- `state` (string): State for CSRF validation

**Returns:**
- `user` (object): User profile
- `session` (object): Session details
- `isNewUser` (boolean): Whether user is new
- `tokens` (object): OAuth tokens

## Related Guides

- [Session Management](/guides/authentication/sessions)
- [Account Linking](/guides/users/account-linking)
- [Social Login Best Practices](/guides/security/social-login)
- [OIDC Integration](/guides/authentication/oidc)