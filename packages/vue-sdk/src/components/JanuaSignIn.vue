<script setup lang="ts">
import { ref } from 'vue';
import { useSignIn } from '../composables';
import { usePasskeys } from '../composables';
import { useOAuth, type OAuthProvider } from '../composables';

type SocialProvider = 'google' | 'github' | 'microsoft' | 'apple';

const props = withDefaults(
  defineProps<{
    onSuccess?: () => void;
    onError?: (error: Error) => void;
    redirectUrl?: string;
    enablePasskeys?: boolean;
    enableSocialLogin?: boolean;
    socialProviders?: SocialProvider[];
    signUpUrl?: string;
    className?: string;
  }>(),
  {
    enablePasskeys: true,
    enableSocialLogin: true,
    socialProviders: () => ['google', 'github'],
    signUpUrl: '/sign-up',
  }
);

const { signIn, isLoading: signInLoading, error: signInError } = useSignIn();
const { authenticateWithPasskey, isSupported: passkeySupported, isLoading: passkeyLoading } = usePasskeys();
const { signInWithOAuth, isLoading: oauthLoading } = useOAuth();

const email = ref('');
const password = ref('');
const localError = ref<string | null>(null);

const isLoading = ref(false);

const providerLabels: Record<SocialProvider, string> = {
  google: 'Google',
  github: 'GitHub',
  microsoft: 'Microsoft',
  apple: 'Apple',
};

async function handleSubmit() {
  localError.value = null;
  isLoading.value = true;
  try {
    await signIn(email.value, password.value);
    props.onSuccess?.();
    if (props.redirectUrl && typeof window !== 'undefined') {
      window.location.href = props.redirectUrl;
    }
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    localError.value = err.message;
    props.onError?.(err);
  } finally {
    isLoading.value = false;
  }
}

async function handlePasskeySignIn() {
  localError.value = null;
  try {
    await authenticateWithPasskey(email.value || undefined);
    props.onSuccess?.();
    if (props.redirectUrl && typeof window !== 'undefined') {
      window.location.href = props.redirectUrl;
    }
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    localError.value = err.message;
    props.onError?.(err);
  }
}

async function handleOAuthSignIn(provider: OAuthProvider) {
  localError.value = null;
  try {
    await signInWithOAuth(provider, props.redirectUrl);
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    localError.value = err.message;
    props.onError?.(err);
  }
}
</script>

<template>
  <div :class="['janua-sign-in', className]">
    <form @submit.prevent="handleSubmit" class="janua-sign-in__form">
      <div class="janua-sign-in__field">
        <label for="janua-sign-in-email" class="janua-sign-in__label">Email</label>
        <input
          id="janua-sign-in-email"
          v-model="email"
          type="email"
          required
          autocomplete="email"
          placeholder="you@example.com"
          class="janua-sign-in__input"
          :disabled="isLoading || signInLoading"
        />
      </div>

      <div class="janua-sign-in__field">
        <label for="janua-sign-in-password" class="janua-sign-in__label">Password</label>
        <input
          id="janua-sign-in-password"
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
          placeholder="Enter your password"
          class="janua-sign-in__input"
          :disabled="isLoading || signInLoading"
        />
      </div>

      <div
        v-if="localError || signInError"
        class="janua-sign-in__error"
        role="alert"
      >
        {{ localError || signInError?.message }}
      </div>

      <button
        type="submit"
        class="janua-sign-in__button janua-sign-in__button--primary"
        :disabled="isLoading || signInLoading"
      >
        <span v-if="isLoading || signInLoading">Signing in...</span>
        <span v-else>Sign in</span>
      </button>
    </form>

    <template v-if="enableSocialLogin && socialProviders.length > 0">
      <div class="janua-sign-in__divider">
        <span>Or continue with</span>
      </div>

      <div class="janua-sign-in__social">
        <button
          v-for="provider in socialProviders"
          :key="provider"
          type="button"
          class="janua-sign-in__button janua-sign-in__button--social"
          :disabled="oauthLoading"
          @click="handleOAuthSignIn(provider)"
        >
          {{ providerLabels[provider] }}
        </button>
      </div>
    </template>

    <template v-if="enablePasskeys && passkeySupported">
      <div class="janua-sign-in__divider">
        <span>Or</span>
      </div>

      <button
        type="button"
        class="janua-sign-in__button janua-sign-in__button--passkey"
        :disabled="passkeyLoading"
        @click="handlePasskeySignIn"
      >
        <span v-if="passkeyLoading">Authenticating...</span>
        <span v-else>Sign in with a passkey</span>
      </button>
    </template>

    <p class="janua-sign-in__footer">
      Don't have an account?
      <a :href="signUpUrl" class="janua-sign-in__link">Sign up</a>
    </p>
  </div>
</template>

<style scoped>
.janua-sign-in {
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
  font-family: system-ui, -apple-system, sans-serif;
}

.janua-sign-in__form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.janua-sign-in__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.janua-sign-in__label {
  font-size: 14px;
  font-weight: 500;
  color: var(--janua-text, #1a1a1a);
}

.janua-sign-in__input {
  padding: 10px 12px;
  border: 1px solid var(--janua-border, #d1d5db);
  border-radius: var(--janua-radius, 6px);
  font-size: 14px;
  color: var(--janua-text, #1a1a1a);
  background: var(--janua-bg, #ffffff);
  outline: none;
  transition: border-color 0.15s;
}

.janua-sign-in__input:focus {
  border-color: var(--janua-primary, #2563eb);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--janua-primary, #2563eb) 20%, transparent);
}

.janua-sign-in__input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.janua-sign-in__error {
  padding: 10px 12px;
  border-radius: var(--janua-radius, 6px);
  background: color-mix(in srgb, var(--janua-error, #dc2626) 10%, transparent);
  color: var(--janua-error, #dc2626);
  font-size: 13px;
}

.janua-sign-in__button {
  padding: 10px 16px;
  border-radius: var(--janua-radius, 6px);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
  border: none;
}

.janua-sign-in__button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.janua-sign-in__button--primary {
  background: var(--janua-primary, #2563eb);
  color: #ffffff;
}

.janua-sign-in__button--primary:hover:not(:disabled) {
  opacity: 0.9;
}

.janua-sign-in__button--social {
  flex: 1;
  background: var(--janua-bg, #ffffff);
  color: var(--janua-text, #1a1a1a);
  border: 1px solid var(--janua-border, #d1d5db);
}

.janua-sign-in__button--social:hover:not(:disabled) {
  background: color-mix(in srgb, var(--janua-border, #d1d5db) 30%, var(--janua-bg, #ffffff));
}

.janua-sign-in__button--passkey {
  width: 100%;
  background: var(--janua-bg, #ffffff);
  color: var(--janua-text, #1a1a1a);
  border: 1px solid var(--janua-border, #d1d5db);
}

.janua-sign-in__button--passkey:hover:not(:disabled) {
  background: color-mix(in srgb, var(--janua-border, #d1d5db) 30%, var(--janua-bg, #ffffff));
}

.janua-sign-in__divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 50%, transparent);
  font-size: 13px;
}

.janua-sign-in__divider::before,
.janua-sign-in__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--janua-border, #d1d5db);
}

.janua-sign-in__social {
  display: flex;
  gap: 8px;
}

.janua-sign-in__footer {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
}

.janua-sign-in__link {
  color: var(--janua-primary, #2563eb);
  text-decoration: none;
  font-weight: 500;
}

.janua-sign-in__link:hover {
  text-decoration: underline;
}
</style>
