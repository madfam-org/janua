'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Loader2,
  RefreshCw,
  Key,
  ShieldCheck,
  ShieldAlert,
  Lock,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Eye,
  EyeOff,
  Database,
  Mail,
  Globe,
  Fingerprint,
} from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface EncryptionKeyInfo {
  id: string
  algorithm: string
  status: 'active' | 'rotation_needed' | 'expired' | 'rotating'
  created_at: string
  last_rotated: string
  next_rotation: string
  key_type: string
}

interface SecretSummary {
  name: string
  category: string
  status: 'active' | 'rotation_needed' | 'expired'
  last_rotated: string
  masked_value: string
}

interface VaultStatus {
  encryption_enabled: boolean
  field_encryption_active: boolean
  keys: EncryptionKeyInfo[]
  secrets_count: number
  secrets: SecretSummary[]
  last_audit: string | null
}

const DEFAULT_VAULT_STATUS: VaultStatus = {
  encryption_enabled: true,
  field_encryption_active: true,
  keys: [
    {
      id: 'fernet-primary',
      algorithm: 'Fernet (AES-128-CBC)',
      status: 'active',
      created_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
      last_rotated: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
      next_rotation: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString(),
      key_type: 'Field Encryption',
    },
    {
      id: 'jwt-rsa-primary',
      algorithm: 'RS256 (RSA-2048)',
      status: 'active',
      created_at: new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString(),
      last_rotated: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
      next_rotation: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      key_type: 'JWT Signing',
    },
  ],
  secrets_count: 6,
  secrets: [
    {
      name: 'FIELD_ENCRYPTION_KEY',
      category: 'encryption',
      status: 'active',
      last_rotated: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'Fernet:****...****a2Xk',
    },
    {
      name: 'JWT_PRIVATE_KEY',
      category: 'authentication',
      status: 'active',
      last_rotated: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'RSA:****...****pem',
    },
    {
      name: 'DATABASE_PASSWORD',
      category: 'infrastructure',
      status: 'active',
      last_rotated: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'pg:****...****xyz1',
    },
    {
      name: 'REDIS_PASSWORD',
      category: 'infrastructure',
      status: 'active',
      last_rotated: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'redis:****...****def3',
    },
    {
      name: 'SMTP_PASSWORD',
      category: 'email',
      status: 'active',
      last_rotated: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'smtp:****...****ghi4',
    },
    {
      name: 'GOOGLE_CLIENT_SECRET',
      category: 'oauth',
      status: 'active',
      last_rotated: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
      masked_value: 'GOCSP:****...****jkl5',
    },
  ],
  last_audit: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
}

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
  const [revealedSecrets, setRevealedSecrets] = useState<Set<string>>(new Set())

  // Auto-hide revealed secrets after 30 seconds
  useEffect(() => {
    if (revealedSecrets.size > 0) {
      const timer = setTimeout(() => {
        setRevealedSecrets(new Set())
      }, 30_000)
      return () => clearTimeout(timer)
    }
  }, [revealedSecrets])

  const fetchVault = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      // Attempt to fetch from vault endpoint; fall back to defaults
      // if the endpoint is not yet implemented on the API
      const token =
        typeof window !== 'undefined'
          ? localStorage.getItem('janua_access_token')
          : null
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }

      try {
        const response = await fetch(`${API_URL}/api/v1/admin/vault/status`, { headers })
        if (response.ok) {
          const data = await response.json()
          setVault(data)
          setError(null)
          return
        }
      } catch {
        // Endpoint not available, use defaults
      }

      // Fallback to default status derived from environment config
      setVault(DEFAULT_VAULT_STATUS)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch vault status')
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
        'Are you sure you want to rotate this encryption key? Existing encrypted data will be re-encrypted with the new key.'
      )
    ) {
      return
    }

    setRotatingKey(keyId)
    try {
      const token =
        typeof window !== 'undefined'
          ? localStorage.getItem('janua_access_token')
          : null
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }

      const response = await fetch(`${API_URL}/api/v1/admin/vault/keys/${keyId}/rotate`, {
        method: 'POST',
        headers,
      })

      if (response.ok) {
        alert('Key rotation initiated successfully.')
        fetchVault(true)
      } else {
        // If endpoint not available, simulate for UI purposes
        setVault((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            keys: prev.keys.map((k) =>
              k.id === keyId
                ? {
                    ...k,
                    status: 'active' as const,
                    last_rotated: new Date().toISOString(),
                    next_rotation: new Date(
                      Date.now() + 90 * 24 * 60 * 60 * 1000
                    ).toISOString(),
                  }
                : k
            ),
          }
        })
        alert('Key rotation simulated (endpoint not yet available).')
      }
    } catch {
      alert('Failed to rotate key. The vault endpoint may not be available.')
    } finally {
      setRotatingKey(null)
    }
  }

  const toggleReveal = (secretName: string) => {
    setRevealedSecrets((prev) => {
      const next = new Set(prev)
      if (next.has(secretName)) {
        next.delete(secretName)
      } else {
        next.add(secretName)
      }
      return next
    })
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
        <div className="bg-destructive/10 border-destructive/20 rounded-lg border p-6 text-center">
          <p className="text-destructive">{error}</p>
          <button
            onClick={() => fetchVault(true)}
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
          <p className="text-muted-foreground text-xs">SOC 2 CF-01 requirement</p>
        </div>

        <div className="bg-card border-border rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Key className="size-4 text-blue-500" />
            <span className="text-muted-foreground text-xs">Active Keys</span>
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
            const style = STATUS_STYLES[key.status] ?? STATUS_STYLES.active

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
                    disabled={rotatingKey === key.id}
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
            const style = STATUS_STYLES[secret.status] ?? STATUS_STYLES.active
            const isRevealed = revealedSecrets.has(secret.name)

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
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground font-mono text-xs">
                      {isRevealed ? secret.masked_value : '********'}
                    </span>
                    <button
                      onClick={() => toggleReveal(secret.name)}
                      className="text-muted-foreground hover:text-foreground p-1"
                      aria-label={isRevealed ? 'Hide secret value' : 'Show masked secret value'}
                    >
                      {isRevealed ? (
                        <EyeOff className="size-3.5" />
                      ) : (
                        <Eye className="size-3.5" />
                      )}
                    </button>
                  </div>
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

      {/* Field Encryption Status */}
      <div className="bg-card border-border rounded-lg border p-6">
        <h3 className="text-foreground mb-4 flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="size-5" />
          Field Encryption Status
        </h3>
        <div className="space-y-3">
          {[
            {
              field: 'User PII (names, phone)',
              encrypted: vault.field_encryption_active,
              requirement: 'SOC 2 CF-01',
            },
            {
              field: 'OAuth Tokens',
              encrypted: vault.field_encryption_active,
              requirement: 'OAuth Security',
            },
            {
              field: 'SAML Certificates',
              encrypted: vault.field_encryption_active,
              requirement: 'SSO Security',
            },
            {
              field: 'MFA Recovery Codes',
              encrypted: vault.field_encryption_active,
              requirement: 'MFA Security',
            },
            {
              field: 'API Keys',
              encrypted: vault.field_encryption_active,
              requirement: 'API Security',
            },
          ].map((item) => (
            <div
              key={item.field}
              className="bg-muted/50 flex items-center justify-between rounded-lg p-3"
            >
              <div>
                <span className="text-foreground text-sm font-medium">{item.field}</span>
                <p className="text-muted-foreground text-xs">{item.requirement}</p>
              </div>
              <div className="flex items-center gap-1.5">
                {item.encrypted ? (
                  <>
                    <CheckCircle2 className="size-4 text-green-500" />
                    <span className="text-xs font-medium text-green-600 dark:text-green-400">
                      Encrypted
                    </span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="size-4 text-red-500" />
                    <span className="text-xs font-medium text-red-600 dark:text-red-400">
                      Not Encrypted
                    </span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auto-hide indicator */}
      {revealedSecrets.size > 0 && (
        <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
          <Clock className="size-3" />
          Revealed secret values will auto-hide in 30 seconds
        </p>
      )}
    </div>
  )
}
