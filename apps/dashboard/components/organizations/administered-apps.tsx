'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { ChevronRight, KeyRound } from 'lucide-react'
import { appRolesAdminPath, errorStatus, getMyAppRoles } from '@/lib/app-roles-api'

/**
 * Links to the delegated app-role admin page for every app the caller holds
 * `<app>:admin` for in this organization. Renders nothing when there are none
 * (the common case) or when the caller is not an active member (404).
 */
export function AdministeredApps({ orgId }: { orgId: string }) {
  const [apps, setApps] = useState<string[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getMyAppRoles(orgId)
      .then((mine) => {
        if (!cancelled) setApps(mine.administered_apps)
      })
      .catch((err) => {
        if (cancelled) return
        if (errorStatus(err) === 404) setApps([])
        else setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [orgId])

  if (failed) {
    return (
      <p className="text-muted-foreground text-sm">
        Could not check which apps you administer in this organization.
      </p>
    )
  }
  if (!apps || apps.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">App roles you administer</CardTitle>
        <CardDescription>
          Grant and revoke roles of these apps for members of this organization.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        {apps.map((app) => (
          <Link
            key={app}
            href={appRolesAdminPath(orgId, app)}
            className="hover:bg-muted flex items-center justify-between rounded-md px-3 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              <KeyRound className="size-4" />
              {app}
            </span>
            <ChevronRight className="text-muted-foreground size-4" />
          </Link>
        ))}
      </CardContent>
    </Card>
  )
}
