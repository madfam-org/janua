'use client'

import * as React from 'react'
import {
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { Search, X, Loader2, AlertCircle, RefreshCw, Download } from 'lucide-react'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@janua/ui'
import { apiCall } from '../../lib/auth'
import type { User, UserAction, UserActionType } from './types'
import { columns } from './columns'
import { FacetedFilter } from './faceted-filter'
import { BulkActionsToolbar } from './bulk-actions-toolbar'
import { ActionDialog } from './action-dialog'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

// Filter options
const STATUS_OPTIONS = [
  { label: 'Active', value: 'active' },
  { label: 'Inactive', value: 'inactive' },
  { label: 'Banned', value: 'banned' },
  { label: 'Pending', value: 'pending' },
]

const ROLE_OPTIONS = [
  { label: 'Owner', value: 'owner' },
  { label: 'Admin', value: 'admin' },
  { label: 'Member', value: 'member' },
  { label: 'Viewer', value: 'viewer' },
]

export function UsersDataTable() {
  const [data, setData] = React.useState<User[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = React.useState({})

  const [statusFilter, setStatusFilter] = React.useState<string[]>([])
  const [roleFilter, setRoleFilter] = React.useState<string[]>([])

  // Action dialog state
  const [actionDialog, setActionDialog] = React.useState<{
    open: boolean
    action: UserAction | null
    loading: boolean
  }>({ open: false, action: null, loading: false })

  // Fetch users from activity logs
  const fetchUsers = React.useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/activity-logs?per_page=100`)

      if (!response.ok) {
        throw new Error('Failed to fetch users')
      }

      const activityLogs = await response.json()

      // Transform activity logs to users
      const userMap = new Map<string, User>()

      for (const log of activityLogs) {
        if (!userMap.has(log.user_id)) {
          const authMethods: string[] = []
          if (log.details?.method) {
            authMethods.push(log.details.method)
          }

          const nameParts = log.user_email.split('@')[0].split('.')
          const firstName = nameParts[0] ? nameParts[0].charAt(0).toUpperCase() + nameParts[0].slice(1) : ''
          const lastName = nameParts[1] ? nameParts[1].charAt(0).toUpperCase() + nameParts[1].slice(1) : ''

          userMap.set(log.user_id, {
            id: log.user_id,
            email: log.user_email,
            firstName: firstName || 'Unknown',
            lastName: lastName || '',
            status: 'active',
            role: 'member',
            mfaEnabled: false,
            lastSignIn: log.created_at,
            createdAt: log.created_at,
            sessionsCount: 1,
            authMethods: authMethods.length > 0 ? authMethods : ['password'],
          })
        } else {
          const existing = userMap.get(log.user_id)!
          if (log.action === 'signin') {
            existing.sessionsCount++
            if (new Date(log.created_at) > new Date(existing.lastSignIn || 0)) {
              existing.lastSignIn = log.created_at
            }
          }
          if (log.details?.method && !existing.authMethods.includes(log.details.method)) {
            existing.authMethods.push(log.details.method)
          }
        }
      }

      setData(Array.from(userMap.values()))
    } catch (err) {
      console.error('Failed to fetch users:', err)
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  // Handle single user actions
  const handleAction = React.useCallback((action: UserAction) => {
    setActionDialog({ open: true, action, loading: false })
  }, [])

  const executeAction = async () => {
    if (!actionDialog.action) return

    setActionDialog((prev) => ({ ...prev, loading: true }))

    try {
      const { type, userId } = actionDialog.action

      switch (type) {
        case 'reset_password':
          await apiCall(`${API_BASE_URL}/api/v1/users/${userId}/reset-password`, {
            method: 'POST',
          })
          break
        case 'ban':
          await apiCall(`${API_BASE_URL}/api/v1/users/${userId}/ban`, {
            method: 'POST',
          })
          break
        case 'unban':
          await apiCall(`${API_BASE_URL}/api/v1/users/${userId}/unban`, {
            method: 'POST',
          })
          break
        case 'delete':
          await apiCall(`${API_BASE_URL}/api/v1/users/${userId}`, {
            method: 'DELETE',
          })
          break
        case 'view_sessions':
          window.location.href = `/?tab=sessions&userId=${userId}`
          return
        case 'change_role':
          console.log('Change role for:', userId)
          break
      }

      await fetchUsers()
      setActionDialog({ open: false, action: null, loading: false })
    } catch (err) {
      console.error('Action failed:', err)
      setActionDialog((prev) => ({ ...prev, loading: false }))
    }
  }

  // Handle bulk actions
  const handleBulkAction = (actionType: UserActionType) => {
    const selectedRows = table.getFilteredSelectedRowModel().rows
    const userIds = selectedRows.map((row) => row.original.id)
    console.log('Bulk action:', actionType, 'on users:', userIds)
  }

  // Apply filters
  React.useEffect(() => {
    if (statusFilter.length > 0) {
      setColumnFilters((prev) => [
        ...prev.filter((f) => f.id !== 'status'),
        { id: 'status', value: statusFilter },
      ])
    } else {
      setColumnFilters((prev) => prev.filter((f) => f.id !== 'status'))
    }
  }, [statusFilter])

  React.useEffect(() => {
    if (roleFilter.length > 0) {
      setColumnFilters((prev) => [
        ...prev.filter((f) => f.id !== 'role'),
        { id: 'role', value: roleFilter },
      ])
    } else {
      setColumnFilters((prev) => prev.filter((f) => f.id !== 'role'))
    }
  }, [roleFilter])

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
    meta: {
      onAction: handleAction,
    },
  })

  const selectedCount = table.getFilteredSelectedRowModel().rows.length

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading users...</span>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Users</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchUsers} variant="outline">
          <RefreshCw className="mr-2 size-4" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
            <Input
              placeholder="Search users..."
              value={(table.getColumn('email')?.getFilterValue() as string) ?? ''}
              onChange={(event) =>
                table.getColumn('email')?.setFilterValue(event.target.value)
              }
              className="w-[250px] pl-8"
            />
          </div>

          {/* Faceted filters */}
          <FacetedFilter
            title="Status"
            options={STATUS_OPTIONS}
            selectedValues={statusFilter}
            onSelectionChange={setStatusFilter}
          />
          <FacetedFilter
            title="Role"
            options={ROLE_OPTIONS}
            selectedValues={roleFilter}
            onSelectionChange={setRoleFilter}
          />

          {/* Clear filters */}
          {(statusFilter.length > 0 || roleFilter.length > 0) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStatusFilter([])
                setRoleFilter([])
              }}
            >
              Clear all
              <X className="ml-2 size-4" />
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchUsers}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 size-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Bulk actions toolbar */}
      {selectedCount > 0 && (
        <BulkActionsToolbar
          selectedCount={selectedCount}
          onAction={handleBulkAction}
          onClear={() => table.resetRowSelection()}
        />
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && 'selected'}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No users found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-2">
        <div className="text-muted-foreground text-sm">
          {selectedCount > 0
            ? `${selectedCount} of ${table.getFilteredRowModel().rows.length} row(s) selected`
            : `${table.getFilteredRowModel().rows.length} user(s)`}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Action confirmation dialog */}
      <ActionDialog
        open={actionDialog.open}
        action={actionDialog.action}
        loading={actionDialog.loading}
        onOpenChange={(open) =>
          !actionDialog.loading &&
          setActionDialog({ open, action: null, loading: false })
        }
        onConfirm={executeAction}
      />
    </div>
  )
}
