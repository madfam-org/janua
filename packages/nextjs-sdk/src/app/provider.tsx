'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { JanuaClient } from '@janua/typescript-sdk';
import type { User, Session, JanuaConfig } from '@janua/typescript-sdk';
import { validateState, retrievePKCEParams, clearPKCEParams } from '../utils/pkce';

interface JanuaContextValue {
  client: JanuaClient;
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  signOut: () => Promise<void>;
  updateUser: () => Promise<void>;
}

const JanuaContext = createContext<JanuaContextValue | undefined>(undefined);

export interface JanuaProviderProps {
  children: React.ReactNode;
  config: JanuaConfig;
  onAuthChange?: (user: User | null) => void;
}

export function JanuaProvider({
  children,
  config,
  onAuthChange
}: JanuaProviderProps) {
  const [client] = useState(() => new JanuaClient(config));
  const [user, setUser] = useState<User | null>(null);
  const userRef = useRef<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const updateAuthState = useCallback(async () => {
    let currentUser: User | null = null;

    if (!config.skipRemoteAuth) {
      currentUser = await client.auth.getCurrentUser();
    } else {
      // Derive user from localStorage token if available
      const token = typeof window !== 'undefined'
        ? localStorage.getItem('janua_access_token') : null;
      if (token) {
        try {
          const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
          currentUser = { id: payload.sub, email: payload.email } as User;
        } catch { /* invalid token */ }
      }
    }

    const currentSession = {
      accessToken: await client.getAccessToken(),
      refreshToken: await client.getRefreshToken()
    };

    setUser(currentUser);
    userRef.current = currentUser;
    setSession(currentSession as any);

    if (onAuthChange) {
      onAuthChange(currentUser);
    }
  }, [client, config, onAuthChange]);

  const updateUser = useCallback(async () => {
    try {
      await client.auth.getCurrentUser();
      updateAuthState();
    } catch (error) {
      // Error handled silently in production
    }
  }, [client, updateAuthState]);

  const signOut = useCallback(async () => {
    try {
      await client.auth.signOut();
      setUser(null);
      setSession(null);

      if (onAuthChange) {
        onAuthChange(null);
      }
    } catch (error) {
      // Error handled silently in production
    }
  }, [client, onAuthChange]);

  // OAuth callback handling and initial auth state
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('code') && urlParams.has('state')) {
      const code = urlParams.get('code')!;
      const state = urlParams.get('state')!;

      // Validate PKCE state before proceeding
      if (!validateState(state)) {
        console.warn('OAuth state mismatch - possible CSRF attack');
        setIsLoading(false);
        return;
      }

      // Retrieve PKCE code verifier for the token exchange
      const pkceParams = retrievePKCEParams();
      const codeVerifier = pkceParams?.verifier;

      client.auth.handleOAuthCallback(code, codeVerifier || state)
        .then(() => {
          clearPKCEParams();
          window.history.replaceState({}, '', window.location.pathname);
          return updateAuthState();
        })
        .catch(() => {
          clearPKCEParams();
          // Error handled silently in production
        })
        .finally(() => setIsLoading(false));
    } else {
      // Load initial auth state
      updateAuthState();
      setIsLoading(false);
    }

    // Set up auth state polling (60 second interval)
    const checkInterval = setInterval(async () => {
      if (config.skipRemoteAuth) return; // Skip remote polling when auth is server-managed
      try {
        const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('janua_access_token');
        if (!hasToken) return;
        const currentUser = await client.auth.getCurrentUser();
        if (currentUser?.id !== userRef.current?.id) {
          updateAuthState();
        }
      } catch {
        // Non-fatal: polling failure is handled by next cycle
      }
    }, 60_000);

    return () => {
      clearInterval(checkInterval);
    };
  }, [client, updateAuthState]);

  // Proactive token auto-refresh before expiry
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const scheduleRefresh = async () => {
      try {
        const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('janua_access_token');
        if (!hasToken) return;
        const accessToken = await client.getAccessToken();
        if (!accessToken) return;

        // Parse JWT exp claim (base64 decode the payload segment)
        const parts = accessToken.split('.');
        if (parts.length !== 3) return;

        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
        const exp = payload.exp;
        if (!exp) return;

        const now = Math.floor(Date.now() / 1000);
        const timeUntilExpiry = exp - now;

        // If already expired or less than 60s remaining, refresh immediately
        if (timeUntilExpiry < 60) {
          try {
            await client.auth.refreshToken();
          } catch {
            // Non-fatal: token refresh failure is handled by next auth check
          }
          // Schedule next check in 30 seconds
          timeoutId = setTimeout(scheduleRefresh, 30_000);
          return;
        }

        // Schedule refresh for 60 seconds before expiry (minimum 30s delay)
        const delay = Math.max((timeUntilExpiry - 60) * 1000, 30_000);
        timeoutId = setTimeout(scheduleRefresh, delay);
      } catch {
        // Non-fatal: schedule a retry in 30 seconds
        timeoutId = setTimeout(scheduleRefresh, 30_000);
      }
    };

    scheduleRefresh();

    return () => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [client]);

  const value: JanuaContextValue = {
    client,
    user,
    session,
    isLoading,
    isAuthenticated: !!user && !!session,
    signOut,
    updateUser,
  };

  return (
    <JanuaContext.Provider value={value}>
      {children}
    </JanuaContext.Provider>
  );
}

export function useJanua(): JanuaContextValue {
  const context = useContext(JanuaContext);
  if (!context) {
    throw new Error('useJanua must be used within a JanuaProvider');
  }
  return context;
}

export function useAuth() {
  const { client, user, session, isAuthenticated, isLoading, signOut } = useJanua();
  return {
    auth: client.auth,
    user,
    session,
    isAuthenticated,
    isLoading,
    signOut,
  };
}

export function useUser() {
  const { user, isLoading, updateUser } = useJanua();
  return {
    user,
    isLoading,
    updateUser,
  };
}

export function useOrganizations() {
  const { client } = useJanua();
  return client.organizations;
}
