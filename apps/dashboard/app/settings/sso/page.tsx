'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import Link from 'next/link'
import {
  Key,
  Plus,
  ArrowLeft,
  Shield,
  Globe,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Settings,
  RefreshCw,
} from 'lucide-react'
import { apiCall } from '../../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface SSOConfiguration {
  id: string
  organization_id: string
  provider: 'saml' | 'oidc'
  status: 'active' | 'pending' | 'disabled' | 'error'
  enabled: boolean
  saml_entity_id?: string
  saml_sso_url?: string
  oidc_issuer?: string
  oidc_client_id?: string
  jit_provisioning: boolean
  default_role: string
  allowed_domains: string[]
  created_at: string
  updated_at: string
}

const statusIcons = {
  active: <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />,
  pending: <AlertCircle className="size-4 text-yellow-600 dark:text-yellow-400" />,
  disabled: <XCircle className="text-muted-foreground size-4" />,
  error: <XCircle className="text-destructive size-4" />,
}

const statusLabels = {
  active: 'Active',
  pending: 'Pending Setup',
  disabled: 'Disabled',
  error: 'Configuration Error',
}

export default function SSOSettingsPage() {
  const [configurations, setConfigurations] = useState<SSOConfiguration[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [organizationId, setOrganizationId] = useState<string | null>(null)

  useEffect(() => {
    fetchConfigurations()
  }, [])

  const fetchConfigurations = async () => {
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

      // Fetch SSO configurations
      const response = await apiCall(`${API_BASE_URL}/api/v1/sso/configurations/${orgId}`)

      if (response.status === 404) {
        setConfigurations([])
      } else if (!response.ok) {
        throw new Error('Failed to fetch SSO configurations')
      } else {
        const data = await response.json()
        setConfigurations(Array.isArray(data) ? data : data ? [data] : [])
      }
    } catch (err) {
      console.error('Failed to fetch SSO configurations:', err)
      setError(err instanceof Error ? err.message : 'Failed to load configurations')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (configId: string) => {
    setTesting(configId)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/sso/test`, {
        method: 'POST',
        body: JSON.stringify({ configuration_id: configId }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Connection test failed')
      }

      alert('Connection test successful!')
      fetchConfigurations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Connection test failed')
    } finally {
      setTesting(null)
    }
  }

  const handleToggle = async (configId: string, enabled: boolean) => {
    try {
      const endpoint = enabled
        ? `${API_BASE_URL}/api/v1/sso/configurations/${organizationId}/enable`
        : `${API_BASE_URL}/api/v1/sso/configurations/${organizationId}/disable`

      const response = await apiCall(endpoint, { method: 'POST' })

      if (!response.ok) throw new Error('Failed to update configuration')

      fetchConfigurations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update configuration')
    }
  }

  const handleDelete = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this SSO configuration?')) return

    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/sso/configurations/${organizationId}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to delete configuration')

      fetchConfigurations()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete configuration')
    }
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading SSO configurations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/settings" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="size-5" />
              </Link>
              <Key className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Single Sign-On (SSO)</h1>
                <p className="text-muted-foreground text-sm">
                  Configure enterprise SSO with SAML 2.0 or OIDC
                </p>
              </div>
            </div>
            <Badge variant="secondary">Enterprise</Badge>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Provider Selection */}
        {configurations.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Configure SSO Provider</CardTitle>
              <CardDescription>
                Choose your identity provider to enable single sign-on for your organization
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Card className="hover:border-primary/50 cursor-pointer transition-colors">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="bg-primary/10 rounded-lg p-2">
                        <Shield className="text-primary size-6" />
                      </div>
                      <div>
                        <CardTitle className="text-base">SAML 2.0</CardTitle>
                        <CardDescription className="text-sm">
                          Okta, Azure AD, OneLogin, PingFederate
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Button className="w-full" variant="outline">
                      <Plus className="mr-2 size-4" />
                      Configure SAML
                    </Button>
                  </CardContent>
                </Card>

                <Card className="hover:border-primary/50 cursor-pointer transition-colors">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-green-500/10 p-2">
                        <Globe className="size-6 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <CardTitle className="text-base">OpenID Connect</CardTitle>
                        <CardDescription className="text-sm">
                          Google Workspace, Auth0, Keycloak
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Button className="w-full" variant="outline">
                      <Plus className="mr-2 size-4" />
                      Configure OIDC
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        ) : (
          /* Existing Configurations */
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>SSO Configuration</CardTitle>
                  <CardDescription>
                    Manage your organization&apos;s SSO settings
                  </CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={fetchConfigurations}>
                  <RefreshCw className="mr-2 size-4" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {configurations.map((config) => (
                <div
                  key={config.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="bg-muted rounded-lg p-2">
                      {config.provider === 'saml' ? (
                        <Shield className="size-5" />
                      ) : (
                        <Globe className="size-5" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {config.provider === 'saml' ? 'SAML 2.0' : 'OpenID Connect'}
                        </span>
                        <div className="flex items-center gap-1">
                          {statusIcons[config.status]}
                          <span className="text-muted-foreground text-sm">
                            {statusLabels[config.status]}
                          </span>
                        </div>
                      </div>
                      <div className="text-muted-foreground text-sm">
                        {config.provider === 'saml'
                          ? config.saml_entity_id || 'Entity ID not set'
                          : config.oidc_issuer || 'Issuer not set'}
                      </div>
                      {config.allowed_domains.length > 0 && (
                        <div className="mt-1 flex gap-1">
                          {config.allowed_domains.map((domain) => (
                            <Badge key={domain} variant="outline" className="text-xs">
                              {domain}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleTest(config.id)}
                      disabled={testing === config.id}
                    >
                      {testing === config.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        'Test'
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggle(config.id, !config.enabled)}
                    >
                      {config.enabled ? 'Disable' : 'Enable'}
                    </Button>
                    <Button variant="outline" size="sm">
                      <Settings className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Information Cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Service Provider Details</CardTitle>
              <CardDescription>
                Use these values when configuring your identity provider
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ACS URL:</span>
                <code className="bg-muted rounded px-2 py-1 text-xs">
                  {API_BASE_URL}/api/v1/sso/saml/acs
                </code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Entity ID:</span>
                <code className="bg-muted rounded px-2 py-1 text-xs">
                  {API_BASE_URL}/api/v1/sso/metadata/{organizationId || '{org_id}'}
                </code>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Just-in-Time Provisioning</CardTitle>
              <CardDescription>
                Automatically create user accounts on first SSO login
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm">
                When enabled, users who authenticate via SSO will automatically
                receive accounts with the default role you specify.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
