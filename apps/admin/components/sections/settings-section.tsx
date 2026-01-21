'use client'

import { useState } from 'react'
import { adminAPI } from '@/lib/admin-api'

export function SettingsSection() {
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleMaintenanceToggle = async () => {
    setSaving(true)
    try {
      await adminAPI.setMaintenanceMode(!maintenanceMode)
      setMaintenanceMode(!maintenanceMode)
    } catch (err) {
      alert('Failed to update maintenance mode')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-foreground text-2xl font-bold">Platform Settings</h2>

      <div className="bg-card border-border rounded-lg border p-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-foreground font-medium">Maintenance Mode</h4>
              <p className="text-muted-foreground text-sm">Temporarily disable access to the platform</p>
            </div>
            <button
              onClick={handleMaintenanceToggle}
              disabled={saving}
              className={`rounded-lg px-4 py-2 ${
                maintenanceMode
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              } disabled:opacity-50`}
            >
              {saving ? 'Saving...' : maintenanceMode ? 'Disable' : 'Enable'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
