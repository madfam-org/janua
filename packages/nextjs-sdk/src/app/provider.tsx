'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { PlintoClient } from '@plinto/js';
import type { User, Session, PlintoConfig } from '@plinto/js';

interface PlintoContextValue {
  client: PlintoClient;
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  signOut: () => Promise<void>;
  updateUser: () => Promise<void>;
}

const PlintoContext = createContext<PlintoContextValue | undefined>(undefined);

export interface PlintoProviderProps {
  children: React.ReactNode;
  config: PlintoConfig;
  onAuthChange?: (user: User | null) => void;
}

export function PlintoProvider({ 
  children, 
  config,
  onAuthChange 
}: PlintoProviderProps) {
  const [client] = useState(() => new PlintoClient(config));
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const updateAuthState = useCallback(() => {
    const currentUser = client.getUser();
    const currentSession = client.getSession();
    
    setUser(currentUser);
    setSession(currentSession);
    
    if (onAuthChange) {
      onAuthChange(currentUser);
    }
  }, [client, onAuthChange]);

  const updateUser = useCallback(async () => {
    try {
      await client.updateSession();
      updateAuthState();
    } catch (error) {
      console.error('Failed to update user:', error);
    }
  }, [client, updateAuthState]);

  const signOut = useCallback(async () => {
    try {
      await client.signOut();
      setUser(null);
      setSession(null);
      
      if (onAuthChange) {
        onAuthChange(null);
      }
    } catch (error) {
      console.error('Failed to sign out:', error);
    }
  }, [client, onAuthChange]);

  useEffect(() => {
    // Check for auth params in URL
    if (client.hasAuthParams()) {
      client.handleRedirectCallback()
        .then(() => updateAuthState())
        .catch(console.error)
        .finally(() => setIsLoading(false));
    } else {
      // Load initial auth state
      updateAuthState();
      setIsLoading(false);
    }

    // Set up auth state listener
    const checkInterval = setInterval(() => {
      const currentUser = client.getUser();
      if (currentUser !== user) {
        updateAuthState();
      }
    }, 1000);

    return () => {
      clearInterval(checkInterval);
    };
  }, [client, updateAuthState, user]);

  const value: PlintoContextValue = {
    client,
    user,
    session,
    isLoading,
    isAuthenticated: !!user && !!session,
    signOut,
    updateUser,
  };

  return (
    <PlintoContext.Provider value={value}>
      {children}
    </PlintoContext.Provider>
  );
}

export function usePlinto(): PlintoContextValue {
  const context = useContext(PlintoContext);
  if (!context) {
    throw new Error('usePlinto must be used within a PlintoProvider');
  }
  return context;
}

export function useAuth() {
  const { client, user, session, isAuthenticated, isLoading, signOut } = usePlinto();
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
  const { user, isLoading, updateUser } = usePlinto();
  return {
    user,
    isLoading,
    updateUser,
  };
}

export function useOrganizations() {
  const { client } = usePlinto();
  return client.organizations;
}