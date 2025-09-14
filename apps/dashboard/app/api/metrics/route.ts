import { NextRequest, NextResponse } from 'next/server'

// Simple metrics collection for frontend applications
const metrics = {
  pageViews: 0,
  apiCalls: 0,
  errors: 0,
  sessionDuration: 0,
  lastReset: Date.now()
}

export async function GET(request: NextRequest) {
  const now = Date.now()
  const uptime = now - metrics.lastReset

  // Basic Prometheus format metrics
  const prometheusMetrics = `
# HELP plinto_dashboard_page_views_total Total page views
# TYPE plinto_dashboard_page_views_total counter
plinto_dashboard_page_views_total ${metrics.pageViews}

# HELP plinto_dashboard_api_calls_total Total API calls
# TYPE plinto_dashboard_api_calls_total counter
plinto_dashboard_api_calls_total ${metrics.apiCalls}

# HELP plinto_dashboard_errors_total Total client errors
# TYPE plinto_dashboard_errors_total counter
plinto_dashboard_errors_total ${metrics.errors}

# HELP plinto_dashboard_uptime_seconds Application uptime in seconds
# TYPE plinto_dashboard_uptime_seconds gauge
plinto_dashboard_uptime_seconds ${Math.floor(uptime / 1000)}

# HELP plinto_dashboard_build_info Build information
# TYPE plinto_dashboard_build_info gauge
plinto_dashboard_build_info{version="1.0.0",environment="${process.env.NODE_ENV || 'development'}"} 1

# HELP plinto_dashboard_memory_usage_bytes Memory usage in bytes
# TYPE plinto_dashboard_memory_usage_bytes gauge
plinto_dashboard_memory_usage_bytes ${process.memoryUsage().rss}
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
      case 'pageView':
        metrics.pageViews += value
        break
      case 'apiCall':
        metrics.apiCalls += value
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