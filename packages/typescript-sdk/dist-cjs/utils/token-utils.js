"use strict";
/**
 * Token-related utilities for JWT handling and token storage
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.TokenManager = exports.MemoryTokenStorage = exports.SessionTokenStorage = exports.LocalTokenStorage = exports.JwtUtils = exports.Base64Url = void 0;
const errors_1 = require("../errors");
/**
 * Base64URL encoding/decoding utilities
 */
class Base64Url {
    static encode(data) {
        return Buffer.from(data)
            .toString('base64')
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=/g, '');
    }
    static decode(data) {
        // Add padding if needed
        let base64 = data.replace(/-/g, '+').replace(/_/g, '/');
        while (base64.length % 4) {
            base64 += '=';
        }
        return Buffer.from(base64, 'base64').toString('utf-8');
    }
}
exports.Base64Url = Base64Url;
/**
 * JWT parsing and validation utilities
 */
class JwtUtils {
    static parseToken(token) {
        const parts = token.split('.');
        if (parts.length !== 3) {
            throw new errors_1.TokenError('Invalid JWT format');
        }
        try {
            const header = JSON.parse(Base64Url.decode(parts[0]));
            const payload = JSON.parse(Base64Url.decode(parts[1]));
            const signature = parts[2];
            return { header, payload, signature };
        }
        catch (error) {
            throw new errors_1.TokenError('Failed to parse JWT payload');
        }
    }
    static isExpired(payload) {
        if (!payload || !payload.exp) {
            return false; // No expiration claim
        }
        return Date.now() >= payload.exp * 1000;
    }
    static getTimeToExpiry(payload) {
        if (!payload || !payload.exp) {
            return Infinity; // No expiration
        }
        const expiryMs = payload.exp * 1000;
        const now = Date.now();
        return Math.max(0, Math.floor((expiryMs - now) / 1000));
    }
}
exports.JwtUtils = JwtUtils;
/**
 * LocalStorage implementation for browser environments
 */
class LocalTokenStorage {
    async getItem(key) {
        try {
            return localStorage.getItem(key);
        }
        catch {
            return null;
        }
    }
    async setItem(key, value) {
        try {
            localStorage.setItem(key, value);
        }
        catch (error) {
            // Silently handle localStorage errors in production
        }
    }
    async removeItem(key) {
        try {
            localStorage.removeItem(key);
        }
        catch (error) {
            // Silently handle localStorage errors in production
        }
    }
}
exports.LocalTokenStorage = LocalTokenStorage;
/**
 * SessionStorage implementation for browser environments
 */
class SessionTokenStorage {
    async getItem(key) {
        try {
            return sessionStorage.getItem(key);
        }
        catch {
            return null;
        }
    }
    async setItem(key, value) {
        try {
            sessionStorage.setItem(key, value);
        }
        catch (error) {
            // Silently handle sessionStorage errors in production
        }
    }
    async removeItem(key) {
        try {
            sessionStorage.removeItem(key);
        }
        catch (error) {
            // Silently handle sessionStorage errors in production
        }
    }
}
exports.SessionTokenStorage = SessionTokenStorage;
/**
 * In-memory storage implementation
 */
class MemoryTokenStorage {
    constructor() {
        this.storage = new Map();
    }
    async getItem(key) {
        return this.storage.get(key) || null;
    }
    async setItem(key, value) {
        this.storage.set(key, value);
    }
    async removeItem(key) {
        this.storage.delete(key);
    }
}
exports.MemoryTokenStorage = MemoryTokenStorage;
/**
 * Token management with storage abstraction
 */
class TokenManager {
    constructor(storage) {
        this.storage = storage;
        this.ACCESS_TOKEN_KEY = 'plinto_access_token';
        this.REFRESH_TOKEN_KEY = 'plinto_refresh_token';
        this.EXPIRES_AT_KEY = 'plinto_token_expires_at';
    }
    async setTokens(tokenData) {
        await Promise.all([
            this.storage.setItem(this.ACCESS_TOKEN_KEY, tokenData.access_token),
            this.storage.setItem(this.REFRESH_TOKEN_KEY, tokenData.refresh_token),
            this.storage.setItem(this.EXPIRES_AT_KEY, tokenData.expires_at.toString())
        ]);
    }
    async getAccessToken() {
        return this.storage.getItem(this.ACCESS_TOKEN_KEY);
    }
    async getRefreshToken() {
        return this.storage.getItem(this.REFRESH_TOKEN_KEY);
    }
    async clearTokens() {
        await Promise.all([
            this.storage.removeItem(this.ACCESS_TOKEN_KEY),
            this.storage.removeItem(this.REFRESH_TOKEN_KEY),
            this.storage.removeItem(this.EXPIRES_AT_KEY)
        ]);
    }
    async hasValidTokens() {
        const [accessToken, expiresAt] = await Promise.all([
            this.getAccessToken(),
            this.storage.getItem(this.EXPIRES_AT_KEY)
        ]);
        if (!accessToken || !expiresAt) {
            return false;
        }
        const expiryTime = parseInt(expiresAt, 10);
        return Date.now() < expiryTime;
    }
    async getTokenData() {
        const [accessToken, refreshToken, expiresAt] = await Promise.all([
            this.getAccessToken(),
            this.getRefreshToken(),
            this.storage.getItem(this.EXPIRES_AT_KEY)
        ]);
        if (!accessToken || !refreshToken || !expiresAt) {
            return null;
        }
        return {
            access_token: accessToken,
            refresh_token: refreshToken,
            expires_at: parseInt(expiresAt, 10)
        };
    }
}
exports.TokenManager = TokenManager;
//# sourceMappingURL=token-utils.js.map