'use client'

import { PasswordReset } from '@plinto/ui'
import { useState } from 'react'

export default function PasswordResetShowcase() {
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleRequestReset = async (email: string) => {
    console.log('Password reset requested for:', email)
    setStatus('success')
    setMessage(`Password reset instructions sent to ${email}`)
    setTimeout(() => setStatus('idle'), 5000)
  }

  const handleResetPassword = async (token: string, newPassword: string) => {
    console.log('Resetting password with token:', token)
    setStatus('success')
    setMessage('Password reset successfully! You can now sign in.')
    setTimeout(() => setStatus('idle'), 5000)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'Password reset failed')
    console.error('Password reset error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          PasswordReset Component
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Secure password reset flow with email verification and password strength validation.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Email-based password reset</li>
              <li>• Secure token validation</li>
              <li>• Password strength checking</li>
              <li>• Confirm password matching</li>
              <li>• Auto-redirect after success</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Props</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <code>onRequestReset</code>: Email reset callback</li>
              <li>• <code>onResetPassword</code>: Password reset callback</li>
              <li>• <code>onError</code>: Error callback</li>
              <li>• <code>token</code>: Reset token from email</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import { PasswordReset } from '@plinto/ui'

<PasswordReset
  onRequestReset={handleRequest}
  onResetPassword={handleReset}
  onError={handleError}
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

      {/* Request Reset Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8 mb-6">
        <div className="max-w-md mx-auto">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
            Request Password Reset
          </h3>

          <PasswordReset
            onRequestReset={handleRequestReset}
            onError={handleError}
          />

          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Demo Note:</strong> Enter any email to see the request flow.
              In production, this sends a reset link to the user's email.
            </p>
          </div>
        </div>
      </div>

      {/* Reset with Token Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <div className="max-w-md mx-auto">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
            Reset Password with Token
          </h3>

          <PasswordReset
            token="demo-reset-token-123"
            onResetPassword={handleResetPassword}
            onError={handleError}
          />

          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Demo Note:</strong> This simulates the view after clicking the reset link in email.
              The token would normally come from the URL query parameter.
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Request Password Reset Page</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { PasswordReset } from '@plinto/ui'
import { useRouter } from 'next/navigation'

export default function ForgotPasswordPage() {
  const router = useRouter()

  return (
    <PasswordReset
      onRequestReset={async (email) => {
        const response = await fetch('/api/auth/password-reset/request', {
          method: 'POST',
          body: JSON.stringify({ email }),
        })

        if (!response.ok) throw new Error('Request failed')

        // Show success message
        router.push('/auth/reset-email-sent')
      }}
      onError={(error) => {
        console.error(error)
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Reset Password with Token</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { PasswordReset } from '@plinto/ui'
import { useRouter, useSearchParams } from 'next/navigation'

export default function ResetPasswordPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  if (!token) {
    return <div>Invalid reset link</div>
  }

  return (
    <PasswordReset
      token={token}
      onResetPassword={async (token, newPassword) => {
        const response = await fetch('/api/auth/password-reset/confirm', {
          method: 'POST',
          body: JSON.stringify({ token, password: newPassword }),
        })

        if (!response.ok) throw new Error('Reset failed')

        // Redirect to login
        router.push('/signin?reset=success')
      }}
      onError={(error) => {
        if (error.message.includes('expired')) {
          router.push('/auth/reset-expired')
        }
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Complete Flow with Email Service</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`// API route: /api/auth/password-reset/request
export async function POST(request: Request) {
  const { email } = await request.json()

  // Find user
  const user = await db.user.findUnique({ where: { email } })
  if (!user) {
    // Don't reveal if email exists
    return Response.json({ success: true })
  }

  // Generate secure token
  const token = await generateResetToken(user.id)

  // Send email with reset link
  await sendEmail({
    to: email,
    subject: 'Password Reset Request',
    html: \`
      <p>Click here to reset your password:</p>
      <a href="https://yourapp.com/reset-password?token=\${token}">
        Reset Password
      </a>
      <p>This link expires in 1 hour.</p>
    \`
  })

  return Response.json({ success: true })
}`}
            </pre>
          </div>
        </div>
      </div>

      {/* Security Best Practices */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Security Best Practices
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Token Security</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Cryptographically secure random tokens</li>
              <li>• Short expiration time (15-60 minutes)</li>
              <li>• Single-use tokens (invalidate after use)</li>
              <li>• Rate limiting on reset requests</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Email Security</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Don't reveal if email exists in system</li>
              <li>• Use HTTPS links only</li>
              <li>• Include warning about phishing</li>
              <li>• Log all reset attempts</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Password Requirements</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Minimum 8 characters</li>
              <li>• Password strength validation</li>
              <li>• Prevent common passwords</li>
              <li>• Confirm password matching</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Experience</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Clear success/error messages</li>
              <li>• Loading states during submission</li>
              <li>• Auto-redirect after success</li>
              <li>• Help text and tooltips</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
