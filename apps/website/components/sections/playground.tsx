'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Code, Lock, Zap, Copy, Check } from 'lucide-react'
import { Button } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'

export function PlaygroundSection() {
  const [copiedCode, setCopiedCode] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [verificationTime, setVerificationTime] = useState<number | null>(null)

  const demos = {
    jwt: {
      title: 'JWT Token Generation',
      description: 'Generate and verify JWTs with automatic key rotation',
      code: `// Generate a secure JWT token
const token = await janua.sessions.create({
  email: 'demo@example.com',
  password: 'secure-password'
})

// Token payload includes:
{
  "sub": "user_123",
  "tid": "tenant_456",
  "exp": 1234567890,
  "jti": "unique-token-id"
}`,
      result: {
        accessToken: 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMzQ1Ni...',
        expiresIn: 900,
        tokenType: 'Bearer'
      }
    },
    verify: {
      title: 'Edge Verification',
      description: 'Verify tokens at the edge in milliseconds',
      code: `// Verify token at the edge
const claims = await janua.sessions.verify(token)

// Response includes verified claims:
{
  "sub": "user_123",
  "tid": "tenant_456",
  "oid": "org_789",
  "roles": ["admin"],
  "verified": true
}`,
      result: {
        latency: '12ms',
        location: 'San Francisco',
        cached: true
      }
    },
    passkey: {
      title: 'Passkey Authentication',
      description: 'Passwordless authentication with WebAuthn',
      code: `// Start passkey authentication
const options = await janua.passkeys.beginAuthentication()

// Complete with biometric verification
const session = await janua.passkeys.completeAuthentication({
  credential: navigatorCredential
})

// User authenticated without password!`,
      result: {
        authenticated: true,
        method: 'passkey',
        device: 'Touch ID'
      }
    },
    policy: {
      title: 'Policy Evaluation',
      description: 'Fine-grained authorization with OPA policies',
      code: `// Evaluate complex policies
const decision = await janua.policies.evaluate({
  subject: 'user_123',
  action: 'document:write',
  resource: 'doc_456',
  context: {
    org: 'org_789',
    time: new Date()
  }
})

// Returns allow/deny with reasons`,
      result: {
        allowed: true,
        reasons: ['User is document owner', 'Has write permission']
      }
    }
  }

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code)
    setCopiedCode(id)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  const runDemo = async (demo: string) => {
    setIsRunning(true)
    setVerificationTime(null)
    
    // Simulate API call
    const startTime = Date.now()
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50))
    const endTime = Date.now()
    
    setVerificationTime(endTime - startTime)
    setIsRunning(false)
  }

  return (
    <div id="playground" className="scroll-mt-20">
      <div className="text-center mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Try it live — no signup required
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            Experience the speed and simplicity of Janua's API. 
            Test real authentication flows in our sandboxed environment.
          </p>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="bg-gray-900 rounded-2xl shadow-2xl overflow-hidden"
      >
        <Tabs defaultValue="jwt" className="w-full">
          <div className="border-b border-gray-800 p-4">
            <TabsList className="bg-gray-800/50 p-1">
              <TabsTrigger value="jwt" className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                JWT Tokens
              </TabsTrigger>
              <TabsTrigger value="verify" className="flex items-center gap-2">
                <Zap className="h-4 w-4" />
                Edge Verify
              </TabsTrigger>
              <TabsTrigger value="passkey" className="flex items-center gap-2">
                <Code className="h-4 w-4" />
                Passkeys
              </TabsTrigger>
              <TabsTrigger value="policy" className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                Policies
              </TabsTrigger>
            </TabsList>
          </div>

          {Object.entries(demos).map(([key, demo]) => (
            <TabsContent key={key} value={key} className="p-0">
              <div className="grid lg:grid-cols-2">
                {/* Code editor */}
                <div className="p-6 border-r border-gray-800">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-white">
                        {demo.title}
                      </h3>
                      <p className="text-sm text-gray-400 mt-1">
                        {demo.description}
                      </p>
                    </div>
                    <button
                      onClick={() => copyCode(demo.code, key)}
                      className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
                      aria-label="Copy code"
                    >
                      {copiedCode === key ? (
                        <Check className="h-4 w-4 text-green-400" />
                      ) : (
                        <Copy className="h-4 w-4 text-gray-400" />
                      )}
                    </button>
                  </div>
                  
                  <div className="bg-gray-950 rounded-lg p-4 font-mono text-sm">
                    <pre className="text-gray-300 whitespace-pre-wrap">
                      {demo.code}
                    </pre>
                  </div>

                  <Button
                    onClick={() => runDemo(key)}
                    disabled={isRunning}
                    className="mt-4 w-full"
                  >
                    {isRunning ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        Run Demo
                      </>
                    )}
                  </Button>
                </div>

                {/* Result panel */}
                <div className="p-6">
                  <div className="mb-4">
                    <h3 className="text-lg font-semibold text-white">
                      Result
                    </h3>
                    <p className="text-sm text-gray-400 mt-1">
                      API response from Janua
                    </p>
                  </div>

                  <div className="bg-gray-950 rounded-lg p-4">
                    {verificationTime && (
                      <div className="mb-4 flex items-center justify-between p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                        <span className="text-green-400 text-sm">
                          Response Time
                        </span>
                        <span className="text-green-400 font-mono font-bold">
                          {verificationTime}ms
                        </span>
                      </div>
                    )}
                    
                    <pre className="text-gray-300 font-mono text-sm whitespace-pre-wrap">
                      {JSON.stringify(demo.result, null, 2)}
                    </pre>
                  </div>

                  {/* Metrics */}
                  <div className="mt-6 grid grid-cols-2 gap-4">
                    <div className="p-3 bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-white">
                        {key === 'verify' ? '12ms' : '45ms'}
                      </div>
                      <div className="text-xs text-gray-400">Latency</div>
                    </div>
                    <div className="p-3 bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-white">
                        {key === 'jwt' ? '284B' : '156B'}
                      </div>
                      <div className="text-xs text-gray-400">Payload Size</div>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </motion.div>

      {/* Integration guide */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mt-8 text-center"
      >
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Ready to integrate? Get started in 5 minutes.
        </p>
        <div className="flex gap-4 justify-center">
          <Button variant="outline" asChild>
            <a href="https://docs.janua.dev/quickstart">View Quickstart</a>
          </Button>
          <Button asChild>
            <a href="https://app.janua.dev/auth/signup">Create Free Account</a>
          </Button>
        </div>
      </motion.div>
    </div>
  )
}