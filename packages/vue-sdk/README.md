# @janua/vue-sdk

Official Janua SDK for Vue 3 applications. Provides composables, pre-built components, and a Nuxt 3 module for integrating Janua authentication into Vue projects.

## Requirements

- Vue 3.0.0 or higher
- Node.js 18.0.0 or higher

---

## Installation

### Registry configuration

The SDK is published to the MADFAM npm registry. Add the following to your `.npmrc` before installing:

```
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

### Install the package

```bash
npm install @janua/vue-sdk
# or
pnpm add @janua/vue-sdk
# or
yarn add @janua/vue-sdk
```

---

## Quick Start

### 1. Configure environment variables

```env
VITE_JANUA_PUBLISHABLE_KEY=pk_live_...
VITE_JANUA_API_URL=https://api.janua.dev
```

### 2. Install the plugin

```typescript
// main.ts
import { createApp } from 'vue';
import { createJanua } from '@janua/vue-sdk';
import App from './App.vue';

const app = createApp(App);

app.use(
  createJanua({
    publishableKey: import.meta.env.VITE_JANUA_PUBLISHABLE_KEY,
    apiUrl: import.meta.env.VITE_JANUA_API_URL,
  })
);

app.mount('#app');
```

### 3. Use composables in components

```vue
<script setup lang="ts">
import { useAuth } from '@janua/vue-sdk';

const { isAuthenticated, isLoading, user, signOut } = useAuth();
</script>

<template>
  <div v-if="isLoading">Loading...</div>

  <div v-else-if="isAuthenticated">
    <p>Signed in as {{ user?.email }}</p>
    <button @click="signOut">Sign out</button>
  </div>

  <div v-else>
    <p>Not signed in.</p>
  </div>
</template>
```

---

## Plugin configuration

`createJanua` accepts all options from `JanuaConfig` (the core TypeScript SDK) plus two additional options:

```typescript
interface JanuaPluginOptions extends JanuaConfig {
  /**
   * Called whenever the authenticated user changes.
   * Receives the current User object, or null after sign-out.
   */
  onAuthChange?: (user: User | null) => void;

  /**
   * How often (in milliseconds) the plugin polls the API to keep
   * auth state current. Defaults to 60000 (60 seconds).
   */
  pollInterval?: number;
}
```

Example with all plugin-level options:

```typescript
app.use(
  createJanua({
    publishableKey: 'pk_live_...',
    apiUrl: 'https://api.janua.dev',
    onAuthChange: (user) => {
      console.log('Auth changed:', user?.email ?? 'signed out');
    },
    pollInterval: 120_000, // check every 2 minutes
  })
);
```

---

## Composables

All composables must be called inside a component or composable that runs after the Janua plugin is installed. They throw an error if called before `app.use(createJanua(...))`.

### `useJanua`

Returns the raw `JanuaVue` instance. Use this when you need direct access to the underlying client or reactive state object.

```typescript
import { useJanua } from '@janua/vue-sdk';

const janua = useJanua();

// Access the underlying TypeScript SDK client
const client = janua.getClient();

// Access the reactive state (read-only)
const state = janua.getState();
// state.user, state.session, state.isLoading, state.isAuthenticated, state.error
```

---

### `useAuth`

The primary composable for authentication state and actions.

```typescript
const {
  auth,             // The raw auth client from @janua/typescript-sdk
  user,             // ComputedRef<User | null>
  session,          // ComputedRef<Session | null>
  isAuthenticated,  // ComputedRef<boolean>
  isLoading,        // ComputedRef<boolean>
  error,            // ComputedRef<Error | null>
  signIn,           // (email: string, password: string) => Promise<...>
  signUp,           // (data: { email, password, firstName?, lastName? }) => Promise<...>
  signOut,          // () => Promise<void>
  updateSession,    // () => Promise<void>  — re-fetches current user from API
} = useAuth();
```

Example:

```vue
<script setup lang="ts">
import { useAuth } from '@janua/vue-sdk';

const { isAuthenticated, user, signOut } = useAuth();
</script>

<template>
  <header>
    <span v-if="isAuthenticated">{{ user?.email }}</span>
    <button v-if="isAuthenticated" @click="signOut">Sign out</button>
  </header>
</template>
```

---

### `useUser`

Access and update the current user's profile.

```typescript
const {
  user,       // ComputedRef<User | null>
  isLoading,  // ComputedRef<boolean>
  updateUser, // (data: Partial<User>) => Promise<User>
} = useUser();
```

Example:

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useUser } from '@janua/vue-sdk';

const { user, updateUser } = useUser();
const displayName = ref('');

async function saveProfile() {
  await updateUser({ firstName: displayName.value });
}
</script>
```

---

### `useSession`

Access the current session and manage session lifecycle.

```typescript
const {
  session,        // ComputedRef<Session | null>
  refreshSession, // () => Promise<void>  — re-fetches auth state from the API
  revokeSession,  // (sessionId: string) => Promise<void>
} = useSession();
```

Revoking the active session signs the user out automatically.

---

### `useOrganizations`

Returns the organizations client from `@janua/typescript-sdk` directly. Use it to list organizations, switch the active organization, and manage membership.

```typescript
import { useOrganizations } from '@janua/vue-sdk';

const organizations = useOrganizations();
// organizations exposes the full client.organizations API
```

---

### `useSignIn`

A focused composable for building custom sign-in forms with local loading and error state.

```typescript
const {
  signIn,    // (email: string, password: string) => Promise<...>
  isLoading, // ComputedRef<boolean>
  error,     // ComputedRef<Error | null>
} = useSignIn();
```

Example:

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useSignIn } from '@janua/vue-sdk';
import { useRouter } from 'vue-router';

const router = useRouter();
const email = ref('');
const password = ref('');
const { signIn, isLoading, error } = useSignIn();

async function handleSubmit() {
  await signIn(email.value, password.value);
  router.push('/dashboard');
}
</script>

<template>
  <form @submit.prevent="handleSubmit">
    <input v-model="email" type="email" required />
    <input v-model="password" type="password" required />
    <p v-if="error" role="alert">{{ error.message }}</p>
    <button type="submit" :disabled="isLoading">
      {{ isLoading ? 'Signing in...' : 'Sign in' }}
    </button>
  </form>
</template>
```

---

### `useSignUp`

A focused composable for building custom registration forms.

```typescript
const {
  signUp,    // (data: { email, password, firstName?, lastName? }) => Promise<...>
  isLoading, // ComputedRef<boolean>
  error,     // ComputedRef<Error | null>
} = useSignUp();
```

---

### `useSignOut`

A minimal composable that exposes only the `signOut` function.

```typescript
const { signOut } = useSignOut();
// signOut: () => Promise<void>
```

---

### `useMagicLink`

Send and verify magic link emails.

```typescript
const {
  sendMagicLink,       // (email: string, redirectUrl?: string) => Promise<void>
  signInWithMagicLink, // (token: string) => Promise<...>
  isLoading,           // ComputedRef<boolean>
  error,               // ComputedRef<Error | null>
} = useMagicLink();
```

Example — request a link:

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useMagicLink } from '@janua/vue-sdk';

const email = ref('');
const sent = ref(false);
const { sendMagicLink, isLoading, error } = useMagicLink();

async function requestLink() {
  await sendMagicLink(email.value, 'https://myapp.com/auth/callback');
  sent.value = true;
}
</script>

<template>
  <div v-if="sent">Check your email for a sign-in link.</div>
  <form v-else @submit.prevent="requestLink">
    <input v-model="email" type="email" required />
    <button type="submit" :disabled="isLoading">Send link</button>
    <p v-if="error" role="alert">{{ error.message }}</p>
  </form>
</template>
```

Example — verify the token on the callback page:

```vue
<script setup lang="ts">
import { onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMagicLink } from '@janua/vue-sdk';

const route = useRoute();
const router = useRouter();
const { signInWithMagicLink } = useMagicLink();

onMounted(async () => {
  const token = route.query.token as string;
  if (token) {
    await signInWithMagicLink(token);
    router.push('/dashboard');
  }
});
</script>
```

---

### `useOAuth`

Initiate OAuth flows with PKCE. The plugin automatically handles the callback on page load — no manual callback handling is needed in most cases.

```typescript
const {
  signInWithOAuth,    // (provider: OAuthProvider, redirectUrl?: string) => Promise<void>
  handleOAuthCallback,// (code: string, state: string) => Promise<void>
  isLoading,          // ComputedRef<boolean>
  error,              // ComputedRef<Error | null>
} = useOAuth(options?: { clientId?: string; redirectUri?: string });
```

`OAuthProvider` values: `'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter'`

`signInWithOAuth` generates a PKCE code verifier, builds the authorization URL, stores PKCE parameters in session storage, and redirects the browser. The callback code and state are validated automatically when the plugin initializes on the redirect page.

Example:

```vue
<script setup lang="ts">
import { useOAuth } from '@janua/vue-sdk';

const { signInWithOAuth, isLoading } = useOAuth();
</script>

<template>
  <button :disabled="isLoading" @click="signInWithOAuth('google')">
    Continue with Google
  </button>
  <button :disabled="isLoading" @click="signInWithOAuth('github')">
    Continue with GitHub
  </button>
</template>
```

If you need to handle the callback manually (for example, in a dedicated `/auth/callback` route):

```typescript
const { handleOAuthCallback } = useOAuth();

const code = route.query.code as string;
const state = route.query.state as string;

await handleOAuthCallback(code, state);
router.push('/dashboard');
```

---

### `usePasskeys`

Register and authenticate with WebAuthn passkeys (FIDO2).

```typescript
const {
  registerPasskey,        // (name?: string) => Promise<void>
  authenticateWithPasskey,// (email?: string) => Promise<void>
  isSupported,            // ComputedRef<boolean>  — false on non-WebAuthn browsers
  isLoading,              // ComputedRef<boolean>
  error,                  // ComputedRef<Error | null>
} = usePasskeys();
```

Example:

```vue
<script setup lang="ts">
import { usePasskeys } from '@janua/vue-sdk';

const { registerPasskey, authenticateWithPasskey, isSupported, isLoading } = usePasskeys();
</script>

<template>
  <div v-if="isSupported">
    <button :disabled="isLoading" @click="authenticateWithPasskey()">
      Sign in with passkey
    </button>
    <button :disabled="isLoading" @click="registerPasskey('My laptop')">
      Register a new passkey
    </button>
  </div>
  <p v-else>Passkeys are not supported in this browser.</p>
</template>
```

---

### `useMFA`

Enable, confirm, disable, and verify multi-factor authentication.

```typescript
const {
  enableMFA,  // (type: 'totp' | 'sms') => Promise<{ secret, qrCode, ... }>
  confirmMFA, // (code: string) => Promise<void>  — confirms enrollment
  disableMFA, // (password: string) => Promise<void>
  verifyMFA,  // (code: string) => Promise<tokens>  — verifies during sign-in
  isLoading,  // ComputedRef<boolean>
  error,      // ComputedRef<Error | null>
} = useMFA();
```

Example — TOTP enrollment flow:

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useMFA } from '@janua/vue-sdk';

const { enableMFA, confirmMFA, isLoading, error } = useMFA();
const qrCode = ref('');
const code = ref('');

async function startEnrollment() {
  const result = await enableMFA('totp');
  qrCode.value = result.qrCode;
}

async function confirm() {
  await confirmMFA(code.value);
}
</script>
```

---

### `useRealtime`

Subscribe to real-time auth events over WebSocket. The connection is closed automatically when the component unmounts.

```typescript
import { useRealtime } from '@janua/vue-sdk';

const {
  status,      // Ref<'connected' | 'disconnected' | 'reconnecting' | 'error'>
  subscribe,   // (channel: string) => void
  unsubscribe, // (channel: string) => void
  on,          // <K>(event: K, handler: (data: ...) => void) => void
  off,         // <K>(event: K, handler: (data: ...) => void) => void
  send,        // (message: WebSocketMessage) => void
  connect,     // () => Promise<void>
  disconnect,  // () => void
} = useRealtime(options?: UseRealtimeOptions);
```

`UseRealtimeOptions`:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `channels` | `string[]` | `[]` | Channels to subscribe to immediately after connecting |
| `url` | `string` | derived from `apiUrl` | Override the WebSocket server URL |
| `reconnect` | `boolean` | `true` | Automatically reconnect on disconnect |
| `autoConnect` | `boolean` | `true` | Connect when the composable is set up |

Example:

```vue
<script setup lang="ts">
import { useRealtime } from '@janua/vue-sdk';

const { status, on } = useRealtime({ channels: ['user-events'] });

on('user.updated', (data) => {
  console.log('User profile updated:', data);
});
</script>

<template>
  <span>WebSocket: {{ status }}</span>
</template>
```

---

## Pre-built components

Import components individually or together with composables:

```typescript
import {
  JanuaSignIn,
  JanuaSignUp,
  JanuaUserButton,
  JanuaMFAChallenge,
  JanuaProtect,
  JanuaSignedIn,
  JanuaSignedOut,
} from '@janua/vue-sdk';
```

---

### `JanuaSignIn`

A complete sign-in form with email/password, optional social login, and optional passkey authentication.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | `() => void` | — | Called after successful sign-in |
| `onError` | `(error: Error) => void` | — | Called when sign-in fails |
| `redirectUrl` | `string` | — | URL to redirect to after sign-in |
| `enablePasskeys` | `boolean` | `true` | Show passkey button when WebAuthn is available |
| `enableSocialLogin` | `boolean` | `true` | Show OAuth provider buttons |
| `socialProviders` | `('google' \| 'github' \| 'microsoft' \| 'apple')[]` | `['google', 'github']` | Which OAuth providers to show |
| `signUpUrl` | `string` | `'/sign-up'` | URL for the "Sign up" link |
| `className` | `string` | — | Additional CSS class on the root element |

```vue
<template>
  <JanuaSignIn
    redirect-url="/dashboard"
    :social-providers="['google', 'github', 'microsoft']"
    sign-up-url="/register"
    @success="onSuccess"
  />
</template>
```

---

### `JanuaSignUp`

A complete registration form with email, password, first name, last name, and optional social login.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | `() => void` | — | Called after successful registration |
| `onError` | `(error: Error) => void` | — | Called when registration fails |
| `redirectUrl` | `string` | — | URL to redirect to after registration |
| `enableSocialLogin` | `boolean` | `true` | Show OAuth provider buttons |
| `socialProviders` | `('google' \| 'github' \| 'microsoft' \| 'apple')[]` | `['google', 'github']` | Which OAuth providers to show |
| `signInUrl` | `string` | `'/sign-in'` | URL for the "Sign in" link |
| `className` | `string` | — | Additional CSS class on the root element |

```vue
<template>
  <JanuaSignUp
    redirect-url="/onboarding"
    sign-in-url="/login"
  />
</template>
```

---

### `JanuaUserButton`

An avatar button that opens a dropdown showing the user's name and email, with a sign-out action.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `showEmail` | `boolean` | `true` | Show email in the dropdown |
| `showName` | `boolean` | `true` | Show display name in the dropdown |
| `afterSignOut` | `() => void` | — | Called after the user signs out |
| `className` | `string` | — | Additional CSS class on the root element |

The component renders nothing when the user is not authenticated.

```vue
<template>
  <nav>
    <JanuaUserButton :after-sign-out="() => router.push('/sign-in')" />
  </nav>
</template>
```

---

### `JanuaMFAChallenge`

A 6-digit OTP input for completing an MFA challenge. Handles paste, keyboard navigation, and auto-submit when all digits are entered.

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | `() => void` | — | Called after the code is verified |
| `onError` | `(error: Error) => void` | — | Called when verification fails |
| `className` | `string` | — | Additional CSS class on the root element |

```vue
<template>
  <JanuaMFAChallenge
    @success="router.push('/dashboard')"
    @error="showToast"
  />
</template>
```

---

### `JanuaProtect`

A guard component that shows its default slot only when the user is authenticated. Supports redirect and custom fallback content.

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `redirectTo` | `string` | URL to redirect to when unauthenticated. Takes priority over the fallback slot. |
| `fallback` | `string` | Text to display when unauthenticated and no `redirectTo` is set. |

**Slots:**

| Slot | Description |
|------|-------------|
| `default` | Rendered when the user is authenticated |
| `loading` | Rendered while auth state is loading. Defaults to a "Loading..." message. |
| `fallback` | Rendered when unauthenticated and `redirectTo` is not set |

```vue
<template>
  <!-- Redirect unauthenticated users -->
  <JanuaProtect redirect-to="/sign-in">
    <DashboardContent />
  </JanuaProtect>

  <!-- Show fallback slot instead of redirecting -->
  <JanuaProtect>
    <template #fallback>
      <p>You must be signed in to view this content.</p>
    </template>
    <ProtectedContent />
  </JanuaProtect>
</template>
```

---

### `JanuaSignedIn`

Renders its default slot only when the user is authenticated and loading is complete.

```vue
<template>
  <JanuaSignedIn>
    <p>Welcome back!</p>
  </JanuaSignedIn>
</template>
```

---

### `JanuaSignedOut`

Renders its default slot only when the user is not authenticated and loading is complete.

```vue
<template>
  <JanuaSignedOut>
    <a href="/sign-in">Sign in</a>
  </JanuaSignedOut>
</template>
```

---

## Nuxt 3 module

The package includes a Nuxt 3 module that registers the Janua plugin and auto-imports all composables.

### Setup

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@janua/vue-sdk/nuxt'],
  janua: {
    publishableKey: process.env.JANUA_PUBLISHABLE_KEY,
    apiUrl: process.env.JANUA_API_URL,
  },
});
```

### Auto-imported composables

When the module is active, the following composables are available in every component and composable without explicit imports:

- `useJanua`
- `useAuth`
- `useUser`
- `useSession`
- `useOrganizations`
- `useSignIn`
- `useSignUp`
- `useSignOut`
- `useMagicLink`
- `useOAuth`
- `usePasskeys`
- `useMFA`

```vue
<!-- No import needed in Nuxt -->
<script setup lang="ts">
const { isAuthenticated, user } = useAuth();
</script>
```

---

## PKCE utilities

These utilities are re-exported from `@janua/typescript-sdk` for use in custom OAuth flows. The `useOAuth` composable uses them internally.

```typescript
import {
  generateCodeVerifier,   // () => string
  generateCodeChallenge,  // (verifier: string) => Promise<string>
  generateState,          // () => string
  storePKCEParams,        // (verifier: string, state: string) => void
  retrievePKCEParams,     // () => { verifier: string; state: string } | null
  clearPKCEParams,        // () => void
  validateState,          // (state: string) => boolean
  buildAuthorizationUrl,  // (baseURL, provider, clientId, redirectUri, challenge, state) => string
} from '@janua/vue-sdk';
```

Example — manual PKCE flow:

```typescript
const verifier = generateCodeVerifier();
const challenge = await generateCodeChallenge(verifier);
const state = generateState();

storePKCEParams(verifier, state);

const url = buildAuthorizationUrl(
  'https://api.janua.dev',
  'google',
  'my-client-id',
  'https://myapp.com/auth/callback',
  challenge,
  state
);

window.location.href = url;

// On the callback page:
const params = retrievePKCEParams();
if (params && validateState(callbackState)) {
  // Exchange code using the stored verifier
  clearPKCEParams();
}
```

---

## TypeScript types

Core types are re-exported from `@janua/typescript-sdk`:

```typescript
import type {
  User,
  Session,
  JanuaConfig,
  JanuaState,
  JanuaPluginOptions,
  JanuaVue,
  OAuthProvider,
  UseRealtimeOptions,
  UseRealtimeReturn,
} from '@janua/vue-sdk';
```

---

## Theming

All pre-built components consume CSS custom properties. Override them in your global stylesheet to match your design system.

```css
:root {
  --janua-primary: #2563eb;  /* Buttons, focus rings, links */
  --janua-text: #1a1a1a;     /* Labels, body text */
  --janua-bg: #ffffff;       /* Input and dropdown backgrounds */
  --janua-border: #d1d5db;   /* Input borders, dividers */
  --janua-radius: 6px;       /* Border radius on inputs and buttons */
  --janua-error: #dc2626;    /* Error message text and backgrounds */
}
```

Dark mode example:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --janua-primary: #3b82f6;
    --janua-text: #f9fafb;
    --janua-bg: #1f2937;
    --janua-border: #374151;
    --janua-error: #f87171;
  }
}
```

You can also scope variables to a specific component using the `className` prop and a scoped selector:

```css
.my-auth-panel {
  --janua-primary: #7c3aed;
  --janua-radius: 8px;
}
```

```vue
<template>
  <JanuaSignIn class-name="my-auth-panel" />
</template>
```

---

## Route protection with Vue Router

Use `JanuaProtect` for template-level guards, or add a navigation guard to your router for programmatic protection:

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/Home.vue') },
    {
      path: '/dashboard',
      component: () => import('./views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true;

  // useJanua() cannot be called outside a component setup context.
  // Access the plugin instance via the app's global properties instead.
  const janua = (router as any).app?.config?.globalProperties?.$janua;
  if (!janua?.isAuthenticated()) {
    return '/sign-in';
  }

  return true;
});

export default router;
```

For simpler cases, wrap protected views with `JanuaProtect`:

```vue
<!-- views/Dashboard.vue -->
<template>
  <JanuaProtect redirect-to="/sign-in">
    <DashboardLayout />
  </JanuaProtect>
</template>
```

---

## Related documentation

- [TypeScript SDK](/packages/typescript-sdk/README.md) — Core client used by this SDK
- [SDK selection guide](/docs/sdks/CHOOSE_YOUR_SDK.md) — Compare all Janua SDKs
- [API reference](/apps/api/docs/api/endpoints-reference.md) — Complete REST API documentation
- [Error handling guide](/docs/guides/ERROR_HANDLING_GUIDE.md) — Error codes and handling patterns

---

## License

AGPL-3.0. See [LICENSE](./LICENSE) for details.
