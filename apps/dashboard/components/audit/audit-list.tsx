import Link from 'next/link'

/** Tenant audit queries, exports and live feeds need an organization-scoped API. */
export function AuditList() {
  return <section aria-label="Organization audit logs" className="space-y-3">
    <p className="font-medium">Organization audit logs are not available yet.</p>
    <p className="text-muted-foreground text-sm">Organization-scoped audit history, search, exports, and live updates are unavailable.</p>
    <Link className="text-primary text-sm underline" href="/?tab=overview">View your recent session activity</Link>
  </section>
}
