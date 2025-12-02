'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Code, Terminal, FileCode, Package, CheckCircle } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'

export function DeveloperExperience() {
  const [selectedLanguage, setSelectedLanguage] = useState('typescript')

  const languages = [
    { id: 'typescript', name: 'TypeScript', icon: FileCode },
    { id: 'python', name: 'Python', icon: Code },
    { id: 'go', name: 'Go', icon: Terminal },
    { id: 'ruby', name: 'Ruby', icon: Package },
  ]

  const codeExamples = {
    typescript: {
      install: 'npm install @janua/nextjs @janua/react-sdk',
      setup: `// middleware.ts
import { withJanua } from '@janua/nextjs/middleware'

export default withJanua({
  publicRoutes: ['/'],
  afterAuth: (auth, req) => {
    if (!auth.orgId) {
      return Response.redirect('/org-selection')
    }
  }
})`,
      usage: `// app/page.tsx
import { SignIn, UserButton } from '@janua/react-sdk'
import { getSession } from '@janua/nextjs'

export default async function Page() {
  const session = await getSession()
  
  return session ? (
    <UserButton />
  ) : (
    <SignIn />
  )
}`
    },
    python: {
      install: 'pip install janua',
      setup: `# main.py
from janua import Janua
import os

janua = Janua(
    api_key=os.environ['JANUA_API_KEY'],
    tenant_id=os.environ['JANUA_TENANT_ID']
)`,
      usage: `# Create identity
identity = janua.identities.create(
    email='user@example.com',
    password='secure-password-123'
)

# Verify session
claims = janua.sessions.verify(token)
if claims:
    print(f"Authenticated: {claims.sub}")`
    },
    go: {
      install: 'go get github.com/madfam-io/janua-go',
      setup: `// main.go
package main

import "github.com/madfam-io/janua-go"

func main() {
    client := janua.NewClient(
        janua.WithAPIKey(os.Getenv("JANUA_API_KEY")),
        janua.WithTenant(os.Getenv("JANUA_TENANT_ID")),
    )
}`,
      usage: `// Create session
session, err := client.Sessions.Create(ctx, &janua.CreateSessionRequest{
    Email:    "user@example.com",
    Password: "secure-password",
})

// Verify token
claims, err := client.Sessions.Verify(ctx, token)
if err == nil {
    log.Printf("User: %s", claims.Sub)
}`
    },
    ruby: {
      install: 'gem install janua',
      setup: `# config/initializers/janua.rb
require 'janua'

Janua.api_key = ENV['JANUA_API_KEY']
Janua.tenant = ENV['JANUA_TENANT_ID']`,
      usage: `# Create identity
identity = Janua::Identity.create(
  email: 'user@example.com',
  password: 'secure-password'
)

# Verify session
claims = Janua::Session.verify(token)
puts "Authenticated: #{claims.sub}" if claims`
    }
  }

  const timeline = [
    { time: '0:00', action: 'Install SDK', complete: true },
    { time: '1:00', action: 'Add middleware', complete: true },
    { time: '3:00', action: 'Configure environment', complete: true },
    { time: '4:00', action: 'Add UI components', complete: true },
    { time: '5:00', action: 'Deploy to production', complete: true },
  ]

  return (
    <div>
      <div className="text-center mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Ship authentication in minutes, not days
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            From zero to production-ready authentication in 5 minutes. 
            No complex configuration. No vendor lock-in. Just simple, powerful APIs.
          </p>
        </motion.div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Timeline */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-1"
        >
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            5-Minute Integration
          </h3>
          
          <div className="space-y-4">
            {timeline.map((step, index) => (
              <motion.div
                key={step.time}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: index * 0.1 }}
                className="flex items-center gap-4"
              >
                <div className="flex-shrink-0">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    step.complete 
                      ? 'bg-green-100 dark:bg-green-900/30' 
                      : 'bg-gray-100 dark:bg-gray-800'
                  }`}>
                    {step.complete ? (
                      <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-gray-400" />
                    )}
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {step.action}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {step.time}
                    </span>
                  </div>
                  {index < timeline.length - 1 && (
                    <div className="mt-4 ml-5 w-px h-8 bg-gray-200 dark:bg-gray-700" />
                  )}
                </div>
              </motion.div>
            ))}
          </div>

          <div className="mt-8 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              <strong>Pro tip:</strong> Use our CLI to generate a complete auth setup:
            </p>
            <code className="block mt-2 text-xs bg-blue-100 dark:bg-blue-900/30 p-2 rounded">
              npx create-janua-app my-app
            </code>
          </div>
        </motion.div>

        {/* Code Examples */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="lg:col-span-2"
        >
          <Tabs value={selectedLanguage} onValueChange={setSelectedLanguage}>
            <TabsList className="grid grid-cols-4 w-full mb-6">
              {languages.map((lang) => {
                const Icon = lang.icon
                return (
                  <TabsTrigger key={lang.id} value={lang.id} className="flex items-center gap-2">
                    <Icon className="h-4 w-4" />
                    {lang.name}
                  </TabsTrigger>
                )
              })}
            </TabsList>

            {Object.entries(codeExamples).map(([langId, examples]) => (
              <TabsContent key={langId} value={langId} className="space-y-6">
                {/* Install */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    1. Install
                  </h4>
                  <div className="bg-gray-900 rounded-lg p-4">
                    <code className="text-sm text-gray-300 font-mono">
                      {examples.install}
                    </code>
                  </div>
                </div>

                {/* Setup */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    2. Setup
                  </h4>
                  <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                    <pre className="text-sm text-gray-300 font-mono whitespace-pre">
                      {examples.setup}
                    </pre>
                  </div>
                </div>

                {/* Usage */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    3. Use
                  </h4>
                  <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                    <pre className="text-sm text-gray-300 font-mono whitespace-pre">
                      {examples.usage}
                    </pre>
                  </div>
                </div>
              </TabsContent>
            ))}
          </Tabs>

          {/* Features list */}
          <div className="mt-8 grid sm:grid-cols-2 gap-4">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white">
                  Type-safe SDKs
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Full TypeScript support with autocompletion
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white">
                  Framework agnostic
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Works with any stack or framework
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white">
                  Local development
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Full Docker setup for offline development
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-gray-900 dark:text-white">
                  Extensive docs
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Guides, API reference, and examples
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}