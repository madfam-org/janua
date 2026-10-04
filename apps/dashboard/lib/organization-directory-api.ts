import { januaClient } from './janua-client'

export interface AccountOrganization {
  id: string
  name: string
  slug: string
  memberCount: number | null
}
export interface OrganizationMember {
  id: string
  role: string
  status: string
  joinedAt: string | null
  isServiceAccount: boolean | null
}

/** Read every page or fail explicitly; never present a partial directory as complete. */
export async function getAccountOrganizations(): Promise<AccountOrganization[]> {
  const organizations = new Map<string, AccountOrganization>()
  let expectedTotal: number | undefined
  for (let page = 1; page <= 100; page++) {
    const response = await januaClient.http.get<unknown>(`/api/v1/organizations/?page=${page}&per_page=100`)
    const data = response.data as { organizations?: unknown; total?: unknown; page?: unknown } | null
    if (!data || !Array.isArray(data.organizations) || typeof data.total !== 'number' || !Number.isSafeInteger(data.total) || data.total < 0 || data.page !== page) throw new Error('Organization directory unavailable')
    if (expectedTotal !== undefined && expectedTotal !== data.total) throw new Error('Organization directory changed; retry')
    expectedTotal = data.total
    for (const org of data.organizations) {
      const row = org as Record<string, unknown> | null
      if (!row || typeof row.id !== 'string' || typeof row.name !== 'string' || typeof row.slug !== 'string' || organizations.has(row.id)) throw new Error('Organization directory unavailable')
      organizations.set(row.id, {
        id: row.id, name: row.name, slug: row.slug,
        memberCount: typeof row.member_count === 'number' && Number.isSafeInteger(row.member_count) && row.member_count >= 0 ? row.member_count : null,
      })
    }
    if (organizations.size === expectedTotal) return Array.from(organizations.values())
    if (!data.organizations.length || organizations.size > expectedTotal) throw new Error('Organization directory unavailable')
  }
  throw new Error('Organization directory exceeds supported size')
}

export async function getOrganizationMembers(organizationId: string): Promise<OrganizationMember[]> {
  const response = await januaClient.http.get<unknown>(`/api/v1/organizations/${encodeURIComponent(organizationId)}/members`)
  if (!Array.isArray(response.data)) throw new Error('Organization members unavailable')
  return response.data.map((member: unknown) => {
    const row = member as Record<string, unknown> | null
    if (!row || typeof row.user_id !== 'string' || row.organization_id !== organizationId || typeof row.role !== 'string' || typeof row.status !== 'string') throw new Error('Organization members unavailable')
    return {
      id: row.user_id, role: row.role, status: row.status,
      joinedAt: typeof row.joined_at === 'string' && Number.isFinite(Date.parse(row.joined_at)) ? row.joined_at : null,
      isServiceAccount: typeof row.is_service_account === 'boolean' ? row.is_service_account : null,
    }
  })
}
