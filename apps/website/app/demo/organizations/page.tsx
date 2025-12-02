'use client'

import { OrganizationSwitcher, OrganizationProfile } from '@janua/ui'
import { useState } from 'react'

export default function OrganizationShowcase() {
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [currentOrg, setCurrentOrg] = useState('org-1')

  const sampleOrganizations = [
    {
      id: 'org-1',
      name: 'Acme Corporation',
      slug: 'acme-corp',
      role: 'owner' as const,
      logoUrl: 'https://api.dicebear.com/7.x/identicon/svg?seed=acme',
      memberCount: 15,
    },
    {
      id: 'org-2',
      name: 'TechStart Inc',
      slug: 'techstart',
      role: 'admin' as const,
      logoUrl: 'https://api.dicebear.com/7.x/identicon/svg?seed=techstart',
      memberCount: 8,
    },
    {
      id: 'org-3',
      name: 'Design Studio',
      slug: 'design-studio',
      role: 'member' as const,
      logoUrl: 'https://api.dicebear.com/7.x/identicon/svg?seed=design',
      memberCount: 23,
    },
  ]

  const currentOrganization = sampleOrganizations.find(org => org.id === currentOrg)

  const handleSwitchOrganization = (org: any) => {
    // removed console.log
    setCurrentOrg(org.id)
    setStatus('success')
    setMessage(`Switched to ${org.name}`)
    setTimeout(() => setStatus('idle'), 2000)
  }

  const handleCreateOrganization = () => {
    // removed console.log
    setStatus('success')
    setMessage('Organization creation flow initiated')
    setTimeout(() => setStatus('idle'), 2000)
  }

  const handleUpdateOrganization = async (data: any) => {
    // removed console.log
    setStatus('success')
    setMessage('Organization updated successfully!')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleInviteMember = async (email: string, role: string) => {
    // removed console.log
    setStatus('success')
    setMessage(`Invitation sent to ${email}`)
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleRemoveMember = async (memberId: string) => {
    // removed console.log
    setStatus('success')
    setMessage('Member removed from organization')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleUpdateMemberRole = async (memberId: string, role: string) => {
    // removed console.log
    setStatus('success')
    setMessage('Member role updated')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleDeleteOrganization = async () => {
    // removed console.log
    setStatus('success')
    setMessage('Organization deletion initiated')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'An error occurred')
    console.error('Organization error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Organization Components
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Organization switcher and profile management for multi-tenant applications.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Components</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• OrganizationSwitcher</li>
              <li>• OrganizationProfile</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Switch between organizations</li>
              <li>• Manage organization settings</li>
              <li>• Invite and manage members</li>
              <li>• Role-based access control</li>
              <li>• Organization deletion</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import {
  OrganizationSwitcher,
  OrganizationProfile
} from '@janua/ui'

<OrganizationSwitcher
  currentOrganization={org}
  organizations={orgs}
  onSwitchOrganization={handleSwitch}
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Status Message */}
      {status !== 'idle' && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            status === 'success'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200'
              : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200'
          }`}
        >
          <p className="font-medium">{message}</p>
        </div>
      )}

      {/* Organization Switcher Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8 mb-6">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Organization Switcher
        </h3>

        <div className="max-w-md">
          <OrganizationSwitcher
            currentOrganization={currentOrganization}
            organizations={sampleOrganizations}
            onSwitchOrganization={handleSwitchOrganization}
            onCreateOrganization={handleCreateOrganization}
            showCreateOrganization={true}
            showPersonalWorkspace={true}
            personalWorkspace={{ id: 'personal', name: 'Personal Workspace' }}
          />
        </div>

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Current Organization:</strong> {currentOrganization?.name} ({currentOrganization?.role})
          </p>
        </div>
      </div>

      {/* Organization Profile Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Organization Profile
        </h3>

        {currentOrganization && (
          <OrganizationProfile
            organization={{
              ...currentOrganization,
              description: 'Building the future of technology',
              createdAt: new Date('2024-01-15'),
            }}
            userRole={currentOrganization.role}
            members={[
              {
                id: 'member-1',
                email: 'alice@example.com',
                name: 'Alice Johnson',
                role: 'owner',
                avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=alice',
                joinedAt: new Date('2024-01-15'),
              },
              {
                id: 'member-2',
                email: 'bob@example.com',
                name: 'Bob Smith',
                role: 'admin',
                avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=bob',
                joinedAt: new Date('2024-02-20'),
              },
              {
                id: 'member-3',
                email: 'charlie@example.com',
                name: 'Charlie Brown',
                role: 'member',
                avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=charlie',
                joinedAt: new Date('2024-03-10'),
              },
            ]}
            onUpdateOrganization={handleUpdateOrganization}
            onInviteMember={handleInviteMember}
            onRemoveMember={handleRemoveMember}
            onUpdateMemberRole={handleUpdateMemberRole}
            onDeleteOrganization={handleDeleteOrganization}
            onError={handleError}
          />
        )}

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Demo Note:</strong> All actions are simulated. In a real application,
            these would connect to your organization management API.
          </p>
        </div>
      </div>

      {/* Implementation Examples */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Implementation Examples
        </h3>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Organization Switcher in Navigation</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { OrganizationSwitcher } from '@janua/ui'
import { useOrganization } from '@/hooks/useOrganization'

export function AppHeader() {
  const { current, organizations, switchTo } = useOrganization()

  return (
    <header className="border-b">
      <div className="flex items-center gap-4 p-4">
        <OrganizationSwitcher
          currentOrganization={current}
          organizations={organizations}
          onSwitchOrganization={async (org) => {
            await switchTo(org.id)
            window.location.reload() // Reload to switch context
          }}
          onCreateOrganization={() => {
            router.push('/organizations/new')
          }}
        />
      </div>
    </header>
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Organization Settings Page</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`import { OrganizationProfile } from '@janua/ui'

export default function OrganizationSettingsPage({ params }) {
  const { organization, userRole } = await getOrganization(params.id)

  return (
    <OrganizationProfile
      organization={organization}
      currentUserRole={userRole}
      onUpdateOrganization={async (data) => {
        await fetch(\`/api/organizations/\${params.id}\`, {
          method: 'PATCH',
          body: JSON.stringify(data),
        })
      }}
      onInviteMember={async (email, role) => {
        await fetch(\`/api/organizations/\${params.id}/invitations\`, {
          method: 'POST',
          body: JSON.stringify({ email, role }),
        })
      }}
      onRemoveMember={async (memberId) => {
        await fetch(\`/api/organizations/\${params.id}/members/\${memberId}\`, {
          method: 'DELETE',
        })
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Role-Based Permissions</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<OrganizationProfile
  organization={org}
  currentUserRole={userRole}
  // Only owners and admins can invite members
  onInviteMember={
    ['owner', 'admin'].includes(userRole)
      ? handleInvite
      : undefined
  }
  // Only owners can delete the organization
  onDeleteOrganization={
    userRole === 'owner'
      ? handleDelete
      : undefined
  }
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Component Specifications */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Component Specifications
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Organization Switcher</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Dropdown menu with organization list</li>
              <li>• Shows current organization with logo</li>
              <li>• Role badges (owner, admin, member)</li>
              <li>• Create organization option</li>
              <li>• Personal workspace toggle</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Organization Profile</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Organization info editing</li>
              <li>• Member management with roles</li>
              <li>• Email invitations</li>
              <li>• Role updates (owner/admin only)</li>
              <li>• Organization deletion (owner only)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Access Control</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Role-based permissions (owner, admin, member)</li>
              <li>• Conditional callback props</li>
              <li>• UI adapts to user role</li>
              <li>• Disabled actions for insufficient permissions</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Experience</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Searchable organization list</li>
              <li>• Member avatars and status</li>
              <li>• Loading states for async operations</li>
              <li>• Confirmation dialogs for destructive actions</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
