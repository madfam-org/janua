/**
 * @jest-environment node
 *
 * Server render regression: JanuaProvider builds a JanuaClient on every
 * server render. Before the SDK fix each one left a permanent 60 s interval
 * that kept the whole request in memory; server renders must now leave no
 * timers behind.
 */
import React from 'react'
import { renderToString } from 'react-dom/server'
import { JanuaProvider } from './provider'

function activeTimeouts(): number {
  return process.getActiveResourcesInfo().filter((r) => r === 'Timeout').length
}

describe('JanuaProvider server render', () => {
  it('runs without a window (precondition)', () => {
    expect(typeof window).toBe('undefined')
  })

  it('leaves no intervals after N server renders', () => {
    const setIntervalSpy = jest.spyOn(global, 'setInterval')
    const before = activeTimeouts()

    for (let i = 0; i < 100; i++) {
      const html = renderToString(
        <JanuaProvider config={{ baseURL: 'https://auth.example.test' }}>
          <p>{`page ${i}`}</p>
        </JanuaProvider>
      )
      expect(html).toContain(`page ${i}`)
    }

    expect(setIntervalSpy).not.toHaveBeenCalled()
    expect(activeTimeouts()).toBe(before)
    setIntervalSpy.mockRestore()
  })
})
