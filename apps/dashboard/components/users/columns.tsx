'use client'

import { ColumnDef } from '@tanstack/react-table'
import {
  MoreHorizontal,
  ArrowUpDown,
  KeyRound,
  Ban,
  Eye,
  Trash2,
  UserCog,
  CheckCircle2,
  Shield,
} from 'lucide-react'
import { Button } from '@janua/ui'
import { Checkbox } from '@janua/ui'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@janua/ui'
import type { User, UserAction } from './types'
import { StatusBadge } from './status-badge'
import { RoleBadge } from './role-badge'

export const columns: ColumnDef<User>[] = [
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
          <ArrowUpDown className="ml-2 size-4" />
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
          <span className="text-muted-foreground text-sm">{user.email}</span>
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
        <Shield className="size-4 text-green-600 dark:text-green-400" />
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
          <ArrowUpDown className="ml-2 size-4" />
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
            <Button variant="ghost" className="size-8 p-0">
              <span className="sr-only">Open menu</span>
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'reset_password', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <KeyRound className="mr-2 size-4" />
              Reset Password
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'view_sessions', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <Eye className="mr-2 size-4" />
              View Sessions
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => meta.onAction({ type: 'change_role', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <UserCog className="mr-2 size-4" />
              Change Role
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {user.status === 'banned' ? (
              <DropdownMenuItem
                onClick={() => meta.onAction({ type: 'unban', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
              >
                <CheckCircle2 className="mr-2 size-4" />
                Unban User
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => meta.onAction({ type: 'ban', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
              >
                <Ban className="mr-2 size-4" />
                Ban User
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              className="text-destructive"
              onClick={() => meta.onAction({ type: 'delete', userId: user.id, userName: `${user.firstName} ${user.lastName}` })}
            >
              <Trash2 className="mr-2 size-4" />
              Delete User
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )
    },
  },
]
