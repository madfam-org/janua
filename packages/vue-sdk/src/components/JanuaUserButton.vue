<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAuth } from '../composables';

const props = withDefaults(
  defineProps<{
    showEmail?: boolean;
    showName?: boolean;
    afterSignOut?: () => void;
    className?: string;
  }>(),
  {
    showEmail: true,
    showName: true,
  }
);

const { user, isAuthenticated, signOut } = useAuth();

const isOpen = ref(false);

const initials = computed(() => {
  const u = user.value;
  if (!u) return '?';
  const first = (u as any).firstName?.[0] || (u as any).first_name?.[0] || '';
  const last = (u as any).lastName?.[0] || (u as any).last_name?.[0] || '';
  if (first || last) return `${first}${last}`.toUpperCase();
  return u.email?.[0]?.toUpperCase() || '?';
});

const displayName = computed(() => {
  const u = user.value;
  if (!u) return '';
  const first = (u as any).firstName || (u as any).first_name || '';
  const last = (u as any).lastName || (u as any).last_name || '';
  if (first || last) return `${first} ${last}`.trim();
  return u.email || '';
});

function toggleDropdown() {
  isOpen.value = !isOpen.value;
}

function closeDropdown() {
  isOpen.value = false;
}

async function handleSignOut() {
  closeDropdown();
  await signOut();
  props.afterSignOut?.();
}
</script>

<template>
  <div v-if="isAuthenticated" :class="['janua-user-button', className]" v-click-outside="closeDropdown">
    <button
      type="button"
      class="janua-user-button__trigger"
      :aria-expanded="isOpen"
      aria-haspopup="true"
      @click="toggleDropdown"
    >
      <span class="janua-user-button__avatar" aria-hidden="true">
        {{ initials }}
      </span>
    </button>

    <Transition name="janua-dropdown">
      <div
        v-if="isOpen"
        class="janua-user-button__dropdown"
        role="menu"
      >
        <div class="janua-user-button__info">
          <span class="janua-user-button__avatar janua-user-button__avatar--large" aria-hidden="true">
            {{ initials }}
          </span>
          <div class="janua-user-button__details">
            <span v-if="showName && displayName" class="janua-user-button__name">
              {{ displayName }}
            </span>
            <span v-if="showEmail && user?.email" class="janua-user-button__email">
              {{ user.email }}
            </span>
          </div>
        </div>

        <div class="janua-user-button__separator" role="separator" />

        <button
          type="button"
          class="janua-user-button__menu-item"
          role="menuitem"
          @click="handleSignOut"
        >
          Sign out
        </button>
      </div>
    </Transition>
  </div>
</template>

<script lang="ts">
/** Click-outside directive for closing the dropdown */
const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    (el as any).__clickOutsideHandler = (event: Event) => {
      if (!el.contains(event.target as Node)) {
        binding.value();
      }
    };
    document.addEventListener('click', (el as any).__clickOutsideHandler);
  },
  unmounted(el: HTMLElement) {
    document.removeEventListener('click', (el as any).__clickOutsideHandler);
    delete (el as any).__clickOutsideHandler;
  },
};

export default {
  directives: {
    'click-outside': vClickOutside,
  },
};
</script>

<style scoped>
.janua-user-button {
  position: relative;
  display: inline-block;
  font-family: system-ui, -apple-system, sans-serif;
}

.janua-user-button__trigger {
  display: flex;
  align-items: center;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  border-radius: 50%;
}

.janua-user-button__trigger:focus-visible {
  outline: 2px solid var(--janua-primary, #2563eb);
  outline-offset: 2px;
}

.janua-user-button__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--janua-primary, #2563eb);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  user-select: none;
}

.janua-user-button__avatar--large {
  width: 44px;
  height: 44px;
  font-size: 16px;
}

.janua-user-button__dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 240px;
  background: var(--janua-bg, #ffffff);
  border: 1px solid var(--janua-border, #d1d5db);
  border-radius: var(--janua-radius, 6px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 50;
  overflow: hidden;
}

.janua-user-button__info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.janua-user-button__details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.janua-user-button__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--janua-text, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.janua-user-button__email {
  font-size: 12px;
  color: color-mix(in srgb, var(--janua-text, #1a1a1a) 60%, transparent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.janua-user-button__separator {
  height: 1px;
  background: var(--janua-border, #d1d5db);
}

.janua-user-button__menu-item {
  display: block;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: none;
  text-align: left;
  font-size: 14px;
  color: var(--janua-text, #1a1a1a);
  cursor: pointer;
  transition: background 0.1s;
}

.janua-user-button__menu-item:hover {
  background: color-mix(in srgb, var(--janua-border, #d1d5db) 30%, var(--janua-bg, #ffffff));
}

.janua-user-button__menu-item:focus-visible {
  outline: 2px solid var(--janua-primary, #2563eb);
  outline-offset: -2px;
}

/* Dropdown transition */
.janua-dropdown-enter-active,
.janua-dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.janua-dropdown-enter-from,
.janua-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
