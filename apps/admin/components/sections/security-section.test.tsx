import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { adminAPI, type AdminStats, type ActivityLog } from '@/lib/admin-api'
import { SecuritySection } from './security-section'

jest.mock('@/lib/admin-api', () => ({ adminAPI: { getStats: jest.fn(), getActivityLogs: jest.fn(), revokeAllSessions: jest.fn() } }))
const getStats = jest.mocked(adminAPI.getStats)
const getLogs = jest.mocked(adminAPI.getActivityLogs)
const stats: AdminStats = { total_users: 30, active_users: 30, suspended_users: 0, deleted_users: 0, total_organizations: 2, total_sessions: 10, active_sessions: 5, mfa_enabled_users: 3, oauth_accounts: 0, passkeys_registered: 0, users_last_24h: 0, sessions_last_24h: 0 }
const event = (id: string, action = 'login_failed'): ActivityLog => ({ id, action, user_id: 'fixture-user', user_email: 'fixture@example.test', ip_address: '192.0.2.1', user_agent: null, details: {}, created_at: new Date().toISOString() })

beforeEach(() => {
  jest.clearAllMocks()
  getStats.mockResolvedValue(stats)
  getLogs.mockResolvedValue([])
})

it('keeps measured MFA counts while every unsupported protection control is unavailable', async () => {
  getLogs.mockResolvedValue([event('one'), event('two'), event('three')])
  render(<SecuritySection />)
  expect(await screen.findByText('3 of 30 users')).toBeInTheDocument()
  expect(screen.getAllByText('10.0%')).toHaveLength(2)
  for (const name of ['Rate Limiting', 'Brute Force Protection', 'CSRF Protection', 'Bot Detection', 'IP Blocklist']) {
    const row = screen.getByText(name).parentElement!.parentElement!
    expect(within(row).getByText('Unavailable')).toBeInTheDocument()
    expect(within(row).queryByText('Active')).not.toBeInTheDocument()
    expect(within(row).queryByText('Inactive')).not.toBeInTheDocument()
  }
  expect(screen.getByText('3 failures')).toBeInTheDocument()
  expect(screen.getByText(/latest 50-event sample, not complete period totals/)).toBeInTheDocument()
  expect(screen.getByText('Failed Logins in Sample')).toBeInTheDocument()
  expect(screen.queryByText('Failed Logins (24h)')).not.toBeInTheDocument()
  expect(getLogs).toHaveBeenCalledWith(50)
  expect(screen.getByRole('button', { name: 'Revoke tracked sessions for other users' })).toBeEnabled()
  expect(adminAPI.revokeAllSessions).not.toHaveBeenCalled()
})

it('describes an empty event sample without asserting platform-wide absence of threats', async () => {
  render(<SecuritySection />)
  expect(await screen.findByText('No matching security events in this sample.')).toBeInTheDocument()
  expect(screen.getByText('No IPs meet the repeated-failure threshold in this sample.')).toBeInTheDocument()
  expect(screen.queryByText('No suspicious IP addresses detected.')).not.toBeInTheDocument()
})

it('shows a stale-data error after refresh fails and clears it after recovery', async () => {
  render(<SecuritySection />)
  await screen.findByText('3 of 30 users')
  getStats.mockRejectedValueOnce(new Error('fixture outage'))
  fireEvent.click(screen.getByRole('button', { name: 'Refresh security data' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Showing previously loaded data; it may be outdated')
  expect(screen.getByText('3 of 30 users')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh security data' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
})

it('offers retry instead of fabricated counts when the initial request fails', async () => {
  getLogs.mockRejectedValueOnce(new Error('fixture outage'))
  render(<SecuritySection />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Security data could not be refreshed')
  expect(screen.queryByText('3 of 30 users')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('3 of 30 users')).toBeInTheDocument()
})


it('describes the tracked-session scope and does not submit a cancelled request', async () => {
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(false)
  try {
    render(<SecuritySection />)
    await screen.findByText('3 of 30 users')
    expect(screen.getByText(/Sessionless tokens may not be covered/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Revoke tracked sessions for other users' }))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Your administrator sessions are preserved'))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('until expiry'))
    expect(adminAPI.revokeAllSessions).not.toHaveBeenCalled()
  } finally { confirm.mockRestore() }
})

it.each([true, false])('reports only the actual request outcome (success=%s)', async (success) => {
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true)
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {})
  const revoke = jest.mocked(adminAPI.revokeAllSessions)
  if (success) revoke.mockResolvedValueOnce(undefined)
  else revoke.mockRejectedValueOnce(new Error('fixture failure'))
  try {
    render(<SecuritySection />)
    await screen.findByText('3 of 30 users')
    fireEvent.click(screen.getByRole('button', { name: 'Revoke tracked sessions for other users' }))
    await waitFor(() => expect(alert).toHaveBeenCalledWith(success ? 'Session revocation request completed' : 'Failed to revoke sessions'))
    expect(alert).not.toHaveBeenCalledWith(expect.stringContaining('All sessions revoked'))
    expect(revoke).toHaveBeenCalledTimes(1)
  } finally { confirm.mockRestore(); alert.mockRestore() }
})
