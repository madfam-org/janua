import { inject, computed, ref, type ComputedRef, type Ref } from 'vue';
import { JANUA_KEY } from './plugin';
import type { JanuaVue } from './plugin';
import type { User, Session } from '@janua/typescript-sdk';
import { checkWebAuthnSupport } from '@janua/typescript-sdk';
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

export function useJanua(): JanuaVue {
  const janua = inject<JanuaVue>(JANUA_KEY);

  if (!janua) {
    throw new Error('Janua plugin not installed. Make sure to call app.use(createJanua(...))');
  }

  return janua;
}

export function useAuth() {
  const janua = useJanua();
  const client = janua.getClient();
  const state = janua.getState();

  return {
    auth: client.auth,
    user: computed(() => state.user),
    session: computed(() => state.session),
    isAuthenticated: computed(() => state.isAuthenticated),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    signIn: janua.signIn.bind(janua),
    signUp: janua.signUp.bind(janua),
    signOut: janua.signOut.bind(janua),
    updateSession: janua.updateSession.bind(janua),
  };
}

export function useUser() {
  const janua = useJanua();
  const client = janua.getClient();
  const state = janua.getState();

  const updateUser = async (data: any) => {
    const updatedUser = await client.users.updateCurrentUser(data);
    await janua.updateSession();
    return updatedUser;
  };

  return {
    user: computed(() => state.user as User | null),
    isLoading: computed(() => state.isLoading),
    updateUser,
  };
}

export function useSession(): {
  session: ComputedRef<Session | null>;
  refreshSession: () => Promise<void>;
  revokeSession: (sessionId: string) => Promise<void>;
} {
  const janua = useJanua();
  const client = janua.getClient();
  const state = janua.getState();

  const refreshSession = async () => {
    await janua.updateSession();
  };

  const revokeSession = async (sessionId: string) => {
    await client.users.revokeSession(sessionId);
    if (state.session?.id === sessionId) {
      await janua.signOut();
    }
  };

  return {
    session: computed(() => state.session),
    refreshSession,
    revokeSession,
  };
}

export function useOrganizations() {
  const janua = useJanua();
  const client = janua.getClient();

  return client.organizations;
}

export function useSignIn() {
  const janua = useJanua();
  const state = janua.getState();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  const signIn = async (email: string, password: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      return await janua.signIn(email, password);
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    signIn,
    isLoading: computed(() => isLoading.value || state.isLoading),
    error: computed(() => error.value),
  };
}

export function useSignUp() {
  const janua = useJanua();
  const state = janua.getState();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  const signUp = async (data: {
    email: string;
    password: string;
    firstName?: string;
    lastName?: string;
  }) => {
    error.value = null;
    isLoading.value = true;
    try {
      return await janua.signUp(data);
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    signUp,
    isLoading: computed(() => isLoading.value || state.isLoading),
    error: computed(() => error.value),
  };
}

export function useSignOut() {
  const janua = useJanua();

  return {
    signOut: janua.signOut.bind(janua),
  };
}

export function useMagicLink() {
  const janua = useJanua();
  const client = janua.getClient();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  const sendMagicLink = async (email: string, redirectUrl?: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      await client.auth.sendMagicLink({ email, redirect_url: redirectUrl });
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const signInWithMagicLink = async (token: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      const response = await client.auth.verifyMagicLink(token);
      await janua.updateSession();
      return response;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    sendMagicLink,
    signInWithMagicLink,
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
  };
}

export type OAuthProvider = 'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter';

export function useOAuth(options?: { clientId?: string; redirectUri?: string }) {
  const janua = useJanua();
  const client = janua.getClient();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  const signInWithOAuth = async (provider: OAuthProvider, redirectUrl?: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      const verifier = generateCodeVerifier();
      const challenge = await generateCodeChallenge(verifier);
      const state = generateState();

      storePKCEParams(verifier, state);

      const clientId = options?.clientId || 'default';
      const redirectUri = redirectUrl
        || options?.redirectUri
        || (typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '');

      const baseURL = (client as any).config?.baseURL || (client as any).baseURL || '';
      const authUrl = buildAuthorizationUrl(baseURL, provider, clientId, redirectUri, challenge, state);

      window.location.href = authUrl;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      isLoading.value = false;
      throw e;
    }
  };

  const handleOAuthCallback = async (code: string, callbackState: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      // Validate state parameter to prevent CSRF
      if (!validateState(callbackState)) {
        throw new Error('Invalid OAuth state - possible CSRF attack');
      }

      const pkceParams = retrievePKCEParams();
      if (!pkceParams) {
        throw new Error('Missing PKCE parameters');
      }

      // Exchange code with code_verifier
      await client.auth.handleOAuthCallback(code, callbackState);
      clearPKCEParams();
      await janua.updateSession();

      // Clean OAuth params from URL
      if (typeof window !== 'undefined') {
        window.history.replaceState({}, '', window.location.pathname);
      }
    } catch (e) {
      clearPKCEParams();
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    signInWithOAuth,
    handleOAuthCallback,
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
  };
}

export function usePasskeys() {
  const janua = useJanua();
  const client = janua.getClient();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  // Check WebAuthn support synchronously on init
  const support = typeof window !== 'undefined' ? checkWebAuthnSupport() : { available: false, platform: false, conditional: false };
  const isSupported = ref(support.available);

  const registerPasskey = async (name?: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      await client.registerPasskey(name);
      await janua.updateSession();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const authenticateWithPasskey = async (email?: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      await client.signInWithPasskey(email);
      await janua.updateSession();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    registerPasskey,
    authenticateWithPasskey,
    isSupported: computed(() => isSupported.value),
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
  };
}

export function useMFA() {
  const janua = useJanua();
  const client = janua.getClient();
  const error = ref<Error | null>(null);
  const isLoading = ref(false);

  const enableMFA = async (type: 'totp' | 'sms') => {
    error.value = null;
    isLoading.value = true;
    try {
      return await client.auth.enableMFA(type);
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const confirmMFA = async (code: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      await client.auth.verifyMFA({ code });
      await janua.updateSession();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const disableMFA = async (password: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      await client.auth.disableMFA(password);
      await janua.updateSession();
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const verifyMFA = async (code: string) => {
    error.value = null;
    isLoading.value = true;
    try {
      const tokens = await client.auth.verifyMFA({ code });
      await janua.updateSession();
      return tokens;
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e));
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    enableMFA,
    confirmMFA,
    disableMFA,
    verifyMFA,
    isLoading: computed(() => isLoading.value),
    error: computed(() => error.value),
  };
}
