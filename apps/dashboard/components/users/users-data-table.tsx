'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
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
import { januaClient } from '@/lib/janua-client'
import { suspendUser, reactivateUser, banUser, unbanUser, unlockUser, resetPassword, deleteUser } from '@/lib/api'
import type { User, UserAction, UserActionType } from './types'
import { columns } from './columns'
import { FacetedFilter } from './faceted-filter'
import { BulkActionsToolbar } from './bulk-actions-toolbar'
import { ActionDialog } from './action-dialog'

// Filter options
const STATUS_OPTIONS = [
  { label: 'Active', value: 'active' },
  { label: 'Inactive', value: 'inactive' },
  { label: 'Suspended', value: 'suspended' },
  { label: 'Banned', value: 'banned' },
  { label: 'Pending', value: 'pending' },
]

const ROLE_OPTIONS = [
  { label: 'Owner', value: 'owner' },
  { label: 'Admin', value: 'admin' },
  { label: 'Member', value: 'member' },
  { label: 'Viewer', value: 'viewer' },
]

interface UsersDataTableProps {
  initialPage?: number
  pageSize?: number
}

export function UsersDataTable({ initialPage = 1, pageSize = 20 }: UsersDataTableProps) {
  const router = useRouter()
  const [data, setData] = React.useState<User[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [totalUsers, setTotalUsers] = React.useState(0)
  const [currentPage, setCurrentPage] = React.useState(initialPage)
  const [totalPages, setTotalPages] = React.useState(1)

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

  // Fetch users from admin API
  const fetchUsers = React.useCallback(async (page = currentPage) => {
    try {
      setLoading(true)
      setError(null)

      const parsedParams: Record<string, any> = {
        page,
        per_page: pageSize,
      }

      if (statusFilter.length === 1) {
        parsedParams.status = statusFilter[0]
      }

      const result = await januaClient.admin.listAllUsers(parsedParams as any)

      // Handle both paginated response and array response
      const users: User[] = (result.data || []).map((u: any) => ({
        id: u.id,
        email: u.email,
        firstName: u.first_name || u.firstName || u.email?.split('@')[0] || 'Unknown',
        lastName: u.last_name || u.lastName || '',
        status: u.status || 'active',
        role: u.role || (u.is_admin ? 'admin' : 'member'),
        mfaEnabled: u.mfa_enabled || u.mfaEnabled || false,
        lastSignIn: u.last_sign_in || u.lastSignIn || u.last_login || null,
        createdAt: u.created_at || u.createdAt,
        sessionsCount: u.sessions_count || u.sessionsCount || 0,
        authMethods: u.auth_methods || u.authMethods || ['password'],
        emailVerified: u.email_verified || u.emailVerified || false,
        isAdmin: u.is_admin || u.isAdmin || false,
        lockedOut: u.locked_out || u.lockedOut || false,
        organizations: u.organizations_count || u.organizations || 0,
      }))

      setData(users)
      setTotalUsers(result.total || users.length)
      setTotalPages(result.total_pages || Math.ceil((result.total || users.length) / pageSize))
      setCurrentPage(page)
    } catch (err) {
      console.error('Failed to fetch users:', err)
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [currentPage, pageSize, statusFilter])

  React.useEffect(() => {
    fetchUsers(1)
  }, [statusFilter])

  React.useEffect(() => {
    fetchUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Handle single user actions
  const handleAction = React.useCallback((action: UserAction) => {
    if (action.type === 'view_detail') {
      router.push(`/users/${action.userId}`)
      return
    }
    if (action.type === 'view_sessions') {
      router.push(`/users/${action.userId}?tab=sessions`)
      return
    }
    if (action.type === 'change_role') {
      // Navigate to user detail profile tab for role management
      router.push(`/users/${action.userId}?tab=profile`)
      return
    }
    setActionDialog({ open: true, action, loading: false })
  }, [router])

  const executeAction = async () => {
    if (!actionDialog.action) return

    setActionDialog((prev) => ({ ...prev, loading: true }))

    try {
      const { type, userId } = actionDialog.action

      switch (type) {
        case 'reset_password':
          await resetPassword(userId)
          break
        case 'suspend':
          await suspendUser(userId)
          break
        case 'reactivate':
          await reactivateUser(userId)
          break
        case 'ban':
          await banUser(userId)
          break
        case 'unban':
          await unbanUser(userId)
          break
        case 'unlock':
          await unlockUser(userId)
          break
        case 'delete':
          await deleteUser(userId)
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
  const handleBulkAction = async (actionType: UserActionType) => {
    const selectedRows = table.getFilteredSelectedRowModel().rows
    const userIds = selectedRows.map((row) => row.original.id)

    for (const userId of userIds) {
      try {
        switch (actionType) {
          case 'ban':
            await banUser(userId)
            break
          case 'delete':
            await deleteUser(userId)
            break
          case 'reset_password':
            await resetPassword(userId)
            break
        }
      } catch (err) {
        console.error(`Bulk action ${actionType} failed for user ${userId}:`, err)
      }
    }

    table.resetRowSelection()
    await fetchUsers()
  }

  // Apply filters
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
  if (loading && data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading users...</span>
      </div>
    )
  }

  // Error state
  if (error && data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Users</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={() => fetchUsers()} variant="outline">
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
          {loading && <Loader2 className="text-muted-foreground size-4 animate-spin" />}
          <Button variant="outline" size="sm" onClick={() => fetchUsers()}>
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
            ? `${selectedCount} of ${totalUsers} row(s) selected`
            : `${totalUsers} user(s) total - Page ${currentPage} of ${totalPages}`}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchUsers(currentPage - 1)}
            disabled={currentPage <= 1 || loading}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchUsers(currentPage + 1)}
            disabled={currentPage >= totalPages || loading}
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
