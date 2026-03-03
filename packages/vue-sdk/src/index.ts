// Re-export everything from @janua/typescript-sdk
export * from '@janua/typescript-sdk';

// Plugin
export { createJanua, JANUA_KEY } from './plugin';
export type { JanuaState, JanuaPluginOptions, JanuaVueType as JanuaVue } from './plugin';

// Composables
export {
  useJanua,
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

export type { OAuthProvider } from './composables';

// Real-time composable
export { useRealtime } from './composables/use-realtime';
export type { UseRealtimeOptions, UseRealtimeReturn } from './composables/use-realtime';

// PKCE utilities (re-exported from @janua/typescript-sdk)
export {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  buildAuthorizationUrl,
} from './utils/pkce';

// Components
export {
  JanuaSignIn,
  JanuaSignUp,
  JanuaUserButton,
  JanuaMFAChallenge,
  JanuaProtect,
  JanuaSignedIn,
  JanuaSignedOut,
} from './components';