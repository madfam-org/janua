'use client'

import { useState } from 'react'
import { adminAPI } from '@/lib/admin-api'

export function SecuritySection() {
  const [revoking, setRevoking] = useState(false)

  const handleRevokeAllSessions = async () => {
    if (!confirm('Are you sure you want to revoke ALL user sessions? This will log out everyone.')) {
      return
    }
    setRevoking(true)
    try {
      await adminAPI.revokeAllSessions()
      alert('All sessions revoked successfully')
    } catch (err) {
      alert('Failed to revoke sessions')
    } finally {
      setRevoking(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-foreground text-2xl font-bold">Security & Compliance</h2>

      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 text-lg font-semibold">Emergency Actions</h3>
        <div className="space-y-4">
          <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-4">
            <h4 className="text-destructive font-medium">Revoke All Sessions</h4>
            <p className="text-destructive/80 mt-1 text-sm">
              This will immediately log out all users from the platform.
            </p>
            <button
              onClick={handleRevokeAllSessions}
              disabled={revoking}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-3 rounded-lg px-4 py-2 disabled:opacity-50"
            >
              {revoking ? 'Revoking...' : 'Revoke All Sessions'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
