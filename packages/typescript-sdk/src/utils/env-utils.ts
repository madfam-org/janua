/**
 * Environment detection and configuration utilities
 */

import type { TokenStorage } from './token-utils';
import { LocalTokenStorage, SessionTokenStorage, MemoryTokenStorage } from './token-utils';

export class EnvUtils {
  /**
   * Check if running in browser environment
   */
  static isBrowser(): boolean {
    return typeof window !== 'undefined' && typeof window.document !== 'undefined';
  }

  /**
   * Check if running in Node.js environment
   */
  static isNode(): boolean {
    return typeof process !== 'undefined' &&
           typeof process.versions === 'object' &&
           typeof process.versions.node === 'string';
  }

  /**
   * Check if running in Web Worker
   */
  static isWebWorker(): boolean {
    return typeof self !== 'undefined' && typeof self.importScripts === 'function';
  }

  /**
   * Check if running in React Native
   */
  static isReactNative(): boolean {
    return typeof navigator !== 'undefined' && navigator.product === 'ReactNative';
  }

  /**
   * Check if running in Electron
   */
  static isElectron(): boolean {
    return typeof window !== 'undefined' &&
           typeof window.process === 'object' &&
           window.process.type === 'renderer';
  }

  /**
   * Get appropriate storage based on environment
   */
  static getDefaultStorage(): TokenStorage {
    if (this.isNode()) {
      // Use memory storage in Node.js
      return new MemoryTokenStorage();
    } else if (this.isBrowser()) {
      // Prefer localStorage in browser
      return new LocalTokenStorage();
    } else if (this.isWebWorker()) {
      // Use memory storage in Web Workers
      return new MemoryTokenStorage();
    } else {
      // Default to memory storage
      return new MemoryTokenStorage();
    }
  }

  /**
   * Get environment name
   */
  static getEnvironment(): string {
    if (this.isNode()) return 'node';
    if (this.isBrowser()) return 'browser';
    if (this.isWebWorker()) return 'webworker';
    if (this.isReactNative()) return 'react-native';
    if (this.isElectron()) return 'electron';
    return 'unknown';
  }

  /**
   * Check if localStorage is available
   */
  static hasLocalStorage(): boolean {
    try {
      const test = '__plinto_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if sessionStorage is available
   */
  static hasSessionStorage(): boolean {
    try {
      const test = '__plinto_test__';
      sessionStorage.setItem(test, test);
      sessionStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if crypto API is available
   */
  static hasCrypto(): boolean {
    return typeof crypto !== 'undefined' && crypto.subtle !== undefined;
  }

  /**
   * Get user agent string
   */
  static getUserAgent(): string {
    if (this.isBrowser()) {
      return navigator.userAgent;
    }
    if (this.isNode()) {
      return `Node.js/${process.version}`;
    }
    return 'Unknown';
  }
}