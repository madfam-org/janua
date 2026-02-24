'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Button,
  Input,
  Label,
  Checkbox,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@janua/ui'
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Copy,
  Eye,
  EyeOff,
  Check,
} from 'lucide-react'
import { apiCall } from '../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface WebhookEndpoint {
  id: string
  url: string
  secret: string
  events: string[]
  is_active: boolean
  description: string | null
  headers: Record<string, string> | null
  created_at: string
  updated_at: string
}

interface WebhookFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  webhook?: WebhookEndpoint
  onSuccess: () => void
}

function generateSecret(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return 'whsec_' + Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('')
}

export function WebhookForm({ open, onOpenChange, webhook, onSuccess }: WebhookFormProps) {
  const isEditMode = !!webhook

  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])
  const [secret, setSecret] = useState('')
  const [active, setActive] = useState(true)
  const [showSecret, setShowSecret] = useState(false)
  const [secretCopied, setSecretCopied] = useState(false)

  const [availableEventTypes, setAvailableEventTypes] = useState<string[]>([])
  const [loadingEventTypes, setLoadingEventTypes] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [regeneratingSecret, setRegeneratingSecret] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const resetForm = useCallback(() => {
    if (webhook) {
      setUrl(webhook.url)
      setDescription(webhook.description || '')
      setSelectedEvents([...webhook.events])
      setSecret(webhook.secret)
      setActive(webhook.is_active)
    } else {
      setUrl('')
      setDescription('')
      setSelectedEvents([])
      setSecret(generateSecret())
      setActive(true)
    }
    setShowSecret(false)
    setSecretCopied(false)
    setError(null)
    setFieldErrors({})
  }, [webhook])

  useEffect(() => {
    if (open) {
      resetForm()
      fetchEventTypes()
    }
  }, [open, resetForm])

  const fetchEventTypes = async () => {
    setLoadingEventTypes(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/events/types`)
      if (response.ok) {
        const types = await response.json()
        setAvailableEventTypes(types)
      }
    } catch (err) {
      console.error('Failed to fetch event types:', err)
    } finally {
      setLoadingEventTypes(false)
    }
  }

  const toggleEvent = (eventType: string) => {
    setSelectedEvents((prev) =>
      prev.includes(eventType)
        ? prev.filter((e) => e !== eventType)
        : [...prev, eventType]
    )
    if (fieldErrors.events) {
      setFieldErrors((prev) => {
        const next = { ...prev }
        delete next.events
        return next
      })
    }
  }

  const selectAllEvents = () => {
    setSelectedEvents([...availableEventTypes])
    if (fieldErrors.events) {
      setFieldErrors((prev) => {
        const next = { ...prev }
        delete next.events
        return next
      })
    }
  }

  const clearAllEvents = () => {
    setSelectedEvents([])
  }

  const copySecret = async () => {
    try {
      await navigator.clipboard.writeText(secret)
      setSecretCopied(true)
      setTimeout(() => setSecretCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy secret:', err)
    }
  }

  const regenerateSecret = async () => {
    if (!webhook) return

    setRegeneratingSecret(true)
    setError(null)
    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/webhooks/${webhook.id}/regenerate-secret`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail || 'Failed to regenerate secret')
      }

      const data = await response.json()
      setSecret(data.secret || data.new_secret || generateSecret())
      setShowSecret(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate secret')
    } finally {
      setRegeneratingSecret(false)
    }
  }

  const validate = (): boolean => {
    const errors: Record<string, string> = {}

    if (!url.trim()) {
      errors.url = 'URL is required'
    } else {
      try {
        const parsed = new URL(url.trim())
        if (!['http:', 'https:'].includes(parsed.protocol)) {
          errors.url = 'URL must use http or https protocol'
        }
      } catch {
        errors.url = 'Please enter a valid URL'
      }
    }

    if (selectedEvents.length === 0) {
      errors.events = 'Select at least one event type'
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    setSubmitting(true)
    setError(null)

    const body = {
      url: url.trim(),
      description: description.trim() || null,
      events: selectedEvents,
      secret,
      active,
    }

    try {
      let response: Response

      if (isEditMode && webhook) {
        response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/${webhook.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        })
      } else {
        response = await apiCall(`${API_BASE_URL}/api/v1/webhooks`, {
          method: 'POST',
          body: JSON.stringify(body),
        })
      }

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail || `Failed to ${isEditMode ? 'update' : 'create'} webhook`)
      }

      onSuccess()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${isEditMode ? 'update' : 'create'} webhook`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>{isEditMode ? 'Edit Webhook' : 'Create Webhook'}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? 'Update the webhook endpoint configuration.'
              : 'Configure a new webhook endpoint to receive event notifications.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          {error && (
            <div
              className="bg-destructive/10 text-destructive flex items-start gap-2 rounded-md p-3 text-sm"
              role="alert"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* URL Field */}
          <div className="space-y-2">
            <Label htmlFor="webhook-url">
              Endpoint URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="webhook-url"
              type="url"
              placeholder="https://example.com/webhooks"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                if (fieldErrors.url) {
                  setFieldErrors((prev) => {
                    const next = { ...prev }
                    delete next.url
                    return next
                  })
                }
              }}
              aria-invalid={!!fieldErrors.url}
              aria-describedby={fieldErrors.url ? 'webhook-url-error' : undefined}
              autoFocus
            />
            {fieldErrors.url && (
              <p id="webhook-url-error" className="text-destructive text-sm">
                {fieldErrors.url}
              </p>
            )}
          </div>

          {/* Description Field */}
          <div className="space-y-2">
            <Label htmlFor="webhook-description">Description</Label>
            <Input
              id="webhook-description"
              type="text"
              placeholder="Optional description for this endpoint"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Event Types */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium leading-none">
              Event Types <span className="text-destructive">*</span>
            </legend>
            {loadingEventTypes ? (
              <div className="flex items-center gap-2 py-4">
                <Loader2 className="text-muted-foreground size-4 animate-spin" />
                <span className="text-muted-foreground text-sm">Loading event types...</span>
              </div>
            ) : availableEventTypes.length === 0 ? (
              <p className="text-muted-foreground py-2 text-sm">
                No event types available.
              </p>
            ) : (
              <>
                <div className="flex items-center gap-2 pb-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={selectAllEvents}
                    className="h-7 text-xs"
                  >
                    Select All
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={clearAllEvents}
                    className="h-7 text-xs"
                  >
                    Clear All
                  </Button>
                  <span className="text-muted-foreground ml-auto text-xs">
                    {selectedEvents.length} of {availableEventTypes.length} selected
                  </span>
                </div>
                <div
                  className="grid max-h-48 grid-cols-1 gap-2 overflow-y-auto rounded-md border p-3 sm:grid-cols-2"
                  role="group"
                  aria-label="Webhook event types"
                >
                  {availableEventTypes.map((eventType) => (
                    <label
                      key={eventType}
                      className="hover:bg-muted/50 flex cursor-pointer items-center gap-2 rounded px-2 py-1.5"
                    >
                      <Checkbox
                        checked={selectedEvents.includes(eventType)}
                        onCheckedChange={() => toggleEvent(eventType)}
                        aria-label={eventType}
                      />
                      <span className="text-sm">{eventType}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
            {fieldErrors.events && (
              <p className="text-destructive text-sm" role="alert">
                {fieldErrors.events}
              </p>
            )}
          </fieldset>

          {/* Secret */}
          <div className="space-y-2">
            <Label htmlFor="webhook-secret">Signing Secret</Label>
            <div className="flex items-center gap-2">
              <div className="bg-muted relative flex-1 overflow-hidden rounded-md border">
                <code className="block truncate px-3 py-2 font-mono text-sm">
                  {showSecret ? secret : '\u2022'.repeat(24)}
                </code>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowSecret(!showSecret)}
                aria-label={showSecret ? 'Hide secret' : 'Show secret'}
              >
                {showSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={copySecret}
                aria-label="Copy secret to clipboard"
              >
                {secretCopied ? (
                  <Check className="size-4 text-green-600" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
              {isEditMode && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={regenerateSecret}
                  disabled={regeneratingSecret}
                  aria-label="Regenerate signing secret"
                >
                  {regeneratingSecret ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw className="size-4" />
                  )}
                </Button>
              )}
            </div>
            <p className="text-muted-foreground text-xs">
              {isEditMode
                ? 'Use this secret to verify webhook signatures. Regenerating will invalidate the current secret.'
                : 'Save this secret securely. It will be used to sign webhook payloads for verification.'}
            </p>
          </div>

          {/* Active Toggle */}
          <label className="hover:bg-muted/50 flex cursor-pointer items-center gap-3 rounded-md border p-3">
            <Checkbox
              checked={active}
              onCheckedChange={(checked) => setActive(checked === true)}
              aria-label="Enable webhook"
            />
            <div>
              <div className="text-sm font-medium">Active</div>
              <div className="text-muted-foreground text-xs">
                {active
                  ? 'This webhook will receive event notifications.'
                  : 'This webhook is paused and will not receive events.'}
              </div>
            </div>
          </label>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
              {isEditMode ? 'Save Changes' : 'Create Webhook'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
