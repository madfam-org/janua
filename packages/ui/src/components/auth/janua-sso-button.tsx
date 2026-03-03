import * as React from 'react'
import { JanuaSSOButton as JanuaSSOButtonBase } from './social-buttons'

export interface JanuaSSOButtonProps {
  /** OAuth redirect URL — defaults to current origin */
  redirectUrl?: string
  /** Janua SDK client instance */
  januaClient?: any
  /** API URL fallback */
  apiUrl?: string
  disabled?: boolean
  className?: string
}

/**
 * "Sign in with Janua" button for MADFAM ecosystem apps.
 * Initiates OAuth flow against Janua as IdP.
 */
export function JanuaSSOLoginButton({
  redirectUrl,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  disabled,
  className,
}: JanuaSSOButtonProps) {
  const [isLoading, setIsLoading] = React.useState(false)

  const handleClick = async () => {
    setIsLoading(true)
    try {
      if (januaClient) {
        const response = await januaClient.auth.initiateOAuth('janua', {
          redirectUrl: redirectUrl || window.location.origin,
        })
        window.location.href = response.url
      } else {
        const target = redirectUrl || window.location.origin
        const oauthUrl = `${apiUrl}/api/v1/auth/oauth/janua?redirect_url=${encodeURIComponent(target)}`
        window.location.href = oauthUrl
      }
    } catch {
      setIsLoading(false)
    }
  }

  return (
    <JanuaSSOButtonBase
      onClick={handleClick}
      disabled={disabled || isLoading}
      className={className}
      label={isLoading ? 'Redirecting...' : 'Sign in with Janua'}
    />
  )
}
