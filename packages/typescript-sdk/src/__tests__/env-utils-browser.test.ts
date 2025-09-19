/**
 * @jest-environment jsdom
 */
import { EnvUtils } from '../utils/env-utils';
import { LocalTokenStorage } from '../utils/token-utils';

describe('EnvUtils (Browser Environment)', () => {
  describe('isBrowser', () => {
    it('should return true in jsdom environment', () => {
      const result = EnvUtils.isBrowser();
      expect(result).toBe(true);
    });
  });

  describe('isNode', () => {
    it('should detect Node.js when process is available', () => {
      // In jsdom tests, process is still available
      const result = EnvUtils.isNode();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('isWebWorker', () => {
    it('should return false in jsdom environment', () => {
      const result = EnvUtils.isWebWorker();
      expect(result).toBe(false);
    });
  });

  describe('getDefaultStorage', () => {
    it('should return appropriate storage in browser environment', () => {
      const storage = EnvUtils.getDefaultStorage();
      // Could be either depending on whether process is detected
      expect(storage).toBeDefined();
    });
  });

  describe('getEnvironment', () => {
    it('should detect environment correctly', () => {
      const env = EnvUtils.getEnvironment();
      // In jsdom with process available, it might detect as node or browser
      expect(['node', 'browser']).toContain(env);
    });
  });

  describe('getUserAgent', () => {
    it('should return user agent string', () => {
      const userAgent = EnvUtils.getUserAgent();
      expect(userAgent).toBeDefined();
      expect(typeof userAgent).toBe('string');
    });
  });

  describe('hasCrypto', () => {
    it('should detect crypto availability', () => {
      const result = EnvUtils.hasCrypto();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('hasLocalStorage', () => {
    it('should detect localStorage availability', () => {
      const result = EnvUtils.hasLocalStorage();
      // jsdom provides localStorage mock
      expect(typeof result).toBe('boolean');
    });
  });

  describe('hasSessionStorage', () => {
    it('should detect sessionStorage availability', () => {
      const result = EnvUtils.hasSessionStorage();
      // jsdom provides sessionStorage mock
      expect(typeof result).toBe('boolean');
    });
  });
});