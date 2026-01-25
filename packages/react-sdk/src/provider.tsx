import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { JanuaClient, type JanuaConfig, type User, type Session } from '@janua/typescript-sdk';
import type {
  JanuaUser,
  JanuaErrorState,
  OAuthProviderName,
  JanuaProviderConfig,
} from './types';
import { STORAGE_KEYS } from './types';
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  buildAuthorizationUrl,
} from './utils/pkce';
import { mapErrorToState, ReactJanuaError } from './utils/errors';

/**
 * Context value interface with full authentication capabilities
 */
export interface JanuaContextValue {
  // Underlying client for advanced usage
  client: JanuaClient;

  // State
  user: JanuaUser | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: JanuaErrorState | null;

  // Core authentication methods
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, options?: SignUpOptions) => Promise<void>;
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
 * Options for sign up
 */
export interface SignUpOptions {
  firstName?: string;
  lastName?: string;
  username?: string;
}

const JanuaContext = createContext<JanuaContextValue | undefined>(undefined);

export interface JanuaProviderProps {
  children: ReactNode;
  config: JanuaConfig | JanuaProviderConfig;
}

/**
 * Map API User to JanuaUser format for Dhanam compatibility
 */
function mapApiUserToJanuaUser(apiUser: User): JanuaUser {
  return {
    id: apiUser.id,
    email: apiUser.email,
    name:
      apiUser.name ||
      (apiUser.first_name && apiUser.last_name
        ? `${apiUser.first_name} ${apiUser.last_name}`
        : apiUser.first_name || apiUser.last_name || null),
    display_name: apiUser.display_name || apiUser.username || apiUser.first_name || null,
    picture: apiUser.profile_image_url,
    locale: apiUser.locale || 'en-US',
    timezone: apiUser.timezone || 'UTC',
    mfa_enabled: apiUser.mfa_enabled || false,
    email_verified: apiUser.email_verified || false,
    created_at: apiUser.created_at,
    updated_at: apiUser.updated_at,
    organization_id: apiUser.organizationId,
    organization_role: apiUser.roles?.[0],
  };
}

/**
 * Check if a JWT token is expired
 */
function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;

    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return false;

    // Add 30 second buffer to account for network latency
    return payload.exp * 1000 < Date.now() - 30000;
  } catch {
    return true;
  }
}

/**
 * JanuaProvider component for React applications
 *
 * Wraps your application and provides authentication context.
 *
 * @example
 * ```tsx
 * import { JanuaProvider } from '@janua/react-sdk';
 *
 * function App() {
 *   return (
 *     <JanuaProvider config={{ baseURL: 'https://api.janua.dev' }}>
 *       <YourApp />
 *     </JanuaProvider>
 *   );
 * }
 * ```
 */
export function JanuaProvider({ children, config }: JanuaProviderProps) {
  const [client] = useState(() => new JanuaClient(config));
  const [user, setUser] = useState<JanuaUser | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<JanuaErrorState | null>(null);

  // Get client ID and redirect URI from config for OAuth
  const clientId = useMemo(() => {
    const cfg = config as JanuaProviderConfig;
    return cfg.clientId || 'default';
  }, [config]);

  const redirectUri = useMemo(() => {
    const cfg = config as JanuaProviderConfig;
    return cfg.redirectUri || (typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '');
  }, [config]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Store tokens in localStorage
   */
  const storeTokens = useCallback((accessToken: string, refreshToken?: string, idToken?: string) => {
    localStorage.setItem(STORAGE_KEYS.accessToken, accessToken);
    if (refreshToken) {
      localStorage.setItem(STORAGE_KEYS.refreshToken, refreshToken);
    }
    if (idToken) {
      localStorage.setItem(STORAGE_KEYS.idToken, idToken);
    }
  }, []);

  /**
   * Clear tokens from localStorage
   */
  const clearTokens = useCallback(() => {
    localStorage.removeItem(STORAGE_KEYS.accessToken);
    localStorage.removeItem(STORAGE_KEYS.refreshToken);
    localStorage.removeItem(STORAGE_KEYS.idToken);
    localStorage.removeItem(STORAGE_KEYS.user);
  }, []);

  /**
   * Refresh the current session
   */
  const refreshSession = useCallback(async (): Promise<void> => {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
    if (!refreshToken) {
      throw new ReactJanuaError('REFRESH_FAILED', 'No refresh token available');
    }

    try {
      const tokens = await client.auth.refreshToken({ refresh_token: refreshToken });
      storeTokens(tokens.access_token, tokens.refresh_token);

      // Fetch updated user
      const currentUser = await client.getCurrentUser();
      if (currentUser) {
        const mappedUser = mapApiUserToJanuaUser(currentUser);
        setUser(mappedUser);
        localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(mappedUser));
      }
    } catch (err) {
      const errorState = mapErrorToState(err);
      errorState.code = 'REFRESH_FAILED';
      setError(errorState);
      clearTokens();
      setUser(null);
      throw ReactJanuaError.fromState(errorState);
    }
  }, [client, storeTokens, clearTokens]);

  /**
   * Get access token, refreshing if needed
   */
  const getAccessToken = useCallback(async (): Promise<string | null> => {
    const token = localStorage.getItem(STORAGE_KEYS.accessToken);
    if (!token) return null;

    if (isTokenExpired(token)) {
      try {
        await refreshSession();
        return localStorage.getItem(STORAGE_KEYS.accessToken);
      } catch {
        return null;
      }
    }

    return token;
  }, [refreshSession]);

  /**
   * Get ID token
   */
  const getIdToken = useCallback(async (): Promise<string | null> => {
    return localStorage.getItem(STORAGE_KEYS.idToken);
  }, []);

  /**
   * Initialize authentication state on mount
   */
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const token = localStorage.getItem(STORAGE_KEYS.accessToken);
        if (!token) {
          setIsLoading(false);
          return;
        }

        // Check if token is expired
        if (isTokenExpired(token)) {
          try {
            await refreshSession();
          } catch {
            // Refresh failed, user will need to re-authenticate
            setIsLoading(false);
            return;
          }
        } else {
          // Token is valid, fetch current user
          const currentUser = await client.getCurrentUser();
          if (currentUser) {
            const mappedUser = mapApiUserToJanuaUser(currentUser);
            setUser(mappedUser);
            localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(mappedUser));
          }
        }
      } catch (err) {
        // Authentication initialization failed
        clearTokens();
        const errorState = mapErrorToState(err);
        setError(errorState);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, [client, refreshSession, clearTokens]);

  /**
   * Sign in with email and password
   */
  const signIn = useCallback(
    async (email: string, password: string): Promise<void> => {
      setError(null);
      setIsLoading(true);

      try {
        const response = await client.signIn({ email, password });

        storeTokens(response.tokens.access_token, response.tokens.refresh_token);

        const currentUser = await client.getCurrentUser();
        if (currentUser) {
          const mappedUser = mapApiUserToJanuaUser(currentUser);
          setUser(mappedUser);
          localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(mappedUser));
        }
      } catch (err) {
        const errorState = mapErrorToState(err);
        setError(errorState);
        throw ReactJanuaError.fromState(errorState);
      } finally {
        setIsLoading(false);
      }
    },
    [client, storeTokens]
  );

  /**
   * Sign up with email and password
   */
  const signUp = useCallback(
    async (email: string, password: string, options?: SignUpOptions): Promise<void> => {
      setError(null);
      setIsLoading(true);

      try {
        const response = await client.signUp({
          email,
          password,
          first_name: options?.firstName,
          last_name: options?.lastName,
          username: options?.username,
        });

        storeTokens(response.tokens.access_token, response.tokens.refresh_token);

        const mappedUser = mapApiUserToJanuaUser(response.user);
        setUser(mappedUser);
        localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(mappedUser));
      } catch (err) {
        const errorState = mapErrorToState(err);
        setError(errorState);
        throw ReactJanuaError.fromState(errorState);
      } finally {
        setIsLoading(false);
      }
    },
    [client, storeTokens]
  );

  /**
   * Sign out the current user
   */
  const signOut = useCallback(async (): Promise<void> => {
    try {
      await client.signOut();
    } catch {
      // Ignore errors during sign out
    } finally {
      clearTokens();
      setUser(null);
      setSession(null);
      setError(null);
    }
  }, [client, clearTokens]);

  /**
   * Initiate OAuth sign in flow with PKCE
   */
  const signInWithOAuth = useCallback(
    async (provider: OAuthProviderName): Promise<void> => {
      setError(null);

      try {
        // Generate PKCE parameters
        const verifier = generateCodeVerifier();
        const challenge = await generateCodeChallenge(verifier);
        const state = generateState();

        // Store parameters for callback verification
        storePKCEParams(verifier, state);

        // Build authorization URL
        const authUrl = buildAuthorizationUrl(
          config.baseURL,
          provider,
          clientId,
          redirectUri,
          challenge,
          state
        );

        // Redirect to OAuth provider
        window.location.href = authUrl;
      } catch (err) {
        const errorState = mapErrorToState(err);
        errorState.code = 'OAUTH_ERROR';
        setError(errorState);
        throw ReactJanuaError.fromState(errorState);
      }
    },
    [config.baseURL, clientId, redirectUri]
  );

  /**
   * Handle OAuth callback and exchange code for tokens
   */
  const handleOAuthCallback = useCallback(
    async (code: string, state: string): Promise<void> => {
      setError(null);
      setIsLoading(true);

      try {
        // Validate state
        if (!validateState(state)) {
          throw new ReactJanuaError('PKCE_ERROR', 'Invalid OAuth state - possible CSRF attack');
        }

        // Retrieve PKCE parameters
        const pkceParams = retrievePKCEParams();
        if (!pkceParams) {
          throw new ReactJanuaError('PKCE_ERROR', 'Missing PKCE parameters');
        }

        // Exchange code for tokens
        // Note: This assumes the API has an endpoint for token exchange
        // Adjust based on your actual API structure
        const response = await fetch(`${config.baseURL}/api/v1/oauth/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            grant_type: 'authorization_code',
            code,
            redirect_uri: redirectUri,
            client_id: clientId,
            code_verifier: pkceParams.verifier,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new ReactJanuaError(
            'OAUTH_ERROR',
            errorData.message || 'Failed to exchange OAuth code',
            response.status,
            errorData
          );
        }

        const tokenData = await response.json();

        // Store tokens
        storeTokens(
          tokenData.access_token,
          tokenData.refresh_token,
          tokenData.id_token
        );

        // Clear PKCE params
        clearPKCEParams();

        // Fetch current user
        const currentUser = await client.getCurrentUser();
        if (currentUser) {
          const mappedUser = mapApiUserToJanuaUser(currentUser);
          setUser(mappedUser);
          localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(mappedUser));
        }
      } catch (err) {
        clearPKCEParams();
        if (err instanceof ReactJanuaError) {
          setError(err.toState());
          throw err;
        }
        const errorState = mapErrorToState(err);
        errorState.code = 'OAUTH_ERROR';
        setError(errorState);
        throw ReactJanuaError.fromState(errorState);
      } finally {
        setIsLoading(false);
      }
    },
    [config.baseURL, client, clientId, redirectUri, storeTokens]
  );

  // Build context value
  const value = useMemo<JanuaContextValue>(
    () => ({
      client,
      user,
      session,
      isLoading,
      isAuthenticated: !!user,
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
    }),
    [
      client,
      user,
      session,
      isLoading,
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
    ]
  );

  return <JanuaContext.Provider value={value}>{children}</JanuaContext.Provider>;
}

/**
 * Hook to access Janua authentication context
 *
 * @throws {Error} If used outside of JanuaProvider
 *
 * @example
 * ```tsx
 * function LoginButton() {
 *   const { signIn, isLoading, error } = useJanua();
 *
 *   const handleLogin = async () => {
 *     await signIn('user@example.com', 'password');
 *   };
 *
 *   return <button onClick={handleLogin} disabled={isLoading}>Log In</button>;
 * }
 * ```
 */
export function useJanua(): JanuaContextValue {
  const context = useContext(JanuaContext);
  if (!context) {
    throw new Error('useJanua must be used within a JanuaProvider');
  }
  return context;
}
