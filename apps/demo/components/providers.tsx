'use client'

import { useState, useEffect } from 'react'
import { PlintoClient } from '@plinto/sdk'
import { useApiConfig } from '@/hooks/useEnvironment'

export function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false)
  const [plintoClient, setPlintoClient] = useState<PlintoClient | null>(null)
  const apiConfig = useApiConfig()

  useEffect(() => {
    setMounted(true)
    
    // Create environment-aware Plinto client
    const client = new PlintoClient({
      apiKey: 'demo-api-key',
      tenantId: 'demo-tenant',
      baseUrl: apiConfig.apiUrl,
    })

    setPlintoClient(client)
    
    // Initialize Plinto SDK
    if (typeof window !== 'undefined') {
      (window as any).plinto = client
    }
  }, [apiConfig])

  if (!mounted || !plintoClient) {
    return null
  }

  return <>{children}</>
}