import { waitFor } from '@testing-library/react'
import { vi } from 'vitest'

/**
 * Test utilities for common testing patterns
 */

/**
 * Setup mock time for consistent timestamp testing
 * @param date - ISO date string to set as current time
 * @example
 * setupMockTime('2025-11-19T00:00:00Z')
 */
export const setupMockTime = (date: string = '2025-11-19T00:00:00Z') => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(date))
}

/**
 * Restore real timers after using mock time
 */
export const restoreRealTime = () => {
  vi.useRealTimers()
}

/**
 * Flexible matcher for relative time strings
 * Matches formats like: "5m ago", "2h ago", "1d ago", "Just now"
 * @param text - Text to validate
 * @returns boolean indicating if text matches relative time format
 */
export const isRelativeTime = (text: string): boolean => {
  return /^(\d+[smhd] ago|Just now|a few (seconds|minutes|hours|days) ago)$/i.test(text)
}

/**
 * Wait for element with retry logic
 * Useful for async-rendered elements
 * @param queryFn - Function that queries for the element
 * @param options - waitFor options
 */
export const waitForElement = async <T>(
  queryFn: () => T,
  options?: { timeout?: number; interval?: number }
) => {
  return await waitFor(queryFn, {
    timeout: options?.timeout ?? 3000,
    interval: options?.interval ?? 50,
  })
}

/**
 * Create a deferred promise for controlling async flow in tests
 * @example
 * const deferred = createDeferred()
 * mockApi.mockReturnValue(deferred.promise)
 * // ... trigger async operation
 * deferred.resolve(data)
 */
export const createDeferred = <T>() => {
  let resolve: (value: T) => void
  let reject: (reason?: any) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve: resolve!, reject: reject! }
}

/**
 * Mock Date.now() to return a specific timestamp
 * @param timestamp - Timestamp in milliseconds or ISO string
 */
export const mockDateNow = (timestamp: number | string) => {
  const time = typeof timestamp === 'string' ? new Date(timestamp).getTime() : timestamp
  vi.spyOn(Date, 'now').mockReturnValue(time)
}

/**
 * Advance timers and wait for async operations
 * Useful when testing components with setTimeout/setInterval
 * @param ms - Milliseconds to advance
 */
export const advanceTimersAndWait = async (ms: number) => {
  await vi.advanceTimersByTimeAsync(ms)
  await waitFor(() => {}, { timeout: 100 })
}
