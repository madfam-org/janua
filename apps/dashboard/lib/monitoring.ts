/**
 * Frontend monitoring utilities for dashboard application
 */

interface MetricData {
  type: 'pageView' | 'apiCall' | 'error' | 'userAction'
  value?: number
  metadata?: Record<string, any>
}

class DashboardMonitoring {
  private baseUrl: string
  private isEnabled: boolean

  constructor() {
    this.baseUrl = '/api/metrics'
    this.isEnabled = process.env.NODE_ENV === 'production' || 
                     process.env.NEXT_PUBLIC_ENABLE_MONITORING === 'true'
  }

  /**
   * Track a metric event
   */
  async track(metric: MetricData): Promise<void> {
    if (!this.isEnabled) {
      if (process.env.NODE_ENV === 'development') {
        console.log('[Monitoring]', metric)
      }
      return
    }

    try {
      await fetch(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(metric)
      })
    } catch (error) {
      console.warn('[Monitoring] Failed to track metric:', error)
    }
  }

  /**
   * Track page view
   */
  trackPageView(page: string): void {
    this.track({
      type: 'pageView',
      metadata: { page }
    })
  }

  /**
   * Track API call
   */
  trackApiCall(endpoint: string, method: string, status?: number): void {
    this.track({
      type: 'apiCall',
      metadata: { endpoint, method, status }
    })
  }

  /**
   * Track error
   */
  trackError(error: Error | string, context?: Record<string, any>): void {
    const errorMessage = error instanceof Error ? error.message : error
    const errorStack = error instanceof Error ? error.stack : undefined
    
    this.track({
      type: 'error',
      metadata: { 
        message: errorMessage,
        stack: errorStack,
        ...context 
      }
    })
  }

  /**
   * Track user action
   */
  trackUserAction(action: string, category?: string): void {
    this.track({
      type: 'userAction',
      metadata: { action, category }
    })
  }

  /**
   * Get current metrics (for debugging)
   */
  async getMetrics(): Promise<any> {
    try {
      const response = await fetch(this.baseUrl)
      return await response.text()
    } catch (error) {
      console.warn('[Monitoring] Failed to get metrics:', error)
      return null
    }
  }
}

// Export singleton instance
export const monitoring = new DashboardMonitoring()

// React hook for easy usage in components
export function useMonitoring() {
  return {
    trackPageView: monitoring.trackPageView.bind(monitoring),
    trackApiCall: monitoring.trackApiCall.bind(monitoring),
    trackError: monitoring.trackError.bind(monitoring),
    trackUserAction: monitoring.trackUserAction.bind(monitoring)
  }
}

// Error boundary integration
export function trackErrorBoundary(error: Error, errorInfo: any) {
  monitoring.trackError(error, {
    component: 'ErrorBoundary',
    errorInfo: errorInfo?.componentStack
  })
}

// Automatic page view tracking for Next.js
export function setupPageViewTracking() {
  if (typeof window === 'undefined') return

  // Track initial page load
  monitoring.trackPageView(window.location.pathname)

  // Track navigation (if using Next.js router)
  const handleRouteChange = (url: string) => {
    monitoring.trackPageView(url)
  }

  // Listen for navigation events
  window.addEventListener('popstate', () => {
    monitoring.trackPageView(window.location.pathname)
  })

  return handleRouteChange
}