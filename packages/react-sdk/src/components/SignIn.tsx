import React from 'react'
import { SignIn as UISignIn } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface SignInProps {
  /** Callback after successful sign-in */
  onSuccess?: () => void
  /** Callback on error */
  onError?: (error: Error) => void
  /** Optional custom class name */
  className?: string
  /** Redirect URL after successful sign-in */
  redirectTo?: string
  /** Enable passkey sign-in */
  enablePasskeys?: boolean
  /** URL to sign-up page */
  signUpUrl?: string
  /** Enable social login providers */
  socialProviders?: {
    google?: boolean
    github?: boolean
    microsoft?: boolean
    apple?: boolean
  }
  /** Custom logo URL */
  logoUrl?: string
  /** Show "Remember me" checkbox */
  showRememberMe?: boolean
  /** Enable SSO email domain detection */
  enableSSO?: boolean
  /** Enable magic link option */
  enableMagicLink?: boolean
}

/**
 * SignIn component - thin wrapper around @janua/ui SignIn
 *
 * Injects the Janua client from context and maps react-sdk props
 * to @janua/ui prop names for backward compatibility.
 */
export function SignIn({
  onSuccess,
  onError,
  className,
  redirectTo,
  enablePasskeys = true,
  signUpUrl,
  socialProviders,
  logoUrl,
  showRememberMe,
  enableSSO,
  enableMagicLink,
}: SignInProps) {
  const { client } = useJanua()

  return (
    <UISignIn
      januaClient={client}
      className={className}
      redirectUrl={redirectTo}
      afterSignIn={onSuccess ? () => onSuccess() : undefined}
      onError={onError}
      enablePasskey={enablePasskeys}
      signUpUrl={signUpUrl}
      socialProviders={socialProviders}
      logoUrl={logoUrl}
      showRememberMe={showRememberMe}
      enableSSO={enableSSO}
      enableMagicLink={enableMagicLink}
    />
  )
}
