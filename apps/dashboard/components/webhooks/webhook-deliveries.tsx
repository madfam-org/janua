'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Button,
  Badge,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@janua/ui'
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { januaClient } from '@/lib/janua-client'

interface WebhookDelivery {
  id: string
  event_type: string
  status: 'success' | 'failed' | 'pending'
  response_code: number | null
  response_time_ms: number | null
  error_message: string | null
  created_at: string
  next_retry_at: string | null
  attempt_number: number
}

interface DeliveriesResponse {
  deliveries: WebhookDelivery[]
  total: number
  page: number
  page_size: number
}

interface WebhookDeliveriesProps {
  endpointId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function WebhookDeliveries({ endpointId, open, onOpenChange }: WebhookDeliveriesProps) {
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState<string | null>(null)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const pageSize = 15
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const fetchDeliveries = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await januaClient.webhooks.listDeliveries(endpointId, {
        limit: pageSize,
        offset: (page - 1) * pageSize,
      }) as unknown as DeliveriesResponse
      setDeliveries(data.deliveries || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('Failed to fetch deliveries:', err)
      setError(err instanceof Error ? err.message : 'Failed to load delivery history')
    } finally {
      setLoading(false)
    }
  }, [endpointId, page])

  useEffect(() => {
    if (open && endpointId) {
      setPage(1)
    }
  }, [open, endpointId])

  useEffect(() => {
    if (open && endpointId) {
      fetchDeliveries()
    }
  }, [open, endpointId, fetchDeliveries])

  const retryDelivery = async (deliveryId: string) => {
    setRetrying(deliveryId)
    try {
      await januaClient.http.post(
        `/api/v1/webhooks/${endpointId}/deliveries/${deliveryId}/retry`
      )

      await fetchDeliveries()
    } catch (err) {
      console.error('Failed to retry delivery:', err)
      setError(err instanceof Error ? err.message : 'Failed to retry delivery')
    } finally {
      setRetrying(null)
    }
  }

  const formatDateTime = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const formatResponseTime = (ms: number | null): string => {
    if (ms === null) return '-'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
      case 'failed':
        return <XCircle className="size-4 text-red-600 dark:text-red-400" />
      default:
        return <Clock className="text-muted-foreground size-4" />
    }
  }

  const getStatusBadgeVariant = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (status) {
      case 'success':
        return 'default'
      case 'failed':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  const getResponseCodeColor = (code: number | null): string => {
    if (code === null) return 'text-muted-foreground'
    if (code >= 200 && code < 300) return 'text-green-600 dark:text-green-400'
    if (code >= 400 && code < 500) return 'text-yellow-600 dark:text-yellow-400'
    if (code >= 500) return 'text-red-600 dark:text-red-400'
    return 'text-muted-foreground'
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[800px]">
        <DialogHeader>
          <DialogTitle>Delivery History</DialogTitle>
          <DialogDescription>
            Recent webhook delivery attempts and their status.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Toolbar */}
          <div className="flex items-center justify-between">
            <div className="text-muted-foreground text-sm">
              {total} {total === 1 ? 'delivery' : 'deliveries'} total
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDeliveries}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              Refresh
            </Button>
          </div>

          {/* Error */}
          {error && (
            <div
              className="bg-destructive/10 text-destructive flex items-start gap-2 rounded-md p-3 text-sm"
              role="alert"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Loading */}
          {loading && deliveries.length === 0 && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="text-muted-foreground size-8 animate-spin" />
              <span className="text-muted-foreground ml-2">Loading deliveries...</span>
            </div>
          )}

          {/* Empty State */}
          {!loading && deliveries.length === 0 && !error && (
            <div className="text-muted-foreground py-12 text-center text-sm">
              No deliveries recorded for this endpoint yet.
            </div>
          )}

          {/* Deliveries Table */}
          {deliveries.length > 0 && (
            <div className="rounded-md border">
              <table className="w-full">
                <thead>
                  <tr className="bg-muted/50 border-b">
                    <th className="p-3 text-left text-xs font-medium">Event Type</th>
                    <th className="p-3 text-left text-xs font-medium">Status</th>
                    <th className="p-3 text-left text-xs font-medium">Response</th>
                    <th className="p-3 text-left text-xs font-medium">Duration</th>
                    <th className="p-3 text-left text-xs font-medium">Timestamp</th>
                    <th className="p-3 text-right text-xs font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((delivery) => (
                    <>
                      <tr
                        key={delivery.id}
                        className="hover:bg-muted/50 cursor-pointer border-b"
                        onClick={() =>
                          setExpandedRow(
                            expandedRow === delivery.id ? null : delivery.id
                          )
                        }
                        role="button"
                        tabIndex={0}
                        aria-expanded={expandedRow === delivery.id}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setExpandedRow(
                              expandedRow === delivery.id ? null : delivery.id
                            )
                          }
                        }}
                      >
                        <td className="p-3">
                          <span className="bg-primary/10 text-primary rounded px-2 py-0.5 text-xs font-medium">
                            {delivery.event_type}
                          </span>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1.5">
                            {getStatusIcon(delivery.status)}
                            <Badge variant={getStatusBadgeVariant(delivery.status)}>
                              {delivery.status}
                            </Badge>
                          </div>
                        </td>
                        <td className="p-3">
                          <span
                            className={`font-mono text-sm ${getResponseCodeColor(
                              delivery.response_code
                            )}`}
                          >
                            {delivery.response_code ?? '-'}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="text-muted-foreground text-sm">
                            {formatResponseTime(delivery.response_time_ms)}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="text-muted-foreground text-sm">
                            {formatDateTime(delivery.created_at)}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          {delivery.status === 'failed' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation()
                                retryDelivery(delivery.id)
                              }}
                              disabled={retrying === delivery.id}
                              title="Retry delivery"
                              aria-label={`Retry delivery for ${delivery.event_type}`}
                            >
                              {retrying === delivery.id ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <RotateCcw className="size-4" />
                              )}
                            </Button>
                          )}
                        </td>
                      </tr>
                      {expandedRow === delivery.id && (
                        <tr key={`${delivery.id}-detail`} className="bg-muted/30 border-b">
                          <td colSpan={6} className="px-6 py-3">
                            <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-3">
                              <div>
                                <dt className="text-muted-foreground text-xs font-medium">
                                  Delivery ID
                                </dt>
                                <dd className="truncate font-mono text-xs">
                                  {delivery.id}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-muted-foreground text-xs font-medium">
                                  Attempt
                                </dt>
                                <dd className="text-xs">
                                  #{delivery.attempt_number}
                                </dd>
                              </div>
                              {delivery.next_retry_at && (
                                <div>
                                  <dt className="text-muted-foreground text-xs font-medium">
                                    Next Retry
                                  </dt>
                                  <dd className="text-xs">
                                    {formatDateTime(delivery.next_retry_at)}
                                  </dd>
                                </div>
                              )}
                              {delivery.error_message && (
                                <div className="col-span-full">
                                  <dt className="text-muted-foreground text-xs font-medium">
                                    Error
                                  </dt>
                                  <dd className="mt-1 rounded border bg-red-500/5 px-2 py-1 font-mono text-xs text-red-600 dark:text-red-400">
                                    {delivery.error_message}
                                  </dd>
                                </div>
                              )}
                            </dl>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-muted-foreground text-sm">
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || loading}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="mr-1 size-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || loading}
                  aria-label="Next page"
                >
                  Next
                  <ChevronRight className="ml-1 size-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
