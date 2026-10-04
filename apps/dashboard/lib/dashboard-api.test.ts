import { getPersonalDashboardStats, getPersonalSessionActivity } from './dashboard-api'
import { januaClient } from './janua-client'

jest.mock('./janua-client', () => ({ januaClient: { http: { get: jest.fn() }, admin: { getStats: jest.fn(), getActivityLogs: jest.fn() } } }))
const get = jest.mocked(januaClient.http.get)
beforeEach(() => { jest.clearAllMocks() })

it('uses current-user endpoints even for platform operators, with genuine zero counts', async () => {
  get.mockResolvedValueOnce({ data: { organizations: [], total: 0, page: 1, per_page: 20 } } as never).mockResolvedValueOnce({ data: { sessions: [], total: 0 } } as never)
  await expect(getPersonalDashboardStats()).resolves.toEqual({ organizations: 0, activeSessions: 0 })
  expect(get.mock.calls.map(([path]) => path)).toEqual(['/api/v1/organizations/', '/api/v1/sessions/'])
  expect(januaClient.admin.getStats).not.toHaveBeenCalled()
})
it('keeps available account data when another source fails; missing metrics never become zero', async () => {
  get.mockResolvedValueOnce({ data: { organizations: [{ id: 'org-a' }], total: 2, page: 1, per_page: 1 } } as never).mockRejectedValueOnce(new Error('offline'))
  await expect(getPersonalDashboardStats()).resolves.toEqual({ organizations: 2, activeSessions: null })
})
it('does not trust malformed or global-admin response shapes', async () => {
  get.mockResolvedValueOnce({ data: { total_organizations: 100 } } as never).mockResolvedValueOnce({ data: { active_sessions: 900 } } as never)
  await expect(getPersonalDashboardStats()).resolves.toEqual({ organizations: null, activeSessions: null })
})
it('reads only personal session activity and discards extra identity/IP fields', async () => {
  get.mockResolvedValueOnce({ data: { activities: [{ session_id: 'session-a', activity_type: 'session_active', timestamp: '2026-10-03T12:00:00Z', device: 'Example browser', revoked: false, ip_address: '192.0.2.1', user_email: 'fixture@example.test' }] } } as never)
  const result = await getPersonalSessionActivity()
  expect(result).toEqual([{ id: 'session-a', action: 'Session active', timestamp: '2026-10-03T12:00:00Z', device: 'Example browser', revoked: false }])
  expect(get).toHaveBeenCalledWith('/api/v1/sessions/activity/recent?limit=10')
  expect(januaClient.admin.getActivityLogs).not.toHaveBeenCalled()
})
it('rejects malformed session activity instead of reporting an empty history', async () => {
  get.mockResolvedValueOnce({ data: {} } as never)
  await expect(getPersonalSessionActivity()).rejects.toThrow('Session activity unavailable')
})
