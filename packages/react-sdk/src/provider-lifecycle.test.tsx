/**
 * JanuaProvider releases the SDK client's background token-refresh interval
 * on unmount, and keeps it running across a React Strict Mode remount.
 */
import React, { StrictMode } from 'react'
import { render, waitFor } from '@testing-library/react'
import { JanuaProvider, useJanua } from './provider'

const AUTO_REFRESH_MS = 60_000

function Probe() {
  const { isLoading } = useJanua()
  return <span data-testid="state">{isLoading ? 'loading' : 'ready'}</span>
}

/** Handles of the SDK's 60 s auto-refresh intervals that are still scheduled. */
function trackRefreshIntervals() {
  const live = new Set<unknown>()
  const setSpy = jest.spyOn(global, 'setInterval')
  const clearSpy = jest.spyOn(global, 'clearInterval')
  setSpy.mockImplementation(((fn: () => void, ms?: number) => {
    const handle = jest.requireActual('timers').setInterval(fn, ms)
    if (ms === AUTO_REFRESH_MS) live.add(handle)
    return handle
  }) as typeof setInterval)
  clearSpy.mockImplementation(((handle: never) => {
    live.delete(handle)
    return jest.requireActual('timers').clearInterval(handle)
  }) as typeof clearInterval)
  return {
    live,
    restore: () => {
      setSpy.mockRestore()
      clearSpy.mockRestore()
    },
  }
}

describe('JanuaProvider auto-refresh lifecycle (browser)', () => {
  let tracker: ReturnType<typeof trackRefreshIntervals>

  beforeEach(() => {
    window.localStorage.clear()
    tracker = trackRefreshIntervals()
  })

  afterEach(() => tracker.restore())

  it('runs the refresh interval while mounted and clears it on unmount', async () => {
    const { getByTestId, unmount } = render(
      <JanuaProvider config={{ baseURL: 'https://auth.example.test' }}>
        <Probe />
      </JanuaProvider>
    )
    await waitFor(() => expect(getByTestId('state')).toHaveTextContent('ready'))
    expect(tracker.live.size).toBe(1)

    unmount()

    expect(tracker.live.size).toBe(0)
  })

  it('keeps exactly one live interval through a Strict Mode remount, none after unmount', async () => {
    const { getByTestId, unmount } = render(
      <StrictMode>
        <JanuaProvider config={{ baseURL: 'https://auth.example.test' }}>
          <Probe />
        </JanuaProvider>
      </StrictMode>
    )
    await waitFor(() => expect(getByTestId('state')).toHaveTextContent('ready'))

    // Strict Mode also runs the useState initializer twice in development;
    // the discarded client's interval is the only extra one allowed.
    expect(tracker.live.size).toBeGreaterThanOrEqual(1)
    expect(tracker.live.size).toBeLessThanOrEqual(2)

    unmount()

    expect(tracker.live.size).toBeLessThanOrEqual(1)
  })

  it('starts nothing when autoRefreshTokens is false', async () => {
    const { getByTestId, unmount } = render(
      <JanuaProvider config={{ baseURL: 'https://auth.example.test', autoRefreshTokens: false }}>
        <Probe />
      </JanuaProvider>
    )
    await waitFor(() => expect(getByTestId('state')).toHaveTextContent('ready'))
    expect(tracker.live.size).toBe(0)
    unmount()
  })
})
