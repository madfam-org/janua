'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { JanuaClient } from '@janua/typescript-sdk';
import type { User, Session, JanuaConfig } from '@janua/typescript-sdk';
import { validateState, retrievePKCEParams, clearPKCEParams } from '../utils/pkce';
import {
  RetryController,
  type CircuitState,
  type RetryControllerOptions,
  type RetrySnapshot,
  isCorsOrNetworkError,
} from './retry-policy';

/**
 * Auth state machine — exposed to consumers so UI can render the correct
 * surface (loading vs unauthenticated vs error vs circuit-broken).
 */
export type JanuaAuthStatus =
  | 'loading'
  | 'authenticated'
  | 'unauthenticated'
  | 'error'
  | 'circuit-broken';

interface JanuaContextValue {
  client: JanuaClient;
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  status: JanuaAuthStatus;
  error: Error | null;
  /** Snapshot of the retry controller — for diagnostics / dashboards. */
  retryState: RetrySnapshot;
  signOut: () => Promise<void>;
  updateUser: () => Promise<void>;
  /** User-triggered retry. Resets the circuit breaker and re-fetches. */
  manualRetry: () => Promise<void>;
}

const JanuaContext = createContext<JanuaContextValue | undefined>(undefined);

export interface JanuaProviderProps {
  children: React.ReactNode;
  config: JanuaConfig;
  onAuthChange?: (user: User | null) => void;
  /**
   * Periodic background re-check interval, in ms. Default 60s.
   * Background polling is automatically paused while the tab is hidden,
   * paused when the circuit breaker is open, and is *not* a retry
   * mechanism — failed background polls go through the same retry
   * controller.
   */
  pollIntervalMs?: number;
  /**
   * Override the retry controller policy. Primarily for tests; production
   * consumers should accept defaults (1s -> 30s, 5 fail circuit, 20% jitter).
   */
  retryOptions?: RetryControllerOptions;
}

export function JanuaProvider({
  children,
  config,
  onAuthChange,
  pollIntervalMs = 60_000,
  retryOptions,
}: JanuaProviderProps) {
  const [client] = useState(() => new JanuaClient(config));
  const [user, setUser] = useState<User | null>(null);
  const userRef = useRef<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [status, setStatus] = useState<JanuaAuthStatus>('loading');
  const [error, setError] = useState<Error | null>(null);
  const [retryState, setRetryState] = useState<RetrySnapshot>({
    state: 'closed',
    consecutiveFailures: 0,
    lastFailureAt: null,
    nextRetryAt: null,
  });

  // Per-provider retry controller. Survives renders.
  const retryRef = useRef<RetryController>(new RetryController(retryOptions));
  // Tracks the in-flight /auth/me request so we can cancel it on unmount /
  // supersession.
  const inFlightAbortRef = useRef<AbortController | null>(null);
  // Backoff timer for scheduled retries.
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Background poll timer.
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelInFlight = useCallback(() => {
    if (inFlightAbortRef.current) {
      inFlightAbortRef.current.abort();
      inFlightAbortRef.current = null;
    }
  }, []);

  const clearTimers = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (pollTimerRef.current !== null) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const publishRetryState = useCallback(() => {
    setRetryState(retryRef.current.snapshot());
  }, []);

  /**
   * Single source of truth for hitting /auth/me.
   * - Cancels prior in-flight request.
   * - Honors the circuit breaker.
   * - Updates state machine.
   * - Does NOT auto-retry. Scheduling is handled by the caller via
   *   scheduleRetryAfterFailure() so we never end up in a recursive loop.
   */
  const fetchAuthState = useCallback(
    async (opts: { source: 'init' | 'poll' | 'manual' | 'visibility' }) => {
      const ctrl = retryRef.current;
      if (!ctrl.canAttempt() && opts.source !== 'manual') {
        return;
      }

      cancelInFlight();
      const abort = new AbortController();
      inFlightAbortRef.current = abort;

      try {
        let currentUser: User | null = null;

        if (!config.skipRemoteAuth) {
          // NOTE: We rely on JanuaClient.auth.getCurrentUser() honoring
          // AbortSignal via its underlying http-client. If the SDK ignores
          // the signal we still safely no-op the result on unmount because
          // we check `abort.signal.aborted` below.
          currentUser = await client.auth.getCurrentUser();
        } else {
          const token =
            typeof window !== 'undefined' ? localStorage.getItem('janua_access_token') : null;
          if (token) {
            try {
              const payload = JSON.parse(
                atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
              );
              currentUser = { id: payload.sub, email: payload.email } as User;
            } catch {
              /* invalid token — treat as unauthenticated */
            }
          }
        }

        if (abort.signal.aborted) return;

        const accessToken = await client.getAccessToken();
        const refreshToken = await client.getRefreshToken();

        if (abort.signal.aborted) return;

        const currentSession = { accessToken, refreshToken } as unknown as Session;

        ctrl.noteSuccess();
        publishRetryState();

        setUser(currentUser);
        userRef.current = currentUser;
        setSession(currentSession);
        setStatus(currentUser ? 'authenticated' : 'unauthenticated');
        setError(null);
        if (onAuthChange) onAuthChange(currentUser);
      } catch (err) {
        if (abort.signal.aborted) return;

        const e = err as Error;
        ctrl.noteFailure(e);
        publishRetryState();

        // Surface the FIRST failure to UI; subsequent failures within the
        // window stay quiet (status already reflects the problem).
        setError(e);

        if (ctrl.isCircuitBroken()) {
          setStatus('circuit-broken');
        } else if (status !== 'authenticated') {
          // Don't downgrade an authenticated session on a transient blip
          setStatus('error');
        }

        // CORS / network failures: do NOT schedule a retry on the same
        // source path. The visibility API or a manual retry will recover.
        // For other errors (5xx, etc.) the controller's nextRetryAt drives
        // the next attempt.
        if (!ctrl.isCircuitBroken() && !isCorsOrNetworkError(e)) {
          scheduleRetryAfterFailure();
        }
      } finally {
        if (inFlightAbortRef.current === abort) {
          inFlightAbortRef.current = null;
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [client, config.skipRemoteAuth, onAuthChange, publishRetryState, cancelInFlight]
  );

  // Forward declaration (set below after fetchAuthState is bound).
  const scheduleRetryAfterFailureRef = useRef<() => void>(() => undefined);

  const scheduleRetryAfterFailure = useCallback(() => {
    scheduleRetryAfterFailureRef.current();
  }, []);

  useEffect(() => {
    scheduleRetryAfterFailureRef.current = () => {
      const ctrl = retryRef.current;
      const snap = ctrl.snapshot();
      if (snap.state === 'open' || snap.nextRetryAt === null) return;

      const delay = Math.max(0, snap.nextRetryAt - Date.now());
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
      }
      retryTimerRef.current = setTimeout(() => {
        retryTimerRef.current = null;
        // Don't auto-retry while the tab is hidden — saves the user from
        // returning to a circuit-broken state caused by background failures.
        if (typeof document !== 'undefined' && document.hidden) return;
        void fetchAuthState({ source: 'poll' });
      }, delay);
    };
  }, [fetchAuthState]);

  const updateUser = useCallback(async () => {
    await fetchAuthState({ source: 'manual' });
  }, [fetchAuthState]);

  const manualRetry = useCallback(async () => {
    retryRef.current.manualReset();
    publishRetryState();
    setError(null);
    setStatus('loading');
    await fetchAuthState({ source: 'manual' });
  }, [fetchAuthState, publishRetryState]);

  const signOut = useCallback(async () => {
    cancelInFlight();
    try {
      await client.auth.signOut();
      setUser(null);
      userRef.current = null;
      setSession(null);
      setStatus('unauthenticated');
      retryRef.current.manualReset();
      publishRetryState();

      if (onAuthChange) onAuthChange(null);
    } catch (e) {
      // Sign-out failure is surfaced but does not retry-storm; nothing to do.
      setError(e as Error);
    }
  }, [client, onAuthChange, cancelInFlight, publishRetryState]);

  // OAuth callback handling and initial auth state
  useEffect(() => {
    const urlParams =
      typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;

    if (urlParams && urlParams.has('code') && urlParams.has('state')) {
      const code = urlParams.get('code')!;
      const state = urlParams.get('state')!;

      if (!validateState(state)) {
        console.warn('OAuth state mismatch - possible CSRF attack');
        setIsLoading(false);
        setStatus('unauthenticated');
        return;
      }

      const pkceParams = retrievePKCEParams();
      const codeVerifier = pkceParams?.verifier;

      client.auth
        .handleOAuthCallback(code, codeVerifier || state)
        .then(() => {
          clearPKCEParams();
          window.history.replaceState({}, '', window.location.pathname);
          return fetchAuthState({ source: 'init' });
        })
        .catch(() => {
          clearPKCEParams();
          // Error captured inside fetchAuthState path on retry; here we just
          // mark unauthenticated.
          setStatus('unauthenticated');
        })
        .finally(() => setIsLoading(false));
    } else {
      void fetchAuthState({ source: 'init' }).finally(() => setIsLoading(false));
    }

    return () => {
      cancelInFlight();
      clearTimers();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  // Background polling — only runs when:
  //   - Not in skipRemoteAuth mode
  //   - Tab is visible
  //   - Circuit is closed
  //   - We have a token to validate
  useEffect(() => {
    if (config.skipRemoteAuth) return;
    if (typeof window === 'undefined') return;

    const schedule = () => {
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
      }
      pollTimerRef.current = setTimeout(async () => {
        pollTimerRef.current = null;
        if (typeof document !== 'undefined' && document.hidden) {
          schedule();
          return;
        }
        if (retryRef.current.isCircuitBroken()) {
          // No background polling while broken — wait for manual retry.
          return;
        }
        const hasToken = !!localStorage.getItem('janua_access_token');
        if (!hasToken) {
          schedule();
          return;
        }
        await fetchAuthState({ source: 'poll' });
        schedule();
      }, pollIntervalMs);
    };

    schedule();
    return () => {
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [config.skipRemoteAuth, pollIntervalMs, fetchAuthState]);

  // Visibility API — pause / resume on tab visibility changes.
  useEffect(() => {
    if (typeof document === 'undefined') return;

    const handleVisibility = () => {
      if (document.hidden) return;
      // Tab became visible. Don't auto-retry if circuit is broken — user
      // must explicitly hit the retry button.
      if (retryRef.current.isCircuitBroken()) return;

      // If we are currently in error state, attempt one recovery fetch now.
      // Otherwise, the next scheduled poll handles it.
      const snap = retryRef.current.snapshot();
      if (snap.consecutiveFailures > 0) {
        void fetchAuthState({ source: 'visibility' });
      } else if (status === 'authenticated' || status === 'unauthenticated') {
        // Cache stale on tab return — refresh exactly once.
        void fetchAuthState({ source: 'visibility' });
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [fetchAuthState, status]);

  // Proactive token auto-refresh before expiry — preserved from prior impl,
  // but now respects the circuit breaker so a broken refresh path does not
  // tight-loop schedule itself.
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const scheduleRefresh = async () => {
      if (cancelled) return;
      try {
        if (retryRef.current.isCircuitBroken()) {
          // Park the refresh loop until manual recovery.
          return;
        }
        const hasToken =
          typeof window !== 'undefined' && !!localStorage.getItem('janua_access_token');
        if (!hasToken) return;
        const accessToken = await client.getAccessToken();
        if (!accessToken) return;

        const parts = accessToken.split('.');
        if (parts.length !== 3) return;

        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
        const exp = payload.exp;
        if (!exp) return;

        const now = Math.floor(Date.now() / 1000);
        const timeUntilExpiry = exp - now;

        if (timeUntilExpiry < 60) {
          try {
            await client.auth.refreshToken();
          } catch {
            // Refresh failure is surfaced via the next /auth/me cycle.
          }
          timeoutId = setTimeout(scheduleRefresh, 30_000);
          return;
        }

        const delay = Math.max((timeUntilExpiry - 60) * 1000, 30_000);
        timeoutId = setTimeout(scheduleRefresh, delay);
      } catch {
        timeoutId = setTimeout(scheduleRefresh, 30_000);
      }
    };

    void scheduleRefresh();

    return () => {
      cancelled = true;
      if (timeoutId !== null) clearTimeout(timeoutId);
    };
  }, [client]);

  const value: JanuaContextValue = {
    client,
    user,
    session,
    isLoading,
    isAuthenticated: !!user && !!session,
    status,
    error,
    retryState,
    signOut,
    updateUser,
    manualRetry,
  };

  return <JanuaContext.Provider value={value}>{children}</JanuaContext.Provider>;
}

export function useJanua(): JanuaContextValue {
  const context = useContext(JanuaContext);
  if (!context) {
    throw new Error('useJanua must be used within a JanuaProvider');
  }
  return context;
}

export function useAuth() {
  const { client, user, session, isAuthenticated, isLoading, status, error, signOut, manualRetry } =
    useJanua();
  return {
    auth: client.auth,
    user,
    session,
    isAuthenticated,
    isLoading,
    status,
    error,
    signOut,
    manualRetry,
  };
}

export function useUser() {
  const { user, isLoading, updateUser } = useJanua();
  return {
    user,
    isLoading,
    updateUser,
  };
}

export function useOrganizations() {
  const { client } = useJanua();
  return client.organizations;
}

export type { CircuitState };
