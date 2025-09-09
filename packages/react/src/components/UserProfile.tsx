import React, { useState } from 'react'
import { usePlinto } from '../provider'

interface UserProfileProps {
  className?: string
  onSignOut?: () => void
  showOrganization?: boolean
  showSessions?: boolean
  allowEdit?: boolean
}

export function UserProfile({ 
  className = '',
  onSignOut,
  showOrganization = true,
  showSessions = false,
  allowEdit = true
}: UserProfileProps) {
  const { identity, session, signOut, isLoading } = usePlinto()
  const [isEditing, setIsEditing] = useState(false)
  const [formData, setFormData] = useState({
    firstName: identity?.firstName || '',
    lastName: identity?.lastName || '',
    email: identity?.email || ''
  })

  const handleSignOut = async () => {
    await signOut()
    if (onSignOut) {
      onSignOut()
    }
  }

  const handleSave = async () => {
    // TODO: Implement profile update
    console.log('Profile update not yet implemented', formData)
    setIsEditing(false)
  }

  if (!identity || !session) {
    return (
      <div className={`plinto-user-profile ${className}`}>
        <p className="text-gray-500">Not authenticated</p>
      </div>
    )
  }

  return (
    <div className={`plinto-user-profile ${className}`}>
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">User Profile</h2>
          {allowEdit && !isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="text-sm text-indigo-600 hover:text-indigo-500"
            >
              Edit
            </button>
          )}
        </div>

        <div className="space-y-4">
          {isEditing ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">First name</label>
                  <input
                    type="text"
                    value={formData.firstName}
                    onChange={(e) => setFormData(prev => ({ ...prev, firstName: e.target.value }))}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Last name</label>
                  <input
                    type="text"
                    value={formData.lastName}
                    onChange={(e) => setFormData(prev => ({ ...prev, lastName: e.target.value }))}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={handleSave}
                  className="flex-1 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex-1 py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <>
              <div>
                <h3 className="text-sm font-medium text-gray-500">Name</h3>
                <p className="mt-1 text-sm text-gray-900">
                  {identity.firstName} {identity.lastName}
                </p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-500">Email</h3>
                <p className="mt-1 text-sm text-gray-900">{identity.email}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-500">User ID</h3>
                <p className="mt-1 text-sm text-gray-900 font-mono">{identity.id}</p>
              </div>
              {showOrganization && session.organization_id && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Organization</h3>
                  <p className="mt-1 text-sm text-gray-900">{session.organization_id}</p>
                </div>
              )}
              {showSessions && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Current Session</h3>
                  <p className="mt-1 text-sm text-gray-900 font-mono">{session.id}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    Expires: {new Date(session.expires_at).toLocaleString()}
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {!isEditing && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <button
              onClick={handleSignOut}
              disabled={isLoading}
              className="w-full py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing out...' : 'Sign out'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}