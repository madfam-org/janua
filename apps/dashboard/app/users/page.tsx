'use client'

import { Suspense } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { UsersDataTable } from '@/components/users/users-data-table'
import { Loader2 } from 'lucide-react'

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Users</h2>
        <p className="text-muted-foreground">
          Manage user accounts, authentication status, and permissions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
          <CardDescription>
            Search, filter, and manage all registered users across your platform.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-12">
                <Loader2 className="text-muted-foreground size-8 animate-spin" />
                <span className="text-muted-foreground ml-2">Loading users...</span>
              </div>
            }
          >
            <UsersDataTable />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  )
}
