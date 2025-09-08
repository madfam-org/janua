// src/provider.tsx
import { createContext, useContext, useState, useEffect } from "react";
import { PlintoClient } from "@plinto/sdk";
import { jsx } from "react/jsx-runtime";
var PlintoContext = createContext(void 0);
function PlintoProvider({ children, config }) {
  const [client] = useState(() => new PlintoClient(config));
  const [identity, setIdentity] = useState(null);
  const [session, setSession] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const token = localStorage.getItem("plinto_access_token");
        if (token) {
          const currentSession = await client.sessions.current(token);
          setSession(currentSession);
          if (currentSession.identity_id) {
            const currentIdentity = await client.identities.get(currentSession.identity_id);
            setIdentity(currentIdentity);
          }
        }
      } catch (error) {
        console.error("Failed to initialize auth:", error);
        localStorage.removeItem("plinto_access_token");
        localStorage.removeItem("plinto_refresh_token");
      } finally {
        setIsLoading(false);
      }
    };
    initializeAuth();
  }, [client]);
  const signIn = async (email, password) => {
    const newSession = await client.sessions.create({ email, password });
    setSession(newSession);
    if (newSession.access_token) {
      localStorage.setItem("plinto_access_token", newSession.access_token);
    }
    if (newSession.refresh_token) {
      localStorage.setItem("plinto_refresh_token", newSession.refresh_token);
    }
    if (newSession.identity_id) {
      const currentIdentity = await client.identities.get(newSession.identity_id);
      setIdentity(currentIdentity);
    }
  };
  const signOut = async () => {
    if (session?.id) {
      await client.sessions.revoke(session.id);
    }
    setSession(null);
    setIdentity(null);
    localStorage.removeItem("plinto_access_token");
    localStorage.removeItem("plinto_refresh_token");
  };
  const value = {
    client,
    identity,
    session,
    isLoading,
    isAuthenticated: !!session && !!identity,
    signIn,
    signOut
  };
  return /* @__PURE__ */ jsx(PlintoContext.Provider, { value, children });
}
function usePlinto() {
  const context = useContext(PlintoContext);
  if (!context) {
    throw new Error("usePlinto must be used within a PlintoProvider");
  }
  return context;
}

// src/hooks/use-auth.ts
function useAuth() {
  const { identity, session, isLoading, isAuthenticated, signIn, signOut } = usePlinto();
  return {
    user: identity,
    session,
    isLoading,
    isAuthenticated,
    signIn,
    signOut
  };
}

// src/hooks/use-organization.ts
import { useState as useState2, useEffect as useEffect2 } from "react";
function useOrganization() {
  const { client, isAuthenticated } = usePlinto();
  const [organizations, setOrganizations] = useState2([]);
  const [isLoading, setIsLoading] = useState2(false);
  useEffect2(() => {
    if (!isAuthenticated) {
      setOrganizations([]);
      return;
    }
    const fetchOrganizations = async () => {
      setIsLoading(true);
      try {
        const result = await client.organizations.list();
        setOrganizations(result.data);
      } catch (error) {
        console.error("Failed to fetch organizations:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchOrganizations();
  }, [client, isAuthenticated]);
  const createOrganization = async (data) => {
    const organization = await client.organizations.create(data);
    setOrganizations((prev) => [...prev, organization]);
    return organization;
  };
  return {
    organizations,
    isLoading,
    createOrganization
  };
}

// src/hooks/use-session.ts
import { useState as useState3 } from "react";
function useSession() {
  const { client, session } = usePlinto();
  const [isRefreshing, setIsRefreshing] = useState3(false);
  const refreshTokens = async () => {
    const refreshToken = localStorage.getItem("plinto_refresh_token");
    if (!refreshToken) {
      return null;
    }
    setIsRefreshing(true);
    try {
      const tokens = await client.sessions.refresh(refreshToken);
      localStorage.setItem("plinto_access_token", tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem("plinto_refresh_token", tokens.refresh_token);
      }
      return tokens;
    } catch (error) {
      console.error("Failed to refresh tokens:", error);
      localStorage.removeItem("plinto_access_token");
      localStorage.removeItem("plinto_refresh_token");
      return null;
    } finally {
      setIsRefreshing(false);
    }
  };
  const verifyToken = async (token) => {
    const tokenToVerify = token || localStorage.getItem("plinto_access_token");
    if (!tokenToVerify) {
      return null;
    }
    try {
      const payload = await client.sessions.verify(tokenToVerify);
      return payload;
    } catch (error) {
      console.error("Token verification failed:", error);
      return null;
    }
  };
  return {
    session,
    isRefreshing,
    refreshTokens,
    verifyToken
  };
}
export {
  PlintoProvider,
  useAuth,
  useOrganization,
  usePlinto,
  useSession
};
