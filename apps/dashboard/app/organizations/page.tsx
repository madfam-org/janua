'use client'

import { Suspense } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { OrganizationList } from '@/components/organizations/organization-list'
import { Loader2 } from 'lucide-react'

export default function OrganizationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Organizations</h2>
        <p className="text-muted-foreground">
          Manage organizations, members, and team structures.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Organizations</CardTitle>
          <CardDescription>
            View and manage all organizations on your platform.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-12">
                <Loader2 className="text-muted-foreground size-8 animate-spin" />
                <span className="text-muted-foreground ml-2">Loading organizations...</span>
              </div>
            }
          >
            <OrganizationList />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  )
}
