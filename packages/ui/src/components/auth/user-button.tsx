import * as React from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
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
  /** Optional custom class name */
  className?: string
}

export function UserButton({
  user,
  onSignOut,
  showManageAccount = true,
  manageAccountUrl = '/account',
  showOrganizations = false,
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
            className
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
          className="min-w-[220px] bg-background rounded-md shadow-md p-1 z-50"
          sideOffset={5}
          align="end"
        >
          {/* User Info Header */}
          <div className="px-3 py-2 mb-1">
            <p className="text-sm font-medium">{displayName}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
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
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
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
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
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
            <svg
              className="w-4 h-4 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
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
            <svg
              className="w-4 h-4 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
