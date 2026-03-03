import * as React from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { User, Users, Settings, LogOut } from 'lucide-react'
import { Avatar, AvatarImage, AvatarFallback } from '../avatar'
import { cn } from '../../lib/utils'

export interface UserButtonProps {
  /** User data */
  user: {
    id: string
    email: string
    firstName?: string
    lastName?: string
    avatarUrl?: string
  }
  /** Callback when user signs out */
  onSignOut?: () => void
  /** Show manage account option */
  showManageAccount?: boolean
  /** Custom manage account URL */
  manageAccountUrl?: string
  /** Show organization switcher */
  showOrganizations?: boolean
  /** Active organization name to display */
  activeOrganization?: string
  /** Optional custom class name */
  className?: string
}

export function UserButton({
  user,
  onSignOut,
  showManageAccount = true,
  manageAccountUrl = '/account',
  showOrganizations = false,
  activeOrganization,
  className,
}: UserButtonProps) {
  const displayName = user.firstName && user.lastName
    ? `${user.firstName} ${user.lastName}`
    : user.email

  const initials = user.firstName && user.lastName
    ? `${user.firstName[0]}${user.lastName[0]}`.toUpperCase()
    : user.email[0].toUpperCase()

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex items-center gap-2 rounded-full hover:opacity-80 transition-opacity focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
            className,
          )}
          aria-label="User menu"
        >
          <Avatar>
            <AvatarImage src={user.avatarUrl} alt={displayName} />
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={cn(
            'min-w-[220px] bg-background rounded-md shadow-md p-1 z-50 border border-border',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
            'data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2',
          )}
          sideOffset={5}
          align="end"
        >
          {/* User Info Header */}
          <div className="px-3 py-2 mb-1">
            <p className="text-sm font-medium">{displayName}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
            {activeOrganization && (
              <p className="text-xs text-muted-foreground mt-0.5">{activeOrganization}</p>
            )}
          </div>

          <DropdownMenu.Separator className="h-px bg-border my-1" />

          {/* Manage Account */}
          {showManageAccount && (
            <DropdownMenu.Item
              className="relative flex items-center px-3 py-2 text-sm outline-none cursor-pointer hover:bg-accent hover:text-accent-foreground rounded-sm"
              onSelect={() => {
                window.location.href = manageAccountUrl
              }}
            >
              <User className="w-4 h-4 mr-2" />
              Manage account
            </DropdownMenu.Item>
          )}

          {/* Organizations (if enabled) */}
          {showOrganizations && (
            <>
              <DropdownMenu.Item
                className="relative flex items-center px-3 py-2 text-sm outline-none cursor-pointer hover:bg-accent hover:text-accent-foreground rounded-sm"
                onSelect={() => {
                  window.location.href = '/organizations'
                }}
              >
                <Users className="w-4 h-4 mr-2" />
                Organizations
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="h-px bg-border my-1" />
            </>
          )}

          {/* Settings */}
          <DropdownMenu.Item
            className="relative flex items-center px-3 py-2 text-sm outline-none cursor-pointer hover:bg-accent hover:text-accent-foreground rounded-sm"
            onSelect={() => {
              window.location.href = '/settings'
            }}
          >
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="h-px bg-border my-1" />

          {/* Sign Out */}
          <DropdownMenu.Item
            className="relative flex items-center px-3 py-2 text-sm outline-none cursor-pointer hover:bg-destructive hover:text-destructive-foreground rounded-sm text-destructive"
            onSelect={() => {
              onSignOut?.()
            }}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
