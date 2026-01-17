'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { SCIMConfigWizard, SCIMSyncStatus } from '@janua/ui'
import type { SyncStatus } from '@janua/ui'
import Link from 'next/link'
import {
  Users,
  ArrowLeft,
  RefreshCw,
  Trash2,
  Settings,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Key,
  RotateCcw,
} from 'lucide-react'
import { apiCall } from '../../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface SCIMConfig {
  id: string
  organization_id: string
  provider: string
  enabled: boolean
  base_url: string
  bearer_token_prefix?: string
  configuration: Record<string, unknown>
  created_at: string
  updated_at: string
}

interface SCIMSyncStatusResponse {
  enabled: boolean
  provider?: string
  total_users: number
  total_groups: number
  synced_users: number
  synced_groups: number
  pending_users: number
  pending_groups: number
  error_users: number
  error_groups: number
  last_sync_at?: string
  recent_operations: Array<{
    id: string
    operation: string
    resource_type: string
    status: string
    synced_at?: string
    error_message?: string
  }>
}

const statusIcons = {
  active: <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />,
  pending: <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />,
  disabled: <XCircle className="h-4 w-4 text-muted-foreground" />,
  error: <XCircle className="h-4 w-4 text-destructive" />,
}

const providerLabels: Record<string, string> = {
  okta: 'Okta',
  azure_ad: 'Azure AD',
  onelogin: 'OneLogin',
  google_workspace: 'Google Workspace',
  jumpcloud: 'JumpCloud',
  ping_identity: 'Ping Identity',
  custom: 'Custom SCIM 2.0',
}

export default function SCIMSettingsPage() {
  const [config, setConfig] = useState<SCIMConfig | null>(null)
  const [syncStatus, setSyncStatus] = useState<SCIMSyncStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [organizationId, setOrganizationId] = useState<string | null>(null)
  const [showWizard, setShowWizard] = useState(false)
  const [rotatingToken, setRotatingToken] = useState(false)
  const [newToken, setNewToken] = useState<string | null>(null)

  useEffect(() => {
    fetchSCIMConfig()
  }, [])

  const fetchSCIMConfig = async () => {
    try {
      setLoading(true)
      setError(null)

      // First get the current user's organization
      const meResponse = await apiCall(`${API_BASE_URL}/api/v1/auth/me`)
      if (!meResponse.ok) throw new Error('Failed to fetch user info')
      const userData = await meResponse.json()

      // Get organization ID from user data or memberships
      const orgId = userData.current_organization_id || userData.organization_id
      if (!orgId) {
        setError('No organization found. Please join or create an organization first.')
        setLoading(false)
        return
      }
      setOrganizationId(orgId)

      // Fetch SCIM configuration
      const configResponse = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${orgId}/scim/config`
      )

      if (configResponse.status === 404) {
        setConfig(null)
      } else if (!configResponse.ok) {
        throw new Error('Failed to fetch SCIM configuration')
      } else {
        const configData = await configResponse.json()
        setConfig(configData)

        // Fetch sync status if config exists
        if (configData) {
          const statusResponse = await apiCall(
            `${API_BASE_URL}/api/v1/organizations/${orgId}/scim/status`
          )
          if (statusResponse.ok) {
            const statusData = await statusResponse.json()
            setSyncStatus(statusData)
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch SCIM configuration:', err)
      setError(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async (enabled: boolean) => {
    if (!organizationId) return

    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${organizationId}/scim/config`,
        {
          method: 'PUT',
          body: JSON.stringify({ enabled }),
        }
      )

      if (!response.ok) throw new Error('Failed to update configuration')

      fetchSCIMConfig()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update configuration')
    }
  }

  const handleDelete = async () => {
    if (!organizationId) return
    if (!confirm('Are you sure you want to delete this SCIM configuration? This will disable all IdP provisioning.')) return

    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${organizationId}/scim/config`,
        { method: 'DELETE' }
      )

      if (!response.ok) throw new Error('Failed to delete configuration')

      setConfig(null)
      setSyncStatus(null)
      setNewToken(null)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete configuration')
    }
  }

  const handleRotateToken = async () => {
    if (!organizationId) return
    if (!confirm('Are you sure you want to rotate the bearer token? The current token will be invalidated immediately.')) return

    try {
      setRotatingToken(true)
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/organizations/${organizationId}/scim/config/token`,
        { method: 'POST' }
      )

      if (!response.ok) throw new Error('Failed to rotate token')

      const data = await response.json()
      setNewToken(data.bearer_token)
      fetchSCIMConfig()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to rotate token')
    } finally {
      setRotatingToken(false)
    }
  }

  const handleWizardSuccess = () => {
    setShowWizard(false)
    fetchSCIMConfig()
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // Convert API response to SyncStatus format expected by component
  const convertToSyncStatus = (status: SCIMSyncStatusResponse): SyncStatus => ({
    last_sync: status.last_sync_at || new Date().toISOString(),
    users_synced: status.synced_users,
    groups_synced: status.synced_groups,
    errors: status.error_users + status.error_groups,
    status: !status.enabled
      ? 'disabled'
      : status.error_users + status.error_groups > 0
      ? 'error'
      : status.pending_users + status.pending_groups > 0
      ? 'pending'
      : 'active',
  })

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading SCIM configuration...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/settings" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <Users className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">SCIM Provisioning</h1>
                <p className="text-sm text-muted-foreground">
                  Automate user provisioning from your identity provider
                </p>
              </div>
            </div>
            <Badge variant="secondary">Enterprise</Badge>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 space-y-6">
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* New Token Display */}
        {newToken && (
          <Card className="border-green-500/30 bg-green-500/10">
            <CardHeader>
              <CardTitle className="text-green-700 dark:text-green-300">New Bearer Token Generated</CardTitle>
              <CardDescription className="text-green-600 dark:text-green-400">
                Copy this token now - it won&apos;t be shown again!
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                <code className="flex-1 p-3 bg-white border rounded font-mono text-sm break-all">
                  {newToken}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(newToken)}
                >
                  Copy
                </Button>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => setNewToken(null)}
              >
                Dismiss
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Configuration Wizard or Existing Config */}
        {showWizard || !config ? (
          <SCIMConfigWizard
            organizationId={organizationId || ''}
            existingConfig={config ? {
              id: config.id,
              organization_id: config.organization_id,
              provider: config.provider as 'okta' | 'azure_ad' | 'google' | 'onelogin' | 'generic',
              scim_url: config.base_url,
              bearer_token: '',
              enabled: config.enabled,
              user_sync_enabled: true,
              group_sync_enabled: true,
              auto_create_users: true,
              auto_suspend_users: false,
            } : undefined}
            apiUrl={API_BASE_URL}
            onCancel={config ? () => setShowWizard(false) : undefined}
            onSuccess={handleWizardSuccess}
            onError={(err) => setError(err.message)}
          />
        ) : (
          <>
            {/* Current Configuration */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>SCIM Configuration</CardTitle>
                    <CardDescription>
                      Manage your organization&apos;s SCIM provisioning settings
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={fetchSCIMConfig}>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setShowWizard(true)}>
                      <Settings className="h-4 w-4 mr-2" />
                      Edit
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-muted rounded-lg">
                      <Users className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {providerLabels[config.provider] || config.provider}
                        </span>
                        <div className="flex items-center gap-1">
                          {config.enabled ? statusIcons.active : statusIcons.disabled}
                          <span className="text-sm text-muted-foreground">
                            {config.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        SCIM Endpoint: {config.base_url}
                      </div>
                      {config.bearer_token_prefix && (
                        <div className="text-sm text-muted-foreground">
                          Token: {config.bearer_token_prefix}...
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRotateToken}
                      disabled={rotatingToken}
                    >
                      {rotatingToken ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <RotateCcw className="h-4 w-4 mr-2" />
                          Rotate Token
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggle(!config.enabled)}
                    >
                      {config.enabled ? 'Disable' : 'Enable'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={handleDelete}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Sync Status */}
            {syncStatus && (
              <SCIMSyncStatus
                organizationId={organizationId || ''}
                syncStatus={convertToSyncStatus(syncStatus)}
              />
            )}

            {/* Recent Sync Operations */}
            {syncStatus && syncStatus.recent_operations.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Recent Sync Operations</CardTitle>
                  <CardDescription>
                    Latest provisioning activity from your identity provider
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {syncStatus.recent_operations.slice(0, 10).map((op) => (
                      <div
                        key={op.id}
                        className="flex items-center justify-between p-3 border rounded-lg text-sm"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`h-2 w-2 rounded-full ${
                            op.status === 'success' ? 'bg-green-500' :
                            op.status === 'failed' ? 'bg-red-500' : 'bg-yellow-500'
                          }`} />
                          <span className="font-medium capitalize">{op.operation}</span>
                          <span className="text-muted-foreground">{op.resource_type}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          {op.error_message && (
                            <span className="text-destructive text-xs">{op.error_message}</span>
                          )}
                          {op.synced_at && (
                            <span className="text-muted-foreground text-xs">
                              {new Date(op.synced_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Information Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">SCIM Endpoint Details</CardTitle>
                  <CardDescription>
                    Use these values when configuring your identity provider
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Base URL:</span>
                    <code className="bg-muted px-2 py-1 rounded text-xs">
                      {config.base_url}
                    </code>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Users Endpoint:</span>
                    <code className="bg-muted px-2 py-1 rounded text-xs">
                      {config.base_url}/Users
                    </code>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Groups Endpoint:</span>
                    <code className="bg-muted px-2 py-1 rounded text-xs">
                      {config.base_url}/Groups
                    </code>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Supported Operations</CardTitle>
                  <CardDescription>
                    SCIM 2.0 operations supported by Janua
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>User Create</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>User Update</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>User Delete</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>User Patch</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>Group Create</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>Group Update</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
