'use client'

/**
 * Global Error Context for Admin Panel
 *
 * Provides application-wide error state management with:
 * - Centralized error collection and display
 * - Error severity levels
 * - Auto-dismiss functionality
 * - Error tracking/reporting integration
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
  useMemo,
} from 'react'

// Error severity levels
export type ErrorSeverity = 'error' | 'warning' | 'info' | 'success'

// Error state interface
export interface AppError {
  id: string
  message: string
  code?: string
  severity: ErrorSeverity
  dismissible: boolean
  timestamp: number
  details?: Record<string, unknown>
  action?: {
    label: string
    onClick: () => void
  }
}

// Error context interface
interface ErrorContextType {
  // Current errors
  errors: AppError[]
  // Most recent error (for simple use cases)
  latestError: AppError | null
  // Add a new error
  addError: (error: Omit<AppError, 'id' | 'timestamp'>) => string
  // Remove an error by ID
  removeError: (id: string) => void
  // Clear all errors
  clearErrors: () => void
  // Clear errors by severity
  clearErrorsBySeverity: (severity: ErrorSeverity) => void
  // Shorthand methods
  showError: (message: string, options?: Partial<AppError>) => string
  showWarning: (message: string, options?: Partial<AppError>) => string
  showInfo: (message: string, options?: Partial<AppError>) => string
  showSuccess: (message: string, options?: Partial<AppError>) => string
}

const ErrorContext = createContext<ErrorContextType | undefined>(undefined)

// Generate unique ID for errors
function generateErrorId(): string {
  return `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// Map API error codes to user-friendly messages
const ERROR_MESSAGES: Record<string, string> = {
  AUTHENTICATION_ERROR: 'Invalid credentials. Please try again.',
  TOKEN_ERROR: 'Your session is invalid. Please sign in again.',
  EMAIL_NOT_VERIFIED: 'Please verify your email address to continue.',
  MFA_REQUIRED: 'Please complete two-factor authentication.',
  PASSWORD_EXPIRED: 'Your password has expired. Please reset it.',
  ACCOUNT_LOCKED: 'Your account is temporarily locked. Please try again later.',
  SESSION_EXPIRED: 'Your session has expired. Please sign in again.',
  AUTHORIZATION_ERROR: "You don't have permission to perform this action.",
  INSUFFICIENT_PERMISSIONS: 'You need additional permissions for this action.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  NOT_FOUND_ERROR: 'The requested resource was not found.',
  CONFLICT_ERROR: 'This action conflicts with existing data.',
  RATE_LIMIT_ERROR: 'Too many requests. Please wait a moment and try again.',
  INTERNAL_ERROR: 'An unexpected error occurred. Please try again later.',
  NETWORK_ERROR: 'Unable to connect. Please check your internet connection.',
}

// Get user-friendly message from error code
export function getUserMessage(code?: string): string | undefined {
  if (!code) return undefined
  return ERROR_MESSAGES[code]
}

// Auto-dismiss timeouts by severity (in milliseconds)
const AUTO_DISMISS_TIMEOUT: Record<ErrorSeverity, number | null> = {
  error: null, // Don't auto-dismiss errors
  warning: 10000, // 10 seconds
  info: 5000, // 5 seconds
  success: 3000, // 3 seconds
}

interface ErrorProviderProps {
  children: ReactNode
  maxErrors?: number // Maximum number of errors to keep in state
  onError?: (error: AppError) => void // Callback for error tracking
}

export function ErrorProvider({
  children,
  maxErrors = 10,
  onError,
}: ErrorProviderProps) {
  const [errors, setErrors] = useState<AppError[]>([])

  // Add a new error
  const addError = useCallback(
    (errorInput: Omit<AppError, 'id' | 'timestamp'>): string => {
      const id = generateErrorId()
      const error: AppError = {
        ...errorInput,
        id,
        timestamp: Date.now(),
      }

      setErrors((prev) => {
        // Keep only maxErrors, removing oldest first
        const newErrors = [error, ...prev].slice(0, maxErrors)
        return newErrors
      })

      // Call error tracking callback if provided
      if (onError) {
        onError(error)
      }

      // Report to Sentry if available
      if (
        typeof window !== 'undefined' &&
        (window as Window & { Sentry?: { captureMessage: (msg: string, level: string) => void } }).Sentry &&
        error.severity === 'error'
      ) {
        ;(window as Window & { Sentry?: { captureMessage: (msg: string, level: string) => void } }).Sentry?.captureMessage(error.message, 'error')
      }

      // Set up auto-dismiss if applicable
      const dismissTimeout = AUTO_DISMISS_TIMEOUT[error.severity]
      if (dismissTimeout && error.dismissible) {
        setTimeout(() => {
          setErrors((prev) => prev.filter((e) => e.id !== id))
        }, dismissTimeout)
      }

      return id
    },
    [maxErrors, onError]
  )

  // Remove an error by ID
  const removeError = useCallback((id: string) => {
    setErrors((prev) => prev.filter((e) => e.id !== id))
  }, [])

  // Clear all errors
  const clearErrors = useCallback(() => {
    setErrors([])
  }, [])

  // Clear errors by severity
  const clearErrorsBySeverity = useCallback((severity: ErrorSeverity) => {
    setErrors((prev) => prev.filter((e) => e.severity !== severity))
  }, [])

  // Shorthand methods
  const showError = useCallback(
    (message: string, options: Partial<AppError> = {}) => {
      return addError({
        message,
        severity: 'error',
        dismissible: true,
        ...options,
      })
    },
    [addError]
  )

  const showWarning = useCallback(
    (message: string, options: Partial<AppError> = {}) => {
      return addError({
        message,
        severity: 'warning',
        dismissible: true,
        ...options,
      })
    },
    [addError]
  )

  const showInfo = useCallback(
    (message: string, options: Partial<AppError> = {}) => {
      return addError({
        message,
        severity: 'info',
        dismissible: true,
        ...options,
      })
    },
    [addError]
  )

  const showSuccess = useCallback(
    (message: string, options: Partial<AppError> = {}) => {
      return addError({
        message,
        severity: 'success',
        dismissible: true,
        ...options,
      })
    },
    [addError]
  )

  // Get the latest error
  const latestError = useMemo(() => {
    return errors.length > 0 ? errors[0]! : null
  }, [errors])

  const contextValue = useMemo(
    () => ({
      errors,
      latestError,
      addError,
      removeError,
      clearErrors,
      clearErrorsBySeverity,
      showError,
      showWarning,
      showInfo,
      showSuccess,
    }),
    [
      errors,
      latestError,
      addError,
      removeError,
      clearErrors,
      clearErrorsBySeverity,
      showError,
      showWarning,
      showInfo,
      showSuccess,
    ]
  )

  return (
    <ErrorContext.Provider value={contextValue}>
      {children}
    </ErrorContext.Provider>
  )
}

// Hook to use the error context
export function useError() {
  const context = useContext(ErrorContext)
  if (context === undefined) {
    throw new Error('useError must be used within an ErrorProvider')
  }
  return context
}

// Utility hook for handling API errors
export function useApiError() {
  const { showError, showWarning } = useError()

  const handleApiError = useCallback(
    (error: unknown, fallbackMessage = 'An error occurred') => {
      // Extract error details
      let message = fallbackMessage
      let code: string | undefined

      if (error instanceof Error) {
        message = error.message
      } else if (typeof error === 'object' && error !== null) {
        const err = error as { message?: string; code?: string; error?: { message?: string; code?: string } }
        if (err.error) {
          message = err.error.message || message
          code = err.error.code
        } else {
          message = err.message || message
          code = err.code
        }
      }

      // Try to get user-friendly message
      const userMessage = getUserMessage(code) || message

      // Determine severity based on error type
      const isWarning =
        code === 'RATE_LIMIT_ERROR' ||
        code === 'VALIDATION_ERROR' ||
        code === 'NOT_FOUND_ERROR'

      if (isWarning) {
        return showWarning(userMessage, { code })
      }

      return showError(userMessage, { code })
    },
    [showError, showWarning]
  )

  return { handleApiError }
}

// Export type for external use
export type { ErrorContextType }
