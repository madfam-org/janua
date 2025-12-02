'use client'

import * as React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui/components/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui/components/card'
import {
  SSOProviderList,
  SSOProviderForm,
  SAMLConfigForm,
  SSOTestConnection,
} from '@janua/ui/components/auth'
import { januaClient } from '@/lib/janua-client'

export default function SSOShowcasePage() {
  const [activeTab, setActiveTab] = React.useState('providers')
  const [selectedProvider, setSelectedProvider] = React.useState<any | null>(null)
  const [showProviderForm, setShowProviderForm] = React.useState(false)
  const [showSAMLConfig, setShowSAMLConfig] = React.useState(false)
  const [showTestConnection, setShowTestConnection] = React.useState(false)

  // Mock organization ID (in production, get from auth context)
  const organizationId = 'demo-org-123'

  // Handler for provider created
  const handleProviderCreated = async (config: any): Promise<any> => {
    // removed console.log

    // In a real app, this would call the API
    // For now, just simulate the response
    const provider = {
      id: `sso-${Date.now()}`,
      ...config,
      created_at: new Date().toISOString(),
      status: 'active'
    }

    setSelectedProvider(provider)
    setShowProviderForm(false)

    // If SAML provider, show SAML config tab
    if (config.provider === 'saml') {
      setShowSAMLConfig(true)
      setActiveTab('saml-config')
    }

    return provider
  }

  // Handler for editing provider
  const handleEditProvider = (provider: any) => {
    setSelectedProvider(provider)
    setShowProviderForm(true)
    setActiveTab('configure')
  }

  // Handler for testing connection
  const handleTestConnection = async (configId: string) => {
    const config = await januaClient.sso.getConfiguration(configId)
    setSelectedProvider(config)
    setShowTestConnection(true)
    setActiveTab('test')
  }

  // Handler for SAML config saved
  const handleSAMLConfigSaved = async (config: any): Promise<void> => {
    // removed console.log
    setActiveTab('test')
    setShowTestConnection(true)
  }

  // Handler for test completed
  const handleTestCompleted = () => {
    // removed console.log
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">SSO Configuration</h1>
          <p className="text-muted-foreground">
            Configure Single Sign-On (SSO) providers for your organization. Support for SAML 2.0, OIDC, and popular identity providers.
          </p>
        </div>

        {/* Info Card */}
        <Card className="border-blue-200 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-800">
          <CardHeader>
            <CardTitle className="text-blue-900 dark:text-blue-100">📘 SSO Overview</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-blue-800 dark:text-blue-200 space-y-2">
            <p><strong>What is SSO?</strong> Single Sign-On allows users to authenticate using your organization's identity provider (like Google Workspace, Azure AD, or Okta).</p>
            <p><strong>Benefits:</strong></p>
            <ul className="list-disc list-inside ml-4 space-y-1">
              <li>Enhanced security with centralized authentication</li>
              <li>Simplified user experience (one login for all services)</li>
              <li>Automated user provisioning with Just-In-Time (JIT) creation</li>
              <li>Compliance with enterprise security policies</li>
            </ul>
            <p><strong>Supported Protocols:</strong> SAML 2.0, OpenID Connect (OIDC), OAuth 2.0</p>
          </CardContent>
        </Card>

        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="providers">
              Providers
              <span className="ml-2 text-xs text-muted-foreground">(List)</span>
            </TabsTrigger>
            <TabsTrigger value="configure">
              Configure
              <span className="ml-2 text-xs text-muted-foreground">(Create/Edit)</span>
            </TabsTrigger>
            <TabsTrigger value="saml-config" disabled={!showSAMLConfig && !selectedProvider}>
              SAML Setup
              <span className="ml-2 text-xs text-muted-foreground">(Advanced)</span>
            </TabsTrigger>
            <TabsTrigger value="test" disabled={!showTestConnection && !selectedProvider}>
              Test
              <span className="ml-2 text-xs text-muted-foreground">(Validate)</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Providers List */}
          <TabsContent value="providers" className="mt-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>SSO Providers</CardTitle>
                    <CardDescription>
                      Manage your organization's SSO configurations
                    </CardDescription>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedProvider(null)
                      setShowProviderForm(true)
                      setActiveTab('configure')
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                  >
                    + Add Provider
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                <SSOProviderList
                  organizationId={organizationId}
                  januaClient={januaClient}
                  onEdit={handleEditProvider}
                  onTest={handleTestConnection}
                  onDelete={async (configId) => {
                    const config = await januaClient.sso.getConfiguration(configId)
                    if (confirm(`Delete ${config.provider}?`)) {
                      // removed console.log
                      await januaClient.sso.deleteConfiguration(configId)
                    }
                  }}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2: Configure Provider */}
          <TabsContent value="configure" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>
                  {selectedProvider ? 'Edit SSO Provider' : 'Create SSO Provider'}
                </CardTitle>
                <CardDescription>
                  {selectedProvider
                    ? `Modify configuration for ${selectedProvider.name}`
                    : 'Configure a new SSO provider for your organization'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SSOProviderForm
                  organizationId={organizationId}
                  configuration={selectedProvider || undefined}
                  januaClient={januaClient}
                  onSubmit={handleProviderCreated}
                  onCancel={() => {
                    setShowProviderForm(false)
                    setSelectedProvider(null)
                    setActiveTab('providers')
                  }}
                />
              </CardContent>
            </Card>

            {/* Quick Start Guides */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>📚 Quick Start Guides</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Google Workspace Guide */}
                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold flex items-center gap-2">
                      <span className="text-2xl">🔵</span>
                      Google Workspace
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Configure SAML SSO with Google Workspace as your identity provider.
                    </p>
                    <ol className="text-sm space-y-1 list-decimal list-inside">
                      <li>Select "SAML" as provider type</li>
                      <li>Download SP metadata from SAML Setup tab</li>
                      <li>Upload to Google Admin Console</li>
                      <li>Copy IdP metadata URL back here</li>
                    </ol>
                  </div>

                  {/* Azure AD Guide */}
                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold flex items-center gap-2">
                      <span className="text-2xl">🔷</span>
                      Azure AD
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Configure SAML or OIDC SSO with Microsoft Azure Active Directory.
                    </p>
                    <ol className="text-sm space-y-1 list-decimal list-inside">
                      <li>Select "SAML" or "OIDC" type</li>
                      <li>Create Enterprise App in Azure</li>
                      <li>Configure SSO in Azure portal</li>
                      <li>Enter metadata/credentials here</li>
                    </ol>
                  </div>

                  {/* Okta Guide */}
                  <div className="border rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold flex items-center gap-2">
                      <span className="text-2xl">🟦</span>
                      Okta
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Configure SAML SSO with Okta as your identity provider.
                    </p>
                    <ol className="text-sm space-y-1 list-decimal list-inside">
                      <li>Select "SAML" as provider type</li>
                      <li>Create SAML 2.0 app in Okta</li>
                      <li>Download SP metadata from SAML Setup</li>
                      <li>Copy IdP metadata from Okta</li>
                    </ol>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 3: SAML Configuration */}
          <TabsContent value="saml-config" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>SAML 2.0 Configuration</CardTitle>
                <CardDescription>
                  Advanced SAML settings, certificate management, and attribute mapping
                  {selectedProvider && ` for ${selectedProvider.name}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedProvider && selectedProvider.provider_type === 'saml' ? (
                  <SAMLConfigForm
                    organizationId={organizationId}
                    januaClient={januaClient}
                    onSubmit={handleSAMLConfigSaved}
                  />
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <p>Select a SAML provider from the Providers tab to configure SAML settings.</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* SAML Information Card */}
            <Card className="mt-6 border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800">
              <CardHeader>
                <CardTitle className="text-amber-900 dark:text-amber-100">🔐 SAML Key Concepts</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-amber-800 dark:text-amber-200 space-y-2">
                <p><strong>Service Provider (SP):</strong> Your application (Janua)</p>
                <p><strong>Identity Provider (IdP):</strong> Your organization's authentication system (Google, Azure, Okta)</p>
                <p><strong>Entity ID:</strong> Unique identifier for your application</p>
                <p><strong>ACS URL:</strong> Assertion Consumer Service - where SAML responses are sent</p>
                <p><strong>Attribute Mapping:</strong> Maps IdP user attributes to your application's user fields</p>
                <p><strong>JIT Provisioning:</strong> Automatically creates users on first SSO login</p>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 4: Test Connection */}
          <TabsContent value="test" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Test SSO Connection</CardTitle>
                <CardDescription>
                  Validate your SSO configuration and troubleshoot issues
                  {selectedProvider && ` for ${selectedProvider.name}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedProvider ? (
                  <SSOTestConnection
                    configurationId={selectedProvider.id}
                    organizationId={organizationId}
                    januaClient={januaClient}
                    onClose={handleTestCompleted}
                  />
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <p>Select a provider from the Providers tab to test the SSO connection.</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Testing Tips */}
            <Card className="mt-6 border-green-200 bg-green-50 dark:bg-green-900/20 dark:border-green-800">
              <CardHeader>
                <CardTitle className="text-green-900 dark:text-green-100">✅ Testing Tips</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-green-800 dark:text-green-200 space-y-2">
                <p><strong>Metadata Validation:</strong> Quick test to verify IdP metadata is valid and accessible</p>
                <p><strong>Authentication Test:</strong> Simulates SSO login flow without actually logging in</p>
                <p><strong>Full Test:</strong> Comprehensive validation including metadata, certificates, and authentication</p>
                <p><strong>Common Issues:</strong></p>
                <ul className="list-disc list-inside ml-4 space-y-1">
                  <li>Certificate expired or invalid</li>
                  <li>Incorrect Entity ID or ACS URL</li>
                  <li>Metadata URL unreachable</li>
                  <li>Attribute mapping mismatch</li>
                </ul>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer Info */}
        <Card className="bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          <CardContent className="pt-6">
            <div className="text-sm text-muted-foreground space-y-2">
              <p><strong>Need Help?</strong></p>
              <ul className="list-disc list-inside ml-4 space-y-1">
                <li>Check our <a href="#" className="text-blue-600 hover:underline">SSO Configuration Guide</a></li>
                <li>View <a href="#" className="text-blue-600 hover:underline">Provider-Specific Tutorials</a></li>
                <li>Contact <a href="#" className="text-blue-600 hover:underline">Enterprise Support</a></li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
