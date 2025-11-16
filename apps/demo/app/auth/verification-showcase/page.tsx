'use client'

import { EmailVerification, PhoneVerification } from '@plinto/ui'
import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@plinto/ui'

export default function VerificationShowcase() {
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  // Email verification handlers
  const handleSendEmailCode = async (email: string) => {
    console.log('Sending verification code to:', email)
    setStatus('success')
    setMessage(`Verification code sent to ${email}`)
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleVerifyEmail = async (code: string) => {
    console.log('Verifying email with code:', code)
    setStatus('success')
    setMessage('Email verified successfully!')
    setTimeout(() => setStatus('idle'), 3000)
  }

  // Phone verification handlers
  const handleSendPhoneCode = async (phone: string) => {
    console.log('Sending verification code to:', phone)
    setStatus('success')
    setMessage(`Verification code sent to ${phone}`)
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleVerifyPhone = async (code: string) => {
    console.log('Verifying phone with code:', code)
    setStatus('success')
    setMessage('Phone number verified successfully!')
    setTimeout(() => setStatus('idle'), 3000)
  }

  const handleError = (error: Error) => {
    setStatus('error')
    setMessage(error.message || 'Verification failed')
    console.error('Verification error:', error)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Verification Components
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Email and phone number verification with secure code delivery and validation.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Components</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• EmailVerification</li>
              <li>• PhoneVerification</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Code-based verification</li>
              <li>• Resend code functionality</li>
              <li>• Auto-submit on code complete</li>
              <li>• Countdown timer for resend</li>
              <li>• Input validation and formatting</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Usage</h3>
            <pre className="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto">
{`import {
  EmailVerification,
  PhoneVerification
} from '@plinto/ui'

<EmailVerification
  onSendCode={handleSend}
  onVerify={handleVerify}
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
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
          Live Component Demo
        </h3>

        <Tabs defaultValue="email" className="max-w-md mx-auto">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="email">Email Verification</TabsTrigger>
            <TabsTrigger value="phone">Phone Verification</TabsTrigger>
          </TabsList>

          <TabsContent value="email">
            <EmailVerification
              email="user@example.com"
              onResendEmail={async () => {
                console.log('Resending verification email')
                setStatus('success')
                setMessage('Verification email resent!')
                setTimeout(() => setStatus('idle'), 3000)
              }}
              onVerify={async (token) => {
                console.log('Verifying email with token:', token)
                setStatus('success')
                setMessage('Email verified successfully!')
                setTimeout(() => setStatus('idle'), 3000)
              }}
              onError={handleError}
            />

            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Demo Note:</strong> Enter any email to receive a simulated verification code.
                In production, this sends a real code via email.
              </p>
            </div>
          </TabsContent>

          <TabsContent value="phone">
            <PhoneVerification
              phoneNumber="+1 (555) 123-4567"
              onSendCode={async (phone) => {
                console.log('Sending verification code to:', phone)
                setStatus('success')
                setMessage(`Verification code sent to ${phone}`)
                setTimeout(() => setStatus('idle'), 3000)
              }}
              onVerifyCode={async (code) => {
                console.log('Verifying phone with code:', code)
                setStatus('success')
                setMessage('Phone number verified successfully!')
                setTimeout(() => setStatus('idle'), 3000)
              }}
              onError={handleError}
            />

            <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Demo Note:</strong> Enter any phone number to receive a simulated verification code.
                In production, this sends a real code via SMS.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Implementation Examples */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Implementation Examples
        </h3>

        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Email Verification Flow</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { EmailVerification } from '@plinto/ui'
import { useRouter } from 'next/navigation'

export default function VerifyEmailPage({ email }) {
  const router = useRouter()

  return (
    <EmailVerification
      defaultEmail={email} // Pre-fill from signup
      onSendCode={async (email) => {
        const response = await fetch('/api/auth/email/send-code', {
          method: 'POST',
          body: JSON.stringify({ email }),
        })

        if (!response.ok) {
          throw new Error('Failed to send code')
        }
      }}
      onVerify={async (code) => {
        const response = await fetch('/api/auth/email/verify', {
          method: 'POST',
          body: JSON.stringify({ email, code }),
        })

        if (!response.ok) {
          throw new Error('Invalid verification code')
        }

        // Redirect to success or dashboard
        router.push('/welcome')
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Phone Verification with SMS</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`import { PhoneVerification } from '@plinto/ui'

export default function VerifyPhonePage() {
  return (
    <PhoneVerification
      onSendCode={async (phone) => {
        // Use Twilio, AWS SNS, or similar service
        const response = await fetch('/api/auth/phone/send-code', {
          method: 'POST',
          body: JSON.stringify({ phone }),
        })

        if (!response.ok) {
          throw new Error('Failed to send SMS')
        }
      }}
      onVerify={async (code) => {
        const response = await fetch('/api/auth/phone/verify', {
          method: 'POST',
          body: JSON.stringify({ code }),
        })

        if (!response.ok) {
          throw new Error('Invalid code')
        }

        // Update user profile
        await updateUserPhone(phone, true)
      }}
    />
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Backend Code Generation (Example)</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`// API route: /api/auth/email/send-code
import crypto from 'crypto'

export async function POST(request: Request) {
  const { email } = await request.json()

  // Generate 6-digit code
  const code = crypto.randomInt(100000, 999999).toString()

  // Store code with expiration (e.g., 10 minutes)
  await redis.setex(
    \`email:verify:\${email}\`,
    600, // 10 minutes
    code
  )

  // Send email with code
  await sendEmail({
    to: email,
    subject: 'Verification Code',
    html: \`
      <h2>Your verification code is:</h2>
      <p style="font-size: 24px; font-weight: bold;">\${code}</p>
      <p>This code expires in 10 minutes.</p>
    \`
  })

  return Response.json({ success: true })
}

// API route: /api/auth/email/verify
export async function POST(request: Request) {
  const { email, code } = await request.json()

  // Verify code
  const storedCode = await redis.get(\`email:verify:\${email}\`)

  if (!storedCode || storedCode !== code) {
    return Response.json(
      { error: 'Invalid or expired code' },
      { status: 400 }
    )
  }

  // Mark email as verified
  await db.user.update({
    where: { email },
    data: { emailVerified: true }
  })

  // Delete used code
  await redis.del(\`email:verify:\${email}\`)

  return Response.json({ success: true })
}`}
            </pre>
          </div>
        </div>
      </div>

      {/* Security & Best Practices */}
      <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Security & Best Practices
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Code Generation</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• 6-digit numeric codes (easy to read)</li>
              <li>• Cryptographically secure random generation</li>
              <li>• Short expiration time (5-15 minutes)</li>
              <li>• Single-use codes (invalidate after verification)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Rate Limiting</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Limit code send requests (e.g., 3 per hour)</li>
              <li>• Limit verification attempts (e.g., 5 per code)</li>
              <li>• Progressive delays on failed attempts</li>
              <li>• IP-based rate limiting</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Experience</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Auto-submit when code is complete</li>
              <li>• Countdown timer for resend button</li>
              <li>• Clear error messages</li>
              <li>• Loading states during verification</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Delivery Methods</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Email: Use transactional email service</li>
              <li>• SMS: Use Twilio, AWS SNS, or similar</li>
              <li>• Consider voice calls as fallback</li>
              <li>• Log all delivery attempts</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
