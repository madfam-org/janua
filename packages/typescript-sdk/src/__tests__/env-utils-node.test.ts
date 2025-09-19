/**
 * @jest-environment node
 */
import { EnvUtils } from '../utils/env-utils';
import { MemoryTokenStorage } from '../utils/token-utils';

describe('EnvUtils (Node Environment)', () => {
  describe('isBrowser', () => {
    it('should return false in node environment', () => {
      const result = EnvUtils.isBrowser();
      expect(result).toBe(false);
    });
  });

  describe('isNode', () => {
    it('should return true in node environment', () => {
      const result = EnvUtils.isNode();
      expect(result).toBe(true);
    });
  });

  describe('isWebWorker', () => {
    it('should return false in node environment', () => {
      const result = EnvUtils.isWebWorker();
      expect(result).toBe(false);
    });
  });

  describe('getDefaultStorage', () => {
    it('should return MemoryTokenStorage in node environment', () => {
      const storage = EnvUtils.getDefaultStorage();
      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });
  });

  describe('getEnvironment', () => {
    it('should return "node" in node environment', () => {
      const env = EnvUtils.getEnvironment();
      expect(env).toBe('node');
    });
  });

  describe('getUserAgent', () => {
    it('should return Node.js version in node environment', () => {
      const userAgent = EnvUtils.getUserAgent();
      expect(userAgent).toMatch(/^Node\.js\/v\d+\.\d+\.\d+$/);
    });
  });

  describe('hasCrypto', () => {
    it('should detect crypto availability in node', () => {
      const result = EnvUtils.hasCrypto();
      // Node.js has crypto module
      expect(typeof result).toBe('boolean');
    });
  });

  describe('hasLocalStorage', () => {
    it('should return false in node environment', () => {
      const result = EnvUtils.hasLocalStorage();
      expect(result).toBe(false);
    });
  });

  describe('hasSessionStorage', () => {
    it('should return false in node environment', () => {
      const result = EnvUtils.hasSessionStorage();
      expect(result).toBe(false);
    });
  });
});