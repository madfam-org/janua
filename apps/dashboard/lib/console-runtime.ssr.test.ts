/** @jest-environment node */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { lazyConsoleClient } from '@janua/ui/console-runtime'

it('creates no SDK, reads no browser credentials and makes no requests during SSR import', async () => {
  const factory = jest.fn(() => ({ request: jest.fn() }))
  const client = lazyConsoleClient('dashboard', factory)
  expect(factory).not.toHaveBeenCalled()
  expect(() => client.request()).toThrow('Console configuration unavailable')
  expect(factory).not.toHaveBeenCalled()
  await expect(import('./janua-client')).resolves.toBeDefined()
  expect(typeof document).toBe('undefined')
})

it('escapes public config as a data attribute, without an executable bootstrap', () => {
  const markup = renderToStaticMarkup(React.createElement('div', { hidden: true, 'data-config': JSON.stringify({ audience: 'synthetic-audience' }) }))
  expect(markup).toContain('&quot;audience&quot;')
  expect(markup).not.toContain('<script')
})
