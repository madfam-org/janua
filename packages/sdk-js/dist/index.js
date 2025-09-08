"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
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
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);

// src/index.ts
var index_exports = {};
__export(index_exports, {
  PlintoAPIError: () => PlintoAPIError,
  PlintoClient: () => PlintoClient,
  createClient: () => createClient,
  verifyToken: () => verifyToken
});
module.exports = __toCommonJS(index_exports);

// src/jwt.ts
var jose = __toESM(require("jose"));
async function verifyToken(token, jwks, options = {}) {
  const {
    audience = "plinto.dev",
    issuer = "https://plinto.dev",
    clockTolerance = 30
  } = options;
  const { kid } = jose.decodeProtectedHeader(token);
  if (!kid) {
    throw new Error("JWT missing kid in header");
  }
  const jwk = jwks.keys.find((key) => key.kid === kid);
  if (!jwk) {
    throw new Error(`JWK not found for kid: ${kid}`);
  }
  const publicKey = await jose.importJWK(jwk);
  const { payload } = await jose.jwtVerify(token, publicKey, {
    audience,
    issuer,
    clockTolerance
  });
  return payload;
}

// src/jwks.ts
var JWKSCache = class {
  // 24 hours
  constructor(jwksUrl) {
    __publicField(this, "jwksUrl");
    __publicField(this, "cache", null);
    __publicField(this, "cacheExpiry", 0);
    __publicField(this, "cacheDuration", 24 * 60 * 60 * 1e3);
    this.jwksUrl = jwksUrl;
  }
  async get() {
    const now = Date.now();
    if (this.cache && now < this.cacheExpiry) {
      return this.cache;
    }
    try {
      const response = await fetch(this.jwksUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch JWKS: ${response.status} ${response.statusText}`);
      }
      const jwks = await response.json();
      if (!jwks.keys || !Array.isArray(jwks.keys)) {
        throw new Error("Invalid JWKS format: missing keys array");
      }
      this.cache = jwks;
      this.cacheExpiry = now + this.cacheDuration;
      return jwks;
    } catch (error) {
      console.error("Failed to fetch JWKS:", error);
      return this.cache;
    }
  }
  clear() {
    this.cache = null;
    this.cacheExpiry = 0;
  }
};

// src/index.ts
var PlintoClient = class {
  constructor(config) {
    __publicField(this, "config");
    __publicField(this, "jwksCache", null);
    /**
     * Identity management
     */
    __publicField(this, "identities", {
      /**
       * Create a new identity
       */
      create: async (data) => {
        return this.request("/api/v1/identities", {
          method: "POST",
          body: data
        });
      },
      /**
       * Get identity by ID
       */
      get: async (id) => {
        return this.request(`/api/v1/identities/${id}`);
      },
      /**
       * Update identity
       */
      update: async (id, data) => {
        return this.request(`/api/v1/identities/${id}`, {
          method: "PATCH",
          body: data
        });
      },
      /**
       * Delete identity
       */
      delete: async (id) => {
        return this.request(`/api/v1/identities/${id}`, {
          method: "DELETE"
        });
      },
      /**
       * List identities
       */
      list: async (params) => {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/v1/identities${query ? `?${query}` : ""}`);
      }
    });
    /**
     * Session management
     */
    __publicField(this, "sessions", {
      /**
       * Create a new session (login)
       */
      create: async (data) => {
        return this.request("/api/v1/sessions", {
          method: "POST",
          body: data
        });
      },
      /**
       * Verify session token
       */
      verify: async (token) => {
        if (this.jwksCache) {
          try {
            const jwks = await this.jwksCache.get();
            if (jwks) {
              return await verifyToken(token, jwks, {
                audience: this.config.audience || "plinto.dev",
                issuer: this.config.issuer || "https://plinto.dev"
              });
            }
          } catch (error) {
            console.warn("Local verification failed, falling back to API:", error);
          }
        }
        return this.request("/api/v1/sessions/verify", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
      },
      /**
       * Refresh session tokens
       */
      refresh: async (refreshToken) => {
        return this.request("/api/v1/sessions/refresh", {
          method: "POST",
          body: { refreshToken }
        });
      },
      /**
       * Revoke session
       */
      revoke: async (sessionId) => {
        return this.request(`/api/v1/sessions/${sessionId}`, {
          method: "DELETE"
        });
      },
      /**
       * Get current session
       */
      current: async (token) => {
        return this.request("/api/v1/sessions/current", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
      }
    });
    /**
     * Organization management
     */
    __publicField(this, "organizations", {
      /**
       * Create organization
       */
      create: async (data) => {
        return this.request("/api/v1/organizations", {
          method: "POST",
          body: data
        });
      },
      /**
       * Get organization
       */
      get: async (id) => {
        return this.request(`/api/v1/organizations/${id}`);
      },
      /**
       * List organizations
       */
      list: async (params) => {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/v1/organizations${query ? `?${query}` : ""}`);
      },
      /**
       * Add member to organization
       */
      addMember: async (orgId, data) => {
        return this.request(`/api/v1/organizations/${orgId}/members`, {
          method: "POST",
          body: data
        });
      },
      /**
       * Remove member from organization
       */
      removeMember: async (orgId, memberId) => {
        return this.request(`/api/v1/organizations/${orgId}/members/${memberId}`, {
          method: "DELETE"
        });
      }
    });
    /**
     * Passkey management
     */
    __publicField(this, "passkeys", {
      /**
       * Begin passkey registration
       */
      beginRegistration: async (identityId) => {
        return this.request("/api/v1/passkeys/registration/begin", {
          method: "POST",
          body: { identityId }
        });
      },
      /**
       * Complete passkey registration
       */
      completeRegistration: async (identityId, credential) => {
        return this.request("/api/v1/passkeys/registration/complete", {
          method: "POST",
          body: { identityId, credential }
        });
      },
      /**
       * Begin passkey authentication
       */
      beginAuthentication: async () => {
        return this.request("/api/v1/passkeys/authentication/begin", {
          method: "POST"
        });
      },
      /**
       * Complete passkey authentication
       */
      completeAuthentication: async (credential) => {
        return this.request("/api/v1/passkeys/authentication/complete", {
          method: "POST",
          body: { credential }
        });
      }
    });
    /**
     * Policy evaluation
     */
    __publicField(this, "policies", {
      /**
       * Evaluate policy
       */
      evaluate: async (data) => {
        return this.request("/api/v1/policies/evaluate", {
          method: "POST",
          body: data
        });
      }
    });
    this.config = {
      baseUrl: "https://plinto.dev",
      ...config
    };
    if (config.enableLocalVerification) {
      this.jwksCache = new JWKSCache(
        config.jwksUrl || `${this.config.baseUrl}/.well-known/jwks.json`
      );
    }
  }
  /**
   * Make authenticated request
   */
  async request(path, options = {}) {
    const url = `${this.config.baseUrl}${path}`;
    const headers = {
      "Content-Type": "application/json",
      "Accept": "application/json",
      ...options.headers
    };
    if (this.config.apiKey) {
      headers["Authorization"] = `Bearer ${this.config.apiKey}`;
    }
    if (this.config.tenantId) {
      headers["X-Plinto-Tenant"] = this.config.tenantId;
    }
    const response = await fetch(url, {
      ...options,
      headers,
      body: options.body ? JSON.stringify(options.body) : void 0
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({
        error: {
          code: "unknown_error",
          message: `HTTP ${response.status}: ${response.statusText}`
        }
      }));
      throw new PlintoAPIError(
        error.error?.message || "Request failed",
        error.error?.code || "unknown_error",
        response.status
      );
    }
    if (response.status === 204) {
      return void 0;
    }
    return response.json();
  }
};
var PlintoAPIError = class extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
    this.name = "PlintoAPIError";
  }
};
function createClient(config) {
  return new PlintoClient(config);
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  PlintoAPIError,
  PlintoClient,
  createClient,
  verifyToken
});
