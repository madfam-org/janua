<script setup lang="ts">
import { watch } from 'vue';
import { useAuth } from '../composables';

const props = defineProps<{
  fallback?: string;
  redirectTo?: string;
}>();

const { isAuthenticated, isLoading } = useAuth();

watch(
  [isAuthenticated, isLoading],
  ([authenticated, loading]) => {
    if (!loading && !authenticated && props.redirectTo && typeof window !== 'undefined') {
      window.location.href = props.redirectTo;
    }
  },
  { immediate: true }
);
</script>

<template>
  <template v-if="isLoading">
    <slot name="loading">
      <div class="janua-protect__loading" aria-live="polite">Loading...</div>
    </slot>
  </template>
  <template v-else-if="isAuthenticated">
    <slot />
  </template>
  <template v-else-if="!redirectTo">
    <slot name="fallback">
      <div class="janua-protect__fallback" v-if="fallback" v-text="fallback" />
    </slot>
  </template>
</template>

<style scoped>
.janua-protect__loading {
  text-align: center;
  padding: 24px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
  font-size: 14px;
  font-family: system-ui, -apple-system, sans-serif;
}

.janua-protect__fallback {
  text-align: center;
  padding: 24px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
  font-size: 14px;
  font-family: system-ui, -apple-system, sans-serif;
}
</style>
