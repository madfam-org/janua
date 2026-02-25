'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@janua/ui'
import Link from 'next/link'
import {
  Plus,
  Copy,
  RefreshCw,
  Trash2,
  Eye,
  EyeOff,
  Loader2,
  AlertCircle,
  Globe,
  Shield,
  ArrowLeft,
  CheckCircle2,
  X,
  Pencil,
  Search,
  ChevronLeft,
  ChevronRight,
  Clock,
  AlertTriangle,
} from 'lucide-react'
import {
  listOAuthClients,
  createOAuthClient,
  updateOAuthClient,
  deleteOAuthClient,
  rotateClientSecret,
  getOAuthClientSecretStatus,
  revokeClientSecret,
  revokeAllOldSecrets,
  type OAuthClient,
  type OAuthClientRotateResponse,
  type OAuthClientSecretStatusResponse,
  type OAuthClientSecretInfo,
} from '@/lib/api'
import { CodeSnippets } from '@/components/oauth/code-snippets'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GRANT_TYPE_OPTIONS = [
  { id: 'authorization_code', label: 'Authorization Code', description: 'Standard web app flow with redirect' },
  { id: 'client_credentials', label: 'Client Credentials', description: 'Machine-to-machine authentication' },
  { id: 'refresh_token', label: 'Refresh Token', description: 'Allow token refresh for long-lived sessions' },
  { id: 'implicit', label: 'Implicit (Legacy)', description: 'Legacy browser-only flow, not recommended' },
]

const SCOPE_OPTIONS = [
  { id: 'openid', label: 'OpenID', description: 'OpenID Connect identity token' },
  { id: 'profile', label: 'Profile', description: 'User profile information' },
  { id: 'email', label: 'Email', description: 'User email address' },
  { id: 'offline_access', label: 'Offline Access', description: 'Refresh token for offline access' },
  { id: 'api', label: 'API', description: 'General API access' },
  { id: 'admin', label: 'Admin', description: 'Administrative operations' },
]

const PER_PAGE = 20

// ---------------------------------------------------------------------------
// Helper Components
// ---------------------------------------------------------------------------

function SecretDisplay({
  secret,
  masked,
  onCopy,
}: {
  secret?: string
  masked: string
  onCopy?: () => void
}) {
  const [visible, setVisible] = useState(false)
  const displayValue = secret ? (visible ? secret : masked) : masked

  return (
    <div className="flex items-center gap-2">
      <code className="bg-muted flex-1 truncate rounded px-2 py-1 font-mono text-sm">
        {displayValue}
      </code>
      {secret && (
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? 'Hide secret' : 'Show secret'}
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
      )}
      {onCopy && (
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onCopy}
          aria-label="Copy to clipboard"
        >
          <Copy className="size-4" />
        </Button>
      )}
    </div>
  )
}

function RedirectUriInput({
  uris,
  onChange,
}: {
  uris: string[]
  onChange: (uris: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  const addUri = () => {
    const trimmed = draft.trim()
    if (!trimmed) return
    try {
      new URL(trimmed)
    } catch {
      return
    }
    if (!uris.includes(trimmed)) {
      onChange([...uris, trimmed])
    }
    setDraft('')
  }

  const removeUri = (uri: string) => {
    onChange(uris.filter((u) => u !== uri))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addUri()
    }
  }

  return (
    <div className="space-y-2">
      <Label>Redirect URIs</Label>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="https://example.com/callback"
          aria-label="Add redirect URI"
        />
        <Button type="button" variant="outline" onClick={addUri}>
          Add
        </Button>
      </div>
      {uris.length > 0 && (
        <ul className="space-y-1" role="list" aria-label="Redirect URIs">
          {uris.map((uri) => (
            <li
              key={uri}
              className="bg-muted flex items-center justify-between rounded px-3 py-1.5 text-sm"
            >
              <span className="truncate font-mono">{uri}</span>
              <Button
                variant="ghost"
                size="icon"
                className="size-6 shrink-0"
                onClick={() => removeUri(uri)}
                aria-label={`Remove ${uri}`}
              >
                <X className="size-3" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: { id: string; label: string; description: string }[]
  selected: string[]
  onChange: (selected: string[]) => void
}) {
  const toggle = (id: string) => {
    onChange(
      selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]
    )
  }

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {options.map((option) => (
          <label
            key={option.id}
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
              selected.includes(option.id)
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted'
            }`}
          >
            <input
              type="checkbox"
              checked={selected.includes(option.id)}
              onChange={() => toggle(option.id)}
              className="mt-1"
            />
            <div>
              <div className="font-medium">{option.label}</div>
              <div className="text-muted-foreground text-sm">{option.description}</div>
            </div>
          </label>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Create / Edit Dialog
// ---------------------------------------------------------------------------

function CreateEditDialog({
  open,
  onOpenChange,
  editClient,
  onSuccess,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  editClient?: OAuthClient | null
  onSuccess: () => void
}) {
  const isEdit = !!editClient

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [redirectUris, setRedirectUris] = useState<string[]>([])
  const [grantTypes, setGrantTypes] = useState<string[]>(['authorization_code', 'refresh_token'])
  const [scopes, setScopes] = useState<string[]>(['openid', 'profile', 'email'])
  const [audience, setAudience] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [isConfidential, setIsConfidential] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Secret + client ID shown only after create
  const [createdSecret, setCreatedSecret] = useState<string | null>(null)
  const [createdClientId, setCreatedClientId] = useState<string | null>(null)
  const [secretCopied, setSecretCopied] = useState(false)

  // Reset form when dialog opens or editClient changes
  useEffect(() => {
    if (open) {
      if (editClient) {
        setName(editClient.name)
        setDescription(editClient.description || '')
        setRedirectUris(editClient.redirect_uris)
        setGrantTypes(editClient.grant_types)
        setScopes(editClient.allowed_scopes)
        setAudience(editClient.audience || '')
        setLogoUrl(editClient.logo_url || '')
        setWebsiteUrl(editClient.website_url || '')
        setIsConfidential(editClient.is_confidential)
      } else {
        setName('')
        setDescription('')
        setRedirectUris([])
        setGrantTypes(['authorization_code', 'refresh_token'])
        setScopes(['openid', 'profile', 'email'])
        setAudience('')
        setLogoUrl('')
        setWebsiteUrl('')
        setIsConfidential(true)
      }
      setCreatedSecret(null)
      setSecretCopied(false)
      setError(null)
    }
  }, [open, editClient])

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Client name is required')
      return
    }
    if (redirectUris.length === 0 && grantTypes.includes('authorization_code')) {
      setError('At least one redirect URI is required for the authorization code flow')
      return
    }
    if (grantTypes.length === 0) {
      setError('Select at least one grant type')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      if (isEdit) {
        await updateOAuthClient(editClient.id, {
          name: name.trim(),
          redirect_uris: redirectUris,
          grant_types: grantTypes,
          allowed_scopes: scopes,
          audience: audience.trim() || undefined,
          description: description.trim() || undefined,
          logo_url: logoUrl.trim() || null,
          website_url: websiteUrl.trim() || null,
        })
        onSuccess()
        onOpenChange(false)
      } else {
        const result = await createOAuthClient({
          name: name.trim(),
          redirect_uris: redirectUris,
          grant_types: grantTypes,
          allowed_scopes: scopes,
          audience: audience.trim() || undefined,
          description: description.trim() || undefined,
          logo_url: logoUrl.trim() || null,
          website_url: websiteUrl.trim() || null,
          is_confidential: isConfidential,
        })
        setCreatedSecret(result.client_secret || null)
        setCreatedClientId(result.client_id)
        onSuccess()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  const handleCopySecret = async () => {
    if (!createdSecret) return
    try {
      await navigator.clipboard.writeText(createdSecret)
      setSecretCopied(true)
      setTimeout(() => setSecretCopied(false), 2000)
    } catch {
      setError('Failed to copy to clipboard')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {createdSecret
              ? 'Client Created Successfully'
              : isEdit
                ? 'Edit OAuth Client'
                : 'Create OAuth Client'}
          </DialogTitle>
        </DialogHeader>

        {createdSecret ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 dark:border-yellow-700 dark:bg-yellow-950">
              <div className="mb-2 flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                <AlertCircle className="size-5" />
                <span className="font-medium">Save this secret now!</span>
              </div>
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                This is the only time the client secret will be displayed. Store it in a
                secure location.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Client Secret</Label>
              <div className="flex gap-2">
                <code className="bg-muted flex-1 break-all rounded-lg border p-3 font-mono text-sm">
                  {createdSecret}
                </code>
                <Button variant="outline" size="icon" onClick={handleCopySecret}>
                  {secretCopied ? (
                    <CheckCircle2 className="size-4 text-green-600" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </div>
            </div>

            {createdClientId && redirectUris.length > 0 && (
              <details className="rounded-lg border">
                <summary className="cursor-pointer px-4 py-2 text-sm font-medium">
                  Integration Code
                </summary>
                <div className="border-t px-4 py-3">
                  <CodeSnippets clientId={createdClientId} redirectUri={redirectUris[0]} />
                </div>
              </details>
            )}

            <div className="flex justify-end">
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {error && (
              <div className="text-destructive flex items-center gap-2 text-sm">
                <AlertCircle className="size-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="client_name">Client Name</Label>
              <Input
                id="client_name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Application"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="client_description">Description (optional)</Label>
              <textarea
                id="client_description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of this client application"
                maxLength={1000}
                rows={2}
                className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              />
            </div>

            {!isEdit && (
              <div className="space-y-2">
                <Label>Client Type</Label>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                      isConfidential ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                  >
                    <input
                      type="radio"
                      name="client_type"
                      checked={isConfidential}
                      onChange={() => setIsConfidential(true)}
                      className="mt-1"
                    />
                    <div>
                      <div className="font-medium">Confidential</div>
                      <div className="text-muted-foreground text-sm">
                        Server-side app that can securely store a client secret
                      </div>
                    </div>
                  </label>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                      !isConfidential ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                    }`}
                  >
                    <input
                      type="radio"
                      name="client_type"
                      checked={!isConfidential}
                      onChange={() => setIsConfidential(false)}
                      className="mt-1"
                    />
                    <div>
                      <div className="font-medium">Public</div>
                      <div className="text-muted-foreground text-sm">
                        SPA or mobile app — uses PKCE only, no client secret
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            )}

            <RedirectUriInput uris={redirectUris} onChange={setRedirectUris} />

            <CheckboxGroup
              label="Grant Types"
              options={GRANT_TYPE_OPTIONS}
              selected={grantTypes}
              onChange={setGrantTypes}
            />

            <CheckboxGroup
              label="Scopes"
              options={SCOPE_OPTIONS}
              selected={scopes}
              onChange={setScopes}
            />

            <div className="space-y-2">
              <Label htmlFor="audience">Audience (optional)</Label>
              <Input
                id="audience"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="your-app-api"
              />
              <p className="text-muted-foreground text-xs">
                JWT audience claim for per-client token validation. Falls back to global audience if not set.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="logo_url">Logo URL (optional)</Label>
                <Input
                  id="logo_url"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  placeholder="https://example.com/logo.png"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="website_url">Website URL (optional)</Label>
                <Input
                  id="website_url"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  placeholder="https://example.com"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                {isEdit ? 'Save Changes' : 'Create Client'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Secret Status Panel (used inside ClientDetailDialog)
// ---------------------------------------------------------------------------

function SecretStatusPanel({
  clientId,
  onRefresh,
}: {
  clientId: string
  onRefresh: () => void
}) {
  const [status, setStatus] = useState<OAuthClientSecretStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revoking, setRevoking] = useState<string | null>(null)
  const [revokingAll, setRevokingAll] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getOAuthClientSecretStatus(clientId)
      setStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load secret status')
    } finally {
      setLoading(false)
    }
  }, [clientId])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const handleRevoke = async (secretId: string) => {
    setRevoking(secretId)
    try {
      await revokeClientSecret(clientId, secretId)
      await fetchStatus()
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke secret')
    } finally {
      setRevoking(null)
    }
  }

  const handleRevokeAllOld = async () => {
    setRevokingAll(true)
    try {
      await revokeAllOldSecrets(clientId)
      await fetchStatus()
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke old secrets')
    } finally {
      setRevokingAll(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm">
        <Loader2 className="size-4 animate-spin" />
        <span className="text-muted-foreground">Loading secret status...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-destructive flex items-center gap-2 py-2 text-sm">
        <AlertCircle className="size-4" />
        <span>{error}</span>
        <Button variant="ghost" size="sm" onClick={fetchStatus} className="ml-auto">
          Retry
        </Button>
      </div>
    )
  }

  if (!status) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-muted-foreground text-xs uppercase">Secrets</Label>
        <div className="flex items-center gap-2">
          {status.rotation_recommended && (
            <Badge variant="outline" className="border-yellow-500 text-yellow-600 dark:text-yellow-400">
              <AlertTriangle className="mr-1 size-3" />
              Rotation recommended
            </Badge>
          )}
          {status.active_count > 1 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRevokeAllOld}
              disabled={revokingAll}
              className="text-xs"
            >
              {revokingAll && <Loader2 className="mr-1 size-3 animate-spin" />}
              Revoke All Old
            </Button>
          )}
        </div>
      </div>

      {status.primary_age_days !== null && (
        <p className="text-muted-foreground text-xs">
          Primary secret: {status.primary_age_days} day{status.primary_age_days !== 1 ? 's' : ''} old
          (max recommended: {status.max_age_days} days)
        </p>
      )}

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="px-3 py-2 text-left text-xs font-medium">Prefix</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Status</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Created</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Expires</th>
              <th className="px-3 py-2 text-right text-xs font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {status.secrets.filter((s) => s.is_valid).map((secret) => (
              <tr key={secret.id} className="border-b last:border-0">
                <td className="px-3 py-2">
                  <code className="text-xs">{secret.prefix}</code>
                </td>
                <td className="px-3 py-2">
                  {secret.is_primary ? (
                    <Badge variant="default" className="text-xs">Primary</Badge>
                  ) : secret.expires_at ? (
                    <Badge variant="outline" className="text-xs">
                      <Clock className="mr-1 size-3" />
                      Grace period
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-xs">Active</Badge>
                  )}
                </td>
                <td className="text-muted-foreground px-3 py-2 text-xs">
                  {new Date(secret.created_at).toLocaleDateString()}
                </td>
                <td className="text-muted-foreground px-3 py-2 text-xs">
                  {secret.expires_at ? new Date(secret.expires_at).toLocaleString() : '—'}
                </td>
                <td className="px-3 py-2 text-right">
                  {!secret.is_primary && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive h-7 text-xs"
                      onClick={() => handleRevoke(secret.id)}
                      disabled={revoking === secret.id}
                    >
                      {revoking === secret.id ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        'Revoke'
                      )}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail Dialog
// ---------------------------------------------------------------------------

function ClientDetailDialog({
  client,
  open,
  onOpenChange,
  onRotate,
  onDelete,
  onEdit,
}: {
  client: OAuthClient
  open: boolean
  onOpenChange: (open: boolean) => void
  onRotate: () => void
  onDelete: () => void
  onEdit: () => void
}) {
  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(client.client_id)
    } catch {
      // clipboard not available
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="size-5" />
            {client.name}
            {client.description && (
              <span className="text-muted-foreground ml-2 text-sm font-normal">
                — {client.description}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          {/* Client ID */}
          <div className="space-y-1">
            <Label className="text-muted-foreground text-xs uppercase">Client ID</Label>
            <div className="flex items-center gap-2">
              <code className="bg-muted flex-1 truncate rounded px-2 py-1 font-mono text-sm">
                {client.client_id}
              </code>
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                onClick={handleCopyId}
                aria-label="Copy client ID"
              >
                <Copy className="size-4" />
              </Button>
            </div>
          </div>

          {/* Client Type */}
          <div className="space-y-1">
            <Label className="text-muted-foreground text-xs uppercase">Client Type</Label>
            <Badge variant={client.is_confidential ? 'default' : 'outline'}>
              {client.is_confidential ? 'Confidential' : 'Public (PKCE)'}
            </Badge>
          </div>

          {/* Audience */}
          {client.audience && (
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs uppercase">Audience</Label>
              <code className="bg-muted block rounded px-2 py-1 font-mono text-sm">
                {client.audience}
              </code>
            </div>
          )}

          {/* Redirect URIs */}
          <div className="space-y-1">
            <Label className="text-muted-foreground text-xs uppercase">Redirect URIs</Label>
            {client.redirect_uris.length > 0 ? (
              <ul className="space-y-1" role="list">
                {client.redirect_uris.map((uri) => (
                  <li key={uri} className="bg-muted rounded px-2 py-1 font-mono text-sm">
                    {uri}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">None configured</p>
            )}
          </div>

          {/* Grant Types */}
          <div className="space-y-1">
            <Label className="text-muted-foreground text-xs uppercase">Grant Types</Label>
            <div className="flex flex-wrap gap-1">
              {client.grant_types.length > 0 ? (
                client.grant_types.map((gt) => (
                  <Badge key={gt} variant="outline">{gt}</Badge>
                ))
              ) : (
                <span className="text-muted-foreground text-sm">None</span>
              )}
            </div>
          </div>

          {/* Scopes */}
          <div className="space-y-1">
            <Label className="text-muted-foreground text-xs uppercase">Scopes</Label>
            <div className="flex flex-wrap gap-1">
              {client.allowed_scopes.length > 0 ? (
                client.allowed_scopes.map((scope) => (
                  <Badge key={scope} variant="secondary">{scope}</Badge>
                ))
              ) : (
                <span className="text-muted-foreground text-sm">None</span>
              )}
            </div>
          </div>

          {/* Website */}
          {client.website_url && (
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs uppercase">Website</Label>
              <a
                href={client.website_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary text-sm hover:underline"
              >
                {client.website_url}
              </a>
            </div>
          )}

          {/* Timestamps */}
          <div className="text-muted-foreground grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="block text-xs uppercase">Created</span>
              {new Date(client.created_at).toLocaleString()}
            </div>
            {client.updated_at && (
              <div>
                <span className="block text-xs uppercase">Updated</span>
                {new Date(client.updated_at).toLocaleString()}
              </div>
            )}
          </div>

          {/* Secret Status Panel */}
          <div className="border-t pt-4">
            <SecretStatusPanel clientId={client.id} onRefresh={() => {}} />
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2 border-t pt-4">
            <Button variant="outline" onClick={onEdit}>
              <Pencil className="mr-2 size-4" />
              Edit
            </Button>
            <Button variant="outline" onClick={onRotate}>
              <RefreshCw className="mr-2 size-4" />
              Rotate Secret
            </Button>
            <Button
              variant="outline"
              className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
              onClick={onDelete}
            >
              <Trash2 className="mr-2 size-4" />
              Delete
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Confirm Dialog (generic — used for delete)
// ---------------------------------------------------------------------------

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  loading,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel: string
  destructive?: boolean
  loading?: boolean
  onConfirm: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <p className="text-muted-foreground text-sm">{description}</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <Loader2 className="mr-2 size-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Rotate Secret Dialog (with grace period control)
// ---------------------------------------------------------------------------

function RotateSecretDialog({
  open,
  onOpenChange,
  clientName,
  loading,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  clientName: string
  loading: boolean
  onConfirm: (gracePeriodHours: number) => void
}) {
  const [gracePeriod, setGracePeriod] = useState(24)

  useEffect(() => {
    if (open) setGracePeriod(24)
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rotate Client Secret</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-muted-foreground text-sm">
            This will generate a new secret for &ldquo;{clientName}&rdquo;. A grace period
            allows old secrets to continue working, enabling zero-downtime updates.
          </p>

          <div className="space-y-2">
            <Label htmlFor="grace_period">Grace Period (hours)</Label>
            <Input
              id="grace_period"
              type="number"
              min={0}
              max={168}
              value={gracePeriod}
              onChange={(e) => setGracePeriod(Math.max(0, Math.min(168, Number(e.target.value) || 0)))}
            />
            <p className="text-muted-foreground text-xs">
              {gracePeriod === 0
                ? 'Old secrets will be invalidated immediately.'
                : `Old secrets will continue working for ${gracePeriod} hour${gracePeriod !== 1 ? 's' : ''}, allowing time to update your application.`}
            </p>
          </div>

          {gracePeriod === 0 && (
            <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-3 dark:border-yellow-700 dark:bg-yellow-950">
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                <AlertTriangle className="mr-1 inline size-4" />
                Setting grace period to 0 will immediately invalidate old secrets. Applications
                using the current secret will break until updated.
              </p>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button onClick={() => onConfirm(gracePeriod)} disabled={loading}>
              {loading && <Loader2 className="mr-2 size-4 animate-spin" />}
              Rotate Secret
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Rotate Secret Result Dialog
// ---------------------------------------------------------------------------

function RotateResultDialog({
  open,
  onOpenChange,
  result,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  result: OAuthClientRotateResponse
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.client_secret)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Secret Rotated Successfully</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 dark:border-yellow-700 dark:bg-yellow-950">
            <div className="mb-2 flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
              <AlertCircle className="size-5" />
              <span className="font-medium">Save this secret now!</span>
            </div>
            <p className="text-sm text-yellow-700 dark:text-yellow-300">
              Copy the new secret before closing this dialog.
              {result.grace_period_hours > 0 && (
                <> Old secrets will remain valid until{' '}
                  <strong>{new Date(result.old_secrets_expire_at).toLocaleString()}</strong>
                  {' '}({result.grace_period_hours}h grace period).
                </>
              )}
              {result.grace_period_hours === 0 && (
                <> Old secrets have been invalidated immediately.</>
              )}
            </p>
          </div>

          <div className="space-y-2">
            <Label>New Client Secret</Label>
            <div className="flex gap-2">
              <code className="bg-muted flex-1 break-all rounded-lg border p-3 font-mono text-sm">
                {result.client_secret}
              </code>
              <Button variant="outline" size="icon" onClick={handleCopy}>
                {copied ? (
                  <CheckCircle2 className="size-4 text-green-600" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
          </div>

          {result.grace_period_hours > 0 && (
            <div className="text-muted-foreground flex items-center gap-2 text-sm">
              <Clock className="size-4" />
              Grace period expires: {new Date(result.old_secrets_expire_at).toLocaleString()}
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={() => onOpenChange(false)}>Done</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function OAuthClientsPage() {
  const [clients, setClients] = useState<OAuthClient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Pagination
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  // Search (client-side)
  const [searchQuery, setSearchQuery] = useState('')

  // Dialogs
  const [createOpen, setCreateOpen] = useState(false)
  const [editClient, setEditClient] = useState<OAuthClient | null>(null)
  const [detailClient, setDetailClient] = useState<OAuthClient | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<OAuthClient | null>(null)
  const [rotateTarget, setRotateTarget] = useState<OAuthClient | null>(null)
  const [rotateResult, setRotateResult] = useState<OAuthClientRotateResponse | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchClients = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await listOAuthClients({ page, per_page: PER_PAGE })
      setClients(data.clients)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to fetch OAuth clients:', err)
      setError(err instanceof Error ? err.message : 'Failed to load OAuth clients')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    fetchClients()
  }, [fetchClients])

  // Clear success message after timeout
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [success])

  // Client-side filtered list
  const filteredClients = searchQuery.trim()
    ? clients.filter((c) => {
        const q = searchQuery.toLowerCase()
        return (
          c.name.toLowerCase().includes(q) ||
          c.client_id.toLowerCase().includes(q) ||
          (c.description && c.description.toLowerCase().includes(q))
        )
      })
    : clients

  const totalPages = Math.ceil(total / PER_PAGE)

  // ---- Delete ----
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setActionLoading(true)
    try {
      await deleteOAuthClient(deleteTarget.id)
      setSuccess(`OAuth client "${deleteTarget.name}" has been deleted.`)
      setDeleteTarget(null)
      setDetailClient(null)
      fetchClients()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete client')
      setDeleteTarget(null)
    } finally {
      setActionLoading(false)
    }
  }

  // ---- Rotate Secret ----
  const handleRotateConfirm = async (gracePeriodHours: number) => {
    if (!rotateTarget) return
    setActionLoading(true)
    try {
      const result = await rotateClientSecret(rotateTarget.id, gracePeriodHours)
      setRotateTarget(null)
      setDetailClient(null)
      setRotateResult(result)
      fetchClients()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rotate secret')
      setRotateTarget(null)
    } finally {
      setActionLoading(false)
    }
  }

  // ---- Edit from detail ----
  const handleEditFromDetail = () => {
    if (!detailClient) return
    setDetailClient(null)
    setEditClient(detailClient)
    setCreateOpen(true)
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading && clients.length === 0) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading OAuth clients...</p>
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
              <Globe className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">OAuth Clients</h1>
                <p className="text-muted-foreground text-sm">
                  Manage OAuth 2.0 client applications for third-party integrations
                </p>
              </div>
            </div>
            <Button
              onClick={() => {
                setEditClient(null)
                setCreateOpen(true)
              }}
            >
              <Plus className="mr-2 size-4" />
              Create Client
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {/* Error banner */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5 shrink-0" />
                <span>{error}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto size-6"
                  onClick={() => setError(null)}
                  aria-label="Dismiss error"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Success banner */}
        {success && (
          <Card className="border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5 shrink-0" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Client List */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Registered Clients</CardTitle>
                <CardDescription>
                  OAuth 2.0 clients that can authenticate against your Janua instance
                  {total > 0 && ` (${total} total)`}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchClients}>
                <RefreshCw className="mr-2 size-4" />
                Refresh
              </Button>
            </div>
            {/* Search */}
            {clients.length > 0 && (
              <div className="relative mt-4">
                <Search className="text-muted-foreground pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name or client ID..."
                  className="pl-9"
                  aria-label="Search clients"
                />
              </div>
            )}
          </CardHeader>
          <CardContent>
            {filteredClients.length === 0 && clients.length === 0 ? (
              <div className="py-8 text-center">
                <Globe className="text-muted-foreground mx-auto size-12" />
                <h3 className="mt-4 text-lg font-medium">No OAuth clients yet</h3>
                <p className="text-muted-foreground mt-2">
                  Create your first OAuth client to enable third-party integrations.
                </p>
                <Button
                  className="mt-4"
                  onClick={() => {
                    setEditClient(null)
                    setCreateOpen(true)
                  }}
                >
                  <Plus className="mr-2 size-4" />
                  Create Client
                </Button>
              </div>
            ) : filteredClients.length === 0 ? (
              <div className="py-8 text-center">
                <Search className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">
                  No clients match &ldquo;{searchQuery}&rdquo;
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredClients.map((client) => (
                  <div
                    key={client.id}
                    className="flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50 cursor-pointer"
                    role="button"
                    tabIndex={0}
                    onClick={() => setDetailClient(client)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setDetailClient(client)
                      }
                    }}
                    aria-label={`View details for ${client.name}`}
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="bg-muted shrink-0 rounded-lg p-2">
                        {client.logo_url ? (
                          <img
                            src={client.logo_url}
                            alt=""
                            className="size-5 rounded"
                            aria-hidden="true"
                          />
                        ) : (
                          <Globe className="size-5" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{client.name}</span>
                          <Badge variant={client.is_active ? 'default' : 'secondary'}>
                            {client.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {client.is_confidential ? 'Confidential' : 'Public'}
                          </Badge>
                        </div>
                        <div className="text-muted-foreground mt-1 text-sm">
                          <code className="bg-muted rounded px-1 text-xs">
                            {client.client_id}
                          </code>
                          {client.description && (
                            <>
                              <span className="mx-2">&middot;</span>
                              <span className="truncate">{client.description}</span>
                            </>
                          )}
                          <span className="mx-2">&middot;</span>
                          Created {new Date(client.created_at).toLocaleDateString()}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {client.grant_types.map((gt) => (
                            <Badge key={gt} variant="outline" className="text-xs">
                              {gt}
                            </Badge>
                          ))}
                          {client.allowed_scopes.slice(0, 4).map((scope) => (
                            <Badge key={scope} variant="secondary" className="text-xs">
                              {scope}
                            </Badge>
                          ))}
                          {client.allowed_scopes.length > 4 && (
                            <Badge variant="secondary" className="text-xs">
                              +{client.allowed_scopes.length - 4} more
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <div
                      className="flex shrink-0 items-center gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => {
                          setEditClient(client)
                          setCreateOpen(true)
                        }}
                        aria-label={`Edit ${client.name}`}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => setRotateTarget(client)}
                        aria-label={`Rotate secret for ${client.name}`}
                      >
                        <RefreshCw className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive size-8"
                        onClick={() => setDeleteTarget(client)}
                        aria-label={`Delete ${client.name}`}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between border-t pt-4">
                    <p className="text-muted-foreground text-sm">
                      Page {page} of {totalPages} ({total} clients)
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                      >
                        <ChevronLeft className="mr-1 size-4" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page >= totalPages}
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      >
                        Next
                        <ChevronRight className="ml-1 size-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Security Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="size-4" />
              OAuth Client Security
            </CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground space-y-2 text-sm">
            <p>
              <strong>Keep secrets secure:</strong> Never expose client secrets in
              client-side code or public repositories. Use environment variables.
            </p>
            <p>
              <strong>Restrict redirect URIs:</strong> Only register exact redirect URIs
              your application uses. Avoid wildcards.
            </p>
            <p>
              <strong>Use minimal scopes:</strong> Request only the scopes your application
              needs to function.
            </p>
            <p>
              <strong>Rotate secrets regularly:</strong> Periodically rotate client secrets
              and use the grace period for zero-downtime updates.
            </p>
            <p>
              <strong>Prefer authorization code flow:</strong> Use the authorization code
              grant with PKCE for web and mobile applications. Avoid the implicit flow.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ---------- Dialogs ---------- */}

      {/* Create / Edit Dialog */}
      <CreateEditDialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open)
          if (!open) setEditClient(null)
        }}
        editClient={editClient}
        onSuccess={() => {
          setSuccess(editClient ? 'Client updated successfully.' : 'Client created successfully.')
          fetchClients()
        }}
      />

      {/* Detail Dialog */}
      {detailClient && (
        <ClientDetailDialog
          client={detailClient}
          open={!!detailClient}
          onOpenChange={(open) => {
            if (!open) setDetailClient(null)
          }}
          onRotate={() => {
            setRotateTarget(detailClient)
          }}
          onDelete={() => {
            setDeleteTarget(detailClient)
          }}
          onEdit={handleEditFromDetail}
        />
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Delete OAuth Client"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? All applications using this client will immediately lose access. This action cannot be undone.`}
        confirmLabel="Delete Client"
        destructive
        loading={actionLoading}
        onConfirm={handleDeleteConfirm}
      />

      {/* Rotate Secret Dialog (with grace period) */}
      <RotateSecretDialog
        open={!!rotateTarget}
        onOpenChange={(open) => {
          if (!open) setRotateTarget(null)
        }}
        clientName={rotateTarget?.name || ''}
        loading={actionLoading}
        onConfirm={handleRotateConfirm}
      />

      {/* Rotated Secret Result */}
      {rotateResult && (
        <RotateResultDialog
          open={!!rotateResult}
          onOpenChange={(open) => {
            if (!open) setRotateResult(null)
          }}
          result={rotateResult}
        />
      )}
    </div>
  )
}
