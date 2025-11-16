'use client'

import { UserProfile } from '@plinto/ui'
import { useState } from 'react'

export default function UserProfileShowcase() {
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const sampleUser = {
    id: 'user-123',
    email: 'john.doe@example.com',
    firstName: 'John',
    lastName: 'Doe',
    username: 'johndoe',
    avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=John',
    phone: '+1 (555) 123-4567',
    emailVerified: true,
    phoneVerified: true,
    twoFactorEnabled: false,
    createdAt: new Date('2024-01-15'),
  }

  const handleUpdateProfile = async (data: {
    firstName?: string
    lastName?: string
    username?: string
    phone?: string
  }) => {
    console.log('Updating profile:', data)
    setStatus('success')
    setMessage('Profile updated successfully!')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleUploadAvatar = async (file: File) => {
    console.log('Uploading avatar:', file.name)
    setStatus('success')
    setMessage('Avatar uploaded successfully!')
    setTimeout(() => setStatus('idle'), 3000)
    return 'https://api.dicebear.com/7.x/avataaars/svg?seed=Updated'
  }

  const handleUpdateEmail = async (email: string) => {
    console.log('Updating email to:', email)
    setStatus('success')
    setMessage('Email update initiated. Check your inbox for verification.')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleUpdatePassword = async (currentPassword: string, newPassword: string) => {
    console.log('Updating password')
    setStatus('success')
    setMessage('Password updated successfully!')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleToggleMFA = async (enabled: boolean) => {
    console.log('Toggling MFA to:', enabled)
    setStatus('success')
    setMessage(`Two-factor authentication ${enabled ? 'enabled' : 'disabled'}!`)
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleDeleteAccount = async () => {
    console.log('Deleting account')
    setStatus('success')
    setMessage('Account deletion initiated. This action cannot be undone.')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'An error occurred')
    console.error('Profile error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          UserProfile Component
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Comprehensive user profile management with tabs for profile info, security settings, and account management.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Profile information editing</li>
              <li>• Avatar upload</li>
              <li>• Email and password updates</li>
              <li>• Two-factor authentication toggle</li>
              <li>• Account deletion (danger zone)</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Props</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>user</code>: User data object</li>
              <li>• <code>onUpdateProfile</code>: Profile update callback</li>
              <li>• <code>onUploadAvatar</code>: Avatar upload callback</li>
              <li>• <code>onUpdateEmail</code>: Email update callback</li>
              <li>• <code>onUpdatePassword</code>: Password update callback</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import { UserProfile } from '@plinto/ui'

<UserProfile
  user={userData}
  onUpdateProfile={handleUpdate}
  onUploadAvatar={handleUpload}
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

      {/* Live Component Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Live Component Demo
        </h3>

        <UserProfile
          user={sampleUser}
          onUpdateProfile={handleUpdateProfile}
          onUploadAvatar={handleUploadAvatar}
          onUpdateEmail={handleUpdateEmail}
          onUpdatePassword={handleUpdatePassword}
          onToggleMFA={handleToggleMFA}
          onDeleteAccount={handleDeleteAccount}
          onError={handleError}
          showSecurityTab={true}
          showDangerZone={true}
        />

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Demo Note:</strong> All actions are simulated. In a real application,
            these would connect to your user management API with proper authentication and validation.
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Basic Profile Management</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { UserProfile } from '@plinto/ui'

export default function ProfilePage({ user }) {
  return (
    <UserProfile
      user={user}
      onUpdateProfile={async (data) => {
        const response = await fetch('/api/user/profile', {
          method: 'PATCH',
          body: JSON.stringify(data),
        })
        if (!response.ok) throw new Error('Update failed')
      }}
      onUploadAvatar={async (file) => {
        const formData = new FormData()
        formData.append('avatar', file)
        const response = await fetch('/api/user/avatar', {
          method: 'POST',
          body: formData,
        })
        const { url } = await response.json()
        return url
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Security Settings</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<UserProfile
  user={user}
  showSecurityTab={true}
  onUpdatePassword={async (current, newPass) => {
    await fetch('/api/user/password', {
      method: 'POST',
      body: JSON.stringify({ currentPassword: current, newPassword: newPass }),
    })
  }}
  onToggleMFA={async (enabled) => {
    await fetch('/api/user/mfa', {
      method: enabled ? 'POST' : 'DELETE',
    })
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Account Deletion</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<UserProfile
  user={user}
  showDangerZone={true}
  onDeleteAccount={async () => {
    // Confirm deletion
    if (window.confirm('Are you sure? This cannot be undone.')) {
      await fetch('/api/user', { method: 'DELETE' })
      // Sign out and redirect
      await signOut()
      router.push('/')
    }
  }}
  onError={(error) => {
    toast.error(error.message)
  }}
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Features</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Tabbed interface (Profile, Security, Account)</li>
              <li>• Avatar upload with preview</li>
              <li>• Form validation and error handling</li>
              <li>• Loading states for async operations</li>
              <li>• Confirmation dialogs for destructive actions</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Security</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Password strength validation</li>
              <li>• Current password required for changes</li>
              <li>• MFA toggle with verification</li>
              <li>• Account deletion with confirmation</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Accessibility</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• WCAG 2.1 AA compliant</li>
              <li>• Keyboard navigation support</li>
              <li>• Screen reader optimized</li>
              <li>• Focus management</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Customization</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Optional tabs (show/hide security)</li>
              <li>• Optional danger zone</li>
              <li>• Custom error handling</li>
              <li>• Flexible callback system</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
