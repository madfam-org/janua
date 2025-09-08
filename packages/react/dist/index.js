"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/index.ts
var index_exports = {};
__export(index_exports, {
  PlintoProvider: () => PlintoProvider,
  useAuth: () => useAuth,
  useOrganization: () => useOrganization,
  usePlinto: () => usePlinto,
  useSession: () => useSession
});
module.exports = __toCommonJS(index_exports);

// src/provider.tsx
var import_react = require("react");
var import_sdk = require("@plinto/sdk");
var import_jsx_runtime = require("react/jsx-runtime");
var PlintoContext = (0, import_react.createContext)(void 0);
function PlintoProvider({ children, config }) {
  const [client] = (0, import_react.useState)(() => new import_sdk.PlintoClient(config));
  const [identity, setIdentity] = (0, import_react.useState)(null);
  const [session, setSession] = (0, import_react.useState)(null);
  const [isLoading, setIsLoading] = (0, import_react.useState)(true);
  (0, import_react.useEffect)(() => {
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
  return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(PlintoContext.Provider, { value, children });
}
function usePlinto() {
  const context = (0, import_react.useContext)(PlintoContext);
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
var import_react2 = require("react");
function useOrganization() {
  const { client, isAuthenticated } = usePlinto();
  const [organizations, setOrganizations] = (0, import_react2.useState)([]);
  const [isLoading, setIsLoading] = (0, import_react2.useState)(false);
  (0, import_react2.useEffect)(() => {
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
var import_react3 = require("react");
function useSession() {
  const { client, session } = usePlinto();
  const [isRefreshing, setIsRefreshing] = (0, import_react3.useState)(false);
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
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  PlintoProvider,
  useAuth,
  useOrganization,
  usePlinto,
  useSession
});
