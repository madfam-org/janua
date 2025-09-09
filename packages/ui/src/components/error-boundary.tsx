'use client'

import React, { Component, ReactNode, ErrorInfo } from 'react'
import { AlertCircle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from './button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './card'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  resetKeys?: Array<string | number>
  resetOnPropsChange?: boolean
  isolate?: boolean
  level?: 'page' | 'layout' | 'component'
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorId: string
  showDetails: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: '',
      showDetails: false
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    return {
      hasError: true,
      error,
      errorId
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo)
    }

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // Store error info in state
    this.setState({
      errorInfo
    })

    // Report to error tracking service
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        extra: {
          errorInfo,
          errorBoundary: true,
          level: this.props.level || 'component',
          errorId: this.state.errorId
        }
      })
    }
  }

  componentDidUpdate(prevProps: Props) {
    const { resetKeys, resetOnPropsChange } = this.props
    const { hasError } = this.state
    
    if (hasError) {
      // Reset on prop changes if configured
      if (resetOnPropsChange && prevProps.children !== this.props.children) {
        this.resetErrorBoundary()
      }
      
      // Reset on specific key changes
      if (resetKeys?.some((key) => prevProps[key as keyof Props] !== this.props[key as keyof Props])) {
        this.resetErrorBoundary()
      }
    }
  }

  resetErrorBoundary = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: '',
      showDetails: false
    })
  }

  render() {
    const { hasError, error, errorInfo, errorId, showDetails } = this.state
    const { fallback, children, level = 'component' } = this.props

    if (hasError && error) {
      // Custom fallback provided
      if (fallback) {
        return <>{fallback}</>
      }

      // Default error UI based on level
      const isPageLevel = level === 'page' || level === 'layout'
      
      return (
        <div className={`min-h-${isPageLevel ? 'screen' : '[400px]'} flex items-center justify-center p-4`}>
          <Card className="w-full max-w-lg">
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <CardTitle>Something went wrong</CardTitle>
              </div>
              <CardDescription>
                {isPageLevel 
                  ? "We're sorry, but this page encountered an error."
                  : "This component encountered an unexpected error."}
              </CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-4">
              <div className="rounded-lg bg-muted p-3 text-sm">
                <p className="font-mono text-muted-foreground">
                  {error.message || 'An unexpected error occurred'}
                </p>
              </div>
              
              {process.env.NODE_ENV === 'development' && (
                <div className="space-y-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => this.setState({ showDetails: !showDetails })}
                    className="w-full justify-between"
                  >
                    <span>Error Details</span>
                    {showDetails ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </Button>
                  
                  {showDetails && errorInfo && (
                    <div className="rounded-lg bg-muted p-3 max-h-64 overflow-auto">
                      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                        {errorInfo.componentStack}
                      </pre>
                    </div>
                  )}
                </div>
              )}
              
              <div className="text-xs text-muted-foreground">
                Error ID: <code className="font-mono">{errorId}</code>
              </div>
            </CardContent>
            
            <CardFooter className="flex gap-2">
              <Button
                onClick={this.resetErrorBoundary}
                className="flex-1"
                variant="default"
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
              
              {isPageLevel && (
                <Button
                  onClick={() => window.location.href = '/'}
                  variant="outline"
                  className="flex-1"
                >
                  <Home className="mr-2 h-4 w-4" />
                  Go Home
                </Button>
              )}
            </CardFooter>
          </Card>
        </div>
      )
    }

    return children
  }
}

// Declarative API using hooks
export function useErrorHandler() {
  return (error: Error, errorInfo?: ErrorInfo) => {
    if (process.env.NODE_ENV === 'development') {
      console.error('Error caught by useErrorHandler:', error, errorInfo)
    }
    
    // Report to Sentry if available
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        extra: { errorInfo, source: 'useErrorHandler' }
      })
    }
  }
}

// HOC for wrapping components with error boundary
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  )
  
  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`
  
  return WrappedComponent
}

// Type augmentation for Sentry
declare global {
  interface Window {
    Sentry?: {
      captureException: (error: Error, context?: any) => void
      captureMessage: (message: string, level?: string) => void
    }
  }
}