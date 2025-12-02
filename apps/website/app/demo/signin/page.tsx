'use client'

import { SignIn } from '@janua/ui'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { januaClient } from '@/lib/janua-client'

export default function SignInShowcase() {
  const router = useRouter()
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSuccess = (user: any) => {
    setStatus('success')
    setMessage('Login successful! Redirecting to dashboard...')
    // removed console.log

    // Simulate redirect after success
    setTimeout(() => {
      router.push('/dashboard')
    }, 1500)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'Login failed. Please try again.')
    console.error('Login error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          SignIn Component
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Production-ready authentication component with built-in validation, error handling, and accessibility features.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Email/password authentication</li>
              <li>• Form validation</li>
              <li>• Error handling</li>
              <li>• Loading states</li>
              <li>• Accessibility (WCAG 2.1 AA)</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Props</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>onSuccess</code>: Success callback</li>
              <li>• <code>onError</code>: Error callback</li>
              <li>• <code>redirectUrl</code>: Post-login redirect</li>
              <li>• <code>showRememberMe</code>: Remember me option</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import { SignIn } from '@janua/ui'

<SignIn
  onSuccess={(data) => {
    // removed console.log
    router.push('/dashboard')
  }}
  onError={(error) => {
    console.error(error)
  }}
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Status Message */}
      {status !== 'idle' && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            status === 'success'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200'
              : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200'
          }`}
        >
          <p className="font-medium">{message}</p>
        </div>
      )}

      {/* Live Component Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <div className="max-w-md mx-auto">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
            Live Component Demo
          </h3>

          <SignIn
            januaClient={januaClient}
            afterSignIn={handleSuccess}
            onError={handleError}
            redirectUrl="/dashboard"
          />

          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Demo Note:</strong> This is the pure @janua/ui component without demo-specific features.
              In a real application, you would connect this to your authentication API.
            </p>
          </div>
        </div>
      </div>

      {/* Implementation Examples */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Implementation Examples
        </h3>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Basic Usage</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { SignIn } from '@janua/ui'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()

  return (
    <SignIn
      onSuccess={(data) => {
        // Store access token
        localStorage.setItem('accessToken', data.accessToken)
        // Redirect to dashboard
        router.push('/dashboard')
      }}
      onError={(error) => {
        console.error('Login failed:', error)
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Custom Redirect</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<SignIn
  redirectUrl="/dashboard"
  onSuccess={(data) => {
    // Handle success (e.g., analytics)
    analytics.track('User Logged In', { userId: data.user.id })
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Remember Me</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<SignIn
  showRememberMe={true}
  onSuccess={(data) => {
    if (data.rememberMe) {
      // Store long-lived session
      localStorage.setItem('refreshToken', data.refreshToken)
    }
    router.push('/dashboard')
  }}
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Component Specifications */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Component Specifications
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Performance</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Bundle size: ~350 LOC + dependencies</li>
              <li>• First render: &lt;50ms</li>
              <li>• Tree-shakeable: ✅ Yes</li>
              <li>• Server Components: Compatible</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Accessibility</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• WCAG 2.1 AA compliant</li>
              <li>• Keyboard navigation: ✅ Full support</li>
              <li>• Screen readers: ✅ Optimized</li>
              <li>• Focus management: ✅ Automatic</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Validation</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Email format validation</li>
              <li>• Password minimum length (8 chars)</li>
              <li>• Real-time error feedback</li>
              <li>• Required field checking</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Dependencies</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Radix UI primitives</li>
              <li>• lucide-react icons</li>
              <li>• Tailwind CSS</li>
              <li>• Zero runtime overhead</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
