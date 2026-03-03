import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { Input } from '../input'
import { Label } from '../label'
import { Button } from '../button'
import { cn } from '../../lib/utils'

export interface SSOEmailDetectorProps {
  /** Callback when no SSO org found — expand to password form */
  onEmailSubmit: (email: string) => void
  /** Callback when SSO org is detected */
  onSSODetected: (domain: string, orgName?: string) => void
  /** API URL for domain detection */
  apiUrl?: string
  /** Janua SDK client */
  januaClient?: any
  disabled?: boolean
  className?: string
}

/**
 * Email-first SSO detection component.
 * User enters email → checks domain against API →
 * if SSO org found: show redirect message
 * if not: calls onEmailSubmit to expand into password form
 */
export function SSOEmailDetector({
  onEmailSubmit,
  onSSODetected,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  januaClient,
  disabled,
  className,
}: SSOEmailDetectorProps) {
  const [email, setEmail] = React.useState('')
  const [isChecking, setIsChecking] = React.useState(false)
  const [ssoOrg, setSSOOrg] = React.useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.includes('@')) return

    const domain = email.split('@')[1]
    setIsChecking(true)

    try {
      let orgName: string | undefined

      if (januaClient) {
        const result = await januaClient.sso?.checkDomain?.(domain)
        if (result?.ssoEnabled) {
          orgName = result.organizationName
        }
      } else {
        const response = await fetch(
          `${apiUrl}/api/v1/auth/sso/check-domain?domain=${encodeURIComponent(domain)}`,
        )
        if (response.ok) {
          const data = await response.json()
          if (data.sso_enabled) {
            orgName = data.organization_name
          }
        }
      }

      if (orgName) {
        setSSOOrg(orgName)
        onSSODetected(domain, orgName)
      } else {
        onEmailSubmit(email)
      }
    } catch {
      // On error, fall through to password form
      onEmailSubmit(email)
    } finally {
      setIsChecking(false)
    }
  }

  if (ssoOrg) {
    return (
      <div
        className={cn('text-center py-4', className)}
        style={{ animation: 'janua-fade-in 300ms ease' }}
      >
        <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3 text-primary" />
        <p className="text-sm font-medium">
          Redirecting to {ssoOrg} SSO...
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {email}
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <Label htmlFor="sso-email">Email</Label>
        <Input
          id="sso-email"
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={disabled || isChecking}
          autoComplete="email"
          autoFocus
        />
      </div>
      <Button type="submit" className="w-full" disabled={disabled || isChecking || !email}>
        {isChecking ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Checking...
          </>
        ) : (
          'Continue'
        )}
      </Button>
    </form>
  )
}
