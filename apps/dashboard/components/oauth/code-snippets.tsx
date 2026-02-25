'use client'

import { useState } from 'react'
import { Button } from '@janua/ui'
import { Copy, CheckCircle2 } from 'lucide-react'

interface CodeSnippetsProps {
  clientId: string
  redirectUri: string
}

type SdkTab = 'react' | 'nextjs' | 'vue' | 'python' | 'go'

const TAB_LABELS: Record<SdkTab, string> = {
  react: 'React',
  nextjs: 'Next.js',
  vue: 'Vue',
  python: 'Python',
  go: 'Go',
}

function getSnippet(tab: SdkTab, clientId: string, redirectUri: string): string {
  switch (tab) {
    case 'react':
      return `import { JanuaClient } from '@janua/react-sdk'

const januaClient = new JanuaClient({
  baseURL: '${process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'}',
  clientId: '${clientId}',
  redirectUri: '${redirectUri}',
})

// In your component:
function LoginButton() {
  const handleLogin = () => {
    januaClient.auth.signInWithOAuth({
      provider: 'custom',
      clientId: '${clientId}',
      redirectUri: '${redirectUri}',
    })
  }

  return <button onClick={handleLogin}>Sign In</button>
}`

    case 'nextjs':
      return `// app/lib/janua.ts
import { JanuaClient } from '@janua/nextjs-sdk'

export const januaClient = new JanuaClient({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '${process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'}',
  clientId: '${clientId}',
  redirectUri: '${redirectUri}',
})

// app/api/auth/callback/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { januaClient } from '@/lib/janua'

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code')
  if (!code) return NextResponse.redirect('/login?error=no_code')

  const tokens = await januaClient.auth.exchangeCode({
    code,
    clientId: '${clientId}',
    redirectUri: '${redirectUri}',
  })

  // Store tokens and redirect
  return NextResponse.redirect('/')
}`

    case 'vue':
      return `// composables/useJanua.ts
import { createJanuaClient } from '@janua/vue-sdk'

export const januaClient = createJanuaClient({
  baseURL: '${process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'}',
  clientId: '${clientId}',
  redirectUri: '${redirectUri}',
})

// In your component:
<script setup>
import { januaClient } from '@/composables/useJanua'

function handleLogin() {
  januaClient.auth.signInWithOAuth({
    provider: 'custom',
    clientId: '${clientId}',
    redirectUri: '${redirectUri}',
  })
}
</script>

<template>
  <button @click="handleLogin">Sign In</button>
</template>`

    case 'python':
      return `from janua import JanuaClient

client = JanuaClient(
    base_url="${process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'}",
    client_id="${clientId}",
    client_secret="YOUR_CLIENT_SECRET",  # Keep secret server-side only
)

# Exchange authorization code for tokens
tokens = client.auth.exchange_code(
    code=authorization_code,
    redirect_uri="${redirectUri}",
)

# Use the access token
user = client.auth.get_current_user(access_token=tokens.access_token)`

    case 'go':
      return `package main

import (
    "fmt"
    janua "github.com/madfam-org/janua/packages/go-sdk"
)

func main() {
    client := janua.NewClient(janua.Config{
        BaseURL:      "${process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'}",
        ClientID:     "${clientId}",
        ClientSecret: "YOUR_CLIENT_SECRET", // Keep secret server-side only
    })

    // Exchange authorization code for tokens
    tokens, err := client.Auth.ExchangeCode(ctx, janua.ExchangeCodeParams{
        Code:        authorizationCode,
        RedirectURI: "${redirectUri}",
    })
    if err != nil {
        fmt.Printf("Error: %v\\n", err)
        return
    }

    fmt.Printf("Access Token: %s\\n", tokens.AccessToken)
}`
  }
}

export function CodeSnippets({ clientId, redirectUri }: CodeSnippetsProps) {
  const [activeTab, setActiveTab] = useState<SdkTab>('react')
  const [copied, setCopied] = useState(false)

  const snippet = getSnippet(activeTab, clientId, redirectUri)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea')
      textarea.value = snippet
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Integration Code</h4>
        <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 gap-1.5 text-xs">
          {copied ? (
            <>
              <CheckCircle2 className="size-3 text-green-600" />
              Copied
            </>
          ) : (
            <>
              <Copy className="size-3" />
              Copy
            </>
          )}
        </Button>
      </div>

      <div className="flex gap-1 rounded-lg border p-1">
        {(Object.keys(TAB_LABELS) as SdkTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              activeTab === tab
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            }`}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      <pre className="bg-muted max-h-64 overflow-auto rounded-lg border p-3 text-xs">
        <code>{snippet}</code>
      </pre>
    </div>
  )
}
