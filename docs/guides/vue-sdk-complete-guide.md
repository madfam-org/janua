# Vue SDK Complete Guide

## Overview

The **@janua/vue** SDK provides a comprehensive Vue 3 plugin and composable system for integrating Janua authentication and user management into your Vue applications. Built on top of the TypeScript SDK, it offers reactive state management, automatic OAuth handling, and a full set of authentication methods.

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Plugin Configuration](#plugin-configuration)
3. [Core Composables](#core-composables)
4. [Authentication Patterns](#authentication-patterns)
5. [Advanced Features](#advanced-features)
6. [Complete Examples](#complete-examples)
7. [Testing Strategies](#testing-strategies)
8. [TypeScript Support](#typescript-support)
9. [Troubleshooting](#troubleshooting)

## Installation & Setup

### Installation

```bash
npm install @janua/vue
# or
yarn add @janua/vue
# or
pnpm add @janua/vue
```

### Basic Setup

```typescript
// main.ts
import { createApp } from 'vue'
import { createJanua } from '@janua/vue-sdk'
import App from './App.vue'

const app = createApp(App)

app.use(createJanua({
  baseUrl: 'https://api.janua.dev',
  clientId: 'your-client-id',
  organizationSlug: 'your-org-slug'
}))

app.mount('#app')
```

### Environment Configuration

```typescript
// config/janua.ts
export const januaConfig = {
  baseUrl: import.meta.env.VITE_JANUA_BASE_URL || 'https://api.janua.dev',
  clientId: import.meta.env.VITE_JANUA_CLIENT_ID,
  organizationSlug: import.meta.env.VITE_JANUA_ORG_SLUG,
  onAuthChange: (user) => {
    console.log('Auth state changed:', user)
    // Custom logic for auth state changes
  }
}
```

```typescript
// main.ts
import { createJanua } from '@janua/vue-sdk'
import { januaConfig } from './config/janua'

app.use(createJanua(januaConfig))
```

## Plugin Configuration

### JanuaPluginOptions Interface

```typescript
interface JanuaPluginOptions {
  baseUrl: string
  clientId: string
  organizationSlug?: string
  environment?: 'development' | 'staging' | 'production'
  onAuthChange?: (user: User | null) => void
  timeout?: number
  retryAttempts?: number
}
```

### Configuration Examples

```typescript
// Development Configuration
const devConfig = {
  baseUrl: 'http://localhost:8000',
  clientId: 'dev-client-id',
  organizationSlug: 'dev-org',
  environment: 'development' as const,
  onAuthChange: (user) => {
    if (user) {
      console.log(`Welcome ${user.firstName}!`)
    } else {
      console.log('User signed out')
    }
  }
}

// Production Configuration
const prodConfig = {
  baseUrl: 'https://api.janua.dev',
  clientId: process.env.VUE_APP_JANUA_CLIENT_ID,
  organizationSlug: process.env.VUE_APP_JANUA_ORG_SLUG,
  environment: 'production' as const,
  timeout: 10000,
  retryAttempts: 3
}
```

## Core Composables

### useAuth - Authentication Management

```vue
<template>
  <div>
    <div v-if="isLoading">Loading...</div>
    <div v-else-if="isAuthenticated">
      <h2>Welcome {{ user?.firstName }}!</h2>
      <button @click="handleSignOut">Sign Out</button>
    </div>
    <div v-else>
      <LoginForm @sign-in="handleSignIn" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuth } from '@janua/vue-sdk'

const {
  user,
  session,
  isAuthenticated,
  isLoading,
  signIn,
  signUp,
  signOut,
  updateSession
} = useAuth()

const handleSignIn = async (email: string, password: string) => {
  try {
    await signIn(email, password)
    // User is automatically updated via reactive state
  } catch (error) {
    console.error('Sign in failed:', error)
  }
}

const handleSignOut = async () => {
  await signOut()
  // Redirect to login page
}
</script>
```

### useUser - User Profile Management

```vue
<template>
  <div v-if="user">
    <h2>User Profile</h2>
    <form @submit.prevent="handleUpdateProfile">
      <input
        v-model="profileForm.firstName"
        placeholder="First Name"
        :disabled="isLoading"
      />
      <input
        v-model="profileForm.lastName"
        placeholder="Last Name"
        :disabled="isLoading"
      />
      <input
        v-model="profileForm.email"
        type="email"
        placeholder="Email"
        :disabled="isLoading"
      />
      <button type="submit" :disabled="isLoading">
        {{ isLoading ? 'Updating...' : 'Update Profile' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useUser } from '@janua/vue-sdk'

const { user, isLoading, updateUser } = useUser()

const profileForm = ref({
  firstName: '',
  lastName: '',
  email: ''
})

// Populate form when user data is available
watch(user, (newUser) => {
  if (newUser) {
    profileForm.value = {
      firstName: newUser.firstName || '',
      lastName: newUser.lastName || '',
      email: newUser.email || ''
    }
  }
}, { immediate: true })

const handleUpdateProfile = async () => {
  try {
    await updateUser(profileForm.value)
    // User state is automatically updated
  } catch (error) {
    console.error('Profile update failed:', error)
  }
}
</script>
```

### useSession - Session Management

```vue
<template>
  <div>
    <div v-if="session">
      <h3>Active Session</h3>
      <p>Session ID: {{ session.id }}</p>
      <p>Expires: {{ sessionExpiry }}</p>

      <button @click="handleRefreshSession">
        Refresh Session
      </button>

      <button @click="handleRevokeSession" class="danger">
        Revoke This Session
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSession } from '@janua/vue-sdk'

const { session, refreshSession, revokeSession } = useSession()

const sessionExpiry = computed(() => {
  if (!session.value?.expiresAt) return 'Unknown'
  return new Date(session.value.expiresAt).toLocaleString()
})

const handleRefreshSession = async () => {
  try {
    await refreshSession()
  } catch (error) {
    console.error('Session refresh failed:', error)
  }
}

const handleRevokeSession = async () => {
  if (!session.value?.id) return

  try {
    await revokeSession(session.value.id)
    // This will sign out the user if it's the current session
  } catch (error) {
    console.error('Session revoke failed:', error)
  }
}
</script>
```

### useOrganizations - Organization Management

```vue
<template>
  <div>
    <h3>Organizations</h3>
    <div v-if="isLoading">Loading organizations...</div>
    <div v-else-if="organizations.length">
      <div
        v-for="org in organizations"
        :key="org.id"
        class="org-card"
        @click="selectOrganization(org)"
      >
        <h4>{{ org.name }}</h4>
        <p>{{ org.description }}</p>
        <span class="role">{{ org.memberRole }}</span>
      </div>
    </div>
    <div v-else>
      <p>No organizations found</p>
      <button @click="createOrganization">Create Organization</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useOrganizations } from '@janua/vue-sdk'
import type { Organization } from '@janua/vue-sdk'

const organizations = ref<Organization[]>([])
const isLoading = ref(true)

const orgApi = useOrganizations()

onMounted(async () => {
  try {
    organizations.value = await orgApi.getUserOrganizations()
  } catch (error) {
    console.error('Failed to load organizations:', error)
  } finally {
    isLoading.value = false
  }
})

const selectOrganization = async (org: Organization) => {
  try {
    await orgApi.switchToOrganization(org.id)
    // Context switched to selected organization
  } catch (error) {
    console.error('Failed to switch organization:', error)
  }
}

const createOrganization = async () => {
  const name = prompt('Organization name:')
  if (!name) return

  try {
    const newOrg = await orgApi.createOrganization({
      name,
      description: ''
    })
    organizations.value.push(newOrg)
  } catch (error) {
    console.error('Failed to create organization:', error)
  }
}
</script>
```

## Authentication Patterns

### Magic Link Authentication

```vue
<template>
  <div class="magic-link-auth">
    <div v-if="!linkSent">
      <h3>Sign in with Magic Link</h3>
      <form @submit.prevent="handleSendMagicLink">
        <input
          v-model="email"
          type="email"
          placeholder="Enter your email"
          required
        />
        <button type="submit" :disabled="isLoading">
          {{ isLoading ? 'Sending...' : 'Send Magic Link' }}
        </button>
      </form>
    </div>

    <div v-else>
      <h3>Check Your Email</h3>
      <p>We've sent a magic link to {{ email }}</p>
      <button @click="resetForm">Try Different Email</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMagicLink } from '@janua/vue-sdk'

const { sendMagicLink, signInWithMagicLink } = useMagicLink()

const email = ref('')
const linkSent = ref(false)
const isLoading = ref(false)

const handleSendMagicLink = async () => {
  isLoading.value = true
  try {
    await sendMagicLink(email.value, '/dashboard')
    linkSent.value = true
  } catch (error) {
    console.error('Failed to send magic link:', error)
  } finally {
    isLoading.value = false
  }
}

const resetForm = () => {
  email.value = ''
  linkSent.value = false
}

// Handle magic link verification (typically in a route component)
const handleMagicLinkCallback = async (token: string) => {
  try {
    await signInWithMagicLink(token)
    // User is now signed in
  } catch (error) {
    console.error('Magic link verification failed:', error)
  }
}
</script>
```

### OAuth Integration

```vue
<template>
  <div class="oauth-login">
    <h3>Sign in with OAuth</h3>

    <button
      v-for="provider in oauthProviders"
      :key="provider.id"
      @click="initiateOAuth(provider.id)"
      :class="`oauth-btn oauth-${provider.id}`"
    >
      <img :src="provider.icon" :alt="provider.name" />
      Continue with {{ provider.name }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useOAuth } from '@janua/vue-sdk'

const { getOAuthUrl, handleOAuthCallback } = useOAuth()

const oauthProviders = ref([
  { id: 'google', name: 'Google', icon: '/icons/google.svg' },
  { id: 'github', name: 'GitHub', icon: '/icons/github.svg' },
  { id: 'microsoft', name: 'Microsoft', icon: '/icons/microsoft.svg' }
])

const initiateOAuth = async (provider: string) => {
  try {
    const authUrl = await getOAuthUrl(provider, '/auth/callback')
    window.location.href = authUrl
  } catch (error) {
    console.error(`OAuth initiation failed for ${provider}:`, error)
  }
}

// OAuth callback handler (typically in a route component)
const handleCallback = async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')
  const state = urlParams.get('state')

  if (code && state) {
    try {
      await handleOAuthCallback(code, state)
      // Redirect to dashboard or intended destination
    } catch (error) {
      console.error('OAuth callback failed:', error)
    }
  }
}
</script>

<style scoped>
.oauth-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  margin: 0.5rem 0;
  border: 1px solid #ddd;
  border-radius: 0.5rem;
  background: white;
  cursor: pointer;
  transition: background-color 0.2s;
}

.oauth-btn:hover {
  background-color: #f5f5f5;
}

.oauth-btn img {
  width: 20px;
  height: 20px;
}
</style>
```

### Multi-Factor Authentication (MFA)

```vue
<template>
  <div class="mfa-setup">
    <div v-if="!mfaEnabled">
      <h3>Enable Two-Factor Authentication</h3>

      <div class="mfa-options">
        <button @click="enableTOTP" :disabled="isLoading">
          Enable TOTP (Authenticator App)
        </button>
        <button @click="enableSMS" :disabled="isLoading">
          Enable SMS Authentication
        </button>
      </div>
    </div>

    <div v-else-if="showQRCode">
      <h3>Scan QR Code</h3>
      <div class="qr-code">
        <img :src="qrCodeUrl" alt="QR Code" />
      </div>
      <p>Scan this QR code with your authenticator app</p>

      <form @submit.prevent="confirmMFASetup">
        <input
          v-model="verificationCode"
          placeholder="Enter 6-digit code"
          maxlength="6"
          pattern="[0-9]{6}"
          required
        />
        <button type="submit" :disabled="isLoading">
          Verify and Enable
        </button>
      </form>
    </div>

    <div v-else>
      <h3>Two-Factor Authentication Enabled</h3>
      <p>Your account is protected with 2FA</p>

      <button @click="disableMFA" class="danger">
        Disable 2FA
      </button>

      <div class="backup-codes">
        <h4>Backup Codes</h4>
        <p>Save these codes in a safe place:</p>
        <ul>
          <li v-for="code in backupCodes" :key="code">{{ code }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMFA } from '@janua/vue-sdk'

const { enableMFA, confirmMFA, disableMFA, verifyMFA } = useMFA()

const mfaEnabled = ref(false)
const showQRCode = ref(false)
const qrCodeUrl = ref('')
const verificationCode = ref('')
const backupCodes = ref<string[]>([])
const isLoading = ref(false)

const enableTOTP = async () => {
  isLoading.value = true
  try {
    const response = await enableMFA('totp')
    qrCodeUrl.value = response.qrCode
    backupCodes.value = response.backupCodes
    showQRCode.value = true
  } catch (error) {
    console.error('Failed to enable TOTP:', error)
  } finally {
    isLoading.value = false
  }
}

const enableSMS = async () => {
  isLoading.value = true
  try {
    await enableMFA('sms')
    mfaEnabled.value = true
  } catch (error) {
    console.error('Failed to enable SMS:', error)
  } finally {
    isLoading.value = false
  }
}

const confirmMFASetup = async () => {
  if (verificationCode.value.length !== 6) return

  isLoading.value = true
  try {
    await confirmMFA(verificationCode.value)
    mfaEnabled.value = true
    showQRCode.value = false
  } catch (error) {
    console.error('MFA verification failed:', error)
  } finally {
    isLoading.value = false
  }
}

const handleDisableMFA = async () => {
  const password = prompt('Enter your password to disable 2FA:')
  if (!password) return

  try {
    await disableMFA(password)
    mfaEnabled.value = false
  } catch (error) {
    console.error('Failed to disable MFA:', error)
  }
}
</script>
```

### Passkey Authentication

```vue
<template>
  <div class="passkey-auth">
    <h3>Passkey Authentication</h3>

    <div v-if="!hasPasskey">
      <p>Set up passwordless authentication with passkeys</p>
      <button @click="registerPasskey" :disabled="isLoading">
        {{ isLoading ? 'Setting up...' : 'Set Up Passkey' }}
      </button>
    </div>

    <div v-else>
      <p>Passkey is ready for authentication</p>
      <button @click="authenticateWithPasskey" :disabled="isLoading">
        {{ isLoading ? 'Authenticating...' : 'Sign in with Passkey' }}
      </button>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { usePasskeys } from '@janua/vue-sdk'

const { registerPasskey, authenticateWithPasskey, isSupported, isLoading: passkeysLoading, error: passkeysError } = usePasskeys()

const hasPasskey = ref(false)
const isLoading = ref(false)
const error = ref('')

const handleRegisterPasskey = async () => {
  if (!window.navigator.credentials) {
    error.value = 'Passkeys are not supported in this browser'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const options = await registerPasskey()

    // Create the credential using WebAuthn API
    const credential = await navigator.credentials.create({
      publicKey: options
    }) as PublicKeyCredential

    if (credential) {
      // Complete registration with Janua
      // await completePasskeyRegistration(credential)
      hasPasskey.value = true
    }
  } catch (err: any) {
    error.value = err.message || 'Failed to register passkey'
  } finally {
    isLoading.value = false
  }
}

const handleAuthenticateWithPasskey = async () => {
  isLoading.value = true
  error.value = ''

  try {
    const options = await authenticateWithPasskey()

    // Get the credential using WebAuthn API
    const credential = await navigator.credentials.get({
      publicKey: options
    }) as PublicKeyCredential

    if (credential) {
      // Complete authentication with Janua
      // await completePasskeyAuthentication(credential)
      // User is now authenticated
    }
  } catch (err: any) {
    error.value = err.message || 'Authentication failed'
  } finally {
    isLoading.value = false
  }
}
</script>
```

## Advanced Features

### Protected Routes with Router Guards

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useJanua } from '@janua/vue-sdk'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue')
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/Dashboard.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('../views/Admin.vue'),
      meta: {
        requiresAuth: true,
        requiresRole: 'admin'
      }
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  const janua = useJanua()
  const state = janua.getState()

  // Wait for auth state to initialize
  while (state.isLoading) {
    await new Promise(resolve => setTimeout(resolve, 100))
  }

  if (to.meta.requiresAuth && !state.isAuthenticated) {
    next('/login')
    return
  }

  if (to.meta.requiresRole) {
    const user = state.user
    if (!user || !user.roles?.includes(to.meta.requiresRole as string)) {
      next('/unauthorized')
      return
    }
  }

  next()
})

export default router
```

### Role-Based Access Control (RBAC)

```vue
<template>
  <div>
    <div v-if="hasPermission('users:read')">
      <UserList />
    </div>

    <div v-if="hasPermission('users:write')">
      <CreateUserForm />
    </div>

    <div v-if="hasRole('admin')">
      <AdminPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuth } from '@janua/vue-sdk'

const { user } = useAuth()

const hasRole = (role: string) => {
  return computed(() => user.value?.roles?.includes(role) ?? false)
}

const hasPermission = (permission: string) => {
  return computed(() => {
    if (!user.value?.permissions) return false
    return user.value.permissions.includes(permission)
  })
}

// You can also create a reusable composable
function usePermissions() {
  const { user } = useAuth()

  const hasRole = (role: string) => {
    return user.value?.roles?.includes(role) ?? false
  }

  const hasPermission = (permission: string) => {
    return user.value?.permissions?.includes(permission) ?? false
  }

  const hasAnyRole = (roles: string[]) => {
    return roles.some(role => hasRole(role))
  }

  const hasAnyPermission = (permissions: string[]) => {
    return permissions.some(permission => hasPermission(permission))
  }

  return {
    hasRole,
    hasPermission,
    hasAnyRole,
    hasAnyPermission,
    userRoles: computed(() => user.value?.roles ?? []),
    userPermissions: computed(() => user.value?.permissions ?? [])
  }
}
</script>
```

### Custom Auth State Management

```typescript
// composables/useCustomAuth.ts
import { ref, computed, watch } from 'vue'
import { useAuth } from '@janua/vue-sdk'
import { useRouter } from 'vue-router'
import { useToast } from './useToast'

export function useCustomAuth() {
  const router = useRouter()
  const toast = useToast()
  const auth = useAuth()

  const loginForm = ref({
    email: '',
    password: '',
    rememberMe: false
  })

  const registrationForm = ref({
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: '',
    acceptTerms: false
  })

  const isLoginLoading = ref(false)
  const isRegistrationLoading = ref(false)

  // Watch for auth changes and handle redirects
  watch(auth.isAuthenticated, (isAuthenticated) => {
    if (isAuthenticated) {
      const redirectPath = sessionStorage.getItem('redirectAfterLogin') || '/dashboard'
      sessionStorage.removeItem('redirectAfterLogin')
      router.push(redirectPath)
    }
  })

  const login = async () => {
    if (!loginForm.value.email || !loginForm.value.password) {
      toast.error('Please fill in all fields')
      return
    }

    isLoginLoading.value = true

    try {
      await auth.signIn(loginForm.value.email, loginForm.value.password)
      toast.success('Successfully signed in!')

      if (loginForm.value.rememberMe) {
        localStorage.setItem('rememberUser', loginForm.value.email)
      }
    } catch (error: any) {
      toast.error(error.message || 'Login failed')
      throw error
    } finally {
      isLoginLoading.value = false
    }
  }

  const register = async () => {
    if (registrationForm.value.password !== registrationForm.value.confirmPassword) {
      toast.error('Passwords do not match')
      return
    }

    if (!registrationForm.value.acceptTerms) {
      toast.error('Please accept the terms of service')
      return
    }

    isRegistrationLoading.value = true

    try {
      await auth.signUp({
        email: registrationForm.value.email,
        password: registrationForm.value.password,
        firstName: registrationForm.value.firstName,
        lastName: registrationForm.value.lastName
      })

      toast.success('Account created successfully!')
    } catch (error: any) {
      toast.error(error.message || 'Registration failed')
      throw error
    } finally {
      isRegistrationLoading.value = false
    }
  }

  const logout = async () => {
    try {
      await auth.signOut()
      toast.success('Signed out successfully')
      router.push('/login')
    } catch (error: any) {
      toast.error('Sign out failed')
    }
  }

  const isFormValid = computed(() => {
    return loginForm.value.email &&
           loginForm.value.password &&
           loginForm.value.email.includes('@')
  })

  const isRegistrationValid = computed(() => {
    return registrationForm.value.email &&
           registrationForm.value.password &&
           registrationForm.value.confirmPassword &&
           registrationForm.value.firstName &&
           registrationForm.value.acceptTerms &&
           registrationForm.value.password === registrationForm.value.confirmPassword
  })

  return {
    // Forms
    loginForm,
    registrationForm,

    // Loading states
    isLoginLoading,
    isRegistrationLoading,

    // Actions
    login,
    register,
    logout,

    // Computed
    isFormValid,
    isRegistrationValid,

    // Auth state from useAuth
    ...auth
  }
}
```

## Complete Examples

### Full Authentication Flow

```vue
<template>
  <div class="auth-container">
    <div v-if="isLoading" class="loading">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>

    <div v-else-if="!isAuthenticated" class="auth-forms">
      <div class="auth-tabs">
        <button
          :class="{ active: activeTab === 'login' }"
          @click="activeTab = 'login'"
        >
          Sign In
        </button>
        <button
          :class="{ active: activeTab === 'register' }"
          @click="activeTab = 'register'"
        >
          Sign Up
        </button>
      </div>

      <!-- Login Form -->
      <form v-if="activeTab === 'login'" @submit.prevent="handleLogin" class="auth-form">
        <h2>Welcome Back</h2>

        <div class="form-group">
          <label for="email">Email</label>
          <input
            id="email"
            v-model="loginForm.email"
            type="email"
            required
            :disabled="isLoginLoading"
          />
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="loginForm.password"
            type="password"
            required
            :disabled="isLoginLoading"
          />
        </div>

        <div class="form-options">
          <label class="checkbox">
            <input v-model="loginForm.rememberMe" type="checkbox" />
            Remember me
          </label>
          <a href="/forgot-password">Forgot password?</a>
        </div>

        <button
          type="submit"
          :disabled="!isFormValid || isLoginLoading"
          class="auth-button"
        >
          {{ isLoginLoading ? 'Signing in...' : 'Sign In' }}
        </button>

        <div class="divider">
          <span>or</span>
        </div>

        <div class="oauth-buttons">
          <button
            v-for="provider in oauthProviders"
            :key="provider.id"
            @click="handleOAuthLogin(provider.id)"
            type="button"
            :class="`oauth-button oauth-${provider.id}`"
          >
            <img :src="provider.icon" :alt="provider.name" />
            Continue with {{ provider.name }}
          </button>
        </div>

        <div class="magic-link">
          <button @click="showMagicLinkForm = true" type="button" class="link-button">
            Sign in with magic link
          </button>
        </div>
      </form>

      <!-- Registration Form -->
      <form v-else @submit.prevent="handleRegister" class="auth-form">
        <h2>Create Account</h2>

        <div class="form-row">
          <div class="form-group">
            <label for="firstName">First Name</label>
            <input
              id="firstName"
              v-model="registrationForm.firstName"
              required
              :disabled="isRegistrationLoading"
            />
          </div>
          <div class="form-group">
            <label for="lastName">Last Name</label>
            <input
              id="lastName"
              v-model="registrationForm.lastName"
              required
              :disabled="isRegistrationLoading"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="email">Email</label>
          <input
            id="email"
            v-model="registrationForm.email"
            type="email"
            required
            :disabled="isRegistrationLoading"
          />
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="registrationForm.password"
            type="password"
            required
            :disabled="isRegistrationLoading"
          />
          <div class="password-requirements">
            <small>At least 8 characters with letters and numbers</small>
          </div>
        </div>

        <div class="form-group">
          <label for="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            v-model="registrationForm.confirmPassword"
            type="password"
            required
            :disabled="isRegistrationLoading"
          />
        </div>

        <div class="form-group">
          <label class="checkbox">
            <input
              v-model="registrationForm.acceptTerms"
              type="checkbox"
              required
            />
            I agree to the <a href="/terms" target="_blank">Terms of Service</a>
          </label>
        </div>

        <button
          type="submit"
          :disabled="!isRegistrationValid || isRegistrationLoading"
          class="auth-button"
        >
          {{ isRegistrationLoading ? 'Creating account...' : 'Create Account' }}
        </button>
      </form>

      <!-- Magic Link Form -->
      <div v-if="showMagicLinkForm" class="magic-link-overlay">
        <div class="magic-link-modal">
          <button @click="showMagicLinkForm = false" class="close-button">&times;</button>
          <MagicLinkForm @success="showMagicLinkForm = false" />
        </div>
      </div>
    </div>

    <!-- Authenticated State -->
    <div v-else class="authenticated">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useCustomAuth } from '../composables/useCustomAuth'
import { useOAuth } from '@janua/vue-sdk'
import MagicLinkForm from '../components/MagicLinkForm.vue'

const {
  // State
  user,
  isAuthenticated,
  isLoading,

  // Forms
  loginForm,
  registrationForm,

  // Loading states
  isLoginLoading,
  isRegistrationLoading,

  // Actions
  login,
  register,

  // Validation
  isFormValid,
  isRegistrationValid
} = useCustomAuth()

const { getOAuthUrl } = useOAuth()

const activeTab = ref<'login' | 'register'>('login')
const showMagicLinkForm = ref(false)

const oauthProviders = ref([
  { id: 'google', name: 'Google', icon: '/icons/google.svg' },
  { id: 'github', name: 'GitHub', icon: '/icons/github.svg' }
])

const handleLogin = async () => {
  try {
    await login()
  } catch (error) {
    // Error handling is done in useCustomAuth
  }
}

const handleRegister = async () => {
  try {
    await register()
    activeTab.value = 'login'
  } catch (error) {
    // Error handling is done in useCustomAuth
  }
}

const handleOAuthLogin = async (provider: string) => {
  try {
    const authUrl = await getOAuthUrl(provider)
    window.location.href = authUrl
  } catch (error) {
    console.error(`OAuth login failed for ${provider}:`, error)
  }
}
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.loading {
  text-align: center;
  color: white;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top: 4px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.auth-forms {
  background: white;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  width: 100%;
  max-width: 400px;
}

.auth-tabs {
  display: flex;
  background: #f8f9fa;
}

.auth-tabs button {
  flex: 1;
  padding: 1rem;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.2s;
}

.auth-tabs button.active {
  background: white;
  border-bottom: 2px solid #667eea;
}

.auth-form {
  padding: 2rem;
}

.auth-form h2 {
  margin: 0 0 1.5rem;
  text-align: center;
  color: #333;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-group {
  margin-bottom: 1rem;
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #555;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
}

.form-group input:disabled {
  background: #f8f9fa;
  cursor: not-allowed;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}

.checkbox input {
  width: auto;
}

.auth-button {
  width: 100%;
  padding: 0.75rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.auth-button:hover:not(:disabled) {
  background: #5a67d8;
}

.auth-button:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

.divider {
  text-align: center;
  margin: 1.5rem 0;
  position: relative;
  color: #666;
}

.divider::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: #ddd;
}

.divider span {
  background: white;
  padding: 0 1rem;
}

.oauth-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.oauth-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: background-color 0.2s;
}

.oauth-button:hover {
  background: #f8f9fa;
}

.oauth-button img {
  width: 20px;
  height: 20px;
}

.magic-link {
  text-align: center;
  margin-top: 1rem;
}

.link-button {
  background: none;
  border: none;
  color: #667eea;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.9rem;
}

.password-requirements {
  margin-top: 0.25rem;
}

.password-requirements small {
  color: #666;
  font-size: 0.8rem;
}

.magic-link-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.magic-link-modal {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  width: 90%;
  max-width: 400px;
  position: relative;
}

.close-button {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #666;
}
</style>
```

## Testing Strategies

### Unit Testing with Vitest

```typescript
// tests/composables/useAuth.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createJanua } from '@janua/vue-sdk'

// Mock the TypeScript SDK
vi.mock('@janua/typescript-sdk', () => ({
  JanuaClient: vi.fn().mockImplementation(() => ({
    auth: {
      signIn: vi.fn(),
      signUp: vi.fn(),
      signOut: vi.fn(),
      getCurrentUser: vi.fn()
    },
    getCurrentUser: vi.fn(),
    getAccessToken: vi.fn(),
    getRefreshToken: vi.fn(),
    signOut: vi.fn()
  }))
}))

describe('useAuth', () => {
  let wrapper: any
  let mockClient: any

  beforeEach(() => {
    const app = createApp({
      template: '<div></div>'
    })

    app.use(createJanua({
      baseUrl: 'http://localhost:8000',
      clientId: 'test-client-id'
    }))

    wrapper = mount({
      template: '<div></div>',
      setup() {
        return useAuth()
      }
    }, {
      global: {
        plugins: [app]
      }
    })
  })

  it('should initialize with loading state', () => {
    expect(wrapper.vm.isLoading).toBe(true)
    expect(wrapper.vm.isAuthenticated).toBe(false)
    expect(wrapper.vm.user).toBe(null)
  })

  it('should sign in successfully', async () => {
    const mockUser = { id: '1', email: 'test@example.com' }
    mockClient.auth.signIn.mockResolvedValue({ user: mockUser })

    await wrapper.vm.signIn('test@example.com', 'password')

    expect(mockClient.auth.signIn).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password'
    })
  })

  it('should handle sign in errors', async () => {
    const error = new Error('Invalid credentials')
    mockClient.auth.signIn.mockRejectedValue(error)

    await expect(
      wrapper.vm.signIn('test@example.com', 'wrong-password')
    ).rejects.toThrow('Invalid credentials')
  })
})
```

### Integration Testing

```typescript
// tests/integration/auth-flow.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import AuthFlow from '../components/AuthFlow.vue'

describe('Authentication Flow Integration', () => {
  let router: any

  beforeEach(() => {
    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/login', component: { template: '<div>Login</div>' } },
        { path: '/dashboard', component: { template: '<div>Dashboard</div>' } }
      ]
    })
  })

  it('should complete full authentication flow', async () => {
    const wrapper = mount(AuthFlow, {
      global: {
        plugins: [router]
      }
    })

    // Fill in login form
    await wrapper.find('input[type="email"]').setValue('test@example.com')
    await wrapper.find('input[type="password"]').setValue('password123')

    // Submit form
    await wrapper.find('form').trigger('submit')

    // Wait for authentication
    await wrapper.vm.$nextTick()

    // Should redirect to dashboard
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('should handle OAuth callback', async () => {
    // Mock URL with OAuth parameters
    delete window.location
    window.location = { search: '?code=auth_code&state=auth_state' } as any

    const wrapper = mount(AuthFlow, {
      global: {
        plugins: [router]
      }
    })

    // Wait for OAuth callback handling
    await new Promise(resolve => setTimeout(resolve, 100))

    // Should be authenticated
    expect(wrapper.vm.isAuthenticated).toBe(true)
  })
})
```

### E2E Testing with Playwright

```typescript
// tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('should sign in with email and password', async ({ page }) => {
    await page.goto('/login')

    await page.fill('input[type="email"]', 'test@example.com')
    await page.fill('input[type="password"]', 'password123')
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL('/dashboard')
    await expect(page.locator('text=Welcome')).toBeVisible()
  })

  test('should handle magic link authentication', async ({ page }) => {
    await page.goto('/login')

    await page.click('text=Sign in with magic link')
    await page.fill('input[type="email"]', 'test@example.com')
    await page.click('text=Send Magic Link')

    await expect(page.locator('text=Check Your Email')).toBeVisible()
  })

  test('should complete OAuth flow', async ({ page, context }) => {
    await page.goto('/login')

    // Click OAuth button - this will open a new tab
    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      page.click('text=Continue with Google')
    ])

    // Handle OAuth provider login (mock or real)
    await newPage.waitForLoadState()
    // ... OAuth provider steps ...

    // Should redirect back to app
    await expect(page).toHaveURL('/dashboard')
  })
})
```

## TypeScript Support

### Type Definitions

```typescript
// types/janua.d.ts
import '@janua/vue-sdk'

declare module '@janua/vue-sdk' {
  interface User {
    id: string
    email: string
    firstName?: string
    lastName?: string
    roles: string[]
    permissions: string[]
    organizations: Organization[]
    createdAt: string
    updatedAt: string
  }

  interface Session {
    id: string
    accessToken: string
    refreshToken: string
    expiresAt: string
    createdAt: string
  }

  interface Organization {
    id: string
    name: string
    description: string
    slug: string
    memberRole: string
    permissions: string[]
  }

  interface JanuaState {
    user: User | null
    session: Session | null
    isLoading: boolean
    isAuthenticated: boolean
  }
}
```

### Typed Composables

```typescript
// composables/useTypedAuth.ts
import type { ComputedRef } from 'vue'
import type { User, Session } from '@janua/vue-sdk'
import { useAuth } from '@janua/vue-sdk'

interface TypedAuthReturn {
  user: ComputedRef<User | null>
  session: ComputedRef<Session | null>
  isAuthenticated: ComputedRef<boolean>
  isLoading: ComputedRef<boolean>
  signIn: (email: string, password: string) => Promise<void>
  signUp: (data: SignUpData) => Promise<void>
  signOut: () => Promise<void>
}

interface SignUpData {
  email: string
  password: string
  firstName?: string
  lastName?: string
}

export function useTypedAuth(): TypedAuthReturn {
  return useAuth()
}
```

## Troubleshooting

### Common Issues

#### 1. Plugin Not Installed Error

```typescript
// Error: Janua plugin not installed
// Solution: Ensure you call app.use(createJanua(...)) before mounting

// main.ts
import { createApp } from 'vue'
import { createJanua } from '@janua/vue-sdk'
import App from './App.vue'

const app = createApp(App)

// MUST be called before app.mount()
app.use(createJanua({
  baseUrl: 'https://api.janua.dev',
  clientId: 'your-client-id'
}))

app.mount('#app')
```

#### 2. Infinite Loading State

```typescript
// Issue: isLoading never becomes false
// Solution: Check network connectivity and API configuration

// Debug loading state
watchEffect(() => {
  console.log('Auth state:', {
    isLoading: isLoading.value,
    isAuthenticated: isAuthenticated.value,
    user: user.value
  })
})

// Check if API is reachable
fetch('https://api.janua.dev/health')
  .then(response => console.log('API Status:', response.status))
  .catch(error => console.error('API Error:', error))
```

#### 3. OAuth Callback Issues

```typescript
// Issue: OAuth callback not handled properly
// Solution: Ensure proper routing and URL configuration

// router/index.ts
{
  path: '/auth/callback',
  name: 'AuthCallback',
  component: () => import('../views/AuthCallback.vue')
}

// AuthCallback.vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useOAuth } from '@janua/vue-sdk'
import { useRouter } from 'vue-router'

const { handleOAuthCallback } = useOAuth()
const router = useRouter()

onMounted(async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')
  const state = urlParams.get('state')

  if (code && state) {
    try {
      await handleOAuthCallback(code, state)
      router.push('/dashboard')
    } catch (error) {
      console.error('OAuth callback failed:', error)
      router.push('/login?error=oauth_failed')
    }
  } else {
    router.push('/login?error=invalid_callback')
  }
})
</script>
```

#### 4. Session Persistence Issues

```typescript
// Issue: User gets signed out on page refresh
// Solution: Ensure proper session handling

// Check for stored tokens on app initialization
const initializeAuth = async () => {
  const accessToken = localStorage.getItem('janua_access_token')
  const refreshToken = localStorage.getItem('janua_refresh_token')

  if (accessToken && refreshToken) {
    try {
      // Validate token and refresh if needed
      await updateSession()
    } catch (error) {
      // Clear invalid tokens
      localStorage.removeItem('janua_access_token')
      localStorage.removeItem('janua_refresh_token')
    }
  }
}
```

#### 5. CORS Issues in Development

```typescript
// Issue: CORS errors in development
// Solution: Configure proxy in Vite config

// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'https://api.janua.dev',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})

// Update Janua config for development
const januaConfig = {
  baseUrl: import.meta.env.DEV ? '/api' : 'https://api.janua.dev',
  clientId: import.meta.env.VITE_JANUA_CLIENT_ID
}
```

### Debug Mode

```typescript
// Enable debug logging
const januaConfig = {
  baseUrl: 'https://api.janua.dev',
  clientId: 'your-client-id',
  debug: true, // Enable debug mode
  onAuthChange: (user) => {
    console.log('Auth change:', user)
  }
}
```

### Performance Optimization

```typescript
// Lazy load authentication components
const LazyLoginForm = defineAsyncComponent(() => import('./LoginForm.vue'))
const LazySignUpForm = defineAsyncComponent(() => import('./SignUpForm.vue'))

// Preload critical auth data
const preloadAuthData = async () => {
  if (isAuthenticated.value) {
    // Preload user organizations
    const orgs = useOrganizations()
    await orgs.getUserOrganizations()
  }
}
```

---

## Summary

The **@janua/vue** SDK provides a comprehensive authentication solution for Vue 3 applications with:

- **Plugin System**: Easy installation and configuration
- **Reactive Composables**: Full suite of authentication composables
- **TypeScript Support**: Complete type definitions and IntelliSense
- **Advanced Features**: MFA, Passkeys, OAuth, Magic Links
- **Security**: Built-in CSRF protection and secure token handling
- **Developer Experience**: Excellent debugging and error handling

This guide covers all aspects from basic setup to advanced enterprise features, providing you with everything needed to implement robust authentication in your Vue applications.

For additional support and advanced use cases, refer to the [Janua documentation](https://docs.janua.dev) or contact our support team.