import { getAccountOrganizations, getOrganizationMembers } from './organization-directory-api'
import { januaClient } from './janua-client'

jest.mock('./janua-client', () => ({ januaClient: { http: { get: jest.fn() } } }))
const get = jest.mocked(januaClient.http.get)
beforeEach(() => get.mockReset())
const org = (id: string) => ({ id, name: id, slug: id })
it('loads the mounted paginated membership contract completely without invented role/plan', async () => {
  get.mockResolvedValueOnce({ data: { organizations: [{ ...org('a'), member_count: 0, billing_email: 'billing@example.test' }], total: 2, page: 1, per_page: 100 } } as never)
    .mockResolvedValueOnce({ data: { organizations: [org('b')], total: 2, page: 2, per_page: 100 } } as never)
  await expect(getAccountOrganizations()).resolves.toEqual([{ id: 'a', name: 'a', slug: 'a', memberCount: 0 }, { id: 'b', name: 'b', slug: 'b', memberCount: null }])
  expect(get.mock.calls.map(([url]) => url)).toEqual(['/api/v1/organizations/?page=1&per_page=100', '/api/v1/organizations/?page=2&per_page=100'])
})
it('uses the mounted member contract without global identity enrichment', async () => {
  get.mockResolvedValueOnce({ data: [{ id: 'membership-a', user_id: 'member-a', organization_id: 'org/a', role: 'admin', status: 'active', joined_at: '2026-10-03T12:00:00Z', is_service_account: false }] } as never)
  await expect(getOrganizationMembers('org/a')).resolves.toEqual([{ id: 'member-a', role: 'admin', status: 'active', joinedAt: '2026-10-03T12:00:00Z', isServiceAccount: false }])
  expect(get).toHaveBeenCalledWith('/api/v1/organizations/org%2Fa/members')
})
it('rejects a mismatched organization in a member response', async () => {
  get.mockResolvedValueOnce({ data: [{ user_id: 'member-a', organization_id: 'org-b', role: 'member', status: 'active' }] } as never)
  await expect(getOrganizationMembers('org-a')).rejects.toThrow('Organization members unavailable')
})
it('does not present failures, old monolith shapes, or incomplete pagination as an empty/complete directory', async () => {
  get.mockRejectedValueOnce(new Error('denied')).mockResolvedValueOnce({ data: [org('a')] } as never)
    .mockResolvedValueOnce({ data: { organizations: [], total: 2, page: 1 } } as never)
  await expect(getOrganizationMembers('org-a')).rejects.toThrow('denied')
  await expect(getAccountOrganizations()).rejects.toThrow('Organization directory unavailable')
  await expect(getAccountOrganizations()).rejects.toThrow('Organization directory unavailable')
})
