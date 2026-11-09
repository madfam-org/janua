// @vitest-environment node
/**
 * Server render regression with the REAL SDK client (no mock): JanuaProvider
 * builds a JanuaClient on every server render. Before the SDK fix each one
 * left a permanent 60 s interval holding the whole request in memory
 * (Next.js apps ran out of heap). Server renders must leave no timers.
 */
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { JanuaProvider } from './provider';

function activeTimeouts(): number {
  return process.getActiveResourcesInfo().filter((r) => r === 'Timeout').length;
}

describe('JanuaProvider server render', () => {
  it('runs without a window (precondition)', () => {
    expect(typeof window).toBe('undefined');
  });

  it('leaves no intervals after N server renders', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
    const before = activeTimeouts();

    for (let i = 0; i < 100; i++) {
      const html = renderToString(
        <JanuaProvider config={{ baseURL: 'https://auth.example.test' }}>
          <p>{`page ${i}`}</p>
        </JanuaProvider>
      );
      expect(html).toContain(`page ${i}`);
    }

    expect(setIntervalSpy).not.toHaveBeenCalled();
    expect(activeTimeouts()).toBe(before);
    setIntervalSpy.mockRestore();
  });
});
