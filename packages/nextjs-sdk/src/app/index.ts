// App Router exports
export { JanuaProvider, useJanua, useAuth, useUser, useOrganizations } from './provider';
export type { JanuaProviderProps, JanuaAuthStatus, CircuitState } from './provider';

// Retry policy primitives — exported for advanced consumers + testing.
export {
  RetryController,
  isCorsOrNetworkError,
  backoffDelay,
  DEFAULT_MAX_FAILURES,
  DEFAULT_BASE_DELAY_MS,
  DEFAULT_MAX_DELAY_MS,
} from './retry-policy';
export type { RetryControllerOptions, RetrySnapshot } from './retry-policy';

export {
  SignInForm,
  SignIn,
  SignUpForm,
  SignUp,
  UserButton,
  SignedIn,
  SignedOut,
  RedirectToSignIn,
  Protect,
} from './components';

export type {
  SignInFormProps,
  SignUpFormProps,
  UserButtonProps,
  SignedInProps,
  SignedOutProps,
  RedirectToSignInProps,
  ProtectProps,
} from './components';

export {
  JanuaServerClient,
  getSession,
  requireAuth,
  validateRequest,
} from './server';

export { useRealtime } from './use-realtime';
export type { UseRealtimeOptions, UseRealtimeReturn } from './use-realtime';