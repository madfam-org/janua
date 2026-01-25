import { useJanua } from '../provider';
import type { JanuaUser, JanuaErrorState, OAuthProviderName } from '../types';
import type { Session } from '@janua/typescript-sdk';

/**
 * Authentication state and methods returned by useAuth hook
 */
export interface UseAuthReturn {
  // State
  user: JanuaUser | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: JanuaErrorState | null;

  // Core methods
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, options?: { firstName?: string; lastName?: string; username?: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;

  // OAuth methods
  signInWithOAuth: (provider: OAuthProviderName) => Promise<void>;
  handleOAuthCallback: (code: string, state: string) => Promise<void>;

  // Token access
  getAccessToken: () => Promise<string | null>;
  getIdToken: () => Promise<string | null>;

  // Error management
  clearError: () => void;
}

/**
 * Hook for authentication functionality
 *
 * Provides access to authentication state and methods.
 *
 * @example
 * ```tsx
 * function LoginForm() {
 *   const { signIn, isLoading, error } = useAuth();
 *
 *   const handleSubmit = async (e: React.FormEvent) => {
 *     e.preventDefault();
 *     await signIn(email, password);
 *   };
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       {error && <p>{error.message}</p>}
 *       <input name="email" />
 *       <input name="password" type="password" />
 *       <button disabled={isLoading}>Sign In</button>
 *     </form>
 *   );
 * }
 * ```
 */
export function useAuth(): UseAuthReturn {
  const {
    user,
    session,
    isLoading,
    isAuthenticated,
    error,
    signIn,
    signUp,
    signOut,
    refreshSession,
    signInWithOAuth,
    handleOAuthCallback,
    getAccessToken,
    getIdToken,
    clearError,
  } = useJanua();

  return {
    user,
    session,
    isLoading,
    isAuthenticated,
    error,
    signIn,
    signUp,
    signOut,
    refreshSession,
    signInWithOAuth,
    handleOAuthCallback,
    getAccessToken,
    getIdToken,
    clearError,
  };
}
