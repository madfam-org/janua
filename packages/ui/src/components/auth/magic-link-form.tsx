import * as React from 'react'
import { Mail, Loader2 } from 'lucide-react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { cn } from '../../lib/utils'

export interface MagicLinkFormProps {
  /** Pre-fill email address */
  email?: string
  /** Janua SDK client */
  januaClient?: any
  /** API URL fallback */
  apiUrl?: string
  /** Callback on error */
  onError?: (error: Error) => void
  disabled?: boolean
  className?: string
}

/**
 * Passwordless magic link form.
 * Sends a sign-in link to the user's email.
 */
export function MagicLinkForm({
  email: initialEmail = '',
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  onError,
  disabled,
  className,
}: MagicLinkFormProps) {
  const [email, setEmail] = React.useState(initialEmail)
  const [isLoading, setIsLoading] = React.useState(false)
  const [sent, setSent] = React.useState(false)
  const [resendCooldown, setResendCooldown] = React.useState(0)

  React.useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [resendCooldown])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      if (januaClient) {
        await januaClient.auth.sendMagicLink({ email })
      } else {
        const response = await fetch(`${apiUrl}/api/v1/auth/magic-link`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        })
        if (!response.ok) {
          throw new Error('Failed to send magic link')
        }
      }
      setSent(true)
      setResendCooldown(60)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to send magic link')
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  if (sent) {
    return (
      <div
        className={cn('text-center py-6', className)}
        style={{ animation: 'janua-fade-in 300ms ease' }}
      >
        <div className="flex justify-center mb-4">
          <div className="rounded-full bg-primary/10 p-4">
            <Mail className="w-8 h-8 text-primary" />
          </div>
        </div>
        <h3 className="text-lg font-semibold mb-1">Check your email</h3>
        <p className="text-sm text-muted-foreground">
          We sent a sign-in link to{' '}
          <span className="font-medium text-foreground">{email}</span>
        </p>
        <button
          type="button"
          className="text-sm text-primary hover:underline mt-4 disabled:opacity-50"
          onClick={() => {
            setSent(false)
            handleSubmit(new Event('submit') as any)
          }}
          disabled={resendCooldown > 0}
        >
          {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend link'}
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <Label htmlFor="magic-email">Email</Label>
        <Input
          id="magic-email"
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={disabled || isLoading}
          autoComplete="email"
        />
      </div>
      <Button type="submit" className="w-full" disabled={disabled || isLoading || !email}>
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Sending...
          </>
        ) : (
          <>
            <Mail className="w-4 h-4 mr-2" />
            Send magic link
          </>
        )}
      </Button>
    </form>
  )
}
