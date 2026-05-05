/**
 * Retry policy with circuit breaker for Janua auth calls.
 *
 * Prevents the "auth storm" failure mode where a transient CORS / network /
 * 401 failure on `/auth/me` causes an unbounded burst of retries — observed
 * in production as 170+ requests in 6 seconds.
 *
 * Behavior:
 *   - Exponential backoff with jitter: 1s -> 2s -> 4s -> 8s -> 30s cap, +/-20% jitter.
 *   - Circuit breaker: after `MAX_FAILURES` (5) consecutive failures, transition
 *     to `circuit-broken`. No further automatic retries until `manualReset()` is
 *     called or `noteSuccess()` is invoked from another path.
 *   - CORS errors short-circuit retries on the SAME attempt (a CORS misconfig
 *     is not a transient error and retrying within the same render cycle just
 *     amplifies the storm). Each CORS failure still counts toward the circuit
 *     breaker.
 *
 * This module is pure — no React, no DOM. Side effects are managed by the
 * provider that owns a RetryController instance.
 */

export const DEFAULT_MAX_FAILURES = 5;
export const DEFAULT_FAILURE_WINDOW_MS = 30_000;
export const DEFAULT_BASE_DELAY_MS = 1_000;
export const DEFAULT_MAX_DELAY_MS = 30_000;
export const DEFAULT_BACKOFF_MULTIPLIER = 2;
export const DEFAULT_JITTER = 0.2;

export type CircuitState = 'closed' | 'open' | 'half-open';

export interface RetryControllerOptions {
  maxFailures?: number;
  failureWindowMs?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  backoffMultiplier?: number;
  jitter?: number;
  /** Inject for deterministic tests. Default: Math.random. */
  random?: () => number;
  /** Inject for deterministic tests. Default: Date.now. */
  now?: () => number;
}

export interface RetrySnapshot {
  state: CircuitState;
  consecutiveFailures: number;
  lastFailureAt: number | null;
  nextRetryAt: number | null;
}

/**
 * Detect CORS / network-level failures that the browser exposes as opaque
 * errors. These are NOT transient and must not retry within the same cycle.
 *
 * The browser does not give us a status code for CORS-blocked responses; the
 * fetch promise rejects with a generic TypeError whose message varies by
 * engine ("Failed to fetch", "Load failed", "NetworkError when attempting to
 * fetch resource"). We treat ANY TypeError on a fetch path as a CORS-class
 * failure for retry purposes.
 */
export function isCorsOrNetworkError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  if (error instanceof TypeError) return true;
  // Heuristic: some SDK wrappers wrap the original error
  const anyErr = error as { name?: string; message?: string; cause?: unknown };
  if (anyErr.name === 'TypeError') return true;
  const msg = (anyErr.message || '').toLowerCase();
  if (
    msg.includes('failed to fetch') ||
    msg.includes('load failed') ||
    msg.includes('networkerror') ||
    msg.includes('cors')
  ) {
    return true;
  }
  if (anyErr.cause && anyErr.cause !== error) {
    return isCorsOrNetworkError(anyErr.cause);
  }
  return false;
}

/**
 * Compute the next backoff delay for a given attempt index (0-indexed).
 * Returns ms with +/- jitter applied.
 */
export function backoffDelay(
  attempt: number,
  opts: Required<
    Pick<RetryControllerOptions, 'baseDelayMs' | 'maxDelayMs' | 'backoffMultiplier' | 'jitter'>
  > & { random: () => number }
): number {
  const raw = opts.baseDelayMs * Math.pow(opts.backoffMultiplier, Math.max(0, attempt));
  const capped = Math.min(raw, opts.maxDelayMs);
  // Jitter: uniform in [-jitter, +jitter]
  const jitterFactor = 1 + (opts.random() * 2 - 1) * opts.jitter;
  return Math.max(0, Math.round(capped * jitterFactor));
}

/**
 * Stateful retry controller. One instance per auth context.
 *
 * Usage:
 *   const ctrl = new RetryController();
 *   if (!ctrl.canAttempt()) return; // circuit broken
 *   try { await fetch(...); ctrl.noteSuccess(); }
 *   catch (e) { ctrl.noteFailure(e); ... }
 *
 *   // Schedule next attempt:
 *   const delayMs = ctrl.nextDelayMs();
 *   setTimeout(retry, delayMs);
 */
export class RetryController {
  private opts: Required<RetryControllerOptions>;
  private consecutiveFailures = 0;
  private lastFailureAt: number | null = null;
  private nextRetryAt: number | null = null;
  private state: CircuitState = 'closed';

  constructor(options: RetryControllerOptions = {}) {
    this.opts = {
      maxFailures: options.maxFailures ?? DEFAULT_MAX_FAILURES,
      failureWindowMs: options.failureWindowMs ?? DEFAULT_FAILURE_WINDOW_MS,
      baseDelayMs: options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS,
      maxDelayMs: options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS,
      backoffMultiplier: options.backoffMultiplier ?? DEFAULT_BACKOFF_MULTIPLIER,
      jitter: options.jitter ?? DEFAULT_JITTER,
      random: options.random ?? Math.random,
      now: options.now ?? Date.now,
    };
  }

  /**
   * True if the controller permits an attempt RIGHT NOW. Returns false if:
   *   - Circuit is open (broken), waiting for manual reset.
   *   - We are still inside the backoff window for the next retry.
   */
  canAttempt(): boolean {
    if (this.state === 'open') return false;
    if (this.nextRetryAt !== null && this.opts.now() < this.nextRetryAt) {
      return false;
    }
    return true;
  }

  /** True if the circuit has tripped. UI should show error + manual retry. */
  isCircuitBroken(): boolean {
    return this.state === 'open';
  }

  noteSuccess(): void {
    this.consecutiveFailures = 0;
    this.lastFailureAt = null;
    this.nextRetryAt = null;
    this.state = 'closed';
  }

  /**
   * Record a failure. Returns the next scheduled retry-at timestamp, or null
   * if the circuit just tripped.
   */
  noteFailure(_error?: unknown): number | null {
    this.consecutiveFailures += 1;
    this.lastFailureAt = this.opts.now();

    if (this.consecutiveFailures >= this.opts.maxFailures) {
      this.state = 'open';
      this.nextRetryAt = null;
      return null;
    }

    const delay = backoffDelay(this.consecutiveFailures - 1, this.opts);
    this.nextRetryAt = this.opts.now() + delay;
    return this.nextRetryAt;
  }

  /** Compute backoff for the NEXT attempt without recording a failure. */
  nextDelayMs(): number {
    return backoffDelay(this.consecutiveFailures, this.opts);
  }

  /**
   * Manual reset — called when the user explicitly retries (button click)
   * or when a successful auth event fires from another path.
   */
  manualReset(): void {
    this.consecutiveFailures = 0;
    this.lastFailureAt = null;
    this.nextRetryAt = null;
    this.state = 'closed';
  }

  snapshot(): RetrySnapshot {
    return {
      state: this.state,
      consecutiveFailures: this.consecutiveFailures,
      lastFailureAt: this.lastFailureAt,
      nextRetryAt: this.nextRetryAt,
    };
  }
}
