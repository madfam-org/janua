'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  ArrowLeft,
  Settings,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Save,
  Plus,
  Trash2,
  Globe,
  Clock,
  Lock,
  ShieldAlert,
  RefreshCw,
} from 'lucide-react'
import { getCorsOrigins, addCorsOrigin, deleteCorsOrigin, getSystemSettings, updateSystemSetting } from '@/lib/api'
import { TOAST_DISMISS_MS } from '@/lib/constants'

interface CorsOrigin {
  id: string
  origin: string
  created_at: string
}

interface SystemSettings {
  // Session settings
  session_timeout_minutes: number
  max_concurrent_sessions: number

  // Password policy
  password_min_length: number
  password_require_uppercase: boolean
  password_require_numbers: boolean
  password_require_special_chars: boolean

  // Rate limiting
  rate_limit_requests_per_minute: number
  rate_limit_login_attempts: number
  rate_limit_lockout_duration_minutes: number
}

const defaultSettings: SystemSettings = {
  session_timeout_minutes: 30,
  max_concurrent_sessions: 5,
  password_min_length: 8,
  password_require_uppercase: true,
  password_require_numbers: true,
  password_require_special_chars: false,
  rate_limit_requests_per_minute: 60,
  rate_limit_login_attempts: 5,
  rate_limit_lockout_duration_minutes: 15,
}

export default function SystemSettingsPage() {
  const [corsOrigins, setCorsOrigins] = useState<CorsOrigin[]>([])
  const [newOrigin, setNewOrigin] = useState('')
  const [settings, setSettings] = useState<SystemSettings>(defaultSettings)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [addingOrigin, setAddingOrigin] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dirtySection, setDirtySection] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchSystemData()
  }, [])

  const fetchSystemData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [corsResult, settingsResult] = await Promise.allSettled([
        getCorsOrigins(),
        getSystemSettings(),
      ])

      if (corsResult.status === 'fulfilled') {
        const data = corsResult.value
        setCorsOrigins(Array.isArray(data) ? data as unknown as CorsOrigin[] : (data as unknown as { origins?: CorsOrigin[] }).origins || [])
      }

      if (settingsResult.status === 'fulfilled') {
        const data = settingsResult.value
        // Merge with defaults so any missing keys are filled in
        setSettings({ ...defaultSettings, ...data } as SystemSettings)
      }
    } catch (err) {
      console.error('Failed to fetch system settings:', err)
      setError(err instanceof Error ? err.message : 'Failed to load system settings')
    } finally {
      setLoading(false)
    }
  }

  const markDirty = (section: string) => {
    setDirtySection((prev) => new Set(prev).add(section))
  }

  const updateSetting = <K extends keyof SystemSettings>(
    key: K,
    value: SystemSettings[K],
    section: string
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    markDirty(section)
  }

  const handleAddOrigin = async () => {
    const trimmedOrigin = newOrigin.trim()

    if (!trimmedOrigin) {
      setError('Please enter an origin URL')
      return
    }

    // Basic URL validation
    try {
      const url = new URL(trimmedOrigin)
      if (!url.protocol.startsWith('http')) {
        throw new Error('Must be http or https')
      }
    } catch {
      setError('Please enter a valid URL (e.g., https://example.com)')
      return
    }

    try {
      setAddingOrigin(true)
      setError(null)

      const added = await addCorsOrigin({ origin: trimmedOrigin })
      setCorsOrigins((prev) => [...prev, added as unknown as CorsOrigin])
      setNewOrigin('')
      setSuccess('CORS origin added')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add CORS origin')
    } finally {
      setAddingOrigin(false)
    }
  }

  const handleDeleteOrigin = async (originId: string) => {
    if (!confirm('Are you sure you want to remove this CORS origin?')) return

    try {
      setError(null)

      await deleteCorsOrigin(originId)

      setCorsOrigins((prev) => prev.filter((o) => o.id !== originId))
      setSuccess('CORS origin removed')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove CORS origin')
    }
  }

  const handleSaveSection = async (section: string, keys: (keyof SystemSettings)[]) => {
    try {
      setSaving(section)
      setError(null)

      const updates = keys.map((key) =>
        updateSystemSetting(key, { value: settings[key] })
      )

      const results = await Promise.allSettled(updates)
      const failures = results.filter((r) => r.status === 'rejected')

      if (failures.length > 0) {
        throw new Error(`Failed to save ${failures.length} setting(s)`)
      }

      setDirtySection((prev) => {
        const next = new Set(prev)
        next.delete(section)
        return next
      })
      setSuccess(`${section.charAt(0).toUpperCase() + section.slice(1)} settings saved`)
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(null)
    }
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading system settings...</p>
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
              <Settings className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">System Settings</h1>
                <p className="text-muted-foreground text-sm">
                  Configure CORS, sessions, password policies, and rate limiting
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={fetchSystemData}>
              <RefreshCw className="mr-2 size-4" />
              Refresh
            </Button>
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

        {success && (
          <Card className="border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* CORS Origins */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="size-5" />
                  CORS Origins
                </CardTitle>
                <CardDescription>
                  Allowed origins for cross-origin requests to the Janua API. Add your frontend
                  application domains here.
                </CardDescription>
              </div>
              <Badge variant="outline">{corsOrigins.length} origin(s)</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Add Origin */}
            <div className="flex gap-2">
              <div className="flex-1">
                <Label htmlFor="new-origin" className="sr-only">
                  New CORS origin
                </Label>
                <Input
                  id="new-origin"
                  value={newOrigin}
                  onChange={(e) => setNewOrigin(e.target.value)}
                  placeholder="https://example.com"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddOrigin()
                  }}
                />
              </div>
              <Button onClick={handleAddOrigin} disabled={addingOrigin}>
                {addingOrigin ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 size-4" />
                )}
                Add Origin
              </Button>
            </div>

            {/* Origins List */}
            {corsOrigins.length === 0 ? (
              <div className="py-4 text-center">
                <Globe className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">
                  No custom CORS origins configured. The API defaults will be used.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {corsOrigins.map((origin) => (
                  <div
                    key={origin.id}
                    className="flex items-center justify-between rounded-lg border px-4 py-3"
                  >
                    <div>
                      <code className="text-sm font-medium">{origin.origin}</code>
                      <p className="text-muted-foreground text-xs">
                        Added {new Date(origin.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteOrigin(origin.id)}
                      aria-label={`Remove origin ${origin.origin}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Session Settings */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="size-5" />
                  Session Settings
                </CardTitle>
                <CardDescription>
                  Control user session duration and concurrency limits
                </CardDescription>
              </div>
              {dirtySection.has('session') && (
                <Badge variant="secondary">Unsaved</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="session-timeout">Session Timeout (minutes)</Label>
                <Input
                  id="session-timeout"
                  type="number"
                  min={5}
                  max={1440}
                  value={settings.session_timeout_minutes}
                  onChange={(e) =>
                    updateSetting(
                      'session_timeout_minutes',
                      parseInt(e.target.value) || 30,
                      'session'
                    )
                  }
                />
                <p className="text-muted-foreground text-xs">
                  Time of inactivity before a session expires. Range: 5-1440 minutes.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max-sessions">Max Concurrent Sessions</Label>
                <Input
                  id="max-sessions"
                  type="number"
                  min={1}
                  max={50}
                  value={settings.max_concurrent_sessions}
                  onChange={(e) =>
                    updateSetting(
                      'max_concurrent_sessions',
                      parseInt(e.target.value) || 5,
                      'session'
                    )
                  }
                />
                <p className="text-muted-foreground text-xs">
                  Maximum number of active sessions per user. Oldest session is terminated when
                  limit is exceeded.
                </p>
              </div>
            </div>

            <div className="flex justify-end border-t pt-4">
              <Button
                onClick={() =>
                  handleSaveSection('session', [
                    'session_timeout_minutes',
                    'max_concurrent_sessions',
                  ])
                }
                disabled={saving === 'session' || !dirtySection.has('session')}
              >
                {saving === 'session' ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Save className="mr-2 size-4" />
                )}
                Save Session Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Password Policy */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Lock className="size-5" />
                  Password Policy
                </CardTitle>
                <CardDescription>
                  Define password complexity requirements for user accounts
                </CardDescription>
              </div>
              {dirtySection.has('password') && (
                <Badge variant="secondary">Unsaved</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="password-min-length">Minimum Password Length</Label>
              <Input
                id="password-min-length"
                type="number"
                min={6}
                max={128}
                value={settings.password_min_length}
                onChange={(e) =>
                  updateSetting(
                    'password_min_length',
                    parseInt(e.target.value) || 8,
                    'password'
                  )
                }
              />
              <p className="text-muted-foreground text-xs">
                Minimum number of characters required. NIST recommends at least 8.
              </p>
            </div>

            <div className="space-y-4">
              <Label>Character Requirements</Label>
              <div className="space-y-3">
                <label className="flex items-center justify-between rounded-lg border p-4">
                  <div>
                    <p className="font-medium">Require uppercase letters</p>
                    <p className="text-muted-foreground text-sm">
                      At least one uppercase letter (A-Z) must be present
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.password_require_uppercase}
                    onChange={(e) =>
                      updateSetting('password_require_uppercase', e.target.checked, 'password')
                    }
                    className="size-5 rounded"
                    aria-label="Require uppercase letters"
                  />
                </label>

                <label className="flex items-center justify-between rounded-lg border p-4">
                  <div>
                    <p className="font-medium">Require numbers</p>
                    <p className="text-muted-foreground text-sm">
                      At least one numeric digit (0-9) must be present
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.password_require_numbers}
                    onChange={(e) =>
                      updateSetting('password_require_numbers', e.target.checked, 'password')
                    }
                    className="size-5 rounded"
                    aria-label="Require numbers"
                  />
                </label>

                <label className="flex items-center justify-between rounded-lg border p-4">
                  <div>
                    <p className="font-medium">Require special characters</p>
                    <p className="text-muted-foreground text-sm">
                      At least one special character (!@#$%^&*) must be present
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.password_require_special_chars}
                    onChange={(e) =>
                      updateSetting('password_require_special_chars', e.target.checked, 'password')
                    }
                    className="size-5 rounded"
                    aria-label="Require special characters"
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end border-t pt-4">
              <Button
                onClick={() =>
                  handleSaveSection('password', [
                    'password_min_length',
                    'password_require_uppercase',
                    'password_require_numbers',
                    'password_require_special_chars',
                  ])
                }
                disabled={saving === 'password' || !dirtySection.has('password')}
              >
                {saving === 'password' ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Save className="mr-2 size-4" />
                )}
                Save Password Policy
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Rate Limiting */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="size-5" />
                  Rate Limiting
                </CardTitle>
                <CardDescription>
                  Protect against brute-force attacks and API abuse
                </CardDescription>
              </div>
              {dirtySection.has('ratelimit') && (
                <Badge variant="secondary">Unsaved</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="rate-limit-rpm">Requests per Minute</Label>
                <Input
                  id="rate-limit-rpm"
                  type="number"
                  min={10}
                  max={1000}
                  value={settings.rate_limit_requests_per_minute}
                  onChange={(e) =>
                    updateSetting(
                      'rate_limit_requests_per_minute',
                      parseInt(e.target.value) || 60,
                      'ratelimit'
                    )
                  }
                />
                <p className="text-muted-foreground text-xs">
                  Maximum API requests per minute per client IP.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="login-attempts">Login Attempts Before Lockout</Label>
                <Input
                  id="login-attempts"
                  type="number"
                  min={3}
                  max={20}
                  value={settings.rate_limit_login_attempts}
                  onChange={(e) =>
                    updateSetting(
                      'rate_limit_login_attempts',
                      parseInt(e.target.value) || 5,
                      'ratelimit'
                    )
                  }
                />
                <p className="text-muted-foreground text-xs">
                  Failed login attempts before account is temporarily locked.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="lockout-duration">Lockout Duration (minutes)</Label>
                <Input
                  id="lockout-duration"
                  type="number"
                  min={1}
                  max={1440}
                  value={settings.rate_limit_lockout_duration_minutes}
                  onChange={(e) =>
                    updateSetting(
                      'rate_limit_lockout_duration_minutes',
                      parseInt(e.target.value) || 15,
                      'ratelimit'
                    )
                  }
                />
                <p className="text-muted-foreground text-xs">
                  How long an account stays locked after exceeding login attempts.
                </p>
              </div>
            </div>

            <div className="flex justify-end border-t pt-4">
              <Button
                onClick={() =>
                  handleSaveSection('ratelimit', [
                    'rate_limit_requests_per_minute',
                    'rate_limit_login_attempts',
                    'rate_limit_lockout_duration_minutes',
                  ])
                }
                disabled={saving === 'ratelimit' || !dirtySection.has('ratelimit')}
              >
                {saving === 'ratelimit' ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Save className="mr-2 size-4" />
                )}
                Save Rate Limiting
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
