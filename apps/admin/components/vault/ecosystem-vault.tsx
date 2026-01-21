'use client'

import * as React from 'react'
import { Key, RefreshCw, AlertTriangle, Clock, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

import type { MaskedSecret, SecretCategory, SecretStatus } from './types'
import { CATEGORY_ICONS, CATEGORY_LABELS } from './constants'
import { VaultStatusBadge } from './status-badge'
import { MaskedValue } from './masked-value'
import { RotationSheet } from './rotation-sheet'

// Mock data for demonstration
const MOCK_SECRETS: MaskedSecret[] = [
  {
    id: '1',
    name: 'JWT_SECRET',
    maskedValue: 'sk_live_****...****4x2a',
    category: 'authentication',
    status: 'active',
    lastRotated: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000),
    dependentServices: ['API Gateway', 'Auth Service'],
    description: 'Main JWT signing secret',
  },
  {
    id: '2',
    name: 'STRIPE_SECRET_KEY',
    maskedValue: 'sk_live_****...****9k3m',
    category: 'payment',
    status: 'active',
    lastRotated: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 75 * 24 * 60 * 60 * 1000),
    dependentServices: ['Billing Service', 'Subscription Manager'],
    description: 'Stripe API secret key',
  },
  {
    id: '3',
    name: 'DATABASE_PASSWORD',
    maskedValue: 'pg_****...****xyz1',
    category: 'infrastructure',
    status: 'active',
    lastRotated: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 45 * 24 * 60 * 60 * 1000),
    dependentServices: ['API', 'Worker', 'Scheduler'],
    description: 'PostgreSQL master password',
  },
  {
    id: '4',
    name: 'SENDGRID_API_KEY',
    maskedValue: 'SG.****...****abc2',
    category: 'email',
    status: 'active',
    lastRotated: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 45 * 24 * 60 * 60 * 1000),
    dependentServices: ['Email Service', 'Notification Worker'],
    description: 'SendGrid transactional email API key',
  },
  {
    id: '5',
    name: 'CLOUDFLARE_API_TOKEN',
    maskedValue: 'cf_****...****def3',
    category: 'infrastructure',
    status: 'rotating',
    lastRotated: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 89 * 24 * 60 * 60 * 1000),
    dependentServices: ['CDN', 'DNS Manager', 'WAF'],
    description: 'Cloudflare API token for DNS and CDN management',
  },
  {
    id: '6',
    name: 'REDIS_PASSWORD',
    maskedValue: 'redis_****...****ghi4',
    category: 'infrastructure',
    status: 'active',
    lastRotated: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000),
    nextRotation: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
    dependentServices: ['Cache Layer', 'Session Store', 'Rate Limiter'],
    description: 'Redis cache password',
  },
]

export function EcosystemVault() {
  const [secrets, setSecrets] = React.useState<MaskedSecret[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [revealedSecrets, setRevealedSecrets] = React.useState<Set<string>>(new Set())
  const [categoryFilter, setCategoryFilter] = React.useState<SecretCategory | 'all'>('all')

  // Auto-hide revealed secrets after 30 seconds
  React.useEffect(() => {
    if (revealedSecrets.size > 0) {
      const timer = setTimeout(() => {
        setRevealedSecrets(new Set())
      }, 30000)
      return () => clearTimeout(timer)
    }
  }, [revealedSecrets])

  // Fetch secrets
  const fetchSecrets = React.useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      // In production, this would call the admin API
      setSecrets(MOCK_SECRETS)
    } catch (err) {
      console.error('Failed to fetch secrets:', err)
      setError(err instanceof Error ? err.message : 'Failed to load secrets')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    fetchSecrets()
  }, [fetchSecrets])

  // Handle secret reveal
  const handleReveal = async (secretId: string) => {
    if (revealedSecrets.has(secretId)) {
      const newRevealed = new Set(revealedSecrets)
      newRevealed.delete(secretId)
      setRevealedSecrets(newRevealed)
    } else {
      const secret = secrets.find((s) => s.id === secretId)
      if (secret) {
        const fullValue = `${secret.name}_FULL_VALUE_${Math.random().toString(36).substring(7)}`
        setSecrets((prev) => prev.map((s) => (s.id === secretId ? { ...s, fullValue } : s)))
        setRevealedSecrets((prev) => new Set(prev).add(secretId))
      }
    }
  }

  // Handle rotation
  const handleRotate = async (secretId: string, newValue: string, reason?: string) => {
    console.log('Rotating secret:', secretId, 'Reason:', reason)
    setSecrets((prev) =>
      prev.map((s) =>
        s.id === secretId
          ? {
              ...s,
              status: 'active' as SecretStatus,
              lastRotated: new Date(),
              nextRotation: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
              maskedValue: `${s.name.substring(0, 4)}_****...****${newValue.substring(newValue.length - 4)}`,
            }
          : s
      )
    )
  }

  // Filter secrets by category
  const filteredSecrets = React.useMemo(() => {
    if (categoryFilter === 'all') return secrets
    return secrets.filter((s) => s.category === categoryFilter)
  }, [secrets, categoryFilter])

  // Count by category
  const categoryCounts = React.useMemo(() => {
    const counts: Record<string, number> = { all: secrets.length }
    for (const secret of secrets) {
      counts[secret.category] = (counts[secret.category] || 0) + 1
    }
    return counts
  }, [secrets])

  // Count overdue
  const overdueCount = secrets.filter(
    (s) => new Date(s.nextRotation) < new Date() && s.status !== 'revoked'
  ).length

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-primary size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading vault...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertTriangle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Vault</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchSecrets} variant="outline">
          <RefreshCw className="mr-2 size-4" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <Key className="text-primary size-6" />
            Ecosystem Vault
          </h2>
          <p className="text-muted-foreground">Manage platform secrets and API keys</p>
        </div>
        <div className="flex items-center gap-2">
          {overdueCount > 0 && (
            <Badge variant="destructive" className="animate-pulse-glow">
              <AlertTriangle className="mr-1 size-3" />
              {overdueCount} overdue
            </Badge>
          )}
          <Button variant="outline" onClick={fetchSecrets}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Category filters */}
      <div className="flex gap-2">
        <Button
          variant={categoryFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setCategoryFilter('all')}
        >
          All ({categoryCounts.all})
        </Button>
        {(Object.keys(CATEGORY_LABELS) as SecretCategory[]).map((category) => (
          <Button
            key={category}
            variant={categoryFilter === category ? 'default' : 'outline'}
            size="sm"
            onClick={() => setCategoryFilter(category)}
          >
            {CATEGORY_ICONS[category]}
            <span className="ml-1">{CATEGORY_LABELS[category]}</span>
            <span className="ml-1">({categoryCounts[category] || 0})</span>
          </Button>
        ))}
      </div>

      {/* Secrets table */}
      <Card className="border-border">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-[200px]">Secret</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Last Rotated</TableHead>
                <TableHead>Next Rotation</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSecrets.map((secret) => {
                const isOverdue = new Date(secret.nextRotation) < new Date() && secret.status !== 'revoked'
                const isRevealed = revealedSecrets.has(secret.id)

                return (
                  <TableRow key={secret.id} className={`border-border ${isOverdue ? 'bg-destructive/5' : ''}`}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-mono font-medium">{secret.name}</span>
                        {secret.description && (
                          <span className="text-muted-foreground text-xs">{secret.description}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {CATEGORY_ICONS[secret.category]}
                        <span className="text-sm">{CATEGORY_LABELS[secret.category]}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <VaultStatusBadge status={secret.status} />
                    </TableCell>
                    <TableCell>
                      <MaskedValue
                        maskedValue={secret.maskedValue}
                        fullValue={secret.fullValue}
                        onReveal={() => handleReveal(secret.id)}
                        revealed={isRevealed}
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(secret.lastRotated).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div
                        className={`flex items-center gap-1 text-sm ${isOverdue ? 'text-destructive' : 'text-muted-foreground'}`}
                      >
                        {isOverdue && <AlertTriangle className="size-3" />}
                        {new Date(secret.nextRotation).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <RotationSheet secret={secret} onRotate={handleRotate} />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Auto-hide notice */}
      {revealedSecrets.size > 0 && (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Clock className="size-4" />
          Revealed secrets will auto-hide in 30 seconds
        </div>
      )}
    </div>
  )
}
