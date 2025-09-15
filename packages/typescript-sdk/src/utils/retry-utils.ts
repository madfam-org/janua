/**
 * Retry and backoff utilities for resilient operations
 */

export interface RetryOptions {
  maxAttempts?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffMultiplier?: number;
  shouldRetry?: (error: any) => boolean;
  onRetry?: (attempt: number, error: any) => void;
}

export class RetryUtils {
  /**
   * Default retry options
   */
  static readonly DEFAULT_OPTIONS: Required<RetryOptions> = {
    maxAttempts: 3,
    initialDelay: 1000,
    maxDelay: 10000,
    backoffMultiplier: 2,
    shouldRetry: () => true,
    onRetry: () => {}
  };

  /**
   * Execute a function with retry logic
   */
  static async withRetry<T>(
    fn: () => Promise<T>,
    options: RetryOptions = {}
  ): Promise<T> {
    const opts = { ...this.DEFAULT_OPTIONS, ...options };
    let lastError: any;

    for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;

        if (attempt === opts.maxAttempts || !opts.shouldRetry(error)) {
          throw error;
        }

        opts.onRetry(attempt, error);

        const delay = this.calculateDelay(
          attempt,
          opts.initialDelay,
          opts.maxDelay,
          opts.backoffMultiplier
        );

        await this.sleep(delay);
      }
    }

    // This line should never be reached due to the logic above,
    // but TypeScript requires it for exhaustiveness
    throw lastError;
  }

  /**
   * Calculate exponential backoff delay
   */
  static calculateDelay(
    attempt: number,
    initialDelay: number,
    maxDelay: number,
    multiplier: number
  ): number {
    const delay = initialDelay * Math.pow(multiplier, attempt - 1);
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 0.1 * delay;
    return Math.min(delay + jitter, maxDelay);
  }

  /**
   * Sleep for specified milliseconds
   */
  static sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Check if error is retryable
   */
  static isRetryableError(error: any): boolean {
    // Handle null/undefined errors
    if (!error) {
      return false;
    }

    // Network errors
    if (error.code === 'ECONNRESET' || error.code === 'ETIMEDOUT') {
      return true;
    }

    // HTTP status codes that are retryable
    if (error.status) {
      // Retry on 429 (rate limit), 502 (bad gateway), 503 (service unavailable), 504 (gateway timeout)
      return [429, 502, 503, 504].includes(error.status);
    }

    // Retry on specific error messages
    if (error.message) {
      const retryableMessages = [
        'network error',
        'timeout',
        'ECONNREFUSED',
        'ENOTFOUND'
      ];
      return retryableMessages.some(msg =>
        error.message.toLowerCase().includes(msg.toLowerCase())
      );
    }

    return false;
  }

  /**
   * Create a retry-enabled function
   */
  static createRetryable<T extends (...args: any[]) => Promise<any>>(
    fn: T,
    options: RetryOptions = {}
  ): T {
    return (async (...args: Parameters<T>) => {
      return this.withRetry(() => fn(...args), options);
    }) as T;
  }

  /**
   * Retry with circuit breaker pattern
   */
  static createCircuitBreaker<T>(
    fn: () => Promise<T>,
    options: {
      threshold?: number;
      timeout?: number;
      resetTimeout?: number;
    } = {}
  ) {
    const state = {
      failures: 0,
      lastFailureTime: 0,
      state: 'closed' as 'closed' | 'open' | 'half-open'
    };

    const threshold = options.threshold || 5;
    const timeout = options.timeout || 60000;
    const resetTimeout = options.resetTimeout || 30000;

    return async (): Promise<T> => {
      // Check if circuit is open
      if (state.state === 'open') {
        const timeSinceFailure = Date.now() - state.lastFailureTime;
        if (timeSinceFailure < resetTimeout) {
          throw new Error('Circuit breaker is open');
        }
        // Try half-open state
        state.state = 'half-open';
      }

      try {
        const result = await Promise.race([
          fn(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('Timeout')), timeout)
          )
        ]);

        // Success - reset the circuit
        if (state.state === 'half-open') {
          state.state = 'closed';
        }
        state.failures = 0;

        return result;
      } catch (error) {
        state.failures++;
        state.lastFailureTime = Date.now();

        if (state.failures >= threshold) {
          state.state = 'open';
        }

        throw error;
      }
    };
  }
}