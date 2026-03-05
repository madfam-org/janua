<script setup lang="ts">
import { ref, nextTick } from 'vue';
import { useMFA } from '../composables';

const props = defineProps<{
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  className?: string;
}>();

const { verifyMFA, isLoading, error: mfaError } = useMFA();

const CODE_LENGTH = 6;
const digits = ref<string[]>(Array(CODE_LENGTH).fill(''));
const inputRefs = ref<(HTMLInputElement | null)[]>([]);
const localError = ref<string | null>(null);

function setInputRef(el: any, index: number) {
  inputRefs.value[index] = el as HTMLInputElement;
}

async function submitCode() {
  const code = digits.value.join('');
  if (code.length !== CODE_LENGTH) return;

  localError.value = null;
  try {
    await verifyMFA(code);
    props.onSuccess?.();
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    localError.value = err.message;
    props.onError?.(err);
    // Clear inputs and refocus first on error
    digits.value = Array(CODE_LENGTH).fill('');
    await nextTick();
    inputRefs.value[0]?.focus();
  }
}

function handleInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement;
  const value = target.value;

  // Handle paste of full code
  if (value.length > 1) {
    const chars = value.replace(/\D/g, '').slice(0, CODE_LENGTH).split('');
    chars.forEach((char, i) => {
      if (i < CODE_LENGTH) {
        digits.value[i] = char;
      }
    });
    const focusIndex = Math.min(chars.length, CODE_LENGTH - 1);
    inputRefs.value[focusIndex]?.focus();

    if (chars.length === CODE_LENGTH) {
      submitCode();
    }
    return;
  }

  // Single character input
  const digit = value.replace(/\D/g, '');
  digits.value[index] = digit;

  if (digit && index < CODE_LENGTH - 1) {
    inputRefs.value[index + 1]?.focus();
  }

  // Auto-submit when all digits filled
  if (digit && digits.value.every((d) => d !== '')) {
    submitCode();
  }
}

function handleKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace') {
    if (!digits.value[index] && index > 0) {
      digits.value[index - 1] = '';
      inputRefs.value[index - 1]?.focus();
      event.preventDefault();
    } else {
      digits.value[index] = '';
    }
  } else if (event.key === 'ArrowLeft' && index > 0) {
    inputRefs.value[index - 1]?.focus();
    event.preventDefault();
  } else if (event.key === 'ArrowRight' && index < CODE_LENGTH - 1) {
    inputRefs.value[index + 1]?.focus();
    event.preventDefault();
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault();
  const pasted = event.clipboardData?.getData('text')?.replace(/\D/g, '').slice(0, CODE_LENGTH) || '';
  if (!pasted) return;

  const chars = pasted.split('');
  chars.forEach((char, i) => {
    if (i < CODE_LENGTH) {
      digits.value[i] = char;
    }
  });

  const focusIndex = Math.min(chars.length, CODE_LENGTH - 1);
  inputRefs.value[focusIndex]?.focus();

  if (chars.length === CODE_LENGTH) {
    submitCode();
  }
}

function handleFocus(event: FocusEvent) {
  (event.target as HTMLInputElement)?.select();
}
</script>

<template>
  <div :class="['janua-mfa', className]">
    <p class="janua-mfa__heading">Enter verification code</p>
    <p class="janua-mfa__description">
      Enter the 6-digit code from your authenticator app.
    </p>

    <div
      class="janua-mfa__inputs"
      role="group"
      aria-label="Verification code"
    >
      <input
        v-for="(_, index) in CODE_LENGTH"
        :key="index"
        :ref="(el) => setInputRef(el, index)"
        type="text"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        :value="digits[index]"
        :aria-label="`Digit ${index + 1} of ${CODE_LENGTH}`"
        class="janua-mfa__digit"
        :disabled="isLoading"
        @input="handleInput(index, $event)"
        @keydown="handleKeydown(index, $event)"
        @paste="handlePaste"
        @focus="handleFocus"
      />
    </div>

    <div
      v-if="localError || mfaError"
      class="janua-mfa__error"
      role="alert"
    >
      {{ localError || mfaError?.message }}
    </div>

    <p v-if="isLoading" class="janua-mfa__status" aria-live="polite">
      Verifying...
    </p>
  </div>
</template>

<style scoped>
.janua-mfa {
  width: 100%;
  max-width: 360px;
  margin: 0 auto;
  text-align: center;
  font-family: system-ui, -apple-system, sans-serif;
}

.janua-mfa__heading {
  font-size: 18px;
  font-weight: 600;
  color: var(--janua-text, #1a1a1a);
  margin: 0 0 4px;
}

.janua-mfa__description {
  font-size: 13px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
  margin: 0 0 24px;
}

.janua-mfa__inputs {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.janua-mfa__digit {
  width: 44px;
  height: 52px;
  text-align: center;
  font-size: 20px;
  font-weight: 600;
  border: 1px solid var(--janua-border, #d1d5db);
  border-radius: var(--janua-radius, 6px);
  color: var(--janua-text, #1a1a1a);
  background: var(--janua-bg, #ffffff);
  outline: none;
  transition: border-color 0.15s;
}

.janua-mfa__digit:focus {
  border-color: var(--janua-primary, #2563eb);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--janua-primary, #2563eb) 20%, transparent);
}

.janua-mfa__digit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.janua-mfa__error {
  margin-top: 16px;
  padding: 10px 12px;
  border-radius: var(--janua-radius, 6px);
  background: color-mix(in srgb, var(--janua-error, #dc2626) 10%, transparent);
  color: var(--janua-error, #dc2626);
  font-size: 13px;
}

.janua-mfa__status {
  margin-top: 16px;
  font-size: 13px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
}
</style>
