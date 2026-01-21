'use client'

interface ServiceStatusProps {
  name: string
  status: string
}

export function ServiceStatus({ name, status }: ServiceStatusProps) {
  const isHealthy = status === 'healthy' || status === 'connected' || status === 'production'
  const statusColor = isHealthy
    ? 'bg-green-500/10 text-green-600 dark:text-green-400'
    : status === 'degraded'
    ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
    : 'bg-muted text-muted-foreground'

  return (
    <div className="bg-muted flex items-center justify-between rounded-lg p-3">
      <div className="text-foreground text-sm font-medium">{name}</div>
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusColor}`}>
        {status}
      </span>
    </div>
  )
}
