# @janua/vue

Official Janua SDK for Vue 3 applications with Composition API support.

## Installation

```bash
npm install @janua/vue
# or
yarn add @janua/vue
# or
pnpm add @janua/vue
```

## Features

- ⚡ **Vue 3 Composition API** - Built for modern Vue development
- 🔐 **Authentication Composables** - Reactive authentication state
- 🔄 **Auto Token Refresh** - Automatic session management
- 📱 **Multi-Factor Auth** - TOTP, SMS, and Passkey support
- 🏢 **Organizations** - Built-in multi-tenant organization support
- 🛡️ **Route Guards** - Vue Router integration for protected routes
- 📦 **TypeScript Support** - Full type safety with TypeScript
- 🎨 **Framework Agnostic** - Works with any Vue 3 setup

## Quick Start

### 1. Environment Configuration

Add your Janua credentials to your environment:

```env
VITE_JANUA_PUBLISHABLE_KEY=pk_live_...
VITE_JANUA_API_URL=https://api.janua.dev
```

### 2. Install the Plugin

```typescript
// main.ts
import { createApp } from 'vue';
import { createJanua } from '@janua/vue';
import App from './App.vue';

const janua = createJanua({
  publishableKey: import.meta.env.VITE_JANUA_PUBLISHABLE_KEY,
  apiUrl: import.meta.env.VITE_JANUA_API_URL,
});

const app = createApp(App);
app.use(janua);
app.mount('#app');
```

### 3. Use in Components

```vue
<template>
  <div>
    <div v-if="isLoading">Loading...</div>

    <div v-else-if="isSignedIn">
      <h1>Welcome back, {{ user?.email }}!</h1>
      <button @click="signOut">Sign Out</button>
    </div>

    <div v-else>
      <h1>Please sign in</h1>
      <SignInForm @success="handleSignIn" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuth, useUser } from '@janua/vue';
import SignInForm from './components/SignInForm.vue';

const { isSignedIn, isLoading, signOut } = useAuth();
const { user } = useUser();

const handleSignIn = (user: any) => {
  console.log('User signed in:', user);
};
</script>
```

## Authentication

### Sign In

```vue
<template>
  <form @submit.prevent="handleSignIn">
    <input v-model="email" type="email" placeholder="Email" required />
    <input v-model="password" type="password" placeholder="Password" required />
    <button type="submit" :disabled="isLoading">
      {{ isLoading ? 'Signing in...' : 'Sign In' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useSignIn } from '@janua/vue';

const email = ref('');
const password = ref('');

const { signIn, isLoading } = useSignIn({
  onSuccess: (user) => {
    console.log('Signed in successfully:', user);
    // Redirect or update UI
  },
  onError: (error) => {
    console.error('Sign in failed:', error);
  }
});

const handleSignIn = async () => {
  await signIn({
    email: email.value,
    password: password.value
  });
};
</script>
```

### Sign Up

```vue
<template>
  <form @submit.prevent="handleSignUp">
    <input v-model="email" type="email" placeholder="Email" required />
    <input v-model="password" type="password" placeholder="Password" required />
    <input v-model="name" type="text" placeholder="Full Name" required />
    <button type="submit" :disabled="isLoading">
      {{ isLoading ? 'Creating account...' : 'Sign Up' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useSignUp } from '@janua/vue';

const email = ref('');
const password = ref('');
const name = ref('');

const { signUp, isLoading } = useSignUp({
  onSuccess: (user) => {
    console.log('Account created:', user);
  },
  onError: (error) => {
    console.error('Sign up failed:', error);
  }
});

const handleSignUp = async () => {
  await signUp({
    email: email.value,
    password: password.value,
    name: name.value
  });
};
</script>
```

## Organizations

```vue
<template>
  <div>
    <h2>Organizations</h2>
    <div v-if="isLoading">Loading organizations...</div>

    <div v-else>
      <div v-for="org in organizations" :key="org.id" class="org-card">
        <h3>{{ org.name }}</h3>
        <p>{{ org.role }}</p>
        <button
          @click="setActiveOrganization(org.id)"
          :class="{ active: activeOrganization?.id === org.id }"
        >
          {{ activeOrganization?.id === org.id ? 'Active' : 'Switch' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useOrganizations } from '@janua/vue';

const {
  organizations,
  activeOrganization,
  setActiveOrganization,
  isLoading
} = useOrganizations();
</script>

<style scoped>
.org-card {
  border: 1px solid #ccc;
  padding: 1rem;
  margin: 0.5rem 0;
  border-radius: 4px;
}

.active {
  background-color: #007bff;
  color: white;
}
</style>
```

## Route Protection

### Using Vue Router Guards

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router';
import { useJanua } from '@janua/vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('../views/Home.vue')
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
      meta: { requiresAuth: true, role: 'admin' }
    }
  ]
});

router.beforeEach(async (to, from, next) => {
  const janua = useJanua();

  if (to.meta.requiresAuth) {
    const session = await janua.auth.getSession();

    if (!session) {
      next('/sign-in');
      return;
    }

    if (to.meta.role && !session.user.roles.includes(to.meta.role)) {
      next('/unauthorized');
      return;
    }
  }

  next();
});

export default router;
```

## API Reference

### Composables

#### `useAuth()`
Get authentication state and methods.

```typescript
const {
  isSignedIn,     // ref<boolean>
  isLoading,      // ref<boolean>
  signOut         // function
} = useAuth();
```

#### `useUser()`
Get current user data.

```typescript
const {
  user,           // ref<User | null>
  isLoading,      // ref<boolean>
  updateProfile   // function
} = useUser();
```

#### `useSession()`
Get current session information.

```typescript
const {
  session,        // ref<Session | null>
  isLoading,      // ref<boolean>
  refresh         // function
} = useSession();
```

#### `useSignIn()`
Handle user sign-in.

```typescript
const {
  signIn,         // function
  isLoading,      // ref<boolean>
  error           // ref<Error | null>
} = useSignIn({
  onSuccess: (user) => {},
  onError: (error) => {}
});
```

#### `useSignUp()`
Handle user registration.

```typescript
const {
  signUp,         // function
  isLoading,      // ref<boolean>
  error           // ref<Error | null>
} = useSignUp({
  onSuccess: (user) => {},
  onError: (error) => {}
});
```

#### `useSignOut()`
Handle user sign-out.

```typescript
const {
  signOut,        // function
  isLoading       // ref<boolean>
} = useSignOut({
  onSuccess: () => {},
  onError: (error) => {}
});
```

#### `useOrganizations()`
Manage organizations.

```typescript
const {
  organizations,        // ref<Organization[]>
  activeOrganization,   // ref<Organization | null>
  setActiveOrganization,// function
  isLoading             // ref<boolean>
} = useOrganizations();
```

#### `useMagicLink()`
Handle magic link authentication.

```typescript
const {
  sendMagicLink,  // function
  isLoading,      // ref<boolean>
  error           // ref<Error | null>
} = useMagicLink();
```

#### `useOAuth()`
Handle OAuth authentication.

```typescript
const {
  signInWithOAuth,  // function
  isLoading,        // ref<boolean>
  error             // ref<Error | null>
} = useOAuth();
```

#### `usePasskeys()`
Handle passkey authentication.

```typescript
const {
  createPasskey,    // function
  signInWithPasskey,// function
  isLoading,        // ref<boolean>
  error             // ref<Error | null>
} = usePasskeys();
```

#### `useMFA()`
Handle multi-factor authentication.

```typescript
const {
  enableMFA,      // function
  disableMFA,     // function
  verifyMFA,      // function
  isLoading,      // ref<boolean>
  error           // ref<Error | null>
} = useMFA();
```

### Plugin Configuration

```typescript
interface JanuaPluginOptions {
  publishableKey: string;
  apiUrl?: string;
  sessionCookieName?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const janua = createJanua({
  publishableKey: 'pk_live_...',
  apiUrl: 'https://api.janua.dev',
  sessionCookieName: 'janua-session',
  autoRefresh: true,
  refreshInterval: 300000 // 5 minutes
});
```

### TypeScript Support

All composables and functions are fully typed:

```typescript
import type { User, Organization, Session } from '@janua/vue';

const user: User = {
  id: 'user_123',
  email: 'user@example.com',
  name: 'John Doe',
  // ... other properties
};
```

## Requirements

- Vue 3.0.0 or higher
- Node.js 14.0.0 or higher

## License

AGPL-3.0 License - see [LICENSE](./LICENSE) file for details.

## Support

- 📖 [Documentation](https://docs.janua.dev)
- 💬 [Discord Community](https://discord.gg/janua)
- 🐛 [Report Issues](https://github.com/madfam-io/janua/issues)
- 📧 [Email Support](mailto:support@janua.dev)