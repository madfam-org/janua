import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SettingsSection } from './settings-section'

const key = { id: 'fixture-key', name: 'Fixture key', key_prefix: 'fixture', scopes: ['read'], created_at: '2025-01-01T00:00:00Z', last_used: '2025-02-01T00:00:00Z', is_active: true }
const keyPage = { items: [key], total: 2, page: 1, per_page: 1 }
const branding = { id: 'fixture-branding', company_name: 'Fixture organization', branding_level: 'basic', is_enabled: true, primary_color: 'black', secondary_color: 'white', accent_color: 'gray', updated_at: '2025-01-01T00:00:00Z' }
const response = (data: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data } as Response)
const fetchMock = jest.fn()
const targets = [
  ['Alerts', 'alerts/active'], ['Alerts', 'alerts/rules'], ['Alerts', 'alerts/channels'],
  ['API Keys', 'api-keys'], ['Branding', 'white-label/configurations'],
]
function goodData(url: string) {
  if (url.endsWith('/api-keys')) return keyPage
  if (url.endsWith('/white-label/configurations')) return [branding]
  return []
}
function openTab(tab: string) {
  render(<SettingsSection />)
  fireEvent.click(screen.getByRole('button', { name: tab }))
}

beforeEach(() => {
  fetchMock.mockReset()
  global.fetch = fetchMock
  jest.spyOn(window, 'confirm').mockReturnValue(true)
  jest.spyOn(window, 'alert').mockImplementation(() => {})
})
afterEach(() => jest.restoreAllMocks())

it('keeps maintenance unavailable and makes no maintenance read or mutation', () => {
  render(<SettingsSection />)
  expect(screen.getByText(/maintenance status and enforcement cannot currently be verified/)).toBeInTheDocument()
  const button = screen.getByRole('button', { name: 'Unavailable' })
  expect(button).toBeDisabled()
  fireEvent.click(button)
  expect(fetchMock).not.toHaveBeenCalled()
})

describe.each(targets)('%s source %s', (tab, path) => {
  it.each([404, 403, 500, 'network', 'malformed', 'invalid-json'])('shows unavailable, not empty success, after %s', async (failure) => {
    fetchMock.mockImplementation(async (url: string) => {
      if (!url.endsWith(`/${path}`)) return response(goodData(url))
      if (failure === 'network') throw new Error('fixture offline')
      if (failure === 'invalid-json') return { ok: true, json: async () => { throw new Error('invalid JSON') } }
      return response(failure === 'malformed' ? [null] : {}, typeof failure === 'number' ? failure : 200)
    })
    openTab(tab)
    expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable/i)
    expect(screen.queryByText('No active alerts')).not.toBeInTheDocument()
    expect(screen.queryByText('No API keys found')).not.toBeInTheDocument()
    expect(screen.queryByText('No branding configurations found')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()

    fetchMock.mockImplementation(async (url: string) => response(goodData(url)))
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    if (tab === 'Alerts') expect(await screen.findByText('No active alerts')).toBeInTheDocument()
    if (tab === 'API Keys') expect(await screen.findByText('Fixture key')).toBeInTheDocument()
    if (tab === 'Branding') expect(await screen.findByText('Fixture organization')).toBeInTheDocument()
  })
})

it('uses the mounted user-scoped API key page and last_used contract', async () => {
  fetchMock.mockResolvedValue(response(keyPage))
  openTab('API Keys')
  expect(await screen.findByText('Fixture key')).toBeInTheDocument()
  expect(screen.getByText('Your API Keys')).toBeInTheDocument()
  expect(screen.getByText('1 shown of 2 keys')).toBeInTheDocument()
  expect(screen.getByText(/Last used:/)).toBeInTheDocument()
  expect(screen.queryByText('Platform API Keys')).not.toBeInTheDocument()
})

it('does not remove an API key after a failed revoke', async () => {
  fetchMock.mockResolvedValueOnce(response(keyPage)).mockResolvedValueOnce(response({}, 500))
  openTab('API Keys')
  await screen.findByText('Fixture key')
  fireEvent.click(screen.getByRole('button', { name: 'Revoke' }))
  await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Failed to revoke API key'))
  expect(screen.getByText('Fixture key')).toBeInTheDocument()
  expect(screen.getByText('Active')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('does not toggle branding after a failed update', async () => {
  fetchMock.mockResolvedValueOnce(response([branding])).mockResolvedValueOnce(response({}, 403))
  openTab('Branding')
  await screen.findByText('Fixture organization')
  fireEvent.click(screen.getByRole('button', { name: 'Disable' }))
  await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Failed to update branding configuration'))
  expect(screen.getByText('Active')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Disable' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
