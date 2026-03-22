import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface SSOConfiguration {
  id: string
  organization_id: string
  provider: 'saml' | 'oidc' | 'google_workspace' | 'azure_ad' | 'okta'
  status: 'active' | 'pending' | 'disabled' | 'error'
  enabled: boolean
  saml_entity_id?: string
  saml_acs_url?: string
  saml_sso_url?: string
  oidc_issuer?: string
  oidc_client_id?: string
  oidc_authorization_url?: string
  jit_provisioning: boolean
  default_role: string
  allowed_domains: string[]
  created_at: string
  updated_at: string
}

export interface SSOProviderListProps {
  className?: string
  organizationId: string
  configurations?: SSOConfiguration[]
  onFetchConfigurations?: () => Promise<SSOConfiguration[]>
  onEdit?: (config: SSOConfiguration) => void
  onDelete?: (configId: string) => Promise<void>
  onTest?: (configId: string) => Promise<void>
  onToggleEnabled?: (configId: string, enabled: boolean) => Promise<void>
  onError?: (error: Error) => void
  januaClient?: any
  apiUrl?: string
  showActions?: boolean
}

export function SSOProviderList({
  className,
  organizationId,
  configurations: initialConfigurations,
  onFetchConfigurations,
  onEdit,
  onDelete,
  onTest,
  onToggleEnabled,
  onError,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  showActions = true,
}: SSOProviderListProps) {
  const [configurations, setConfigurations] = React.useState<SSOConfiguration[]>(
    initialConfigurations || []
  )
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Fetch configurations
  const fetchConfigurations = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      let configs: SSOConfiguration[]

      if (januaClient) {
        const config = await januaClient.sso.getConfiguration(organizationId)
        configs = config ? [config] : []
      } else if (onFetchConfigurations) {
        configs = await onFetchConfigurations()
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/configurations/${organizationId}`, {
          credentials: 'include',
        })

        if (res.status === 404) {
          configs = []
        } else if (!res.ok) {
          throw new Error('Failed to fetch SSO configurations')
        } else {
          const config = await res.json()
          configs = [config]
        }
      }

      setConfigurations(configs)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch SSO configurations')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }, [organizationId, januaClient, onFetchConfigurations, apiUrl, onError])

  React.useEffect(() => {
    if (!initialConfigurations) {
      fetchConfigurations()
    }
  }, [initialConfigurations, fetchConfigurations])

  // Handle delete
  const handleDelete = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this SSO configuration?')) {
      return
    }

    try {
      if (januaClient) {
        await januaClient.sso.deleteConfiguration(organizationId)
      } else if (onDelete) {
        await onDelete(configId)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/configurations/${organizationId}`, {
          method: 'DELETE',
          credentials: 'include',
        })

        if (!res.ok) {
          throw new Error('Failed to delete SSO configuration')
        }
      }

      await fetchConfigurations()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to delete SSO configuration')
      setError(error.message)
      onError?.(error)
    }
  }

  // Handle test
  const handleTest = async (configId: string) => {
    try {
      if (januaClient) {
        await januaClient.sso.testConfiguration(configId)
      } else if (onTest) {
        await onTest(configId)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/test`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ configuration_id: configId }),
        })

        if (!res.ok) {
          throw new Error('SSO test failed')
        }
      }

      alert('SSO configuration test successful!')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('SSO test failed')
      alert(`Test failed: ${error.message}`)
      onError?.(error)
    }
  }

  // Handle toggle enabled
  const handleToggleEnabled = async (configId: string, enabled: boolean) => {
    try {
      if (januaClient) {
        if (enabled) {
          await januaClient.sso.enableConfiguration(organizationId)
        } else {
          await januaClient.sso.disableConfiguration(organizationId)
        }
      } else if (onToggleEnabled) {
        await onToggleEnabled(configId, enabled)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/configurations/${organizationId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ enabled }),
        })

        if (!res.ok) {
          throw new Error('Failed to update SSO configuration')
        }
      }

      await fetchConfigurations()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update SSO configuration')
      setError(error.message)
      onError?.(error)
    }
  }

  // Get provider display name
  const getProviderName = (provider: string) => {
    const names: Record<string, string> = {
      saml: 'SAML 2.0',
      oidc: 'OIDC/OAuth2',
      google_workspace: 'Google Workspace',
      azure_ad: 'Azure AD',
      okta: 'Okta',
    }
    return names[provider] || provider
  }

  // Get status badge
  const getStatusBadge = (status: string, enabled: boolean) => {
    if (!enabled) {
      return <Badge variant="secondary">Disabled</Badge>
    }

    const variants: Record<string, { variant: any; label: string }> = {
      active: { variant: 'success', label: 'Active' },
      pending: { variant: 'default', label: 'Pending' },
      disabled: { variant: 'secondary', label: 'Disabled' },
      error: { variant: 'destructive', label: 'Error' },
    }

    const config = variants[status] ?? { variant: 'default' as const, label: 'Pending' }

    return <Badge variant={config.variant as any}>{config.label}</Badge>
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">SSO Providers</h3>
          <p className="text-sm text-muted-foreground">
            Configure enterprise Single Sign-On for your organization
          </p>
        </div>
        <Button onClick={() => fetchConfigurations()} variant="outline" disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Refresh'}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Configurations */}
      {isLoading ? (
        <div className="p-8 text-center text-muted-foreground">
          Loading SSO configurations...
        </div>
      ) : configurations.length === 0 ? (
        <div className="p-8 border-2 border-dashed rounded-lg text-center space-y-4">
          <div className="mx-auto w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h4 className="font-medium">No SSO Configuration</h4>
            <p className="text-sm text-muted-foreground mt-1">
              Configure SAML or OIDC to enable Single Sign-On for your organization
            </p>
          </div>
          <Button onClick={() => onEdit?.({} as SSOConfiguration)}>
            Configure SSO
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {configurations.map((config) => (
            <div
              key={config.id}
              className="p-6 border rounded-lg space-y-4 hover:shadow-md transition-shadow"
            >
              {/* Header */}
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <h4 className="text-lg font-semibold">
                      {getProviderName(config.provider)}
                    </h4>
                    {getStatusBadge(config.status, config.enabled)}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Created {new Date(config.created_at).toLocaleDateString()}
                  </p>
                </div>

                {/* Toggle */}
                {showActions && (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.enabled}
                      onChange={(e) => handleToggleEnabled(config.id, e.target.checked)}
                      className="rounded"
                    />
                    <span className="text-sm font-medium">Enabled</span>
                  </label>
                )}
              </div>

              {/* Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                {config.provider === 'saml' && (
                  <>
                    {config.saml_entity_id && (
                      <div>
                        <span className="font-medium">Entity ID:</span>
                        <div className="text-muted-foreground truncate">{config.saml_entity_id}</div>
                      </div>
                    )}
                    {config.saml_sso_url && (
                      <div>
                        <span className="font-medium">SSO URL:</span>
                        <div className="text-muted-foreground truncate">{config.saml_sso_url}</div>
                      </div>
                    )}
                  </>
                )}

                {config.provider === 'oidc' && (
                  <>
                    {config.oidc_issuer && (
                      <div>
                        <span className="font-medium">Issuer:</span>
                        <div className="text-muted-foreground truncate">{config.oidc_issuer}</div>
                      </div>
                    )}
                    {config.oidc_client_id && (
                      <div>
                        <span className="font-medium">Client ID:</span>
                        <div className="text-muted-foreground truncate">{config.oidc_client_id}</div>
                      </div>
                    )}
                  </>
                )}

                <div>
                  <span className="font-medium">Default Role:</span>
                  <span className="text-muted-foreground capitalize ml-2">{config.default_role}</span>
                </div>

                <div>
                  <span className="font-medium">JIT Provisioning:</span>
                  <span className="text-muted-foreground ml-2">
                    {config.jit_provisioning ? 'Enabled' : 'Disabled'}
                  </span>
                </div>

                {config.allowed_domains.length > 0 && (
                  <div className="md:col-span-2">
                    <span className="font-medium">Allowed Domains:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {config.allowed_domains.map((domain) => (
                        <Badge key={domain} variant="outline" className="text-xs">
                          {domain}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Actions */}
              {showActions && (
                <div className="flex gap-2 pt-2 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleTest(config.id)}
                  >
                    Test Connection
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit?.(config)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(config.id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    Delete
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
