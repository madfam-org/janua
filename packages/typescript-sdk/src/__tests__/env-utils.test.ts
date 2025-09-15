/**
 * Tests for environment utilities
 */
import { EnvUtils } from '../utils/env-utils';
import { LocalTokenStorage, MemoryTokenStorage } from '../utils/token-utils';

describe('EnvUtils', () => {
  // Clean up environment before each test
  const cleanEnvironment = () => {
    (global as any).window = undefined;
    (global as any).process = undefined;
    (global as any).navigator = undefined;
    (global as any).self = undefined;
    (global as any).localStorage = undefined;
    (global as any).sessionStorage = undefined;
    (global as any).crypto = undefined;
  };

  beforeEach(() => {
    cleanEnvironment();
  });

  describe('isBrowser', () => {
    it('should return true when window and document are available', () => {
      (global as any).window = { document: {} };

      const result = EnvUtils.isBrowser();

      expect(result).toBe(true);
    });

    it('should return false when window is undefined', () => {
      const result = EnvUtils.isBrowser();

      expect(result).toBe(false);
    });

    it('should return false when document is undefined', () => {
      (global as any).window = {};

      const result = EnvUtils.isBrowser();

      expect(result).toBe(false);
    });
  });

  describe('isNode', () => {
    it('should return true when process with versions.node is available', () => {
      (global as any).process = {
        versions: {
          node: '16.0.0'
        }
      };

      const result = EnvUtils.isNode();

      expect(result).toBe(true);
    });

    it('should return false when process is undefined', () => {
      const result = EnvUtils.isNode();

      expect(result).toBe(false);
    });

    it('should return false when process.versions is undefined', () => {
      (global as any).process = {};

      const result = EnvUtils.isNode();

      expect(result).toBe(false);
    });

    it('should return false when process.versions.node is undefined', () => {
      (global as any).process = {
        versions: {}
      };

      const result = EnvUtils.isNode();

      expect(result).toBe(false);
    });

    it('should return false when process.versions is not an object', () => {
      (global as any).process = {
        versions: 'not-an-object'
      };

      const result = EnvUtils.isNode();

      expect(result).toBe(false);
    });

    it('should return false when process.versions.node is not a string', () => {
      (global as any).process = {
        versions: {
          node: 123
        }
      };

      const result = EnvUtils.isNode();

      expect(result).toBe(false);
    });
  });

  describe('isWebWorker', () => {
    it('should return true when self with importScripts is available', () => {
      (global as any).self = {
        importScripts: jest.fn()
      };

      const result = EnvUtils.isWebWorker();

      expect(result).toBe(true);
    });

    it('should return false when self is undefined', () => {
      const result = EnvUtils.isWebWorker();

      expect(result).toBe(false);
    });

    it('should return false when importScripts is undefined', () => {
      (global as any).self = {};

      const result = EnvUtils.isWebWorker();

      expect(result).toBe(false);
    });

    it('should return false when importScripts is not a function', () => {
      (global as any).self = {
        importScripts: 'not-a-function'
      };

      const result = EnvUtils.isWebWorker();

      expect(result).toBe(false);
    });
  });

  describe('isReactNative', () => {
    it('should return true when navigator.product is ReactNative', () => {
      (global as any).navigator = {
        product: 'ReactNative'
      };

      const result = EnvUtils.isReactNative();

      expect(result).toBe(true);
    });

    it('should return false when navigator is undefined', () => {
      const result = EnvUtils.isReactNative();

      expect(result).toBe(false);
    });

    it('should return false when navigator.product is not ReactNative', () => {
      (global as any).navigator = {
        product: 'Gecko'
      };

      const result = EnvUtils.isReactNative();

      expect(result).toBe(false);
    });
  });

  describe('isElectron', () => {
    it('should return true when window.process.type is renderer', () => {
      (global as any).window = {
        process: {
          type: 'renderer'
        }
      };

      const result = EnvUtils.isElectron();

      expect(result).toBe(true);
    });

    it('should return false when window is undefined', () => {
      const result = EnvUtils.isElectron();

      expect(result).toBe(false);
    });

    it('should return false when window.process is undefined', () => {
      (global as any).window = {};

      const result = EnvUtils.isElectron();

      expect(result).toBe(false);
    });

    it('should return false when window.process is not an object', () => {
      (global as any).window = {
        process: 'not-an-object'
      };

      const result = EnvUtils.isElectron();

      expect(result).toBe(false);
    });

    it('should return false when window.process.type is not renderer', () => {
      (global as any).window = {
        process: {
          type: 'main'
        }
      };

      const result = EnvUtils.isElectron();

      expect(result).toBe(false);
    });
  });

  describe('getDefaultStorage', () => {
    it('should return MemoryTokenStorage for Node.js environment', () => {
      (global as any).process = {
        versions: {
          node: '16.0.0'
        }
      };

      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });

    it('should return LocalTokenStorage for browser environment', () => {
      (global as any).window = { document: {} };

      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(LocalTokenStorage);
    });

    it('should return MemoryTokenStorage for Web Worker environment', () => {
      (global as any).self = {
        importScripts: jest.fn()
      };

      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });

    it('should return MemoryTokenStorage for unknown environment', () => {
      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });

    it('should prioritize Node.js detection over browser', () => {
      // Both Node and browser globals present
      (global as any).process = {
        versions: {
          node: '16.0.0'
        }
      };
      (global as any).window = { document: {} };

      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });

    it('should prioritize browser detection over Web Worker', () => {
      // Both browser and web worker globals present
      (global as any).window = { document: {} };
      (global as any).self = {
        importScripts: jest.fn()
      };

      const storage = EnvUtils.getDefaultStorage();

      expect(storage).toBeInstanceOf(LocalTokenStorage);
    });
  });

  describe('getEnvironment', () => {
    it('should return "node" for Node.js environment', () => {
      (global as any).process = {
        versions: {
          node: '16.0.0'
        }
      };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('node');
    });

    it('should return "browser" for browser environment', () => {
      (global as any).window = { document: {} };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('browser');
    });

    it('should return "webworker" for Web Worker environment', () => {
      (global as any).self = {
        importScripts: jest.fn()
      };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('webworker');
    });

    it('should return "react-native" for React Native environment', () => {
      (global as any).navigator = {
        product: 'ReactNative'
      };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('react-native');
    });

    it('should return "electron" for Electron environment', () => {
      (global as any).window = {
        process: {
          type: 'renderer'
        }
      };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('electron');
    });

    it('should return "unknown" for unrecognized environment', () => {
      const env = EnvUtils.getEnvironment();

      expect(env).toBe('unknown');
    });

    it('should prioritize node over browser in environment detection', () => {
      (global as any).process = {
        versions: {
          node: '16.0.0'
        }
      };
      (global as any).window = { document: {} };

      const env = EnvUtils.getEnvironment();

      expect(env).toBe('node');
    });
  });

  describe('hasLocalStorage', () => {
    it('should return true when localStorage is available and working', () => {
      const mockLocalStorage = {
        setItem: jest.fn(),
        removeItem: jest.fn()
      };
      (global as any).localStorage = mockLocalStorage;

      const result = EnvUtils.hasLocalStorage();

      expect(result).toBe(true);
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('__plinto_test__', '__plinto_test__');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('__plinto_test__');
    });

    it('should return false when localStorage throws on setItem', () => {
      const mockLocalStorage = {
        setItem: jest.fn().mockImplementation(() => {
          throw new Error('Storage quota exceeded');
        }),
        removeItem: jest.fn()
      };
      (global as any).localStorage = mockLocalStorage;

      const result = EnvUtils.hasLocalStorage();

      expect(result).toBe(false);
    });

    it('should return false when localStorage throws on removeItem', () => {
      const mockLocalStorage = {
        setItem: jest.fn(),
        removeItem: jest.fn().mockImplementation(() => {
          throw new Error('Storage not available');
        })
      };
      (global as any).localStorage = mockLocalStorage;

      const result = EnvUtils.hasLocalStorage();

      expect(result).toBe(false);
    });

    it('should return false when localStorage is undefined', () => {
      const result = EnvUtils.hasLocalStorage();

      expect(result).toBe(false);
    });
  });

  describe('hasSessionStorage', () => {
    it('should return true when sessionStorage is available and working', () => {
      const mockSessionStorage = {
        setItem: jest.fn(),
        removeItem: jest.fn()
      };
      (global as any).sessionStorage = mockSessionStorage;

      const result = EnvUtils.hasSessionStorage();

      expect(result).toBe(true);
      expect(mockSessionStorage.setItem).toHaveBeenCalledWith('__plinto_test__', '__plinto_test__');
      expect(mockSessionStorage.removeItem).toHaveBeenCalledWith('__plinto_test__');
    });

    it('should return false when sessionStorage throws on setItem', () => {
      const mockSessionStorage = {
        setItem: jest.fn().mockImplementation(() => {
          throw new Error('Storage quota exceeded');
        }),
        removeItem: jest.fn()
      };
      (global as any).sessionStorage = mockSessionStorage;

      const result = EnvUtils.hasSessionStorage();

      expect(result).toBe(false);
    });

    it('should return false when sessionStorage throws on removeItem', () => {
      const mockSessionStorage = {
        setItem: jest.fn(),
        removeItem: jest.fn().mockImplementation(() => {
          throw new Error('Storage not available');
        })
      };
      (global as any).sessionStorage = mockSessionStorage;

      const result = EnvUtils.hasSessionStorage();

      expect(result).toBe(false);
    });

    it('should return false when sessionStorage is undefined', () => {
      const result = EnvUtils.hasSessionStorage();

      expect(result).toBe(false);
    });
  });

  describe('hasCrypto', () => {
    it('should return true when crypto with subtle is available', () => {
      (global as any).crypto = {
        subtle: {}
      };

      const result = EnvUtils.hasCrypto();

      expect(result).toBe(true);
    });

    it('should return false when crypto is undefined', () => {
      const result = EnvUtils.hasCrypto();

      expect(result).toBe(false);
    });

    it('should return false when crypto.subtle is undefined', () => {
      (global as any).crypto = {};

      const result = EnvUtils.hasCrypto();

      expect(result).toBe(false);
    });
  });

  describe('getUserAgent', () => {
    it('should return navigator.userAgent in browser environment', () => {
      (global as any).window = { document: {} };
      (global as any).navigator = {
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      };

      const userAgent = EnvUtils.getUserAgent();

      expect(userAgent).toBe('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
    });

    it('should return Node.js version in Node environment', () => {
      (global as any).process = {
        versions: {
          node: '16.14.0'
        },
        version: 'v16.14.0'
      };

      const userAgent = EnvUtils.getUserAgent();

      expect(userAgent).toBe('Node.js/v16.14.0');
    });

    it('should return "Unknown" for unknown environment', () => {
      const userAgent = EnvUtils.getUserAgent();

      expect(userAgent).toBe('Unknown');
    });

    it('should prioritize Node.js over browser for user agent', () => {
      (global as any).process = {
        versions: {
          node: '16.14.0'
        },
        version: 'v16.14.0'
      };
      (global as any).window = { document: {} };
      (global as any).navigator = {
        userAgent: 'Mozilla/5.0'
      };

      const userAgent = EnvUtils.getUserAgent();

      expect(userAgent).toBe('Node.js/v16.14.0');
    });

    it('should handle missing navigator in browser environment', () => {
      (global as any).window = { document: {} };

      const userAgent = EnvUtils.getUserAgent();

      expect(userAgent).toBe('Unknown');
    });
  });
});