'use client'

import Link from 'next/link'

import { useCallback, useEffect, useState } from 'react'
import { getAccountOrganizations, type AccountOrganization } from '@/lib/organization-directory-api'

export function OrganizationList() {
  const [organizations, setOrganizations] = useState<AccountOrganization[]>([])
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)
  const [search, setSearch] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    setUnavailable(false)
    try { setOrganizations(await getAccountOrganizations()) }
    catch { setOrganizations([]); setUnavailable(true) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  if (loading) return <p role="status">Loading your organizations…</p>
  if (unavailable) return <div role="status"><p>Your organizations are unavailable.</p><button className="text-primary underline" onClick={() => void load()}>Try again</button></div>
  if (!organizations.length) return <p className="text-muted-foreground">No organizations are associated with your account.</p>
  const filtered = organizations.filter(org => `${org.name} ${org.slug}`.toLowerCase().includes(search.toLowerCase()))
  return <section aria-label="Your organizations" className="space-y-4">
    <label className="block text-sm">Search your organizations<input className="border-input bg-background mt-1 block w-full rounded-md border p-2" value={search} onChange={event => setSearch(event.target.value)} /></label>
    {!filtered.length ? <p>No organizations match your search.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <caption className="sr-only">Your organizations</caption>
      <thead><tr><th className="p-2">Organization</th><th className="p-2">Members</th></tr></thead>
      <tbody>{filtered.map(org => <tr key={org.id} className="border-t"><td className="p-2"><Link className="text-primary underline" href={`/organizations/${encodeURIComponent(org.id)}`}>{org.name}</Link><p className="text-muted-foreground text-xs">{org.slug}</p></td><td className="p-2">{org.memberCount ?? 'Unavailable'}</td></tr>)}</tbody>
    </table></div>}
  </section>
}
