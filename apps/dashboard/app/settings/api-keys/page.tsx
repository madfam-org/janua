'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  Code,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Plus,
  Copy,
  Trash2,
  Key,
  Eye,
  EyeOff,
  RefreshCw,
} from 'lucide-react'
import { listApiKeys, createApiKey, revokeApiKey } from '@/lib/api'
import { TOAST_DISMISS_MS } from '@/lib/constants'

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  created_at: string
  last_used_at: string | null
  expires_at: string | null
  is_active: boolean
}

interface NewApiKeyResponse {
  id: string
  name: string
  key: string // Full key, shown only once
  key_prefix: string
  scopes: string[]
  created_at: string
  expires_at: string | null
}

const availableScopes = [
  { id: 'read:users', label: 'Read Users', description: 'View user information' },
  { id: 'write:users', label: 'Write Users', description: 'Create and update users' },
  { id: 'read:organizations', label: 'Read Organizations', description: 'View organization data' },
  { id: 'write:organizations', label: 'Write Organizations', description: 'Manage organizations' },
  { id: 'read:sessions', label: 'Read Sessions', description: 'View session information' },
  { id: 'write:sessions', label: 'Write Sessions', description: 'Manage sessions' },
  { id: 'read:audit', label: 'Read Audit Logs', description: 'View audit trail' },
  { id: 'admin', label: 'Admin Access', description: 'Full administrative access' },
]

export default function ApiKeysPage() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // New key form
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [newKeyResponse, setNewKeyResponse] = useState<NewApiKeyResponse | null>(null)
  const [showKey, setShowKey] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetchApiKeys()
  }, [])

  const fetchApiKeys = async () => {
    try {
      setLoading(true)
      setError(null)

      const data = await listApiKeys()
      setApiKeys(Array.isArray(data) ? data as unknown as ApiKey[] : [])
    } catch (err) {
      console.error('Failed to fetch API keys:', err)
      setError(err instanceof Error ? err.message : 'Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      setError('Please enter a name for the API key')
      return
    }

    if (selectedScopes.length === 0) {
      setError('Please select at least one scope')
      return
    }

    setCreating(true)
    setError(null)

    try {
      const data = await createApiKey({
        name: newKeyName.trim(),
        permissions: selectedScopes,
      })
      setNewKeyResponse(data as unknown as NewApiKeyResponse)
      setSuccess('API key created successfully! Copy it now - you won\'t be able to see it again.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  const handleCopyKey = async () => {
    if (!newKeyResponse?.key) return

    try {
      await navigator.clipboard.writeText(newKeyResponse.key)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Failed to copy to clipboard')
    }
  }

  const handleDeleteKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
      return
    }

    try {
      await revokeApiKey(keyId)

      setSuccess('API key revoked successfully')
      setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
      fetchApiKeys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke API key')
    }
  }

  const handleCloseCreateModal = () => {
    setShowCreateForm(false)
    setNewKeyName('')
    setSelectedScopes([])
    setNewKeyResponse(null)
    setShowKey(false)
    fetchApiKeys()
  }

  const toggleScope = (scopeId: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeId) ? prev.filter((s) => s !== scopeId) : [...prev, scopeId]
    )
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading API keys...</p>
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
              <Code className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">API Keys</h1>
                <p className="text-muted-foreground text-sm">
                  Manage programmatic access to the Janua API
                </p>
              </div>
            </div>
            <Button onClick={() => setShowCreateForm(true)}>
              <Plus className="mr-2 size-4" />
              Create API Key
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

        {/* Create Key Modal */}
        {showCreateForm && (
          <Card className="border-primary">
            <CardHeader>
              <CardTitle>
                {newKeyResponse ? 'API Key Created' : 'Create New API Key'}
              </CardTitle>
              <CardDescription>
                {newKeyResponse
                  ? 'Copy your API key now. You won\'t be able to see it again!'
                  : 'Create a new API key for programmatic access'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {newKeyResponse ? (
                <div className="space-y-4">
                  <div className="rounded-lg border bg-yellow-50 p-4 dark:bg-yellow-950">
                    <div className="mb-2 flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                      <AlertCircle className="size-5" />
                      <span className="font-medium">Save this key securely!</span>
                    </div>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300">
                      This is the only time you&apos;ll see the full API key. Store it in a secure location.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>API Key</Label>
                    <div className="flex gap-2">
                      <div className="bg-muted flex-1 rounded-lg border p-3 font-mono text-sm">
                        {showKey ? newKeyResponse.key : '•'.repeat(40)}
                      </div>
                      <Button variant="outline" size="icon" onClick={() => setShowKey(!showKey)}>
                        {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                      </Button>
                      <Button variant="outline" size="icon" onClick={handleCopyKey}>
                        {copied ? (
                          <CheckCircle2 className="size-4 text-green-600" />
                        ) : (
                          <Copy className="size-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={handleCloseCreateModal}>Done</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="key_name">Key Name</Label>
                    <Input
                      id="key_name"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      placeholder="Production API Key"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Scopes</Label>
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      {availableScopes.map((scope) => (
                        <label
                          key={scope.id}
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                            selectedScopes.includes(scope.id)
                              ? 'border-primary bg-primary/5'
                              : 'hover:bg-muted'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedScopes.includes(scope.id)}
                            onChange={() => toggleScope(scope.id)}
                            className="mt-1"
                          />
                          <div>
                            <div className="font-medium">{scope.label}</div>
                            <div className="text-muted-foreground text-sm">{scope.description}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={handleCloseCreateModal}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateKey} disabled={creating}>
                      {creating ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <Key className="mr-2 size-4" />
                      )}
                      Create Key
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* API Keys List */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Active API Keys</CardTitle>
                <CardDescription>
                  Manage your existing API keys
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchApiKeys}>
                <RefreshCw className="mr-2 size-4" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {apiKeys.length === 0 ? (
              <div className="py-8 text-center">
                <Key className="text-muted-foreground mx-auto size-12" />
                <h3 className="mt-4 text-lg font-medium">No API keys yet</h3>
                <p className="text-muted-foreground mt-2">
                  Create your first API key to get started with programmatic access.
                </p>
                <Button className="mt-4" onClick={() => setShowCreateForm(true)}>
                  <Plus className="mr-2 size-4" />
                  Create API Key
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {apiKeys.map((key) => (
                  <div
                    key={key.id}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div className="flex items-center gap-4">
                      <div className="bg-muted rounded-lg p-2">
                        <Key className="size-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{key.name}</span>
                          <Badge variant={key.is_active ? 'default' : 'secondary'}>
                            {key.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                        <div className="text-muted-foreground mt-1 text-sm">
                          <code className="bg-muted rounded px-1">{key.key_prefix}...</code>
                          <span className="mx-2">·</span>
                          Created {new Date(key.created_at).toLocaleDateString()}
                          {key.last_used_at && (
                            <>
                              <span className="mx-2">·</span>
                              Last used {new Date(key.last_used_at).toLocaleDateString()}
                            </>
                          )}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {key.scopes.map((scope) => (
                            <Badge key={scope} variant="outline" className="text-xs">
                              {scope}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                      onClick={() => handleDeleteKey(key.id)}
                    >
                      <Trash2 className="mr-2 size-4" />
                      Revoke
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Security Information */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">API Key Security</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground space-y-2 text-sm">
            <p>
              <strong>Keep keys secret:</strong> Never expose API keys in client-side code, public
              repositories, or share them publicly.
            </p>
            <p>
              <strong>Use minimal scopes:</strong> Only grant the permissions your integration needs.
            </p>
            <p>
              <strong>Rotate regularly:</strong> Create new keys and revoke old ones periodically.
            </p>
            <p>
              <strong>Monitor usage:</strong> Review the &quot;last used&quot; timestamps to detect unauthorized
              access.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
