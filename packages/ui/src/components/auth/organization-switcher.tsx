import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface Organization {
  /** Organization ID */
  id: string
  /** Organization name */
  name: string
  /** Organization slug/identifier */
  slug: string
  /** User's role in the organization */
  role?: 'owner' | 'admin' | 'member'
  /** Organization logo URL */
  logoUrl?: string
  /** Number of members */
  memberCount?: number
}

export interface OrganizationSwitcherProps {
  /** Optional custom class name */
  className?: string
  /** Currently active organization (optional if januaClient provided) */
  currentOrganization?: Organization
  /** List of organizations user belongs to (optional if januaClient provided) */
  organizations?: Organization[]
  /** Callback to fetch organizations */
  onFetchOrganizations?: () => Promise<Organization[]>
  /** Callback when organization is switched */
  onSwitchOrganization?: (organization: Organization) => void
  /** Callback to create new organization */
  onCreateOrganization?: () => void
  /** Callback on error */
  onError?: (error: Error) => void
  /** Show create organization option */
  showCreateOrganization?: boolean
  /** Show personal workspace option */
  showPersonalWorkspace?: boolean
  /** Personal workspace data */
  personalWorkspace?: {
    id: string
    name: string
  }
  /** Janua client instance for API integration */
  januaClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
}

export function OrganizationSwitcher({
  className,
  currentOrganization,
  organizations: initialOrganizations,
  onFetchOrganizations,
  onSwitchOrganization,
  onCreateOrganization,
  onError,
  showCreateOrganization = true,
  showPersonalWorkspace = true,
  personalWorkspace,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: OrganizationSwitcherProps) {
  const [organizations, setOrganizations] = React.useState(initialOrganizations)
  const [isOpen, setIsOpen] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Fetch organizations from SDK or callback when dropdown opens
  React.useEffect(() => {
    if (!organizations && isOpen) {
      setIsLoading(true)
      const fetchOrganizations = async () => {
        try {
          if (januaClient) {
            // Use Janua SDK client for real API integration
            const response = await januaClient.organizations.listOrganizations()
            setOrganizations(response.data || response)
          } else if (onFetchOrganizations) {
            // Use custom callback
            const orgs = await onFetchOrganizations()
            setOrganizations(orgs)
          } else {
            // Fallback to direct fetch if SDK client not provided
            const response = await fetch(`${apiUrl}/api/v1/organizations`, {
              credentials: 'include',
            })

            if (!response.ok) {
              throw new Error('Failed to fetch organizations')
            }

            const data = await response.json()
            setOrganizations(data.data || data)
          }
        } catch (err) {
          const error = err instanceof Error ? err : new Error('Failed to fetch organizations')
          setError(error.message)
          onError?.(error)
        } finally {
          setIsLoading(false)
        }
      }

      fetchOrganizations()
    }
  }, [organizations, onFetchOrganizations, onError, isOpen, januaClient, apiUrl])

  const handleSwitchOrganization = (org: Organization) => {
    onSwitchOrganization?.(org)
    setIsOpen(false)
  }

  const handleCreateOrganization = () => {
    onCreateOrganization?.()
    setIsOpen(false)
  }

  const getOrgInitials = (name: string) => {
    return name
      .split(' ')
      .map((word) => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const renderOrgLogo = (org: Organization | { name: string; logoUrl?: string }) => {
    if (org.logoUrl) {
      return (
        <img
          src={org.logoUrl}
          alt={org.name}
          className="w-8 h-8 rounded-md object-cover"
        />
      )
    }

    return (
      <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
        <span className="text-xs font-semibold text-primary">
          {getOrgInitials(org.name)}
        </span>
      </div>
    )
  }

  return (
    <div className={cn('relative', className)}>
      {/* Trigger Button */}
      <Button
        variant="outline"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full justify-between"
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {currentOrganization ? (
            <>
              {renderOrgLogo(currentOrganization)}
              <div className="flex flex-col items-start min-w-0 flex-1">
                <span className="text-sm font-medium truncate max-w-full">
                  {currentOrganization.name}
                </span>
                {currentOrganization.role && (
                  <span className="text-xs text-muted-foreground capitalize">
                    {currentOrganization.role}
                  </span>
                )}
              </div>
            </>
          ) : (
            <span className="text-sm text-muted-foreground">Select organization</span>
          )}
        </div>
        <svg
          className={cn(
            'w-4 h-4 transition-transform ml-2 shrink-0',
            isOpen && 'rotate-180'
          )}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </Button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute top-full left-0 right-0 mt-2 bg-background border rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
              </div>
            ) : (
              <>
                {/* Error Message */}
                {error && (
                  <div className="p-3 text-sm text-destructive border-b">
                    {error}
                  </div>
                )}

                {/* Personal Workspace */}
                {showPersonalWorkspace && personalWorkspace && (
                  <>
                    <div className="p-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Personal
                    </div>
                    <button
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-2 hover:bg-muted transition-colors text-left',
                        !currentOrganization && 'bg-muted'
                      )}
                      onClick={() => {
                        onSwitchOrganization?.({
                          id: personalWorkspace.id,
                          name: personalWorkspace.name,
                          slug: 'personal',
                        })
                        setIsOpen(false)
                      }}
                    >
                      <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {personalWorkspace.name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Personal workspace
                        </div>
                      </div>
                      {!currentOrganization && (
                        <svg className="w-4 h-4 text-primary shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </button>
                  </>
                )}

                {/* Organizations */}
                {organizations && organizations.length > 0 && (
                  <>
                    <div className="p-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Organizations
                    </div>
                    {organizations.map((org) => (
                      <button
                        key={org.id}
                        className={cn(
                          'w-full flex items-center gap-3 px-3 py-2 hover:bg-muted transition-colors text-left',
                          currentOrganization?.id === org.id && 'bg-muted'
                        )}
                        onClick={() => handleSwitchOrganization(org)}
                      >
                        {renderOrgLogo(org)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium truncate">
                              {org.name}
                            </span>
                            {org.role && (
                              <Badge variant="secondary" className="text-xs capitalize shrink-0">
                                {org.role}
                              </Badge>
                            )}
                          </div>
                          {org.memberCount !== undefined && (
                            <div className="text-xs text-muted-foreground">
                              {org.memberCount} {org.memberCount === 1 ? 'member' : 'members'}
                            </div>
                          )}
                        </div>
                        {currentOrganization?.id === org.id && (
                          <svg className="w-4 h-4 text-primary shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                      </button>
                    ))}
                  </>
                )}

                {/* Create Organization */}
                {showCreateOrganization && onCreateOrganization && (
                  <>
                    <div className="border-t my-1"></div>
                    <button
                      className="w-full flex items-center gap-3 px-3 py-2 hover:bg-muted transition-colors text-left"
                      onClick={handleCreateOrganization}
                    >
                      <div className="w-8 h-8 rounded-md border-2 border-dashed border-muted-foreground/30 flex items-center justify-center">
                        <svg className="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 4v16m8-8H4"
                          />
                        </svg>
                      </div>
                      <span className="text-sm font-medium">Create organization</span>
                    </button>
                  </>
                )}

                {/* Empty State */}
                {(!organizations || organizations.length === 0) && !showPersonalWorkspace && (
                  <div className="p-6 text-center">
                    <p className="text-sm text-muted-foreground mb-2">
                      No organizations yet
                    </p>
                    {showCreateOrganization && onCreateOrganization && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCreateOrganization}
                      >
                        Create your first organization
                      </Button>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
