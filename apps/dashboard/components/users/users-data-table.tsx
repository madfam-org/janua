'use client'

import Link from 'next/link'

import { useCallback, useEffect, useRef, useState } from 'react'
import { getAccountOrganizations, getOrganizationMembers, type AccountOrganization, type OrganizationMember } from '@/lib/organization-directory-api'

/** Membership directory: platform-wide user/security operations live in Admin. */
export function UsersDataTable() {
  const [organizations, setOrganizations] = useState<AccountOrganization[]>([])
  const [organizationId, setOrganizationId] = useState('')
  const [members, setMembers] = useState<OrganizationMember[]>([])
  const [loadingOrganizations, setLoadingOrganizations] = useState(true)
  const [loadingMembers, setLoadingMembers] = useState(false)
  const [organizationError, setOrganizationError] = useState(false)
  const [memberError, setMemberError] = useState(false)
  const [search, setSearch] = useState('')
  const requestVersion = useRef(0)

  const loadOrganizations = useCallback(async () => {
    setLoadingOrganizations(true)
    setOrganizationError(false)
    try { setOrganizations(await getAccountOrganizations()) }
    catch { setOrganizations([]); setOrganizationError(true) }
    finally { setLoadingOrganizations(false) }
  }, [])
  useEffect(() => { void loadOrganizations() }, [loadOrganizations])

  const loadMembers = useCallback(async (id: string) => {
    const version = ++requestVersion.current
    setMembers([])
    setMemberError(false)
    if (!id) { setLoadingMembers(false); return }
    setLoadingMembers(true)
    try {
      const result = await getOrganizationMembers(id)
      if (version === requestVersion.current) setMembers(result)
    } catch {
      if (version === requestVersion.current) setMemberError(true)
    } finally {
      if (version === requestVersion.current) setLoadingMembers(false)
    }
  }, [])
  const selectOrganization = (id: string) => {
    // Only offer current account memberships; API enforces access again.
    if (id && !organizations.some(org => org.id === id)) return
    setOrganizationId(id)
    setSearch('')
    void loadMembers(id)
  }
  const organization = organizations.find(org => org.id === organizationId)
  const filteredMembers = members.filter(member => `${member.id} ${member.role}`.toLowerCase().includes(search.toLowerCase()))

  if (loadingOrganizations) return <p role="status">Loading your organizations…</p>
  if (organizationError) return <div role="status"><p>Your organizations are unavailable.</p><button className="text-primary underline" onClick={() => void loadOrganizations()}>Try again</button></div>
  if (!organizations.length) return <p className="text-muted-foreground">No organizations are associated with your account.</p>
  return (
    <section aria-label="Organization members" className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="member-organization" className="block text-sm font-medium">Organization</label>
        <select id="member-organization" className="border-input bg-background w-full rounded-md border p-2" value={organizationId} onChange={event => selectOrganization(event.target.value)}>
          <option value="">Choose an organization</option>
          {organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}
        </select>
      </div>
      {!organizationId && <p className="text-muted-foreground text-sm">Choose an organization to view its members.</p>}
      {organization && <p className="text-sm">Members of {organization.name}. <Link href={`/organizations/${encodeURIComponent(organization.id)}?tab=members`} className="text-primary underline">Manage organization membership</Link></p>}
      {loadingMembers && <p role="status">Loading organization members…</p>}
      {memberError && <div role="status"><p>Members of this organization are unavailable or access was denied.</p><button className="text-primary underline" onClick={() => void loadMembers(organizationId)}>Try again</button></div>}
      {organizationId && !loadingMembers && !memberError && <>
        <label className="block text-sm">Search member IDs or roles<input className="border-input bg-background mt-1 block w-full rounded-md border p-2" value={search} onChange={event => setSearch(event.target.value)} /></label>
        {!filteredMembers.length ? <p className="text-muted-foreground">{members.length ? 'No members match your search.' : 'No members were returned for this organization.'}</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <caption className="sr-only">Members of {organization?.name}</caption>
          <thead><tr><th className="p-2">Member ID</th><th className="p-2">Membership status</th><th className="p-2">Organization role</th><th className="p-2">Joined</th></tr></thead>
          <tbody>{filteredMembers.map(member => <tr key={member.id} className="border-t"><td className="p-2">{member.id}</td><td className="p-2">{member.status}</td><td className="p-2">{member.role}</td><td className="p-2">{member.joinedAt ? new Date(member.joinedAt).toLocaleDateString() : 'Unavailable'}</td></tr>)}</tbody>
        </table></div>}
        <p className="text-muted-foreground text-xs">Names and email addresses are unavailable from the organization membership API. Account-wide authentication status and security controls are managed in Janua Admin.</p>
      </>}
    </section>
  )
}
