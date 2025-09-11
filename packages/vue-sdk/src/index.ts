// Re-export everything from @plinto/js
export * from '@plinto/js';

// Plugin
export { createPlinto, PLINTO_KEY } from './plugin';
export type { PlintoState, PlintoPluginOptions, PlintoVue } from './plugin';

// Composables
export {
  usePlinto,
  useAuth,
  useUser,
  useSession,
  useOrganizations,
  useSignIn,
  useSignUp,
  useSignOut,
  useMagicLink,
  useOAuth,
  usePasskeys,
  useMFA,
} from './composables';