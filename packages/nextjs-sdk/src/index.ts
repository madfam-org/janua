// Re-export everything from @plinto/js
export * from '@plinto/js';
export { PlintoClient } from '@plinto/js';

// Export middleware utilities
export { createPlintoMiddleware, withAuth, config } from './middleware';
export type { PlintoMiddlewareConfig } from './middleware';

// Export App Router utilities (most common)
export {
  PlintoProvider,
  usePlinto,
  useAuth,
  useUser,
  useOrganizations,
  SignInForm,
  SignUpForm,
  UserButton,
  SignedIn,
  SignedOut,
  RedirectToSignIn,
  Protect,
  PlintoServerClient,
  getSession,
  requireAuth,
  validateRequest,
} from './app';

export type {
  PlintoProviderProps,
  SignInFormProps,
  SignUpFormProps,
  UserButtonProps,
  SignedInProps,
  SignedOutProps,
  RedirectToSignInProps,
  ProtectProps,
} from './app';