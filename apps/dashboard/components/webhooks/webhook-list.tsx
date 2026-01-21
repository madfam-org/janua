'use client'

import { useState, useEffect } from 'react'
import { Button } from '@janua/ui'
import {
  Plus,
  Search,
  Loader2,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  MoreHorizontal,
  Send,
  Trash2,
  Copy,
  Eye,
  EyeOff
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

interface WebhookStats {
  total_deliveries: number
  successful: number
  failed: number
  success_rate: number
  average_delivery_time: number
  period_days: number
}

export function WebhookList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({})
  const [eventTypes, setEventTypes] = useState<string[]>([])

  useEffect(() => {
    fetchWebhooks()
    fetchEventTypes()
  }, [])

  const fetchWebhooks = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/`)

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication required')
        }
        throw new Error('Failed to fetch webhooks')
      }

      const data = await response.json()
      setWebhooks(data.endpoints || [])
    } catch (err) {
      console.error('Failed to fetch webhooks:', err)
      setError(err instanceof Error ? err.message : 'Failed to load webhooks')
    } finally {
      setLoading(false)
    }
  }

  const fetchEventTypes = async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/events/types`)
      if (response.ok) {
        const types = await response.json()
        setEventTypes(types)
      }
    } catch (err) {
      console.error('Failed to fetch event types:', err)
    }
  }

  const testWebhook = async (id: string) => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/${id}/test`, {
        method: 'POST'
      })

      if (response.ok) {
        alert('Test webhook sent successfully!')
      } else {
        alert('Failed to send test webhook')
      }
    } catch (err) {
      console.error('Failed to test webhook:', err)
      alert('Failed to send test webhook')
    }
  }

  const deleteWebhook = async (id: string) => {
    if (!confirm('Are you sure you want to delete this webhook?')) return

    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/webhooks/${id}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        setWebhooks(webhooks.filter(w => w.id !== id))
      } else {
        alert('Failed to delete webhook')
      }
    } catch (err) {
      console.error('Failed to delete webhook:', err)
      alert('Failed to delete webhook')
    }
  }

  const copySecret = async (secret: string) => {
    try {
      await navigator.clipboard.writeText(secret)
      alert('Secret copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy secret:', err)
    }
  }

  const toggleSecretVisibility = (id: string) => {
    setShowSecret(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const formatDateTime = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const filteredWebhooks = webhooks.filter(webhook =>
    webhook.url.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (webhook.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground size-8 animate-spin" />
        <span className="text-muted-foreground ml-2">Loading webhooks...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="text-destructive mb-4 size-12" />
        <h3 className="mb-2 text-lg font-semibold">Failed to Load Webhooks</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchWebhooks} variant="outline">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Stats Banner */}
      <div className="bg-muted/50 grid grid-cols-3 gap-4 rounded-lg p-4">
        <div>
          <div className="text-2xl font-bold">{webhooks.length}</div>
          <div className="text-muted-foreground text-sm">Total Endpoints</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            {webhooks.filter(w => w.is_active).length}
          </div>
          <div className="text-muted-foreground text-sm">Active</div>
        </div>
        <div>
          <div className="text-2xl font-bold">{eventTypes.length}</div>
          <div className="text-muted-foreground text-sm">Event Types</div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="text-muted-foreground absolute left-2 top-2.5 size-4" />
          <input
            placeholder="Search webhooks by URL or description..."
            className="focus:ring-primary w-full rounded-md border py-2 pl-8 pr-4 focus:outline-none focus:ring-2"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={fetchWebhooks}>
            <RefreshCw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button size="sm" disabled title="Create webhook endpoint">
            <Plus className="mr-2 size-4" />
            Add Webhook
          </Button>
        </div>
      </div>

      {/* Webhook Table */}
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/50 border-b">
              <th className="p-4 text-left text-sm font-medium">Endpoint</th>
              <th className="p-4 text-left text-sm font-medium">Events</th>
              <th className="p-4 text-left text-sm font-medium">Secret</th>
              <th className="p-4 text-left text-sm font-medium">Status</th>
              <th className="p-4 text-left text-sm font-medium">Created</th>
              <th className="p-4 text-left text-sm font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredWebhooks.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground p-8 text-center">
                  {searchTerm ? 'No webhooks match your search' : 'No webhooks configured yet'}
                </td>
              </tr>
            ) : (
              filteredWebhooks.map((webhook) => (
                <tr key={webhook.id} className="hover:bg-muted/50 border-b">
                  <td className="p-4">
                    <div>
                      <div className="max-w-[250px] truncate font-mono text-sm" title={webhook.url}>
                        {webhook.url}
                      </div>
                      {webhook.description && (
                        <div className="text-muted-foreground text-xs">{webhook.description}</div>
                      )}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex flex-wrap gap-1">
                      {webhook.events.slice(0, 2).map(event => (
                        <span
                          key={event}
                          className="bg-primary/10 text-primary rounded px-2 py-0.5 text-xs"
                        >
                          {event}
                        </span>
                      ))}
                      {webhook.events.length > 2 && (
                        <span className="bg-muted text-muted-foreground rounded px-2 py-0.5 text-xs">
                          +{webhook.events.length - 2} more
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <code className="bg-muted rounded px-2 py-1 font-mono text-xs">
                        {showSecret[webhook.id]
                          ? webhook.secret.slice(0, 16) + '...'
                          : '••••••••••••'}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleSecretVisibility(webhook.id)}
                        title={showSecret[webhook.id] ? 'Hide secret' : 'Show secret'}
                      >
                        {showSecret[webhook.id] ? (
                          <EyeOff className="size-3" />
                        ) : (
                          <Eye className="size-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copySecret(webhook.secret)}
                        title="Copy secret"
                      >
                        <Copy className="size-3" />
                      </Button>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                      webhook.is_active
                        ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                        : 'bg-muted text-muted-foreground'
                    }`}>
                      {webhook.is_active ? (
                        <><CheckCircle2 className="mr-1 size-3" /> Active</>
                      ) : (
                        <><XCircle className="mr-1 size-3" /> Inactive</>
                      )}
                    </span>
                  </td>
                  <td className="text-muted-foreground p-4 text-sm">
                    {formatDateTime(webhook.created_at)}
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => testWebhook(webhook.id)}
                        title="Send test webhook"
                      >
                        <Send className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteWebhook(webhook.id)}
                        title="Delete webhook"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Available Event Types */}
      {eventTypes.length > 0 && (
        <div className="bg-muted/30 rounded-lg p-4">
          <h4 className="mb-2 text-sm font-medium">Available Event Types</h4>
          <div className="flex flex-wrap gap-2">
            {eventTypes.map(type => (
              <span
                key={type}
                className="bg-background rounded border px-2 py-1 text-xs"
              >
                {type}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="text-muted-foreground flex items-center justify-between text-sm">
        <div>
          Showing {filteredWebhooks.length} of {webhooks.length} webhooks
        </div>
      </div>
    </div>
  )
}
