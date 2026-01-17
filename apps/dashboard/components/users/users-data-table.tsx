'use client'

import * as React from 'react'
import {
  ColumnDef,
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
import {
  MoreHorizontal,
  ArrowUpDown,
  Search,
  X,
  Filter,
  KeyRound,
  Ban,
  Eye,
  Trash2,
  UserCog,
  Download,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
  XCircle,
  Shield,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import { Badge } from '@janua/ui'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@janua/ui'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@janua/ui'
import { Checkbox } from '@janua/ui'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@janua/ui'
import { apiCall } from '../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

// Types
export type UserStatus = 'active' | 'inactive' | 'banned' | 'pending'
export type UserRole = 'owner' | 'admin' | 'member' | 'viewer'

export interface User {
  id: string
  email: string
  firstName: string
  lastName: string
  status: UserStatus
  role: UserRole
  mfaEnabled: boolean
  lastSignIn: string | null
  createdAt: string
  sessionsCount: number
  authMethods: string[]
}

export type UserActionType = 
  | 'reset_password' 
  | 'ban' 
  | 'unban' 
  | 'view_sessions' 
  | 'delete' 
  | 'change_role'

interface UserAction {
  type: UserActionType
  userId: string
  userName?: string
}

// Status badge component
function StatusBadge({ status }: { status: UserStatus }) {
  const statusConfig = {
    active: { icon: CheckCircle2, className: 'badge-active', label: 'Active' },
    inactive: { icon: Clock, className: 'badge-inactive', label: 'Inactive' },
    banned: { icon: XCircle, className: 'badge-banned', label: 'Banned' },
    pending: { icon: Clock, className: 'badge-pending', label: 'Pending' },
  }
  
  const config = statusConfig[status]
  const Icon = config.icon
  
  return (
    <Badge variant="outline" className={config.className}>
      <Icon className="h-3 w-3 mr-1" />
      {config.label}
    </Badge>
  )
}

// Role badge component
function RoleBadge({ role }: { role: UserRole }) {
  const roleConfig = {
    owner: { className: 'badge-owner', label: 'Owner' },
    admin: { className: 'badge-admin', label: 'Admin' },
    member: { className: 'badge-member', label: 'Member' },
    viewer: { className: 'badge-viewer', label: 'Viewer' },
  }
  
  const config = roleConfig[role]
  
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  )
}

// Column definitions
const columns: ColumnDef<User>[] = [
  {
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && 'indeterminate')
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: 'email',
    header: ({ column }) => {
      return (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          User
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      )
    },
    cell: ({ row }) => {
      const user = row.original
      return (
        <div className="flex flex-col">
          <span className="font-medium">
            {user.firstName} {user.lastName}
          </span>
          <span className="text-sm text-muted-foreground">{user.email}</span>
        </div>
      )
    },
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusBadge status={row.getValue('status')} />,
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
  },
  {
    accessorKey: 'role',
    header: 'Role',
    cell: ({ row }) => <RoleBadge role={row.getValue('role')} />,
    filterFn: (row, id, value) => {
      return value.includes(row.getValue(id))
    },
  },
  {
    accessorKey: 'mfaEnabled',
    header: 'MFA',
    cell: ({ row }) => {
      const mfaEnabled = row.getValue('mfaEnabled') as boolean
      return mfaEnabled ? (
        <Shield className="h-4 w-4 text-green-500" />
      ) : (
        <span className="text-muted-foreground text-sm">-</span>
      )
    },
  },
  {
    accessorKey: 'sessionsCount',
    header: 'Sessions',
    cell: ({ row }) => {
      const count = row.getValue('sessionsCount') as number
      return <span className="text-sm">{count}</span>
    },
  },
  {
    accessorKey: 'lastSignIn',
    header: ({ column }) => {
      return (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Last Sign In
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      )
    },
    cell: ({ row }) => {
      const lastSignIn = row.getValue('lastSignIn') as string | null
      if (!lastSignIn) return <span className="text-muted-foreground text-sm">Never</span>
      return (
        <span className="text-sm">
          {new Date(lastSignIn).toLocaleDateString()}
        </span>
      )
    },
  },
  {
    id: 'actions',
    enableHiding: false,
    cell: ({ row, table }) => {
      const user = row.original
      const meta = table.options.meta as { onAction: (action: UserAction) => void }
      
      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <span className="sr-only">Open menu</span>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'reset_password', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <KeyRound className="mr-2 h-4 w-4" />
              Reset Password
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'view_sessions', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <Eye className="mr-2 h-4 w-4" />
              View Sessions
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'change_role', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <UserCog className="mr-2 h-4 w-4" />
              Change Role
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {user.status === 'banned' ? (
              <DropdownMenuItem
                onClick={() => meta.onAction({ type: 'unban', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Unban User
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => meta.onAction({ type: 'ban', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
              >
                <Ban className="mr-2 h-4 w-4" />
                Ban User
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              className="text-destructive"
              onClick={() => meta.onAction({ type: 'delete', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete User
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )
    },
  },
]

// Faceted filter component
function FacetedFilter({
  title,
  options,
  selectedValues,
  onSelectionChange,
}: {
  title: string
  options: { label: string; value: string }[]
  selectedValues: string[]
  onSelectionChange: (values: string[]) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 border-dashed">
          <Filter className="mr-2 h-4 w-4" />
          {title}
          {selectedValues.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {selectedValues.length}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[200px]">
        <DropdownMenuLabel>{title}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((option) => {
          const isSelected = selectedValues.includes(option.value)
          return (
            <DropdownMenuItem
              key={option.value}
              onClick={() => {
                if (isSelected) {
                  onSelectionChange(selectedValues.filter((v) => v !== option.value))
                } else {
                  onSelectionChange([...selectedValues, option.value])
                }
              }}
            >
              <Checkbox
                checked={isSelected}
                className="mr-2"
              />
              {option.label}
            </DropdownMenuItem>
          )
        })}
        {selectedValues.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onSelectionChange([])}>
              Clear filters
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// Bulk actions toolbar
function BulkActionsToolbar({
  selectedCount,
  onAction,
  onClear,
}: {
  selectedCount: number
  onAction: (action: UserActionType) => void
  onClear: () => void
}) {
  return (
    <div className="flex items-center gap-2 p-2 bg-muted rounded-lg animate-fade-in">
      <span className="text-sm font-medium">
        {selectedCount} selected
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction('reset_password')}
      >
        <KeyRound className="mr-2 h-4 w-4" />
        Reset Passwords
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction('ban')}
      >
        <Ban className="mr-2 h-4 w-4" />
        Ban Selected
      </Button>
      <Button
        variant="destructive"
        size="sm"
        onClick={() => onAction('delete')}
      >
        <Trash2 className="mr-2 h-4 w-4" />
        Delete Selected
      </Button>
      <Button variant="ghost" size="sm" onClick={onClear}>
        <X className="h-4 w-4" />
      </Button>
    </div>
  )
}

// Main component
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

  // Fetch users
  const fetchUsers = React.useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await apiCall(`${API_BASE_URL}/api/v1/admin/activity-logs?per_page=100`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch users')
      }
      
      const activityLogs = await response.json()
      
      // Transform activity logs to users (same logic as identity-list)
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

  // Handle user actions
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
          // Navigate to sessions page
          window.location.href = `/?tab=sessions&userId=${userId}`
          return
        case 'change_role':
          // Would open a role change dialog
          console.log('Change role for:', userId)
          break
      }
      
      // Refresh data after action
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
    
    // For now, just log - in production would open confirmation dialog
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading users...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <h3 className="text-lg font-semibold mb-2">Failed to Load Users</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchUsers} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
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
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={(table.getColumn('email')?.getFilterValue() as string) ?? ''}
              onChange={(event) =>
                table.getColumn('email')?.setFilterValue(event.target.value)
              }
              className="pl-8 w-[250px]"
            />
          </div>
          
          {/* Faceted filters */}
          <FacetedFilter
            title="Status"
            options={[
              { label: 'Active', value: 'active' },
              { label: 'Inactive', value: 'inactive' },
              { label: 'Banned', value: 'banned' },
              { label: 'Pending', value: 'pending' },
            ]}
            selectedValues={statusFilter}
            onSelectionChange={setStatusFilter}
          />
          <FacetedFilter
            title="Role"
            options={[
              { label: 'Owner', value: 'owner' },
              { label: 'Admin', value: 'admin' },
              { label: 'Member', value: 'member' },
              { label: 'Viewer', value: 'viewer' },
            ]}
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
              <X className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchUsers}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
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
        <div className="text-sm text-muted-foreground">
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
      <AlertDialog
        open={actionDialog.open}
        onOpenChange={(open) =>
          !actionDialog.loading &&
          setActionDialog({ open, action: null, loading: false })
        }
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {actionDialog.action?.type === 'delete' && 'Delete User'}
              {actionDialog.action?.type === 'ban' && 'Ban User'}
              {actionDialog.action?.type === 'unban' && 'Unban User'}
              {actionDialog.action?.type === 'reset_password' && 'Reset Password'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {actionDialog.action?.type === 'delete' &&
                `Are you sure you want to delete ${actionDialog.action.userName}? This action cannot be undone.`}
              {actionDialog.action?.type === 'ban' &&
                `Are you sure you want to ban ${actionDialog.action.userName}? They will no longer be able to access the platform.`}
              {actionDialog.action?.type === 'unban' &&
                `Are you sure you want to unban ${actionDialog.action.userName}? They will regain access to the platform.`}
              {actionDialog.action?.type === 'reset_password' &&
                `A password reset email will be sent to ${actionDialog.action.userName}.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionDialog.loading}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={executeAction}
              disabled={actionDialog.loading}
              className={
                actionDialog.action?.type === 'delete' ||
                actionDialog.action?.type === 'ban'
                  ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                  : ''
              }
            >
              {actionDialog.loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                'Confirm'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
