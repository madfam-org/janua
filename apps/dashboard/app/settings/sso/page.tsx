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
  active: <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />,
  pending: <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />,
  disabled: <XCircle className="h-4 w-4 text-muted-foreground" />,
  error: <XCircle className="h-4 w-4 text-destructive" />,
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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading SSO configurations...</p>
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
              <Key className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">Single Sign-On (SSO)</h1>
                <p className="text-sm text-muted-foreground">
                  Configure enterprise SSO with SAML 2.0 or OIDC
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="cursor-pointer hover:border-primary/50 transition-colors">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <Shield className="h-6 w-6 text-primary" />
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
                      <Plus className="h-4 w-4 mr-2" />
                      Configure SAML
                    </Button>
                  </CardContent>
                </Card>

                <Card className="cursor-pointer hover:border-primary/50 transition-colors">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-green-500/10 rounded-lg">
                        <Globe className="h-6 w-6 text-green-600 dark:text-green-400" />
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
                      <Plus className="h-4 w-4 mr-2" />
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
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {configurations.map((config) => (
                <div
                  key={config.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-muted rounded-lg">
                      {config.provider === 'saml' ? (
                        <Shield className="h-5 w-5" />
                      ) : (
                        <Globe className="h-5 w-5" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {config.provider === 'saml' ? 'SAML 2.0' : 'OpenID Connect'}
                        </span>
                        <div className="flex items-center gap-1">
                          {statusIcons[config.status]}
                          <span className="text-sm text-muted-foreground">
                            {statusLabels[config.status]}
                          </span>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {config.provider === 'saml'
                          ? config.saml_entity_id || 'Entity ID not set'
                          : config.oidc_issuer || 'Issuer not set'}
                      </div>
                      {config.allowed_domains.length > 0 && (
                        <div className="flex gap-1 mt-1">
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
                        <Loader2 className="h-4 w-4 animate-spin" />
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
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Information Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                <code className="bg-muted px-2 py-1 rounded text-xs">
                  {API_BASE_URL}/api/v1/sso/saml/acs
                </code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Entity ID:</span>
                <code className="bg-muted px-2 py-1 rounded text-xs">
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
              <p className="text-sm text-muted-foreground">
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
