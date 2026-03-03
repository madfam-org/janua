<script setup lang="ts">
import { ref } from 'vue';
import { useSignUp } from '../composables';
import { useOAuth, type OAuthProvider } from '../composables';

type SocialProvider = 'google' | 'github' | 'microsoft' | 'apple';

const props = withDefaults(
  defineProps<{
    onSuccess?: () => void;
    onError?: (error: Error) => void;
    redirectUrl?: string;
    enableSocialLogin?: boolean;
    socialProviders?: SocialProvider[];
    signInUrl?: string;
    className?: string;
  }>(),
  {
    enableSocialLogin: true,
    socialProviders: () => ['google', 'github'],
    signInUrl: '/sign-in',
  }
);

const { signUp, isLoading: signUpLoading, error: signUpError } = useSignUp();
const { signInWithOAuth, isLoading: oauthLoading } = useOAuth();

const firstName = ref('');
const lastName = ref('');
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
    await signUp({
      email: email.value,
      password: password.value,
      firstName: firstName.value || undefined,
      lastName: lastName.value || undefined,
    });
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
  <div :class="['janua-sign-up', className]">
    <form @submit.prevent="handleSubmit" class="janua-sign-up__form">
      <div class="janua-sign-up__name-row">
        <div class="janua-sign-up__field">
          <label for="janua-sign-up-first-name" class="janua-sign-up__label">First name</label>
          <input
            id="janua-sign-up-first-name"
            v-model="firstName"
            type="text"
            autocomplete="given-name"
            placeholder="First name"
            class="janua-sign-up__input"
            :disabled="isLoading || signUpLoading"
          />
        </div>

        <div class="janua-sign-up__field">
          <label for="janua-sign-up-last-name" class="janua-sign-up__label">Last name</label>
          <input
            id="janua-sign-up-last-name"
            v-model="lastName"
            type="text"
            autocomplete="family-name"
            placeholder="Last name"
            class="janua-sign-up__input"
            :disabled="isLoading || signUpLoading"
          />
        </div>
      </div>

      <div class="janua-sign-up__field">
        <label for="janua-sign-up-email" class="janua-sign-up__label">Email</label>
        <input
          id="janua-sign-up-email"
          v-model="email"
          type="email"
          required
          autocomplete="email"
          placeholder="you@example.com"
          class="janua-sign-up__input"
          :disabled="isLoading || signUpLoading"
        />
      </div>

      <div class="janua-sign-up__field">
        <label for="janua-sign-up-password" class="janua-sign-up__label">Password</label>
        <input
          id="janua-sign-up-password"
          v-model="password"
          type="password"
          required
          autocomplete="new-password"
          placeholder="Create a password"
          class="janua-sign-up__input"
          :disabled="isLoading || signUpLoading"
        />
      </div>

      <div
        v-if="localError || signUpError"
        class="janua-sign-up__error"
        role="alert"
      >
        {{ localError || signUpError?.message }}
      </div>

      <button
        type="submit"
        class="janua-sign-up__button janua-sign-up__button--primary"
        :disabled="isLoading || signUpLoading"
      >
        <span v-if="isLoading || signUpLoading">Creating account...</span>
        <span v-else>Sign up</span>
      </button>
    </form>

    <template v-if="enableSocialLogin && socialProviders.length > 0">
      <div class="janua-sign-up__divider">
        <span>Or continue with</span>
      </div>

      <div class="janua-sign-up__social">
        <button
          v-for="provider in socialProviders"
          :key="provider"
          type="button"
          class="janua-sign-up__button janua-sign-up__button--social"
          :disabled="oauthLoading"
          @click="handleOAuthSignIn(provider)"
        >
          {{ providerLabels[provider] }}
        </button>
      </div>
    </template>

    <p class="janua-sign-up__footer">
      Already have an account?
      <a :href="signInUrl" class="janua-sign-up__link">Sign in</a>
    </p>
  </div>
</template>

<style scoped>
.janua-sign-up {
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
  font-family: system-ui, -apple-system, sans-serif;
}

.janua-sign-up__form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.janua-sign-up__name-row {
  display: flex;
  gap: 12px;
}

.janua-sign-up__name-row .janua-sign-up__field {
  flex: 1;
}

.janua-sign-up__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.janua-sign-up__label {
  font-size: 14px;
  font-weight: 500;
  color: var(--janua-text, #1a1a1a);
}

.janua-sign-up__input {
  padding: 10px 12px;
  border: 1px solid var(--janua-border, #d1d5db);
  border-radius: var(--janua-radius, 6px);
  font-size: 14px;
  color: var(--janua-text, #1a1a1a);
  background: var(--janua-bg, #ffffff);
  outline: none;
  transition: border-color 0.15s;
}

.janua-sign-up__input:focus {
  border-color: var(--janua-primary, #2563eb);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--janua-primary, #2563eb) 20%, transparent);
}

.janua-sign-up__input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.janua-sign-up__error {
  padding: 10px 12px;
  border-radius: var(--janua-radius, 6px);
  background: color-mix(in srgb, var(--janua-error, #dc2626) 10%, transparent);
  color: var(--janua-error, #dc2626);
  font-size: 13px;
}

.janua-sign-up__button {
  padding: 10px 16px;
  border-radius: var(--janua-radius, 6px);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
  border: none;
}

.janua-sign-up__button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.janua-sign-up__button--primary {
  background: var(--janua-primary, #2563eb);
  color: #ffffff;
}

.janua-sign-up__button--primary:hover:not(:disabled) {
  opacity: 0.9;
}

.janua-sign-up__button--social {
  flex: 1;
  background: var(--janua-bg, #ffffff);
  color: var(--janua-text, #1a1a1a);
  border: 1px solid var(--janua-border, #d1d5db);
}

.janua-sign-up__button--social:hover:not(:disabled) {
  background: color-mix(in srgb, var(--janua-border, #d1d5db) 30%, var(--janua-bg, #ffffff));
}

.janua-sign-up__divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 50%, transparent);
  font-size: 13px;
}

.janua-sign-up__divider::before,
.janua-sign-up__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--janua-border, #d1d5db);
}

.janua-sign-up__social {
  display: flex;
  gap: 8px;
}

.janua-sign-up__footer {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
}

.janua-sign-up__link {
  color: var(--janua-primary, #2563eb);
  text-decoration: none;
  font-weight: 500;
}

.janua-sign-up__link:hover {
  text-decoration: underline;
}
</style>
