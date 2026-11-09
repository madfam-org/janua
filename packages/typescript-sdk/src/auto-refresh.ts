/**
 * Background token-refresh timer for JanuaClient.
 *
 * The timer runs only where a browser `window` exists. On a server (or any
 * runtime without `window`) a JanuaClient is short-lived and per-request:
 * `<JanuaProvider>` builds one on every server render. A never-cleared
 * `setInterval` there pinned each request (headers, response, render stream)
 * in memory forever, and Next.js apps ran out of heap. Server code keeps
 * working without it: the HTTP client still refreshes on demand when a
 * request comes back 401.
 */

/** How often the browser client checks whether the access token is near expiry. */
export const AUTO_REFRESH_INTERVAL_MS = 60_000;

/** True when a browser-like global `window` exists (browsers, React Native, jsdom). */
export function hasBrowserWindow(): boolean {
  return typeof window !== 'undefined';
}

/**
 * Let a Node timer stop holding the process open. Browser timers are plain
 * numbers and are left alone.
 */
export function unrefTimer(timer: unknown): void {
  if (timer !== null && typeof timer === 'object') {
    const unref = (timer as { unref?: unknown }).unref;
    if (typeof unref === 'function') unref.call(timer);
  }
}

/** One restartable interval. `start()` is a no-op without a browser window. */
export class AutoRefreshTimer {
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private readonly tick: () => void,
    private readonly intervalMs: number = AUTO_REFRESH_INTERVAL_MS
  ) {}

  /** Whether the interval is currently scheduled. */
  get active(): boolean {
    return this.timer !== null;
  }

  /**
   * Schedule the interval if it is not already running.
   * Returns whether it is running afterwards (always false without `window`).
   */
  start(): boolean {
    if (this.timer !== null) return true;
    if (!hasBrowserWindow()) return false;
    this.timer = setInterval(this.tick, this.intervalMs);
    unrefTimer(this.timer);
    return true;
  }

  /** Clear the interval. Safe to call repeatedly. */
  stop(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
