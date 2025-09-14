/**
 * Frontend monitoring utilities for admin application
 */

interface MetricData {
  type: 'adminAction' | 'userOperation' | 'configChange' | 'error'
  value?: number
  metadata?: Record<string, any>
}

class AdminMonitoring {
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
        console.log('[Admin Monitoring]', metric)
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
      console.warn('[Admin Monitoring] Failed to track metric:', error)
    }
  }

  /**
   * Track admin action
   */
  trackAdminAction(action: string, resource?: string, userId?: string): void {
    this.track({
      type: 'adminAction',
      metadata: { action, resource, userId, timestamp: Date.now() }
    })
  }

  /**
   * Track user operation (performed by admin on user)
   */
  trackUserOperation(operation: string, targetUserId: string, adminUserId?: string): void {
    this.track({
      type: 'userOperation',
      metadata: { operation, targetUserId, adminUserId, timestamp: Date.now() }
    })
  }

  /**
   * Track configuration change
   */
  trackConfigChange(setting: string, oldValue?: any, newValue?: any, adminUserId?: string): void {
    this.track({
      type: 'configChange',
      metadata: { 
        setting, 
        oldValue: oldValue !== undefined ? String(oldValue) : undefined,
        newValue: newValue !== undefined ? String(newValue) : undefined,
        adminUserId,
        timestamp: Date.now()
      }
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
        timestamp: Date.now(),
        ...context 
      }
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
      console.warn('[Admin Monitoring] Failed to get metrics:', error)
      return null
    }
  }
}

// Export singleton instance
export const adminMonitoring = new AdminMonitoring()

// React hook for easy usage in components
export function useAdminMonitoring() {
  return {
    trackAdminAction: adminMonitoring.trackAdminAction.bind(adminMonitoring),
    trackUserOperation: adminMonitoring.trackUserOperation.bind(adminMonitoring),
    trackConfigChange: adminMonitoring.trackConfigChange.bind(adminMonitoring),
    trackError: adminMonitoring.trackError.bind(adminMonitoring)
  }
}

// Error boundary integration
export function trackErrorBoundary(error: Error, errorInfo: any) {
  adminMonitoring.trackError(error, {
    component: 'ErrorBoundary',
    errorInfo: errorInfo?.componentStack
  })
}

// Security-focused tracking for admin operations
export function trackSecurityEvent(eventType: string, severity: 'low' | 'medium' | 'high', details: Record<string, any>) {
  adminMonitoring.trackAdminAction(`security_${eventType}`, 'security', undefined)
  
  // Also track as error if high severity
  if (severity === 'high') {
    adminMonitoring.trackError(`Security event: ${eventType}`, {
      severity,
      securityEvent: true,
      ...details
    })
  }
}