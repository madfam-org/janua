import { 
  validateEmail,
  validatePassword,
  parseJWT,
  isTokenExpired,
  generateCodeChallenge,
  generateCodeVerifier,
  base64URLEncode,
  sha256,
  buildQueryString,
  parseQueryString,
  getCookie,
  setCookie,
  deleteCookie,
  debounce,
  throttle,
  retry,
  formatError,
  sanitizeInput,
  generateFingerprint,
  hashValue
} from '../utils';

describe('SDK Utils', () => {
  describe('validateEmail', () => {
    it('should validate correct email formats', () => {
      expect(validateEmail('user@example.com')).toBe(true);
      expect(validateEmail('user.name@example.com')).toBe(true);
      expect(validateEmail('user+tag@example.co.uk')).toBe(true);
    });

    it('should reject invalid email formats', () => {
      expect(validateEmail('invalid')).toBe(false);
      expect(validateEmail('@example.com')).toBe(false);
      expect(validateEmail('user@')).toBe(false);
      expect(validateEmail('user@.com')).toBe(false);
      expect(validateEmail('user@example')).toBe(false);
      expect(validateEmail('user @example.com')).toBe(false);
    });

    it('should handle edge cases', () => {
      expect(validateEmail('')).toBe(false);
      expect(validateEmail(null as any)).toBe(false);
      expect(validateEmail(undefined as any)).toBe(false);
      expect(validateEmail(123 as any)).toBe(false);
    });
  });

  describe('validatePassword', () => {
    it('should validate strong passwords', () => {
      expect(validatePassword('StrongP@ss123')).toBe(true);
      expect(validatePassword('Another$ecure1')).toBe(true);
      expect(validatePassword('C0mplex!Pass')).toBe(true);
    });

    it('should reject weak passwords', () => {
      expect(validatePassword('short')).toBe(false);
      expect(validatePassword('12345678')).toBe(false);
      expect(validatePassword('password')).toBe(false);
      expect(validatePassword('PASSWORD')).toBe(false);
      expect(validatePassword('Pass123')).toBe(false); // No special char
    });

    it('should enforce minimum length', () => {
      expect(validatePassword('Sh0rt!')).toBe(false);
      expect(validatePassword('L0nger!Pass')).toBe(true);
    });

    it('should require mixed case', () => {
      expect(validatePassword('lowercase123!')).toBe(false);
      expect(validatePassword('UPPERCASE123!')).toBe(false);
      expect(validatePassword('MixedCase123!')).toBe(true);
    });

    it('should require numbers', () => {
      expect(validatePassword('NoNumbers!Here')).toBe(false);
      expect(validatePassword('WithNumber1!')).toBe(true);
    });

    it('should require special characters', () => {
      expect(validatePassword('NoSpecialChar1')).toBe(false);
      expect(validatePassword('WithSpecial1!')).toBe(true);
    });
  });

  describe('parseJWT', () => {
    const validToken = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiZW1haWwiOiJqb2huQGV4YW1wbGUuY29tIiwiZXhwIjoxNzA0MDY3MjAwLCJpYXQiOjE3MDQwNjM2MDB9.signature';

    it('should parse valid JWT', () => {
      const parsed = parseJWT(validToken);
      expect(parsed).toHaveProperty('sub', '1234567890');
      expect(parsed).toHaveProperty('name', 'John Doe');
      expect(parsed).toHaveProperty('email', 'john@example.com');
      expect(parsed).toHaveProperty('exp');
      expect(parsed).toHaveProperty('iat');
    });

    it('should handle malformed tokens', () => {
      expect(parseJWT('invalid')).toBeNull();
      expect(parseJWT('invalid.token')).toBeNull();
      expect(parseJWT('invalid.token.signature')).toBeNull();
      expect(parseJWT('')).toBeNull();
    });

    it('should handle non-JWT strings', () => {
      expect(parseJWT('not-a-jwt')).toBeNull();
      expect(parseJWT('Bearer token')).toBeNull();
    });
  });

  describe('isTokenExpired', () => {
    it('should identify expired tokens', () => {
      const expiredToken = {
        exp: Math.floor(Date.now() / 1000) - 3600 // 1 hour ago
      };
      expect(isTokenExpired(expiredToken)).toBe(true);
    });

    it('should identify valid tokens', () => {
      const validToken = {
        exp: Math.floor(Date.now() / 1000) + 3600 // 1 hour from now
      };
      expect(isTokenExpired(validToken)).toBe(false);
    });

    it('should handle buffer time', () => {
      const almostExpired = {
        exp: Math.floor(Date.now() / 1000) + 30 // 30 seconds from now
      };
      expect(isTokenExpired(almostExpired, 60)).toBe(true); // With 60s buffer
      expect(isTokenExpired(almostExpired, 0)).toBe(false); // No buffer
    });

    it('should handle missing exp claim', () => {
      expect(isTokenExpired({})).toBe(true);
      expect(isTokenExpired({ iat: 123456 })).toBe(true);
    });
  });

  describe('PKCE functions', () => {
    describe('generateCodeVerifier', () => {
      it('should generate valid code verifier', () => {
        const verifier = generateCodeVerifier();
        expect(verifier).toMatch(/^[A-Za-z0-9\-._~]{43,128}$/);
        expect(verifier.length).toBeGreaterThanOrEqual(43);
        expect(verifier.length).toBeLessThanOrEqual(128);
      });

      it('should generate unique verifiers', () => {
        const verifier1 = generateCodeVerifier();
        const verifier2 = generateCodeVerifier();
        expect(verifier1).not.toBe(verifier2);
      });
    });

    describe('generateCodeChallenge', () => {
      it('should generate valid challenge from verifier', async () => {
        const verifier = generateCodeVerifier();
        const challenge = await generateCodeChallenge(verifier);
        expect(challenge).toMatch(/^[A-Za-z0-9\-_]+$/);
        expect(challenge).not.toContain('='); // No padding
        expect(challenge).not.toContain('+'); // URL safe
        expect(challenge).not.toContain('/'); // URL safe
      });

      it('should generate consistent challenge for same verifier', async () => {
        const verifier = 'test-verifier';
        const challenge1 = await generateCodeChallenge(verifier);
        const challenge2 = await generateCodeChallenge(verifier);
        expect(challenge1).toBe(challenge2);
      });
    });
  });

  describe('base64URLEncode', () => {
    it('should encode to URL-safe base64', () => {
      const input = new Uint8Array([255, 254, 253]);
      const encoded = base64URLEncode(input);
      expect(encoded).not.toContain('+');
      expect(encoded).not.toContain('/');
      expect(encoded).not.toContain('=');
    });

    it('should handle empty input', () => {
      const encoded = base64URLEncode(new Uint8Array([]));
      expect(encoded).toBe('');
    });
  });

  describe('sha256', () => {
    it('should hash strings consistently', async () => {
      const hash1 = await sha256('test-string');
      const hash2 = await sha256('test-string');
      expect(hash1).toEqual(hash2);
    });

    it('should produce different hashes for different inputs', async () => {
      const hash1 = await sha256('string1');
      const hash2 = await sha256('string2');
      expect(hash1).not.toEqual(hash2);
    });

    it('should handle empty strings', async () => {
      const hash = await sha256('');
      expect(hash).toBeDefined();
      expect(hash.length).toBeGreaterThan(0);
    });
  });

  describe('buildQueryString', () => {
    it('should build query string from object', () => {
      const params = {
        foo: 'bar',
        baz: 'qux',
        num: 123
      };
      const query = buildQueryString(params);
      expect(query).toBe('foo=bar&baz=qux&num=123');
    });

    it('should handle special characters', () => {
      const params = {
        url: 'https://example.com',
        text: 'hello world',
        special: 'a&b=c'
      };
      const query = buildQueryString(params);
      expect(query).toContain('url=https%3A%2F%2Fexample.com');
      expect(query).toContain('text=hello%20world');
      expect(query).toContain('special=a%26b%3Dc');
    });

    it('should skip null and undefined values', () => {
      const params = {
        foo: 'bar',
        null: null,
        undefined: undefined,
        empty: '',
        zero: 0
      };
      const query = buildQueryString(params);
      expect(query).toBe('foo=bar&empty=&zero=0');
      expect(query).not.toContain('null');
      expect(query).not.toContain('undefined');
    });

    it('should handle arrays', () => {
      const params = {
        items: ['a', 'b', 'c']
      };
      const query = buildQueryString(params);
      expect(query).toBe('items=a&items=b&items=c');
    });

    it('should handle empty object', () => {
      expect(buildQueryString({})).toBe('');
    });
  });

  describe('parseQueryString', () => {
    it('should parse query string to object', () => {
      const query = 'foo=bar&baz=qux&num=123';
      const params = parseQueryString(query);
      expect(params).toEqual({
        foo: 'bar',
        baz: 'qux',
        num: '123'
      });
    });

    it('should handle URL encoded values', () => {
      const query = 'url=https%3A%2F%2Fexample.com&text=hello%20world';
      const params = parseQueryString(query);
      expect(params).toEqual({
        url: 'https://example.com',
        text: 'hello world'
      });
    });

    it('should handle duplicate keys as arrays', () => {
      const query = 'item=a&item=b&item=c';
      const params = parseQueryString(query);
      expect(params).toEqual({
        item: ['a', 'b', 'c']
      });
    });

    it('should handle empty values', () => {
      const query = 'foo=&bar=baz';
      const params = parseQueryString(query);
      expect(params).toEqual({
        foo: '',
        bar: 'baz'
      });
    });

    it('should handle leading question mark', () => {
      const query = '?foo=bar';
      const params = parseQueryString(query);
      expect(params).toEqual({ foo: 'bar' });
    });

    it('should handle empty string', () => {
      expect(parseQueryString('')).toEqual({});
      expect(parseQueryString('?')).toEqual({});
    });
  });

  describe('Cookie functions', () => {
    beforeEach(() => {
      // Clear all cookies
      document.cookie.split(';').forEach(cookie => {
        const eqPos = cookie.indexOf('=');
        const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
      });
    });

    describe('setCookie', () => {
      it('should set cookie with value', () => {
        setCookie('test', 'value');
        expect(document.cookie).toContain('test=value');
      });

      it('should set cookie with expiry', () => {
        const expires = new Date(Date.now() + 86400000); // 1 day
        setCookie('test', 'value', { expires });
        expect(document.cookie).toContain('test=value');
      });

      it('should set cookie with path', () => {
        setCookie('test', 'value', { path: '/app' });
        // Note: Can't verify path in document.cookie
        expect(document.cookie).toContain('test=value');
      });

      it('should set secure cookie', () => {
        setCookie('test', 'value', { secure: true });
        // Note: Secure flag not visible in document.cookie
        expect(document.cookie).toContain('test=value');
      });

      it('should set SameSite cookie', () => {
        setCookie('test', 'value', { sameSite: 'Strict' });
        expect(document.cookie).toContain('test=value');
      });
    });

    describe('getCookie', () => {
      it('should get cookie value', () => {
        document.cookie = 'test=value';
        expect(getCookie('test')).toBe('value');
      });

      it('should return null for non-existent cookie', () => {
        expect(getCookie('nonexistent')).toBeNull();
      });

      it('should handle multiple cookies', () => {
        document.cookie = 'foo=bar';
        document.cookie = 'baz=qux';
        expect(getCookie('foo')).toBe('bar');
        expect(getCookie('baz')).toBe('qux');
      });

      it('should handle URL encoded values', () => {
        document.cookie = 'encoded=hello%20world';
        expect(getCookie('encoded')).toBe('hello world');
      });
    });

    describe('deleteCookie', () => {
      it('should delete cookie', () => {
        document.cookie = 'test=value';
        expect(getCookie('test')).toBe('value');
        
        deleteCookie('test');
        expect(getCookie('test')).toBeNull();
      });

      it('should handle non-existent cookie', () => {
        expect(() => deleteCookie('nonexistent')).not.toThrow();
      });
    });
  });

  describe('debounce', () => {
    jest.useFakeTimers();

    it('should debounce function calls', () => {
      const fn = jest.fn();
      const debounced = debounce(fn, 100);

      debounced();
      debounced();
      debounced();

      expect(fn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should pass latest arguments', () => {
      const fn = jest.fn();
      const debounced = debounce(fn, 100);

      debounced('first');
      debounced('second');
      debounced('third');

      jest.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledWith('third');
    });

    it('should reset timer on new calls', () => {
      const fn = jest.fn();
      const debounced = debounce(fn, 100);

      debounced();
      jest.advanceTimersByTime(50);
      debounced();
      jest.advanceTimersByTime(50);
      
      expect(fn).not.toHaveBeenCalled();
      
      jest.advanceTimersByTime(50);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });

  describe('throttle', () => {
    jest.useFakeTimers();

    it('should throttle function calls', () => {
      const fn = jest.fn();
      const throttled = throttle(fn, 100);

      throttled();
      throttled();
      throttled();

      expect(fn).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(100);
      throttled();
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should pass first call arguments', () => {
      const fn = jest.fn();
      const throttled = throttle(fn, 100);

      throttled('first');
      throttled('second');
      throttled('third');

      expect(fn).toHaveBeenCalledWith('first');
    });

    it('should allow calls after delay', () => {
      const fn = jest.fn();
      const throttled = throttle(fn, 100);

      throttled();
      expect(fn).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(50);
      throttled();
      expect(fn).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(50);
      throttled();
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });

  describe('retry', () => {
    it('should retry on failure', async () => {
      let attempts = 0;
      const fn = jest.fn(async () => {
        attempts++;
        if (attempts < 3) {
          throw new Error('Failed');
        }
        return 'success';
      });

      const result = await retry(fn, { maxAttempts: 3, delay: 0 });
      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(3);
    });

    it('should throw after max attempts', async () => {
      const fn = jest.fn(async () => {
        throw new Error('Always fails');
      });

      await expect(retry(fn, { maxAttempts: 3, delay: 0 }))
        .rejects.toThrow('Always fails');
      expect(fn).toHaveBeenCalledTimes(3);
    });

    it('should not retry on success', async () => {
      const fn = jest.fn(async () => 'success');

      const result = await retry(fn);
      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should apply exponential backoff', async () => {
      const fn = jest.fn(async () => {
        throw new Error('Failed');
      });

      const start = Date.now();
      await retry(fn, { 
        maxAttempts: 3, 
        delay: 100,
        backoff: 2
      }).catch(() => {});
      
      const duration = Date.now() - start;
      // 100ms + 200ms = 300ms minimum
      expect(duration).toBeGreaterThanOrEqual(300);
    });
  });

  describe('formatError', () => {
    it('should format Error objects', () => {
      const error = new Error('Test error');
      const formatted = formatError(error);
      expect(formatted).toBe('Test error');
    });

    it('should format error responses', () => {
      const error = {
        response: {
          data: {
            error: 'API error message'
          }
        }
      };
      const formatted = formatError(error);
      expect(formatted).toBe('API error message');
    });

    it('should format error with message property', () => {
      const error = { message: 'Custom error' };
      const formatted = formatError(error);
      expect(formatted).toBe('Custom error');
    });

    it('should format string errors', () => {
      const formatted = formatError('String error');
      expect(formatted).toBe('String error');
    });

    it('should handle unknown error types', () => {
      const formatted = formatError({ foo: 'bar' });
      expect(formatted).toBe('An unknown error occurred');
      
      const formatted2 = formatError(null);
      expect(formatted2).toBe('An unknown error occurred');
      
      const formatted3 = formatError(undefined);
      expect(formatted3).toBe('An unknown error occurred');
    });
  });

  describe('sanitizeInput', () => {
    it('should escape HTML entities', () => {
      const input = '<script>alert("XSS")</script>';
      const sanitized = sanitizeInput(input);
      expect(sanitized).toBe('&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;');
    });

    it('should handle special characters', () => {
      const input = '& < > " \' /';
      const sanitized = sanitizeInput(input);
      expect(sanitized).toBe('&amp; &lt; &gt; &quot; &#x27; &#x2F;');
    });

    it('should handle normal text', () => {
      const input = 'Normal text without special chars';
      const sanitized = sanitizeInput(input);
      expect(sanitized).toBe('Normal text without special chars');
    });

    it('should handle empty input', () => {
      expect(sanitizeInput('')).toBe('');
      expect(sanitizeInput(null as any)).toBe('');
      expect(sanitizeInput(undefined as any)).toBe('');
    });
  });

  describe('generateFingerprint', () => {
    it('should generate consistent fingerprint', () => {
      const fp1 = generateFingerprint();
      const fp2 = generateFingerprint();
      expect(fp1).toBe(fp2);
    });

    it('should include browser properties', () => {
      const fingerprint = generateFingerprint();
      expect(fingerprint).toBeDefined();
      expect(typeof fingerprint).toBe('string');
      expect(fingerprint.length).toBeGreaterThan(0);
    });
  });

  describe('hashValue', () => {
    it('should hash strings consistently', async () => {
      const hash1 = await hashValue('test');
      const hash2 = await hashValue('test');
      expect(hash1).toBe(hash2);
    });

    it('should produce different hashes for different inputs', async () => {
      const hash1 = await hashValue('test1');
      const hash2 = await hashValue('test2');
      expect(hash1).not.toBe(hash2);
    });

    it('should handle various input types', async () => {
      const hash1 = await hashValue('string');
      const hash2 = await hashValue(123);
      const hash3 = await hashValue({ key: 'value' });
      
      expect(hash1).toBeDefined();
      expect(hash2).toBeDefined();
      expect(hash3).toBeDefined();
      expect(hash1).not.toBe(hash2);
      expect(hash2).not.toBe(hash3);
    });
  });
});