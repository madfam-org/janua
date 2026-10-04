'use client'

import { useState, useEffect, useCallback } from 'react'
import { z } from 'zod'
import {
  Loader2,
  RefreshCw,
  Key,
  ShieldCheck,
  ShieldAlert,
  Lock,
  RotateCcw,
  AlertTriangle,
  Database,
  Mail,
  Globe,
  Fingerprint,
} from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

const dateString = z.string().refine((value) => Number.isFinite(Date.parse(value)))
const keyStatus = z.enum(['active', 'rotation_needed', 'expired', 'rotating'])
const vaultStatusSchema = z.object({
  encryption_enabled: z.boolean(),
  field_encryption_active: z.boolean(),
  keys: z.array(z.object({
    id: z.string().min(1), algorithm: z.string().min(1), status: keyStatus,
    created_at: dateString, last_rotated: dateString, next_rotation: dateString,
    key_type: z.string().min(1),
  })),
  secrets_count: z.number().int().nonnegative(),
  secrets: z.array(z.object({
    name: z.string().min(1), category: z.string().min(1),
    status: z.enum(['active', 'rotation_needed', 'expired']), last_rotated: dateString,
  })),
  last_audit: dateString.nullable(),
})
type VaultStatus = z.infer<typeof vaultStatusSchema>

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  encryption: Key,
  authentication: Fingerprint,
  infrastructure: Database,
  email: Mail,
  oauth: Globe,
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  active: {
    bg: 'bg-green-500/10',
    text: 'text-green-600 dark:text-green-400',
    label: 'Active',
  },
  rotation_needed: {
    bg: 'bg-yellow-500/10',
    text: 'text-yellow-600 dark:text-yellow-400',
    label: 'Rotation Needed',
  },
  expired: {
    bg: 'bg-red-500/10',
    text: 'text-red-600 dark:text-red-400',
    label: 'Expired',
  },
  rotating: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-600 dark:text-blue-400',
    label: 'Rotating',
  },
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (24 * 60 * 60 * 1000))
}

function daysSince(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / (24 * 60 * 60 * 1000))
}

export function VaultSection() {
  const [vault, setVault] = useState<VaultStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [rotatingKey, setRotatingKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const fetchVault = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      const token =
        typeof window !== 'undefined'
          ? localStorage.getItem('janua_access_token')
          : null
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }

      const response = await fetch(`${API_URL}/api/v1/admin/vault/status`, { headers })
      if (!response.ok) throw new Error(`Vault status unavailable (HTTP ${response.status}).`)
      const result = vaultStatusSchema.safeParse(await response.json())
      if (!result.success) throw new Error('Vault status unavailable: invalid response.')
      setVault(result.data)
      setError(null)
    } catch {
      // Discard an old snapshot rather than displaying it as current security state.
      setVault(null)
      setError('Vault status unavailable. The service did not return a verified status. Retry to check again.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchVault()
  }, [fetchVault])

  const handleRotateKey = async (keyId: string) => {
    if (
      !confirm(
        'Request rotation of this key? Rotation can affect services that depend on it.'
      )
    ) {
      return
    }

    setRotatingKey(keyId)
    setActionError(null)
    setNotice(null)
    try {
      const token =
        typeof window !== 'undefined'
          ? localStorage.getItem('janua_access_token')
          : null
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }

      const response = await fetch(`${API_URL}/api/v1/admin/vault/keys/${encodeURIComponent(keyId)}/rotate`, {
        method: 'POST',
        headers,
      })

      if (!response.ok) throw new Error('Rotation request failed')
      setNotice('Rotation request accepted. Check the refreshed status for confirmation.')
      await fetchVault(true)
    } catch {
      setActionError('Rotation could not be confirmed. The displayed key status has not been changed. Refresh before trying again.')
    } finally {
      setRotatingKey(null)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  if (error && !vault) {
    return (
      <div className="space-y-6">
        <h2 className="text-foreground text-2xl font-bold">Vault and Encryption</h2>
        <div role="alert" className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
          <p className="text-destructive">{error}</p>
          <button
            onClick={() => fetchVault(true)}
            disabled={refreshing}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90 mt-3 rounded-lg px-4 py-2 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!vault) return null

  const keysNeedingRotation = vault.keys.filter(
    (k) => k.status === 'rotation_needed' || daysUntil(k.next_rotation) <= 7
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-foreground text-2xl font-bold">Vault and Encryption</h2>
          {keysNeedingRotation.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-yellow-500/10 px-2.5 py-0.5 text-xs font-medium text-yellow-600 dark:text-yellow-400">
              <AlertTriangle className="size-3" />
              {keysNeedingRotation.length} key(s) need rotation
            </span>
          )}
        </div>
        <button
          onClick={() => fetchVault(true)}
          disabled={refreshing}
          className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg p-2 transition-colors disabled:opacity-50"
          aria-label="Refresh vault status"
        >
          <RefreshCw className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {actionError && <p role="alert" className="text-destructive">{actionError}</p>}
      {notice && <p role="status" className="text-muted-foreground">{notice}</p>}

      {/* Encryption Status Overview */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            {vault.encryption_enabled ? (
              <ShieldCheck className="size-4 text-green-500" />
            ) : (
              <ShieldAlert className="size-4 text-red-500" />
            )}
            <span className="text-muted-foreground text-xs">Encryption</span>
          </div>
          <p className="text-foreground mt-1 text-lg font-semibold">
            {vault.encryption_enabled ? 'Enabled' : 'Disabled'}
          </p>
        </div>

        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            {vault.field_encryption_active ? (
              <Lock className="size-4 text-green-500" />
            ) : (
              <AlertTriangle className="size-4 text-yellow-500" />
            )}
            <span className="text-muted-foreground text-xs">Field Encryption</span>
          </div>
          <p className="text-foreground mt-1 text-lg font-semibold">
            {vault.field_encryption_active ? 'Active' : 'Inactive'}
          </p>
        </div>

        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Key className="size-4 text-blue-500" />
            <span className="text-muted-foreground text-xs">Keys Reported</span>
          </div>
          <p className="text-foreground mt-1 text-lg font-semibold">{vault.keys.length}</p>
        </div>

        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Lock className="size-4 text-purple-500" />
            <span className="text-muted-foreground text-xs">Stored Secrets</span>
          </div>
          <p className="text-foreground mt-1 text-lg font-semibold">{vault.secrets_count}</p>
          {vault.last_audit && (
            <p className="text-muted-foreground text-xs">
              Last audit: {daysSince(vault.last_audit)}d ago
            </p>
          )}
        </div>
      </div>

      {/* Encryption Keys */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
          <Key className="size-5" />
          Encryption Keys
        </h3>
        <div className="space-y-4">
          {vault.keys.map((key) => {
            const daysLeft = daysUntil(key.next_rotation)
            const isUrgent = daysLeft <= 7
            const style = STATUS_STYLES[key.status]

            return (
              <div
                key={key.id}
                className={`rounded-lg border p-4 ${
                  isUrgent ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-border bg-muted/30'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-foreground font-mono text-sm font-medium">
                        {key.id}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
                      >
                        {style.label}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {key.key_type} -- {key.algorithm}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRotateKey(key.id)}
                    disabled={rotatingKey !== null || refreshing || key.status === 'rotating'}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors disabled:opacity-50 ${
                      isUrgent
                        ? 'bg-yellow-500 text-white hover:bg-yellow-600'
                        : 'bg-muted text-foreground hover:bg-muted/80'
                    }`}
                  >
                    <RotateCcw
                      className={`size-3.5 ${rotatingKey === key.id ? 'animate-spin' : ''}`}
                    />
                    {rotatingKey === key.id ? 'Rotating...' : 'Rotate'}
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-4 text-xs">
                  <div>
                    <span className="text-muted-foreground">Created</span>
                    <p className="text-foreground mt-0.5">
                      {new Date(key.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Last Rotated</span>
                    <p className="text-foreground mt-0.5">
                      {daysSince(key.last_rotated)}d ago
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Next Rotation</span>
                    <p
                      className={`mt-0.5 font-medium ${
                        isUrgent
                          ? 'text-yellow-600 dark:text-yellow-400'
                          : 'text-foreground'
                      }`}
                    >
                      {daysLeft > 0 ? `${daysLeft}d` : 'Overdue'}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Secrets Overview */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
          <Lock className="size-5" />
          Secrets Overview
        </h3>
        <div className="divide-border divide-y">
          {vault.secrets.map((secret) => {
            const CategoryIcon = CATEGORY_ICONS[secret.category] ?? Key
            const style = STATUS_STYLES[secret.status]

            return (
              <div
                key={secret.name}
                className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  <CategoryIcon className="text-muted-foreground size-4" />
                  <div>
                    <span className="text-foreground font-mono text-sm">{secret.name}</span>
                    <div className="text-muted-foreground mt-0.5 flex items-center gap-2 text-xs">
                      <span className="capitalize">{secret.category}</span>
                      <span>--</span>
                      <span>Rotated {daysSince(secret.last_rotated)}d ago</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-muted-foreground text-xs">Values hidden</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
                  >
                    {style.label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <p className="text-muted-foreground text-sm">
        Field-level encryption coverage and compliance evidence are not provided by this status endpoint.
      </p>
    </div>
  )
}
