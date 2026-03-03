import React from 'react'
import { SignUp as UISignUp } from '@janua/ui/components/auth'
import { useJanua } from '../provider'

export interface SignUpProps {
  /** Callback after successful sign-up */
  onSuccess?: () => void
  /** Callback on error */
  onError?: (error: Error) => void
  /** Optional custom class name */
  className?: string
  /** Redirect URL after successful sign-up */
  redirectTo?: string
  /** Require organization name during sign-up */
  requireOrganization?: boolean
  /** Require email verification after sign-up */
  requireEmailVerification?: boolean
  /** URL to sign-in page */
  signInUrl?: string
  /** Enable social login providers */
  socialProviders?: {
    google?: boolean
    github?: boolean
    microsoft?: boolean
    apple?: boolean
  }
  /** Custom logo URL */
  logoUrl?: string
  /** Show password strength meter */
  showPasswordStrength?: boolean
}

/**
 * SignUp component - thin wrapper around @janua/ui SignUp
 *
 * Injects the Janua client from context and maps react-sdk props
 * to @janua/ui prop names for backward compatibility.
 */
export function SignUp({
  onSuccess,
  onError,
  className,
  redirectTo,
  requireEmailVerification = false,
  signInUrl,
  socialProviders,
  logoUrl,
  showPasswordStrength,
}: SignUpProps) {
  const { client } = useJanua()

  return (
    <UISignUp
      januaClient={client}
      className={className}
      redirectUrl={redirectTo}
      afterSignUp={onSuccess ? () => onSuccess() : undefined}
      onError={onError}
      requireEmailVerification={requireEmailVerification}
      signInUrl={signInUrl}
      socialProviders={socialProviders}
      logoUrl={logoUrl}
      showPasswordStrength={showPasswordStrength}
    />
  )
}
