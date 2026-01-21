'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'

export function VaultSection() {
  // Dynamic import to avoid SSR issues with the vault component
  const [VaultComponent, setVaultComponent] = useState<React.ComponentType | null>(null)

  useEffect(() => {
    import('@/components/vault/ecosystem-vault').then((mod) => {
      setVaultComponent(() => mod.EcosystemVault)
    })
  }, [])

  if (!VaultComponent) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    )
  }

  return <VaultComponent />
}
