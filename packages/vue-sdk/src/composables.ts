import { inject, computed, ComputedRef } from 'vue';
import { PLINTO_KEY, PlintoVue } from './plugin';
import type { User, Session } from '@plinto/js';

export function usePlinto(): PlintoVue {
  const plinto = inject<PlintoVue>(PLINTO_KEY);
  
  if (!plinto) {
    throw new Error('Plinto plugin not installed. Make sure to call app.use(createPlinto(...))');
  }

  return plinto;
}

export function useAuth() {
  const plinto = usePlinto();
  const client = plinto.getClient();
  const state = plinto.getState();

  return {
    auth: client.auth,
    user: computed(() => state.user),
    session: computed(() => state.session),
    isAuthenticated: computed(() => state.isAuthenticated),
    isLoading: computed(() => state.isLoading),
    signIn: plinto.signIn.bind(plinto),
    signUp: plinto.signUp.bind(plinto),
    signOut: plinto.signOut.bind(plinto),
    updateSession: plinto.updateSession.bind(plinto),
  };
}

export function useUser(): {
  user: ComputedRef<User | null>;
  isLoading: ComputedRef<boolean>;
  updateUser: (data: any) => Promise<User>;
} {
  const plinto = usePlinto();
  const client = plinto.getClient();
  const state = plinto.getState();

  const updateUser = async (data: any) => {
    const updatedUser = await client.users.updateCurrentUser(data);
    await plinto.updateSession();
    return updatedUser;
  };

  return {
    user: computed(() => state.user),
    isLoading: computed(() => state.isLoading),
    updateUser,
  };
}

export function useSession(): {
  session: ComputedRef<Session | null>;
  refreshSession: () => Promise<void>;
  revokeSession: (sessionId: string) => Promise<void>;
} {
  const plinto = usePlinto();
  const client = plinto.getClient();
  const state = plinto.getState();

  const refreshSession = async () => {
    await plinto.updateSession();
  };

  const revokeSession = async (sessionId: string) => {
    await client.users.revokeSession(sessionId);
    if (state.session?.id === sessionId) {
      await plinto.signOut();
    }
  };

  return {
    session: computed(() => state.session),
    refreshSession,
    revokeSession,
  };
}

export function useOrganizations() {
  const plinto = usePlinto();
  const client = plinto.getClient();
  
  return client.organizations;
}

export function useSignIn() {
  const plinto = usePlinto();
  const state = plinto.getState();

  return {
    signIn: plinto.signIn.bind(plinto),
    isLoading: computed(() => state.isLoading),
  };
}

export function useSignUp() {
  const plinto = usePlinto();
  const state = plinto.getState();

  return {
    signUp: plinto.signUp.bind(plinto),
    isLoading: computed(() => state.isLoading),
  };
}

export function useSignOut() {
  const plinto = usePlinto();
  
  return {
    signOut: plinto.signOut.bind(plinto),
  };
}

export function useMagicLink() {
  const plinto = usePlinto();
  const client = plinto.getClient();

  const sendMagicLink = async (email: string, redirectUrl?: string) => {
    await client.auth.sendMagicLink({ email, redirectUrl });
  };

  const signInWithMagicLink = async (token: string) => {
    const response = await client.auth.signInWithMagicLink(token);
    await plinto.updateSession();
    return response;
  };

  return {
    sendMagicLink,
    signInWithMagicLink,
  };
}

export function useOAuth() {
  const plinto = usePlinto();
  const client = plinto.getClient();

  const getOAuthUrl = async (
    provider: 'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter' | 'linkedin',
    redirectUrl?: string
  ) => {
    return client.auth.getOAuthUrl({ provider, redirectUrl });
  };

  const handleOAuthCallback = async (code: string, state: string) => {
    const response = await client.auth.handleOAuthCallback(code, state);
    await plinto.updateSession();
    return response;
  };

  return {
    getOAuthUrl,
    handleOAuthCallback,
  };
}

export function usePasskeys() {
  const plinto = usePlinto();
  const client = plinto.getClient();

  const registerPasskey = async (options?: any) => {
    const registrationOptions = await client.auth.beginPasskeyRegistration(options);
    // In a real implementation, you would use the WebAuthn API here
    // const credential = await navigator.credentials.create(registrationOptions);
    // await client.auth.completePasskeyRegistration(credential);
    return registrationOptions;
  };

  const authenticateWithPasskey = async () => {
    const authOptions = await client.auth.beginPasskeyAuthentication();
    // In a real implementation, you would use the WebAuthn API here
    // const credential = await navigator.credentials.get(authOptions);
    // const response = await client.auth.completePasskeyAuthentication(credential);
    // await plinto.updateSession();
    return authOptions;
  };

  return {
    registerPasskey,
    authenticateWithPasskey,
  };
}

export function useMFA() {
  const plinto = usePlinto();
  const client = plinto.getClient();

  const enableMFA = async (type: 'totp' | 'sms') => {
    return client.auth.enableMFA(type);
  };

  const confirmMFA = async (code: string) => {
    await client.auth.confirmMFA(code);
    await plinto.updateSession();
  };

  const disableMFA = async (code: string) => {
    await client.auth.disableMFA(code);
    await plinto.updateSession();
  };

  const verifyMFA = async (code: string) => {
    const tokens = await client.auth.verifyMFA(code);
    await plinto.updateSession();
    return tokens;
  };

  return {
    enableMFA,
    confirmMFA,
    disableMFA,
    verifyMFA,
  };
}