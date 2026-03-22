import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface SSOTestRequest {
  configuration_id: string
  test_type?: 'metadata' | 'authentication' | 'full'
}

export interface SSOTestResponse {
  success: boolean
  test_type: string
  results: {
    metadata_valid?: boolean
    certificate_valid?: boolean
    endpoints_reachable?: boolean
    authentication_successful?: boolean
    user_attributes?: Record<string, any>
    errors?: string[]
    warnings?: string[]
  }
  details?: string
  timestamp: string
}

export interface SSOTestConnectionProps {
  className?: string
  configurationId: string
  organizationId: string
  onTest?: (request: SSOTestRequest) => Promise<SSOTestResponse>
  onClose?: () => void
  onError?: (error: Error) => void
  januaClient?: any
  apiUrl?: string
}

export function SSOTestConnection({
  className,
  configurationId,
  organizationId: _organizationId,
  onTest,
  onClose,
  onError,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: SSOTestConnectionProps) {
  const [isTesting, setIsTesting] = React.useState(false)
  const [testType, setTestType] = React.useState<'metadata' | 'authentication' | 'full'>('full')
  const [result, setResult] = React.useState<SSOTestResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  // Run test
  const runTest = async () => {
    setIsTesting(true)
    setError(null)
    setResult(null)

    try {
      const testRequest: SSOTestRequest = {
        configuration_id: configurationId,
        test_type: testType,
      }

      let response: SSOTestResponse

      if (januaClient) {
        response = await januaClient.sso.testConfiguration(configurationId)
      } else if (onTest) {
        response = await onTest(testRequest)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/sso/test`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(testRequest),
        })

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}))
          throw new Error(errorData.detail || 'SSO test failed')
        }

        response = await res.json()
      }

      setResult(response)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to test SSO configuration')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsTesting(false)
    }
  }

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Test Configuration */}
      {!result && (
        <div className="space-y-4">
          <div className="p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20 space-y-2">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-semibold text-sm">Test Your SSO Configuration</span>
            </div>
            <p className="text-sm text-muted-foreground ml-7">
              Validate your SSO setup by testing metadata, certificates, and authentication flow
            </p>
          </div>

          {/* Test Type Selection */}
          <div className="space-y-2">
            <label className="block text-sm font-medium">Test Type</label>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setTestType('metadata')}
                className={cn(
                  'w-full p-4 border-2 rounded-lg text-left transition-colors',
                  testType === 'metadata'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="font-semibold">Metadata Validation</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Quick test - validates metadata structure and certificate format
                </div>
              </button>

              <button
                type="button"
                onClick={() => setTestType('authentication')}
                className={cn(
                  'w-full p-4 border-2 rounded-lg text-left transition-colors',
                  testType === 'authentication'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="font-semibold">Authentication Test</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Tests SSO login flow and attribute mapping
                </div>
              </button>

              <button
                type="button"
                onClick={() => setTestType('full')}
                className={cn(
                  'w-full p-4 border-2 rounded-lg text-left transition-colors',
                  testType === 'full'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="font-semibold">Full Comprehensive Test</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Complete validation - metadata, certificates, endpoints, and authentication
                </div>
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button onClick={runTest} disabled={isTesting} className="flex-1">
              {isTesting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Testing...
                </>
              ) : (
                'Run Test'
              )}
            </Button>
            {onClose && (
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Test Results */}
      {result && (
        <div className="space-y-4">
          {/* Overall Status */}
          <div
            className={cn(
              'p-6 border rounded-lg space-y-4',
              result.success
                ? 'border-green-200 bg-green-50 dark:bg-green-900/20'
                : 'border-red-200 bg-red-50 dark:bg-red-900/20'
            )}
          >
            <div className="flex items-center gap-3">
              {result.success ? (
                <>
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <div className="font-semibold text-lg text-green-800 dark:text-green-200">
                      Test Successful!
                    </div>
                    <div className="text-sm text-green-700 dark:text-green-300">
                      Your SSO configuration is working correctly
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <div className="font-semibold text-lg text-red-800 dark:text-red-200">
                      Test Failed
                    </div>
                    <div className="text-sm text-red-700 dark:text-red-300">
                      Issues detected in your SSO configuration
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center gap-4 text-sm">
              <div>
                <span className="font-medium">Test Type:</span>
                <Badge variant="outline" className="ml-2 capitalize">
                  {result.test_type}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Timestamp:</span>
                <span className="ml-2 text-muted-foreground">{formatTimestamp(result.timestamp)}</span>
              </div>
            </div>
          </div>

          {/* Detailed Results */}
          <div className="space-y-3">
            <h4 className="font-semibold">Test Results</h4>

            {/* Metadata Validation */}
            {result.results.metadata_valid !== undefined && (
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  {result.results.metadata_valid ? (
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                  <span className="font-medium">Metadata Valid</span>
                </div>
                <Badge variant={result.results.metadata_valid ? 'default' : 'destructive'}>
                  {result.results.metadata_valid ? 'Pass' : 'Fail'}
                </Badge>
              </div>
            )}

            {/* Certificate Validation */}
            {result.results.certificate_valid !== undefined && (
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  {result.results.certificate_valid ? (
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                  <span className="font-medium">Certificate Valid</span>
                </div>
                <Badge variant={result.results.certificate_valid ? 'default' : 'destructive'}>
                  {result.results.certificate_valid ? 'Pass' : 'Fail'}
                </Badge>
              </div>
            )}

            {/* Endpoints Reachable */}
            {result.results.endpoints_reachable !== undefined && (
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  {result.results.endpoints_reachable ? (
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                  <span className="font-medium">Endpoints Reachable</span>
                </div>
                <Badge variant={result.results.endpoints_reachable ? 'default' : 'destructive'}>
                  {result.results.endpoints_reachable ? 'Pass' : 'Fail'}
                </Badge>
              </div>
            )}

            {/* Authentication */}
            {result.results.authentication_successful !== undefined && (
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  {result.results.authentication_successful ? (
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                  <span className="font-medium">Authentication Successful</span>
                </div>
                <Badge variant={result.results.authentication_successful ? 'default' : 'destructive'}>
                  {result.results.authentication_successful ? 'Pass' : 'Fail'}
                </Badge>
              </div>
            )}
          </div>

          {/* User Attributes */}
          {result.results.user_attributes && Object.keys(result.results.user_attributes).length > 0 && (
            <div className="space-y-2">
              <h4 className="font-semibold">User Attributes Received</h4>
              <div className="p-4 border rounded-lg bg-gray-50 dark:bg-gray-900">
                <pre className="text-xs overflow-x-auto">
                  {JSON.stringify(result.results.user_attributes, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Errors */}
          {result.results.errors && result.results.errors.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-semibold text-red-800 dark:text-red-200">Errors</h4>
              <div className="space-y-1">
                {result.results.errors.map((error, i) => (
                  <div key={i} className="p-3 border border-red-200 bg-red-50 dark:bg-red-900/20 rounded-md text-sm text-red-800 dark:text-red-200">
                    {error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.results.warnings && result.results.warnings.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-semibold text-yellow-800 dark:text-yellow-200">Warnings</h4>
              <div className="space-y-1">
                {result.results.warnings.map((warning, i) => (
                  <div key={i} className="p-3 border border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20 rounded-md text-sm text-yellow-800 dark:text-yellow-200">
                    {warning}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Details */}
          {result.details && (
            <div className="space-y-2">
              <h4 className="font-semibold">Additional Details</h4>
              <div className="p-4 border rounded-lg bg-gray-50 dark:bg-gray-900 text-sm">
                {result.details}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              onClick={() => {
                setResult(null)
                setError(null)
              }}
              variant="outline"
              className="flex-1"
            >
              Run Another Test
            </Button>
            {onClose && (
              <Button onClick={onClose} className="flex-1">
                Close
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
