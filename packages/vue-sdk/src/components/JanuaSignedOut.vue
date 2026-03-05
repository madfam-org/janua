<script setup lang="ts">
import { useAuth } from '../composables';

const { isAuthenticated, isLoading } = useAuth();
</script>

<template>
  <slot v-if="!isLoading && !isAuthenticated" />
</template>
