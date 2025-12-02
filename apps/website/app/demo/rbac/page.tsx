'use client'

import { SCIMConfigWizard, SCIMSyncStatus, RoleManager } from '@janua/ui'
import { useState } from 'react'

export default function SCIMRBACShowcase() {
  const [activeTab, setActiveTab] = useState<'scim' | 'rbac'>('scim')

  // Sample data
  const samplePermissions = [
    'users:read',
    'users:write',
    'users:delete',
    'organizations:read',
    'organizations:write',
    'roles:read',
    'roles:write',
    'audit:read',
    'compliance:read',
    'compliance:write',
    'sso:configure',
    'scim:configure',
  ]

  const sampleRoles = [
    {
      id: 'role-admin',
      name: 'Administrator',
      description: 'Full system access',
      permissions: samplePermissions,
      organization_id: 'org-123',
      is_system_role: true,
      created_at: new Date().toISOString(),
    },
    {
      id: 'role-manager',
      name: 'Manager',
      description: 'Manage users and view reports',
      permissions: ['users:read', 'users:write', 'organizations:read', 'audit:read'],
      organization_id: 'org-123',
      is_system_role: false,
      created_at: new Date().toISOString(),
    },
  ]

  const sampleSyncStatus = {
    last_sync: new Date(Date.now() - 3600000).toISOString(),
    users_synced: 42,
    groups_synced: 8,
    errors: 0,
    status: 'active' as const,
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            SCIM Provisioning & RBAC Management
          </h1>
          <p className="mt-2 text-gray-600">
            Enterprise user provisioning with SCIM 2.0 and role-based access control
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6 flex space-x-1 rounded-lg bg-white p-1 shadow">
          {[
            { key: 'scim' as const, label: 'SCIM Provisioning', icon: '🔄' },
            { key: 'rbac' as const, label: 'Role Management', icon: '👥' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === 'scim' && (
            <div className="space-y-6">
              <div className="rounded-lg bg-blue-50 p-4">
                <h3 className="font-semibold text-blue-900">SCIM 2.0 Provisioning</h3>
                <p className="mt-1 text-sm text-blue-700">
                  Automatically sync users and groups from your Identity Provider (Okta, Azure AD,
                  Google, OneLogin)
                </p>
              </div>

              <SCIMSyncStatus
                organizationId="org-demo-123"
                syncStatus={sampleSyncStatus}
              />

              <SCIMConfigWizard
                organizationId="org-demo-123"
                onSubmit={async (config) => {
                  // removed console.log
                  await new Promise((resolve) => setTimeout(resolve, 1500))
                  return {
                    ...config,
                    id: 'scim-' + Date.now(),
                  }
                }}
                onSuccess={(config) => {
                  // removed console.log
                }}
              />
            </div>
          )}

          {activeTab === 'rbac' && (
            <div className="space-y-6">
              <div className="rounded-lg bg-purple-50 p-4">
                <h3 className="font-semibold text-purple-900">
                  Role-Based Access Control (RBAC)
                </h3>
                <p className="mt-1 text-sm text-purple-700">
                  Create custom roles with granular permissions for your organization
                </p>
              </div>

              <RoleManager
                organizationId="org-demo-123"
                roles={sampleRoles}
                permissions={samplePermissions}
                onCreateRole={async (role) => {
                  // removed console.log
                  await new Promise((resolve) => setTimeout(resolve, 1000))
                  return {
                    ...role,
                    id: 'role-' + Date.now(),
                    created_at: new Date().toISOString(),
                  }
                }}
              />
            </div>
          )}
        </div>

        {/* Features Grid */}
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-2xl">
              🔄
            </div>
            <h3 className="mt-4 font-semibold">Auto-Sync</h3>
            <p className="mt-2 text-sm text-gray-600">
              Automatically create, update, and suspend users based on IdP changes
            </p>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100 text-2xl">
              🔐
            </div>
            <h3 className="mt-4 font-semibold">SCIM 2.0 Compliant</h3>
            <p className="mt-2 text-sm text-gray-600">
              Full SCIM 2.0 specification support for seamless IdP integration
            </p>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-2xl">
              👥
            </div>
            <h3 className="mt-4 font-semibold">Custom Roles</h3>
            <p className="mt-2 text-sm text-gray-600">
              Define roles with specific permission sets for fine-grained access control
            </p>
          </div>
        </div>

        {/* Supported Providers */}
        <div className="mt-12">
          <h2 className="mb-4 text-xl font-semibold">Supported Identity Providers</h2>
          <div className="grid gap-4 md:grid-cols-5">
            {[
              { name: 'Okta', icon: '🔐' },
              { name: 'Azure AD', icon: '🔷' },
              { name: 'Google Workspace', icon: '🔵' },
              { name: 'OneLogin', icon: '🟡' },
              { name: 'Generic SCIM 2.0', icon: '⚙️' },
            ].map((provider) => (
              <div
                key={provider.name}
                className="flex flex-col items-center rounded-lg bg-white p-4 shadow"
              >
                <span className="text-4xl">{provider.icon}</span>
                <p className="mt-2 text-sm font-medium">{provider.name}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
