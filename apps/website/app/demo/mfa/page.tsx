'use client'

import { MFASetup, MFAChallenge, BackupCodes } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import { useState } from 'react'
import { januaClient } from '@/lib/janua-client'

export default function MFAShowcase() {
  const [setupComplete, setSetupComplete] = useState(false)
  const [challengeVerified, setChallengeVerified] = useState(false)
  const [backupCodesGenerated, setBackupCodesGenerated] = useState(false)

  // Sample backup codes for demo
  const sampleBackupCodes = [
    { code: 'ABCD-1234-EFGH', used: false },
    { code: 'IJKL-5678-MNOP', used: false },
    { code: 'QRST-9012-UVWX', used: false },
    { code: 'YZAB-3456-CDEF', used: false },
    { code: 'GHIJ-7890-KLMN', used: false },
    { code: 'OPQR-1234-STUV', used: false },
    { code: 'WXYZ-5678-ABCD', used: true },
    { code: 'EFGH-9012-IJKL', used: false }
  ]

  const handleSetupComplete = async (verificationCode: string) => {
    setSetupComplete(true)
    // removed console.log
  }

  const handleChallengeVerify = async (code: string) => {
    setChallengeVerified(true)
    // removed console.log
    setTimeout(() => setChallengeVerified(false), 3000)
  }

  const handleBackupCodesDownload = () => {
    setBackupCodesGenerated(true)
    // removed console.log
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Component Info */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Multi-Factor Authentication (MFA)
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Complete MFA implementation with TOTP setup, verification challenges, and backup code generation.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Components</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• <strong>MFASetup</strong>: TOTP configuration</li>
              <li>• <strong>MFAChallenge</strong>: Code verification</li>
              <li>• <strong>BackupCodes</strong>: Recovery codes</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Features</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• QR code generation</li>
              <li>• Manual secret entry</li>
              <li>• 6-digit TOTP verification</li>
              <li>• Backup code generation</li>
              <li>• Secure code storage</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Security</h3>
            <ul className="text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Time-based OTP (RFC 6238)</li>
              <li>• 30-second time window</li>
              <li>• Rate limiting support</li>
              <li>• Encrypted backup codes</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {setupComplete && (
        <div className="mb-6 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200">
          <p className="font-medium">✅ MFA Setup Complete! Scan the QR code with your authenticator app.</p>
        </div>
      )}

      {challengeVerified && (
        <div className="mb-6 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200">
          <p className="font-medium">✅ MFA Code Verified Successfully!</p>
        </div>
      )}

      {/* Live Component Demo */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-8">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 text-center">
          Live Component Demos
        </h3>

        <Tabs defaultValue="setup" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="setup">MFA Setup</TabsTrigger>
            <TabsTrigger value="challenge">Challenge</TabsTrigger>
            <TabsTrigger value="backup">Backup Codes</TabsTrigger>
          </TabsList>

          <TabsContent value="setup" className="mt-6">
            <div className="max-w-md mx-auto">
              <MFASetup
                januaClient={januaClient}
                onComplete={handleSetupComplete}
                onError={(error) => console.error('MFA Setup Error:', error)}
              />
              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Demo:</strong> Scan the QR code with Google Authenticator, Authy, or any TOTP app.
                  The secret key is also provided for manual entry.
                </p>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="challenge" className="mt-6">
            <div className="max-w-md mx-auto">
              <MFAChallenge
                onVerify={handleChallengeVerify}
              />
              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Demo:</strong> Enter the 6-digit code from your authenticator app.
                  The code refreshes every 30 seconds.
                </p>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="backup" className="mt-6">
            <div className="max-w-md mx-auto">
              <BackupCodes
                backupCodes={sampleBackupCodes}
              />
              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  <strong>Demo:</strong> These are sample backup codes. In production, generate cryptographically
                  secure codes and store them securely. Each code can be used once.
                </p>
              </div>
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Complete MFA Flow</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`'use client'
import { MFASetup, MFAChallenge, BackupCodes } from '@janua/ui'
import { useState } from 'react'

export default function MFAPage() {
  const [step, setStep] = useState<'setup' | 'challenge' | 'backup'>('setup')
  const [backupCodes, setBackupCodes] = useState<string[]>([])

  return (
    <>
      {step === 'setup' && (
        <MFASetup
          onComplete={async (secret, qrCode) => {
            // Store MFA secret in database
            await saveMFASecret(secret)
            // Generate backup codes
            const codes = await generateBackupCodes()
            setBackupCodes(codes)
            setStep('backup')
          }}
        />
      )}

      {step === 'backup' && (
        <BackupCodes
          codes={backupCodes}
          onDownload={() => {
            // User has saved backup codes
            setStep('challenge')
          }}
        />
      )}

      {step === 'challenge' && (
        <MFAChallenge
          onSuccess={() => {
            // MFA verification complete
            router.push('/dashboard')
          }}
        />
      )}
    </>
  )
}`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">MFA Setup with API Integration</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`<MFASetup
  onComplete={async (secret, qrCode) => {
    try {
      // Save to backend
      await fetch('/api/mfa/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret })
      })

      // Generate and store backup codes
      const response = await fetch('/api/mfa/backup-codes', {
        method: 'POST'
      })
      const { codes } = await response.json()

      setBackupCodes(codes)
      setMFAEnabled(true)
    } catch (error) {
      console.error('MFA setup failed:', error)
    }
  }}
/>`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">MFA Challenge with Rate Limiting</h4>
            <pre className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm">
{`import { MFAChallenge } from '@janua/ui'

const [attempts, setAttempts] = useState(0)
const MAX_ATTEMPTS = 3

<MFAChallenge
  onSuccess={async (code) => {
    // Verify with backend
    const response = await fetch('/api/mfa/verify', {
      method: 'POST',
      body: JSON.stringify({ code })
    })

    if (response.ok) {
      router.push('/dashboard')
    }
  }}
  onError={(error) => {
    setAttempts(prev => prev + 1)

    if (attempts >= MAX_ATTEMPTS) {
      // Lock account temporarily
      router.push('/account-locked')
    }
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

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">MFASetup</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Bundle: ~450 LOC</li>
              <li>• QR code generation: Built-in</li>
              <li>• Secret format: Base32</li>
              <li>• TOTP: RFC 6238 compliant</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">MFAChallenge</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Bundle: ~300 LOC</li>
              <li>• Code format: 6 digits</li>
              <li>• Time window: 30 seconds</li>
              <li>• Auto-focus: Enabled</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">BackupCodes</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• Bundle: ~250 LOC</li>
              <li>• Code format: Customizable</li>
              <li>• Download: CSV/TXT support</li>
              <li>• Copy: Clipboard API</li>
            </ul>
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
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Setup Phase</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Generate cryptographically secure secrets</li>
              <li>✓ Use HTTPS for secret transmission</li>
              <li>✓ Encrypt secrets in database</li>
              <li>✓ Verify setup with test code</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Verification Phase</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Implement rate limiting (3-5 attempts)</li>
              <li>✓ Use constant-time comparison</li>
              <li>✓ Log failed attempts</li>
              <li>✓ Allow time drift (±1 window)</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">Backup Codes</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Generate 8-10 codes minimum</li>
              <li>✓ Each code single-use only</li>
              <li>✓ Hash codes before storage</li>
              <li>✓ Allow regeneration anytime</li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">User Experience</h4>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>✓ Provide clear setup instructions</li>
              <li>✓ Show QR code + manual secret</li>
              <li>✓ Verify setup before enabling</li>
              <li>✓ Offer account recovery options</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
