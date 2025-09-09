'use client'

import { useState, useEffect } from 'react'
import { PlintoClient } from '@plinto/sdk'

const plintoClient = new PlintoClient({
  issuer: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000',
  clientId: 'demo-client',
  redirectUri: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3002',
})

export function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Initialize Plinto SDK
    if (typeof window !== 'undefined') {
      (window as any).plinto = plintoClient
    }
  }, [])

  if (!mounted) {
    return null
  }

  return <>{children}</>
}