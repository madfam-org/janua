'use client'

import * as React from 'react'
import { Eye, EyeOff, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface MaskedValueProps {
  maskedValue: string
  fullValue?: string
  onReveal: () => void
  revealed: boolean
}

export function MaskedValue({ maskedValue, fullValue, onReveal, revealed }: MaskedValueProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = async () => {
    if (fullValue) {
      await navigator.clipboard.writeText(fullValue)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="flex items-center gap-2 font-mono text-sm">
      <span className="secret-masked text-muted-foreground">
        {revealed && fullValue ? fullValue : maskedValue}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="size-6 p-0"
        onClick={revealed ? handleCopy : onReveal}
      >
        {revealed ? (
          copied ? (
            <Check className="text-primary size-3" />
          ) : (
            <Copy className="size-3" />
          )
        ) : (
          <Eye className="size-3" />
        )}
      </Button>
      {revealed && (
        <Button variant="ghost" size="sm" className="size-6 p-0" onClick={onReveal}>
          <EyeOff className="size-3" />
        </Button>
      )}
    </div>
  )
}
