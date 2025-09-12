"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Shield, AlertCircle, CheckCircle, XCircle, Copy, Download, Upload } from 'lucide-react'

interface SSOConfig {
  id: string
  organizationId: string
  provider: 'saml' | 'oidc' | 'oauth2'
  status: 'active' | 'inactive' | 'pending' | 'error'
  enabled: boolean
  samlEntityId?: string
  samlAcsUrl?: string
  samlSsoUrl?: string
  samlMetadataUrl?: string
  oidcIssuer?: string
  oidcClientId?: string
  oidcAuthorizationUrl?: string
  jitProvisioning: boolean
  defaultRole: string
  allowedDomains: string[]
  createdAt: string
  updatedAt: string
}

interface SSOConfigurationProps {
  organizationId: string
}

export function SSOConfiguration({ organizationId }: SSOConfigurationProps) {
  const [config, setConfig] = useState<SSOConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('configuration')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  // Form state
  const [provider, setProvider] = useState<'saml' | 'oidc'>('saml')
  const [metadataUrl, setMetadataUrl] = useState('')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [issuer, setIssuer] = useState('')
  const [jitProvisioning, setJitProvisioning] = useState(true)
  const [defaultRole, setDefaultRole] = useState('member')
  const [allowedDomains, setAllowedDomains] = useState<string[]>([])
  const [domainInput, setDomainInput] = useState('')

  useEffect(() => {
    fetchConfiguration()
  }, [organizationId])

  const fetchConfiguration = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/v1/sso/configurations/${organizationId}`)
      if (response.ok) {
        const data = await response.json()
        setConfig(data)
        // Populate form with existing config
        if (data) {
          setProvider(data.provider)
          setMetadataUrl(data.samlMetadataUrl || '')
          setClientId(data.oidcClientId || '')
          setIssuer(data.oidcIssuer || '')
          setJitProvisioning(data.jitProvisioning)
          setDefaultRole(data.defaultRole)
          setAllowedDomains(data.allowedDomains || [])
        }
      } else if (response.status === 404) {
        // No configuration exists yet
        setConfig(null)
      } else {
        throw new Error('Failed to fetch SSO configuration')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveConfiguration = async () => {
    try {
      const payload: any = {
        provider,
        jit_provisioning: jitProvisioning,
        default_role: defaultRole,
        allowed_domains: allowedDomains,
      }

      if (provider === 'saml') {
        payload.saml_metadata_url = metadataUrl
      } else if (provider === 'oidc') {
        payload.oidc_client_id = clientId
        payload.oidc_client_secret = clientSecret
        payload.oidc_issuer = issuer
      }

      const url = config 
        ? `/api/v1/sso/configurations/${organizationId}`
        : `/api/v1/sso/configurations`
      
      const method = config ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config ? payload : { ...payload, organization_id: organizationId })
      })

      if (response.ok) {
        const data = await response.json()
        setConfig(data)
        setError(null)
      } else {
        throw new Error('Failed to save SSO configuration')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }

  const handleTestConfiguration = async () => {
    if (!config) return
    
    try {
      const response = await fetch('/api/v1/sso/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ configuration_id: config.id })
      })

      const data = await response.json()
      setTestResult({
        success: response.ok,
        message: data.message || (response.ok ? 'Configuration test successful' : 'Configuration test failed')
      })
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : 'Test failed'
      })
    }
  }

  const handleToggleSSO = async () => {
    if (!config) return
    
    try {
      const response = await fetch(`/api/v1/sso/configurations/${organizationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !config.enabled })
      })

      if (response.ok) {
        const data = await response.json()
        setConfig(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle SSO')
    }
  }

  const handleAddDomain = () => {
    if (domainInput && !allowedDomains.includes(domainInput)) {
      setAllowedDomains([...allowedDomains, domainInput])
      setDomainInput('')
    }
  }

  const handleRemoveDomain = (domain: string) => {
    setAllowedDomains(allowedDomains.filter(d => d !== domain))
  }

  const downloadSPMetadata = () => {
    window.open(`/api/v1/sso/metadata/${organizationId}`, '_blank')
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  if (loading) {
    return <div className="flex items-center justify-center p-8">Loading SSO configuration...</div>
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Shield className="h-5 w-5" />
              <CardTitle>Single Sign-On (SSO)</CardTitle>
            </div>
            {config && (
              <div className="flex items-center space-x-4">
                <Badge variant={config.status === 'active' ? 'success' : 'secondary'}>
                  {config.status}
                </Badge>
                <Switch
                  checked={config.enabled}
                  onCheckedChange={handleToggleSSO}
                />
              </div>
            )}
          </div>
          <CardDescription>
            Configure enterprise SSO for your organization using SAML 2.0 or OIDC
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="configuration">Configuration</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
              <TabsTrigger value="test">Test & Debug</TabsTrigger>
            </TabsList>

            <TabsContent value="configuration" className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider Type</Label>
                <Select value={provider} onValueChange={(v: any) => setProvider(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="saml">SAML 2.0</SelectItem>
                    <SelectItem value="oidc">OpenID Connect (OIDC)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {provider === 'saml' && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="metadata-url">IdP Metadata URL</Label>
                    <Input
                      id="metadata-url"
                      placeholder="https://idp.example.com/metadata"
                      value={metadataUrl}
                      onChange={(e) => setMetadataUrl(e.target.value)}
                    />
                  </div>

                  {config && (
                    <div className="space-y-2">
                      <Label>Service Provider URLs</Label>
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <span>Entity ID:</span>
                          <div className="flex items-center space-x-2">
                            <code>{config.samlEntityId}</code>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => copyToClipboard(config.samlEntityId || '')}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                          <span>ACS URL:</span>
                          <div className="flex items-center space-x-2">
                            <code>{config.samlAcsUrl}</code>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => copyToClipboard(config.samlAcsUrl || '')}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={downloadSPMetadata}
                        className="mt-2"
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Download SP Metadata
                      </Button>
                    </div>
                  )}
                </>
              )}

              {provider === 'oidc' && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="issuer">Issuer URL</Label>
                    <Input
                      id="issuer"
                      placeholder="https://idp.example.com"
                      value={issuer}
                      onChange={(e) => setIssuer(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="client-id">Client ID</Label>
                    <Input
                      id="client-id"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="client-secret">Client Secret</Label>
                    <Input
                      id="client-secret"
                      type="password"
                      value={clientSecret}
                      onChange={(e) => setClientSecret(e.target.value)}
                    />
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="settings" className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Just-In-Time (JIT) Provisioning</Label>
                  <p className="text-sm text-gray-500">
                    Automatically create user accounts on first SSO login
                  </p>
                </div>
                <Switch
                  checked={jitProvisioning}
                  onCheckedChange={setJitProvisioning}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="default-role">Default Role</Label>
                <Select value={defaultRole} onValueChange={setDefaultRole}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="viewer">Viewer</SelectItem>
                    <SelectItem value="member">Member</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Allowed Email Domains</Label>
                <div className="flex space-x-2">
                  <Input
                    placeholder="example.com"
                    value={domainInput}
                    onChange={(e) => setDomainInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAddDomain()}
                  />
                  <Button onClick={handleAddDomain}>Add</Button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {allowedDomains.map((domain) => (
                    <Badge key={domain} variant="secondary">
                      {domain}
                      <button
                        onClick={() => handleRemoveDomain(domain)}
                        className="ml-2 text-xs hover:text-red-600"
                      >
                        ×
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="test" className="space-y-4">
              <div className="space-y-4">
                <Button 
                  onClick={handleTestConfiguration}
                  disabled={!config}
                  className="w-full"
                >
                  Test SSO Configuration
                </Button>

                {testResult && (
                  <Alert variant={testResult.success ? 'default' : 'destructive'}>
                    {testResult.success ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    <AlertDescription>{testResult.message}</AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <Label>SSO Login URL</Label>
                  <div className="flex items-center space-x-2">
                    <Input
                      readOnly
                      value={`${window.location.origin}/api/v1/sso/initiate?organization_slug=${organizationId}`}
                    />
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyToClipboard(`${window.location.origin}/api/v1/sso/initiate?organization_slug=${organizationId}`)}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end mt-6">
            <Button onClick={handleSaveConfiguration}>
              Save Configuration
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}