/**
 * Tests for retry utilities
 */
import { RetryUtils, RetryOptions } from '../utils/retry-utils';

describe('RetryUtils', () => {
  beforeEach(() => {
    jest.clearAllTimers();
  });

  describe('DEFAULT_OPTIONS', () => {
    it('should have correct default values', () => {
      expect(RetryUtils.DEFAULT_OPTIONS).toEqual({
        maxAttempts: 3,
        initialDelay: 1000,
        maxDelay: 10000,
        backoffMultiplier: 2,
        shouldRetry: expect.any(Function),
        onRetry: expect.any(Function)
      });
    });

    it('should have default shouldRetry that returns true', () => {
      expect(RetryUtils.DEFAULT_OPTIONS.shouldRetry(new Error('test'))).toBe(true);
    });

    it('should have default onRetry that does nothing', () => {
      expect(() => RetryUtils.DEFAULT_OPTIONS.onRetry(1, new Error('test'))).not.toThrow();
    });
  });

  describe('withRetry', () => {
    it('should succeed on first attempt', async () => {
      const fn = jest.fn().mockResolvedValue('success');
      
      const result = await RetryUtils.withRetry(fn);
      
      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should retry on failure and eventually succeed', async () => {
      // Mock sleep to avoid actual delays
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const fn = jest.fn()
        .mockRejectedValueOnce(new Error('first failure'))
        .mockRejectedValueOnce(new Error('second failure'))
        .mockResolvedValue('success');
      
      const result = await RetryUtils.withRetry(fn);
      
      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(3);
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should fail after max attempts', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const error = new Error('persistent failure');
      const fn = jest.fn().mockRejectedValue(error);
      
      await expect(RetryUtils.withRetry(fn, { maxAttempts: 2 })).rejects.toThrow('persistent failure');
      expect(fn).toHaveBeenCalledTimes(2);
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should respect shouldRetry option', async () => {
      const error = new Error('non-retryable');
      const fn = jest.fn().mockRejectedValue(error);
      const shouldRetry = jest.fn().mockReturnValue(false);
      
      await expect(RetryUtils.withRetry(fn, { shouldRetry })).rejects.toThrow('non-retryable');
      expect(fn).toHaveBeenCalledTimes(1);
      expect(shouldRetry).toHaveBeenCalledWith(error);
    });

    it('should call onRetry callback', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const error = new Error('failure');
      const fn = jest.fn()
        .mockRejectedValueOnce(error)
        .mockResolvedValue('success');
      const onRetry = jest.fn();
      
      await RetryUtils.withRetry(fn, { onRetry });
      
      expect(onRetry).toHaveBeenCalledWith(1, error);
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should use custom retry options', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const fn = jest.fn()
        .mockRejectedValueOnce(new Error('failure'))
        .mockResolvedValue('success');
      
      const options: RetryOptions = {
        maxAttempts: 5,
        initialDelay: 500,
        maxDelay: 5000,
        backoffMultiplier: 1.5
      };
      
      const result = await RetryUtils.withRetry(fn, options);
      
      expect(result).toBe('success');
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should not retry when shouldRetry returns false on first failure', async () => {
      const error = new Error('immediate failure');
      const fn = jest.fn().mockRejectedValue(error);
      const shouldRetry = jest.fn().mockReturnValue(false);
      
      await expect(RetryUtils.withRetry(fn, { shouldRetry, maxAttempts: 3 })).rejects.toThrow('immediate failure');
      expect(fn).toHaveBeenCalledTimes(1);
      expect(shouldRetry).toHaveBeenCalledWith(error);
    });

    it('should throw last error when all attempts fail', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const lastError = new Error('last failure');
      const fn = jest.fn()
        .mockRejectedValueOnce(new Error('first failure'))
        .mockRejectedValue(lastError);
      
      await expect(RetryUtils.withRetry(fn, { maxAttempts: 2 })).rejects.toThrow('last failure');
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should throw last error when maxAttempts is reached and loop completes', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const lastError = new Error('final error');
      const fn = jest.fn().mockRejectedValue(lastError);
      
      // This should hit the throw lastError line after the for loop
      await expect(RetryUtils.withRetry(fn, { maxAttempts: 1 })).rejects.toThrow('final error');
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });
  });

  describe('calculateDelay', () => {
    it('should calculate exponential backoff', () => {
      const delay1 = RetryUtils.calculateDelay(1, 1000, 10000, 2);
      const delay2 = RetryUtils.calculateDelay(2, 1000, 10000, 2);
      const delay3 = RetryUtils.calculateDelay(3, 1000, 10000, 2);
      
      // Should be approximately 1000, 2000, 4000 (plus jitter)
      expect(delay1).toBeGreaterThanOrEqual(1000);
      expect(delay1).toBeLessThanOrEqual(1100);
      
      expect(delay2).toBeGreaterThanOrEqual(2000);
      expect(delay2).toBeLessThanOrEqual(2200);
      
      expect(delay3).toBeGreaterThanOrEqual(4000);
      expect(delay3).toBeLessThanOrEqual(4400);
    });

    it('should respect max delay', () => {
      const delay = RetryUtils.calculateDelay(10, 1000, 5000, 2);
      expect(delay).toBeLessThanOrEqual(5000);
    });

    it('should add jitter to prevent thundering herd', () => {
      const delays = Array.from({ length: 10 }, () =>
        RetryUtils.calculateDelay(1, 1000, 10000, 2)
      );
      
      // All delays should be slightly different due to jitter
      const uniqueDelays = new Set(delays);
      expect(uniqueDelays.size).toBeGreaterThan(1);
    });

    it('should handle edge cases', () => {
      // Zero initial delay
      const zeroDelay = RetryUtils.calculateDelay(1, 0, 1000, 2);
      expect(zeroDelay).toBeGreaterThanOrEqual(0);
      expect(zeroDelay).toBeLessThanOrEqual(1000);
      
      // Max delay smaller than calculated delay
      const cappedDelay = RetryUtils.calculateDelay(5, 1000, 500, 2);
      expect(cappedDelay).toBeLessThanOrEqual(500);
    });
  });

  describe('sleep', () => {
    it('should resolve after specified time', (done) => {
      jest.useFakeTimers();
      
      const sleepPromise = RetryUtils.sleep(1000);
      
      // Promise should not be resolved yet
      let resolved = false;
      sleepPromise.then(() => { 
        resolved = true;
        expect(resolved).toBe(true);
        jest.useRealTimers();
        done();
      });
      
      expect(resolved).toBe(false);
      
      // Fast-forward time
      jest.advanceTimersByTime(1000);
    });

    it('should handle zero delay', async () => {
      jest.useFakeTimers();
      
      const sleepPromise = RetryUtils.sleep(0);
      
      jest.advanceTimersByTime(0);
      
      await expect(sleepPromise).resolves.toBeUndefined();
      
      jest.useRealTimers();
    });
  });

  describe('isRetryableError', () => {
    it('should identify network errors by code', () => {
      expect(RetryUtils.isRetryableError({ code: 'ECONNRESET' })).toBe(true);
      expect(RetryUtils.isRetryableError({ code: 'ETIMEDOUT' })).toBe(true);
      expect(RetryUtils.isRetryableError({ code: 'OTHER_ERROR' })).toBe(false);
    });

    it('should identify retryable HTTP status codes', () => {
      expect(RetryUtils.isRetryableError({ status: 429 })).toBe(true); // Rate limit
      expect(RetryUtils.isRetryableError({ status: 502 })).toBe(true); // Bad gateway
      expect(RetryUtils.isRetryableError({ status: 503 })).toBe(true); // Service unavailable
      expect(RetryUtils.isRetryableError({ status: 504 })).toBe(true); // Gateway timeout
      expect(RetryUtils.isRetryableError({ status: 400 })).toBe(false); // Bad request
      expect(RetryUtils.isRetryableError({ status: 404 })).toBe(false); // Not found
    });

    it('should identify retryable error messages', () => {
      expect(RetryUtils.isRetryableError({ message: 'Network Error' })).toBe(true);
      expect(RetryUtils.isRetryableError({ message: 'timeout occurred' })).toBe(true);
      expect(RetryUtils.isRetryableError({ message: 'ECONNREFUSED connection' })).toBe(true);
      expect(RetryUtils.isRetryableError({ message: 'ENOTFOUND hostname' })).toBe(true);
      expect(RetryUtils.isRetryableError({ message: 'Validation failed' })).toBe(false);
    });

    it('should handle case insensitive message matching', () => {
      expect(RetryUtils.isRetryableError({ message: 'NETWORK ERROR' })).toBe(true);
      expect(RetryUtils.isRetryableError({ message: 'Timeout Occurred' })).toBe(true);
    });

    it('should return false for non-retryable errors', () => {
      expect(RetryUtils.isRetryableError({})).toBe(false);
      expect(RetryUtils.isRetryableError(null)).toBe(false);
      expect(RetryUtils.isRetryableError(undefined)).toBe(false);
      expect(RetryUtils.isRetryableError({ other: 'property' })).toBe(false);
    });
  });

  describe('createRetryable', () => {
    it('should create a retryable function', async () => {
      jest.spyOn(RetryUtils, 'sleep').mockResolvedValue(undefined);
      
      const originalFn = jest.fn()
        .mockRejectedValueOnce(new Error('failure'))
        .mockResolvedValue('success');
      
      const retryableFn = RetryUtils.createRetryable(originalFn);
      
      const result = await retryableFn('arg1', 'arg2');
      
      expect(result).toBe('success');
      expect(originalFn).toHaveBeenCalledWith('arg1', 'arg2');
      expect(originalFn).toHaveBeenCalledTimes(2);
      
      (RetryUtils.sleep as jest.Mock).mockRestore();
    });

    it('should pass custom options to retry logic', async () => {
      const originalFn = jest.fn().mockRejectedValue(new Error('failure'));
      const retryableFn = RetryUtils.createRetryable(originalFn, { maxAttempts: 1 });
      
      const promise = retryableFn();
      
      jest.runAllTimers();
      
      await expect(promise).rejects.toThrow('failure');
      expect(originalFn).toHaveBeenCalledTimes(1);
    });

    it('should preserve function signature and return type', async () => {
      const typedFn = async (a: string, b: number): Promise<boolean> => {
        return a.length > b;
      };
      
      const retryableTypedFn = RetryUtils.createRetryable(typedFn);
      
      const result = await retryableTypedFn('hello', 3);
      
      expect(result).toBe(true);
      expect(typeof result).toBe('boolean');
    });
  });

  describe('createCircuitBreaker', () => {
    it('should allow calls when circuit is closed', async () => {
      const fn = jest.fn().mockResolvedValue('success');
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn);
      
      const result = await circuitBreaker();
      
      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should open circuit after threshold failures', async () => {
      const error = new Error('service failure');
      const fn = jest.fn().mockRejectedValue(error);
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn, { threshold: 2 });
      
      // First failure
      await expect(circuitBreaker()).rejects.toThrow('service failure');
      
      // Second failure - should open circuit
      await expect(circuitBreaker()).rejects.toThrow('service failure');
      
      // Third call - circuit should be open
      await expect(circuitBreaker()).rejects.toThrow('Circuit breaker is open');
      
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('should transition to half-open after reset timeout', async () => {
      // Mock Date.now to control time
      const originalNow = Date.now;
      let currentTime = 1000;
      Date.now = jest.fn(() => currentTime);
      
      const error = new Error('service failure');
      const fn = jest.fn()
        .mockRejectedValueOnce(error)
        .mockRejectedValueOnce(error) // Open circuit
        .mockResolvedValue('success'); // Half-open success
      
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn, {
        threshold: 2,
        resetTimeout: 1000
      });
      
      // Trigger circuit opening
      await expect(circuitBreaker()).rejects.toThrow('service failure');
      await expect(circuitBreaker()).rejects.toThrow('service failure');
      
      // Circuit should be open
      await expect(circuitBreaker()).rejects.toThrow('Circuit breaker is open');
      
      // Fast-forward past reset timeout
      currentTime += 1000;
      
      // Should transition to half-open and succeed
      const result = await circuitBreaker();
      expect(result).toBe('success');
      
      Date.now = originalNow;
    });

    it('should reset circuit on successful half-open call', async () => {
      const originalNow = Date.now;
      let currentTime = 1000;
      Date.now = jest.fn(() => currentTime);
      
      const error = new Error('service failure');
      const fn = jest.fn()
        .mockRejectedValueOnce(error)
        .mockRejectedValueOnce(error) // Open circuit
        .mockResolvedValueOnce('success') // Half-open success
        .mockResolvedValue('continued success');
      
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn, {
        threshold: 2,
        resetTimeout: 1000
      });
      
      // Open circuit
      await expect(circuitBreaker()).rejects.toThrow();
      await expect(circuitBreaker()).rejects.toThrow();
      
      // Wait for reset timeout
      currentTime += 1000;
      
      // Half-open success
      await expect(circuitBreaker()).resolves.toBe('success');
      
      // Circuit should be closed now
      await expect(circuitBreaker()).resolves.toBe('continued success');
      
      Date.now = originalNow;
    });

    it('should handle timeout in circuit breaker', async () => {
      jest.useFakeTimers();
      
      const fn = jest.fn().mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve('delayed'), 2000))
      );
      
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn, { timeout: 1000 });
      
      const promise = circuitBreaker();
      
      // Fast-forward past timeout
      jest.advanceTimersByTime(1000);
      
      await expect(promise).rejects.toThrow('Timeout');
      
      jest.useRealTimers();
    });

    it('should use default options when not provided', async () => {
      const fn = jest.fn().mockResolvedValue('success');
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn);
      
      const result = await circuitBreaker();
      
      expect(result).toBe('success');
    });

    it('should maintain separate failure counts for multiple circuit breakers', async () => {
      const fn1 = jest.fn().mockRejectedValue(new Error('failure1'));
      const fn2 = jest.fn().mockResolvedValue('success2');
      
      const cb1 = RetryUtils.createCircuitBreaker(fn1, { threshold: 1 });
      const cb2 = RetryUtils.createCircuitBreaker(fn2, { threshold: 1 });
      
      // cb1 should fail and open
      await expect(cb1()).rejects.toThrow('failure1');
      await expect(cb1()).rejects.toThrow('Circuit breaker is open');
      
      // cb2 should still work
      await expect(cb2()).resolves.toBe('success2');
    });

    it('should handle race condition between timeout and success', async () => {
      jest.useFakeTimers();
      
      const fn = jest.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve('success'), 500))
      );
      
      const circuitBreaker = RetryUtils.createCircuitBreaker(fn, { timeout: 1000 });
      
      const promise = circuitBreaker();
      
      // Fast-forward to just before success
      jest.advanceTimersByTime(500);
      
      const result = await promise;
      expect(result).toBe('success');
      
      jest.useRealTimers();
    });
  });
});