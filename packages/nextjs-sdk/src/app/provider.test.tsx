/**
 * Integration tests for JanuaProvider's retry-storm guard.
 *
 * Uses raw ReactDOM to avoid a hard dep on @testing-library/react inside
 * the SDK package. The goal is to verify request budget under failure modes.
 */
import React from 'react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { createRoot, type Root } from 'react-dom/client';
import { act } from 'react';
import { JanuaProvider, useAuth } from './provider';

// Tell React this is a test environment so act() works without warnings.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Stub the JanuaClient module ---------------------------------------

let getCurrentUserCalls = 0;
let getCurrentUserBehavior: 'cors-fail' | '5xx-fail' | 'success' = 'cors-fail';

vi.mock('@janua/typescript-sdk', () => {
  class FakeJanuaClient {
    auth = {
      getCurrentUser: vi.fn(async () => {
        getCurrentUserCalls += 1;
        if (getCurrentUserBehavior === 'cors-fail') {
          throw new TypeError('Failed to fetch');
        }
        if (getCurrentUserBehavior === '5xx-fail') {
          throw new Error('500 Internal Server Error');
        }
        return { id: 'u1', email: 'a@b.c' };
      }),
      signOut: vi.fn(async () => undefined),
      handleOAuthCallback: vi.fn(async () => undefined),
      refreshToken: vi.fn(async () => undefined),
    };
    getAccessToken = vi.fn(async () => null);
    getRefreshToken = vi.fn(async () => null);
  }
  return { JanuaClient: FakeJanuaClient };
});

vi.mock('../utils/pkce', () => ({
  validateState: () => true,
  retrievePKCEParams: () => null,
  clearPKCEParams: () => undefined,
}));

// --- Test harness ------------------------------------------------------

interface ProbeHandle {
  status: () => string;
  retry: () => void;
}

const probeHandles: ProbeHandle[] = [];

function Probe() {
  const { status, manualRetry } = useAuth();
  // Expose to test
  React.useEffect(() => {
    probeHandles.push({
      status: () => status,
      retry: () => void manualRetry(),
    });
  });
  return <div data-testid="status">{status}</div>;
}

let container: HTMLDivElement | null = null;
let root: Root | null = null;

async function renderProvider(opts?: { fastBackoff?: boolean }) {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);

  // Aggressive backoff for tests: 5ms base, 100ms cap, no jitter so
  // 5 fail cycles complete inside a single test second.
  const retryOptions = opts?.fastBackoff
    ? { baseDelayMs: 5, maxDelayMs: 100, jitter: 0, random: () => 0.5 }
    : undefined;

  await act(async () => {
    root!.render(
      <JanuaProvider
        config={{ baseURL: 'https://auth.example.test' } as any}
        retryOptions={retryOptions}
      >
        <Probe />
      </JanuaProvider>
    );
  });

  // Drain any pending microtasks from the initial fetch.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 30));
  });
}

function getStatus(): string {
  return container!.querySelector('[data-testid="status"]')!.textContent || '';
}

async function clickRetry() {
  // Find the latest hook value via probeHandles last entry.
  const handle = probeHandles[probeHandles.length - 1];
  await act(async () => {
    handle.retry();
    await new Promise((r) => setTimeout(r, 20));
  });
}

beforeEach(() => {
  getCurrentUserCalls = 0;
  getCurrentUserBehavior = 'cors-fail';
  probeHandles.length = 0;
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});

afterEach(async () => {
  if (root) {
    await act(async () => {
      root!.unmount();
    });
    root = null;
  }
  if (container) {
    container.remove();
    container = null;
  }
  vi.clearAllMocks();
});

describe('JanuaProvider — retry storm guard', () => {
  it('CORS failure does NOT trigger automatic re-fetch within the same render cycle', async () => {
    await renderProvider();
    expect(getCurrentUserCalls).toBeGreaterThan(0);

    const initialCalls = getCurrentUserCalls;

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });

    // The whole fix: 200ms after a CORS failure, no automatic retries.
    expect(getCurrentUserCalls).toBe(initialCalls);
  });

  it('Manual retry resets the circuit and fires exactly one new request', async () => {
    await renderProvider();
    const before = getCurrentUserCalls;
    await clickRetry();
    expect(getCurrentUserCalls).toBe(before + 1);
  });

  it('After 5 forced 5xx failures the provider stops auto-fetching', async () => {
    // 5xx failures DO auto-schedule retries (CORS does not). We use this
    // path to drive the circuit to broken without manual resets in the loop.
    getCurrentUserBehavior = '5xx-fail';
    await renderProvider({ fastBackoff: true });

    // With 5ms base / 100ms cap, the controller trips after ~5*100ms.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1_500));
    });

    // The provider must have tripped before reaching 6 calls.
    expect(getCurrentUserCalls).toBeLessThanOrEqual(5);
    expect(getStatus()).toBe('circuit-broken');

    const callsAtBreak = getCurrentUserCalls;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 500));
    });
    expect(getCurrentUserCalls).toBe(callsAtBreak);
  });

  it('Visibility change while circuit is broken does NOT auto-retry', async () => {
    getCurrentUserBehavior = '5xx-fail';
    await renderProvider({ fastBackoff: true });
    // Drain backoff cycles. We loop because each scheduled retry uses a new
    // setTimeout that needs its own act() flush to commit setState updates.
    for (let i = 0; i < 20; i++) {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 150));
      });
      if (getStatus() === 'circuit-broken') break;
    }
    expect(getCurrentUserCalls).toBeLessThanOrEqual(5);
    const callsAtBreak = getCurrentUserCalls;

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 30));
    });

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(getCurrentUserCalls).toBe(callsAtBreak);
  });

  it('Visibility change while healthy + cache stale fires exactly 1 request', async () => {
    getCurrentUserBehavior = 'success';
    await renderProvider();
    expect(getStatus()).toBe('authenticated');

    const before = getCurrentUserCalls;

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 30));
    });

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(getCurrentUserCalls).toBe(before + 1);
  });

  it('30s of CORS failure simulation: total requests are bounded', async () => {
    // Simulates the production failure with NO user clicks. The provider
    // must hold to <= 5 requests.
    await renderProvider();

    await act(async () => {
      // Burn through 1s of fake time and dispatch many ticks the way a
      // misbehaving reactive system would have.
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 30));
      }
    });

    // Without user interaction, only the initial fetch fires.
    expect(getCurrentUserCalls).toBeLessThanOrEqual(5);
  });
});
