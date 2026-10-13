import React from 'react'
import { webcrypto } from 'node:crypto'
import { TextEncoder } from 'node:util'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

// These are provider/native-self fixtures, not a hosted login or JWT proof.
const SELF_ID = '11111111-1111-4111-8111-111111111111'
const ORG_ID = '22222222-2222-4222-8222-222222222222'
const INVITE_TOKEN = 'a'.repeat(43)
const mockSearch = new URLSearchParams()
const mockSelf = { id: SELF_ID, email: 'invited@sim.invalid', status: 'active', is_service_account: false }
let mockAuth = { isLoading: false, isAuthenticated: true, user: mockSelf }
const mockClient = {
  getConfig: jest.fn(), getAccessToken: jest.fn(),
  users: { getCurrentUser: jest.fn() },
  invitations: { validateToken: jest.fn(), acceptInvitation: jest.fn() },
}
const mockFetch = jest.fn()
jest.mock('next/navigation', () => ({ useSearchParams: () => mockSearch }))
jest.mock('@janua/nextjs/app/client', () => ({ useJanua: () => ({ client: mockClient }) }))
jest.mock('@/lib/auth', () => ({ useAuth: () => mockAuth }))

import InvitationAcceptPage from './page'

const invitation = { valid: true, email: mockSelf.email, organization_id: ORG_ID, organization_name: 'Synthetic training organization', role: 'member' }
const receipt = { success: true, user_id: SELF_ID, organization_id: ORG_ID, is_new_user: false }
const response = (body: unknown = receipt, ok = true) => ({ ok, text: async () => JSON.stringify(body) })

describe('dashboard invitation acceptance — explicit one-shot transport', () => {
  beforeAll(() => {
    Object.defineProperty(window, 'crypto', { configurable: true, value: webcrypto })
    Object.defineProperty(global, 'TextEncoder', { configurable: true, value: TextEncoder })
    global.fetch = mockFetch
  })
  beforeEach(() => {
    jest.clearAllMocks()
    mockSearch.forEach((_, key) => mockSearch.delete(key))
    mockSearch.set('token', INVITE_TOKEN)
    sessionStorage.clear()
    mockAuth = { isLoading: false, isAuthenticated: true, user: mockSelf }
    mockClient.getConfig.mockReturnValue({ baseURL: 'https://api.janua.dev' })
    mockClient.getAccessToken.mockResolvedValue('fixture-bearer')
    mockClient.users.getCurrentUser.mockResolvedValue(mockSelf)
    mockClient.invitations.validateToken.mockResolvedValue(invitation)
    mockFetch.mockResolvedValue(response())
  })
  afterEach(() => { jest.useRealTimers() })

  async function ready() {
    const rendered = render(<InvitationAcceptPage />)
    await screen.findByRole('button', { name: 'Accept invitation' })
    return rendered
  }

  it('verifies native self, shows actual invite details as plain text, and waits for an explicit submit', async () => {
    mockClient.invitations.validateToken.mockResolvedValue({ ...invitation, organization_name: '<script>fixture</script>' })
    await ready()
    expect(screen.getByText('<script>fixture</script>')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
    expect(mockClient.users.getCurrentUser).toHaveBeenCalledTimes(1)
    expect(mockClient.invitations.validateToken).toHaveBeenCalledWith(INVITE_TOKEN)
    expect(mockFetch).not.toHaveBeenCalled()
    expect(mockClient.invitations.acceptInvitation).not.toHaveBeenCalled()
  })

  it('sends exactly one token-only POST with native bearer despite a synchronous double click', async () => {
    await ready()
    const button = screen.getByRole('button', { name: 'Accept invitation' })
    fireEvent.click(button)
    fireEvent.click(button)
    await screen.findByText(/The API confirmed acceptance/)
    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toBe('https://api.janua.dev/api/v1/invitations/accept')
    expect(options).toMatchObject({ method: 'POST', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer', cache: 'no-store', headers: { Authorization: 'Bearer fixture-bearer' } })
    expect(JSON.parse(options.body)).toEqual({ token: INVITE_TOKEN })
    expect(options.signal).toBeInstanceOf(AbortSignal)
    expect(mockClient.invitations.acceptInvitation).not.toHaveBeenCalled()
    const retained = Object.entries(sessionStorage)
    expect(retained).toHaveLength(1)
    expect(retained[0][0]).toMatch(/^janua\.invitation\.accept\.[a-f0-9]{64}$/)
    expect(JSON.stringify(retained)).not.toContain(INVITE_TOKEN)
    expect(JSON.stringify(retained)).not.toContain('fixture-bearer')
  })

  it.each([401, 500, 503])('retains unknown after HTTP %s and permits only GET status checks, including reload', async status => {
    mockFetch.mockResolvedValue({ ...response({}, false), status })
    const rendered = await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByRole('button', { name: 'Check invitation status' })
    expect(mockFetch).toHaveBeenCalledTimes(1)
    mockClient.invitations.validateToken.mockResolvedValue({ ...invitation, valid: false })
    fireEvent.click(screen.getByRole('button', { name: 'Check invitation status' }))
    await screen.findByText(/does not confirm active membership/)
    expect(mockFetch).toHaveBeenCalledTimes(1)
    rendered.unmount()
    render(<InvitationAcceptPage />)
    await screen.findByRole('button', { name: 'Check invitation status' })
    expect(screen.queryByRole('button', { name: 'Accept invitation' })).not.toBeInTheDocument()
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it.each(['transport-loss', 'response-loss', 'malformed-ack', 'foreign-ack'])('never replays after %s', async failure => {
    if (failure === 'transport-loss') mockFetch.mockRejectedValue(new Error('fixture lost transport'))
    if (failure === 'response-loss') mockFetch.mockResolvedValue({ ok: true, text: async () => { throw new Error('fixture lost response') } })
    if (failure === 'malformed-ack') mockFetch.mockResolvedValue({ ok: true, text: async () => '{' })
    if (failure === 'foreign-ack') mockFetch.mockResolvedValue(response({ ...receipt, user_id: ORG_ID }))
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByRole('button', { name: 'Check invitation status' })
    fireEvent.click(screen.getByRole('button', { name: 'Check invitation status' }))
    await screen.findByText(/previous acceptance remains unconfirmed/)
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('aborts a pending POST at the bound and never retries after timeout', async () => {
    await ready()
    jest.useFakeTimers()
    mockFetch.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new Error('fixture timeout')))
    }))
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1))
    await act(async () => { jest.advanceTimersByTime(10_000) })
    expect(await screen.findByRole('button', { name: 'Check invitation status' })).toBeInTheDocument()
    expect(mockFetch.mock.calls[0][1].signal.aborted).toBe(true)
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it.each(['missing', 'duplicate', 'path', 'oversized'])('rejects a %s invitation token before any API request', async value => {
    if (value === 'missing') mockSearch.delete('token')
    if (value === 'duplicate') mockSearch.append('token', INVITE_TOKEN)
    if (value === 'path') mockSearch.set('token', '../fixture')
    if (value === 'oversized') mockSearch.set('token', 'a'.repeat(129))
    render(<InvitationAcceptPage />)
    await screen.findByText(/could not be verified/)
    expect(mockClient.users.getCurrentUser).not.toHaveBeenCalled()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it.each(['foreign-email', 'service-account', 'inactive', 'native-id', 'token-refresh'])('blocks %s native self/session before an accept is offered', async mismatch => {
    if (mismatch === 'foreign-email') mockClient.users.getCurrentUser.mockResolvedValue({ ...mockSelf, email: 'other@sim.invalid' })
    if (mismatch === 'service-account') mockClient.users.getCurrentUser.mockResolvedValue({ ...mockSelf, is_service_account: true })
    if (mismatch === 'inactive') mockClient.users.getCurrentUser.mockResolvedValue({ ...mockSelf, status: 'inactive' })
    if (mismatch === 'native-id') mockClient.users.getCurrentUser.mockResolvedValue({ ...mockSelf, id: ORG_ID })
    if (mismatch === 'token-refresh') mockClient.getAccessToken.mockResolvedValueOnce('before').mockResolvedValue('after')
    render(<InvitationAcceptPage />)
    await screen.findByText(/could not be verified/)
    expect(screen.queryByRole('button', { name: 'Accept invitation' })).not.toBeInTheDocument()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('rechecks self and blocks changed bearer before transport, rather than replaying with a refreshed session', async () => {
    await ready()
    mockClient.getAccessToken.mockResolvedValue('different-bearer')
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByText(/No acceptance was sent/)
    expect(mockFetch).not.toHaveBeenCalled()
    expect(sessionStorage.length).toBe(0)
  })

  it('holds a session change after transport as unknown, without attributing the result to another account', async () => {
    await ready()
    mockFetch.mockImplementation(async () => {
      mockAuth = { ...mockAuth, user: { ...mockSelf, id: ORG_ID } }
      mockClient.getAccessToken.mockResolvedValue('changed-after-submit')
      return response()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByRole('button', { name: 'Check invitation status' })
    expect(screen.queryByText(/API confirmed acceptance/)).not.toBeInTheDocument()
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it.each(['https://foreign.invalid', 'https://api.janua.dev/api/v1', 'https://api.janua.dev/?token=fixture', 'http://api.janua.dev', 'https://user:secret@api.janua.dev'])('refuses an undeclared or non-root API base %s', async baseURL => {
    mockClient.getConfig.mockReturnValue({ baseURL })
    render(<InvitationAcceptPage />)
    await screen.findByText(/could not be verified/)
    expect(mockClient.users.getCurrentUser).not.toHaveBeenCalled()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('does not submit when uncertainty cannot be retained locally', async () => {
    await ready()
    const storage = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('fixture storage disabled') })
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByText(/No acceptance was sent/)
    expect(mockFetch).not.toHaveBeenCalled()
    storage.mockRestore()
  })

  it('rechecks a marker retained after render and refuses a second same-tab attempt', async () => {
    await ready()
    const storage = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('unconfirmed')
    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
    await screen.findByRole('button', { name: 'Check invitation status' })
    expect(mockFetch).not.toHaveBeenCalled()
    storage.mockRestore()
  })

  it('does not verify or submit while provider auth is loading or unauthenticated', async () => {
    mockAuth = { ...mockAuth, isLoading: true }
    const rendered = render(<InvitationAcceptPage />)
    expect(mockClient.users.getCurrentUser).not.toHaveBeenCalled()
    mockAuth = { ...mockAuth, isLoading: false, isAuthenticated: false }
    rendered.rerender(<InvitationAcceptPage />)
    expect(await screen.findByText('Sign in to the invited account to continue.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in with the invited account' }).getAttribute('href')).toBe(`/login?${new URLSearchParams({ redirect: `/invitations/accept?token=${INVITE_TOKEN}`, reason: 'session_expired' })}`)
    expect(mockFetch).not.toHaveBeenCalled()
  })
})
