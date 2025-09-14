import { NextRequest, NextResponse } from 'next/server'

// Simple metrics collection for admin application
const metrics = {
  adminActions: 0,
  userOperations: 0,
  configChanges: 0,
  errors: 0,
  lastReset: Date.now()
}

export async function GET(request: NextRequest) {
  const now = Date.now()
  const uptime = now - metrics.lastReset

  // Basic Prometheus format metrics
  const prometheusMetrics = `
# HELP plinto_admin_actions_total Total admin actions performed
# TYPE plinto_admin_actions_total counter
plinto_admin_actions_total ${metrics.adminActions}

# HELP plinto_admin_user_operations_total Total user operations
# TYPE plinto_admin_user_operations_total counter
plinto_admin_user_operations_total ${metrics.userOperations}

# HELP plinto_admin_config_changes_total Total configuration changes
# TYPE plinto_admin_config_changes_total counter
plinto_admin_config_changes_total ${metrics.configChanges}

# HELP plinto_admin_errors_total Total admin interface errors
# TYPE plinto_admin_errors_total counter
plinto_admin_errors_total ${metrics.errors}

# HELP plinto_admin_uptime_seconds Application uptime in seconds
# TYPE plinto_admin_uptime_seconds gauge
plinto_admin_uptime_seconds ${Math.floor(uptime / 1000)}

# HELP plinto_admin_build_info Build information
# TYPE plinto_admin_build_info gauge
plinto_admin_build_info{version="1.0.0",environment="${process.env.NODE_ENV || 'development'}"} 1

# HELP plinto_admin_memory_usage_bytes Memory usage in bytes
# TYPE plinto_admin_memory_usage_bytes gauge
plinto_admin_memory_usage_bytes ${process.memoryUsage().rss}
`.trim()

  return new NextResponse(prometheusMetrics, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8'
    }
  })
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { type, value = 1 } = body

    switch (type) {
      case 'adminAction':
        metrics.adminActions += value
        break
      case 'userOperation':
        metrics.userOperations += value
        break
      case 'configChange':
        metrics.configChanges += value
        break
      case 'error':
        metrics.errors += value
        break
      default:
        return NextResponse.json({ error: 'Invalid metric type' }, { status: 400 })
    }

    return NextResponse.json({ success: true, metrics })
  } catch (error) {
    metrics.errors += 1
    return NextResponse.json({ error: 'Failed to record metric' }, { status: 500 })
  }
}