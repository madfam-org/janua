'use client'

import { SignUp } from '@plinto/ui'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function SignUpShowcase() {
  const router = useRouter()
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSuccess = (user: any) => {
    setStatus('success')
    setMessage('Account created successfully! Redirecting...')
    console.log('Signup successful:', user)

    // Simulate redirect after success
    setTimeout(() => {
      router.push('/dashboard')
    }, 2000)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'Signup failed. Please try again.')
    console.error('Signup error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          SignUp Component
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          User registration component with comprehensive validation, password strength checking, and terms acceptance.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Email/password registration</li>
              <li>• Password strength validation</li>
              <li>• Confirm password matching</li>
              <li>• Terms of service acceptance</li>
              <li>• Real-time validation feedback</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Props</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>onSuccess</code>: Registration callback</li>
              <li>• <code>onError</code>: Error callback</li>
              <li>• <code>requireName</code>: Name field optional</li>
              <li>• <code>termsUrl</code>: Terms of service URL</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import { SignUp } from '@plinto/ui'

<SignUp
  onSuccess={(data) => {
    console.log(data)
    router.push('/welcome')
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

          <SignUp
            afterSignUp={handleSuccess}
            onError={handleError}
          />

          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Demo Note:</strong> This is the pure @plinto/ui component without demo-specific features.
              In a real application, you would connect this to your user registration API.
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
import { SignUp } from '@plinto/ui'
import { useRouter } from 'next/navigation'

export default function RegisterPage() {
  const router = useRouter()

  return (
    <SignUp
      onSuccess={(data) => {
        // Create user session
        localStorage.setItem('userId', data.user.id)
        // Redirect to welcome page
        router.push('/welcome')
      }}
      onError={(error) => {
        console.error('Registration failed:', error)
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Name Field Required</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<SignUp
  requireName={true}
  onSuccess={(data) => {
    // Analytics with user name
    analytics.identify(data.user.id, {
      name: data.user.name,
      email: data.user.email
    })
    router.push('/onboarding')
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Custom Terms URL</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<SignUp
  termsUrl="/legal/terms-of-service"
  privacyUrl="/legal/privacy-policy"
  onSuccess={(data) => {
    // Send welcome email
    await sendWelcomeEmail(data.user.email)
    router.push('/dashboard')
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">With Auto Sign-In After Registration</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`import { SignUp } from '@plinto/ui'

<SignUp
  onSuccess={async (data) => {
    // Automatically sign in after registration
    const signInResult = await signIn({
      email: data.user.email,
      password: data.password
    })

    if (signInResult.accessToken) {
      localStorage.setItem('accessToken', signInResult.accessToken)
      router.push('/dashboard')
    }
  }}
/>`}
            </pre>
          </div>
        </div>
      </div>

      {/* Validation Rules */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Validation Rules
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Email Validation</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Valid email format required</li>
              <li>• No duplicate email addresses</li>
              <li>• Case-insensitive validation</li>
              <li>• Real-time format checking</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Password Requirements</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Minimum 8 characters</li>
              <li>• Password strength indicator</li>
              <li>• Confirm password must match</li>
              <li>• Real-time strength feedback</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Name Field (Optional)</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Can be made required via props</li>
              <li>• Minimum 2 characters when required</li>
              <li>• Unicode character support</li>
              <li>• Whitespace trimming</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Terms Acceptance</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Required checkbox validation</li>
              <li>• Customizable terms URL</li>
              <li>• Privacy policy link support</li>
              <li>• Clear acceptance tracking</li>
            </ul>
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
              <li>• Bundle size: ~400 LOC + dependencies</li>
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Security</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Password strength validation</li>
              <li>• XSS protection built-in</li>
              <li>• CSRF token support</li>
              <li>• Secure password handling</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Experience</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Real-time validation feedback</li>
              <li>• Loading states during submission</li>
              <li>• Success/error notifications</li>
              <li>• Clear error messages</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
