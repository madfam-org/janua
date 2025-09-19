"use strict";
/**
 * Environment detection and configuration utilities
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.EnvUtils = void 0;
const token_utils_1 = require("./token-utils");
class EnvUtils {
    /**
     * Check if running in browser environment
     */
    static isBrowser() {
        return typeof window !== 'undefined' && typeof window.document !== 'undefined';
    }
    /**
     * Check if running in Node.js environment
     */
    static isNode() {
        return typeof process !== 'undefined' &&
            typeof process.versions === 'object' &&
            typeof process.versions.node === 'string';
    }
    /**
     * Check if running in Web Worker
     */
    static isWebWorker() {
        return typeof self !== 'undefined' && typeof self.importScripts === 'function';
    }
    /**
     * Check if running in React Native
     */
    static isReactNative() {
        return typeof navigator !== 'undefined' && navigator.product === 'ReactNative';
    }
    /**
     * Check if running in Electron
     */
    static isElectron() {
        return typeof window !== 'undefined' &&
            typeof window.process === 'object' &&
            window.process.type === 'renderer';
    }
    /**
     * Get appropriate storage based on environment
     */
    static getDefaultStorage() {
        if (this.isNode()) {
            // Use memory storage in Node.js
            return new token_utils_1.MemoryTokenStorage();
        }
        else if (this.isBrowser()) {
            // Prefer localStorage in browser
            return new token_utils_1.LocalTokenStorage();
        }
        else if (this.isWebWorker()) {
            // Use memory storage in Web Workers
            return new token_utils_1.MemoryTokenStorage();
        }
        else {
            // Default to memory storage
            return new token_utils_1.MemoryTokenStorage();
        }
    }
    /**
     * Get environment name
     */
    static getEnvironment() {
        if (this.isNode())
            return 'node';
        if (this.isBrowser())
            return 'browser';
        if (this.isWebWorker())
            return 'webworker';
        if (this.isReactNative())
            return 'react-native';
        if (this.isElectron())
            return 'electron';
        return 'unknown';
    }
    /**
     * Check if localStorage is available
     */
    static hasLocalStorage() {
        try {
            const test = '__plinto_test__';
            localStorage.setItem(test, test);
            localStorage.removeItem(test);
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Check if sessionStorage is available
     */
    static hasSessionStorage() {
        try {
            const test = '__plinto_test__';
            sessionStorage.setItem(test, test);
            sessionStorage.removeItem(test);
            return true;
        }
        catch {
            return false;
        }
    }
    /**
     * Check if crypto API is available
     */
    static hasCrypto() {
        return typeof crypto !== 'undefined' && crypto.subtle !== undefined;
    }
    /**
     * Get user agent string
     */
    static getUserAgent() {
        if (this.isBrowser()) {
            return navigator.userAgent;
        }
        if (this.isNode()) {
            return `Node.js/${process.version}`;
        }
        return 'Unknown';
    }
}
exports.EnvUtils = EnvUtils;
//# sourceMappingURL=env-utils.js.map