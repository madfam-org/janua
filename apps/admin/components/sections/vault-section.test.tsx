import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { VaultSection } from './vault-section'

const fixture = {
  encryption_enabled: true, field_encryption_active: true,
  keys: [{
    id: 'fixture-key', algorithm: 'fixture-algorithm', status: 'rotation_needed',
    created_at: '2025-01-01T00:00:00Z', last_rotated: '2025-02-01T00:00:00Z',
    next_rotation: '2025-03-01T00:00:00Z', key_type: 'Fixture encryption',
  }],
  secrets_count: 1,
  secrets: [{ name: 'FIXTURE_SECRET', category: 'encryption', status: 'active', last_rotated: '2025-02-01T00:00:00Z', masked_value: 'must-not-render' }],
  last_audit: null,
}
const response = (data: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data } as Response)
const fetchMock = jest.fn()

beforeEach(() => {
  fetchMock.mockReset()
  global.fetch = fetchMock
  jest.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => jest.restoreAllMocks())

it.each([404, 401, 403, 500])('shows unavailable on HTTP %s without fabricated healthy data', async (status) => {
  fetchMock.mockResolvedValue(response({}, status))
  render(<VaultSection />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Vault status unavailable')
  expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()
  expect(screen.queryByText('Enabled')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Rotate' })).not.toBeInTheDocument()
})

it('offers retry after a network error and renders only validated metadata', async () => {
  fetchMock.mockRejectedValueOnce(new Error('fixture offline')).mockResolvedValue(response(fixture))
  render(<VaultSection />)
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('fixture-key')).toBeInTheDocument()
  expect(screen.queryByText('must-not-render')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /secret value/i })).not.toBeInTheDocument()
  expect(screen.queryByText('Encrypted')).not.toBeInTheDocument()
  expect(screen.getByText(/Field-level encryption coverage and compliance evidence are not provided/)).toBeInTheDocument()
})

it.each([
  null, {}, { ...fixture, encryption_enabled: 'true' }, { ...fixture, keys: null },
  { ...fixture, secrets_count: -1 }, { ...fixture, secrets: [{}] },
  { ...fixture, keys: [{ ...fixture.keys[0], status: 'unknown' }] },
  { ...fixture, keys: [{ ...fixture.keys[0], last_rotated: 'invalid-date' }] },
])('rejects malformed successful status payload %#', async (data) => {
  fetchMock.mockResolvedValue(response(data))
  render(<VaultSection />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Vault status unavailable')
  expect(screen.queryByText('Enabled')).not.toBeInTheDocument()
})

it('rejects invalid JSON and clears a previous healthy snapshot after refresh failure', async () => {
  fetchMock.mockResolvedValueOnce(response(fixture)).mockResolvedValue({ ok: true, json: async () => { throw new Error('invalid JSON') } })
  render(<VaultSection />)
  await screen.findByText('fixture-key')
  fireEvent.click(screen.getByRole('button', { name: 'Refresh vault status' }))
  await screen.findByRole('alert')
  expect(screen.queryByText('fixture-key')).not.toBeInTheDocument()
  expect(screen.queryByText('Enabled')).not.toBeInTheDocument()
})

it.each([404, 403, 500, 'network'])('does not simulate a rotation after %s', async (failure) => {
  fetchMock.mockResolvedValueOnce(response(fixture))
  if (failure === 'network') fetchMock.mockRejectedValueOnce(new Error('fixture offline'))
  else fetchMock.mockResolvedValueOnce(response({}, failure as number))
  render(<VaultSection />)
  await screen.findByText('fixture-key')
  const originalRotation = screen.getByText('Last Rotated').parentElement?.textContent
  fireEvent.click(screen.getByRole('button', { name: 'Rotate' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Rotation could not be confirmed')
  expect(screen.getByText('Rotation Needed')).toBeInTheDocument()
  expect(screen.getByText('Last Rotated').parentElement?.textContent).toBe(originalRotation)
  expect(fetchMock).toHaveBeenCalledTimes(2)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

it('uses a fresh status response after an accepted rotation instead of changing it locally', async () => {
  fetchMock.mockResolvedValueOnce(response(fixture)).mockResolvedValueOnce(response({}, 202))
    .mockResolvedValueOnce(response({ ...fixture, keys: [{ ...fixture.keys[0], status: 'rotating' }] }))
  render(<VaultSection />)
  await screen.findByText('fixture-key')
  fireEvent.click(screen.getByRole('button', { name: 'Rotate' }))
  expect(await screen.findByText('Rotating')).toBeInTheDocument()
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(screen.getByRole('status')).toHaveTextContent('Check the refreshed status for confirmation')
})
