import * as React from 'react'
import { Loader2, Mail } from 'lucide-react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Checkbox } from '../checkbox'
import { cn } from '../../lib/utils'
import { parseApiError, formatErrorMessage, AUTH_ERRORS } from '../../lib/error-messages'
import { AuthCard, type AuthCardLayout } from './auth-card'
import { SocialButton, type SocialProvider } from './social-buttons'
import { AuthDivider } from './divider'
import { PasswordInput, calculatePasswordStrength } from './password-input'

export interface SignUpProps {
  /** Optional custom class name */
  className?: string
  /** Redirect URL after successful sign-up */
  redirectUrl?: string
  /** URL to sign-in page */
  signInUrl?: string
  /** Callback after successful sign-up */
  afterSignUp?: (user: any) => void
  /** Callback on error */
  onError?: (error: Error) => void
  /** Theme customization */
  appearance?: {
    theme?: 'light' | 'dark'
    variables?: {
      colorPrimary?: string
      colorBackground?: string
      colorText?: string
    }
  }
  /** Enable/disable social login providers */
  socialProviders?: {
    google?: boolean
    github?: boolean
    microsoft?: boolean
    apple?: boolean
  }
  /** Custom logo URL */
  logoUrl?: string
  /** Require email verification */
  requireEmailVerification?: boolean
  /** Show password strength meter */
  showPasswordStrength?: boolean
  /** Janua client instance for API integration */
  januaClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
  /** Layout variant */
  layout?: AuthCardLayout
  /** Terms of Service URL */
  termsUrl?: string
  /** Privacy Policy URL */
  privacyUrl?: string
}

export function SignUp({
  className,
  redirectUrl,
  signInUrl,
  afterSignUp,
  onError,
  appearance: _appearance = { theme: 'light' },
  socialProviders = {
    google: true,
    github: true,
    microsoft: false,
    apple: false,
  },
  logoUrl,
  requireEmailVerification = true,
  showPasswordStrength = true,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  layout = 'card',
  termsUrl = '/terms',
  privacyUrl = '/privacy',
}: SignUpProps) {
  const [firstName, setFirstName] = React.useState('')
  const [lastName, setLastName] = React.useState('')
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [agreedToTerms, setAgreedToTerms] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [emailSent, setEmailSent] = React.useState(false)

  const passwordStrength = calculatePasswordStrength(password)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!agreedToTerms) {
      setError(formatErrorMessage(AUTH_ERRORS.REQUIRED_FIELD('Terms agreement'), true))
      return
    }

    if (passwordStrength < 50) {
      setError(formatErrorMessage(AUTH_ERRORS.WEAK_PASSWORD, true))
      return
    }

    setIsLoading(true)

    try {
      if (januaClient) {
        const response = await januaClient.auth.signUp({
          email,
          password,
          firstName,
          lastName,
        })

        if (requireEmailVerification) {
          setEmailSent(true)
        } else {
          afterSignUp?.(response.user)
          if (redirectUrl) {
            window.location.href = redirectUrl
          }
        }
      } else {
        const response = await fetch(`${apiUrl}/api/v1/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            email,
            password,
            firstName,
            lastName,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          const actionableError = parseApiError(errorData, { status: response.status })
          setError(formatErrorMessage(actionableError, true))
          onError?.(new Error(actionableError.message))
          setIsLoading(false)
          return
        }

        const data = await response.json()

        if (requireEmailVerification) {
          setEmailSent(true)
        } else {
          afterSignUp?.(data.user)
          if (redirectUrl) {
            window.location.href = redirectUrl
          }
        }
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: err instanceof Error ? err.message : undefined,
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
    } finally {
      setIsLoading(false)
    }
  }

  const handleSocialSignUp = async (provider: string) => {
    setIsLoading(true)
    try {
      if (januaClient) {
        const response = await januaClient.auth.initiateOAuth(provider, {
          redirectUrl: redirectUrl || window.location.origin,
        })
        window.location.href = response.url
      } else {
        const oauthUrl = `${apiUrl}/api/v1/auth/oauth/${provider}?redirect_url=${encodeURIComponent(redirectUrl || window.location.origin)}`
        window.location.href = oauthUrl
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: `${provider} sign up failed`,
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
      setIsLoading(false)
    }
  }

  const socialProviderList: SocialProvider[] = []
  if (socialProviders.google) socialProviderList.push('google')
  if (socialProviders.github) socialProviderList.push('github')
  if (socialProviders.microsoft) socialProviderList.push('microsoft')
  if (socialProviders.apple) socialProviderList.push('apple')

  const hasSocialProviders = socialProviderList.length > 0

  // Email verification success state
  if (emailSent) {
    return (
      <AuthCard layout={layout} logo={logoUrl} className={className}>
        <div
          className="text-center py-8"
          style={{ animation: 'janua-fade-in 400ms ease' }}
        >
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-primary/10 p-4">
              <Mail className="w-8 h-8 text-primary" />
            </div>
          </div>
          <h2 className="text-2xl font-bold mb-2">Check your email</h2>
          <p className="text-sm text-muted-foreground">
            We&apos;ve sent a verification link to{' '}
            <span className="font-medium text-foreground">{email}</span>
          </p>
          <p className="text-xs text-muted-foreground mt-4">
            Didn&apos;t receive the email? Check your spam folder.
          </p>
        </div>
      </AuthCard>
    )
  }

  const header = (
    <div className="text-center mb-6" style={{ animation: 'janua-fade-in 300ms ease' }}>
      <h2 className="text-2xl font-bold">Create your account</h2>
      <p className="text-sm text-muted-foreground mt-1">
        Get started with your free account
      </p>
    </div>
  )

  const footer = signInUrl ? (
    <p className="text-center text-sm text-muted-foreground mt-6">
      Already have an account?{' '}
      <a href={signInUrl} className="text-primary hover:underline font-medium">
        Sign in
      </a>
    </p>
  ) : undefined

  return (
    <AuthCard layout={layout} logo={logoUrl} header={header} footer={footer} className={className}>
      {/* Social Sign Up Buttons */}
      {hasSocialProviders && (
        <>
          <div className="space-y-2.5 mb-6">
            {socialProviderList.map((provider, i) => (
              <SocialButton
                key={provider}
                provider={provider}
                onClick={() => handleSocialSignUp(provider)}
                disabled={isLoading}
                label={`Sign up with ${provider.charAt(0).toUpperCase() + provider.slice(1)}`}
                animationIndex={i}
              />
            ))}
          </div>
          <AuthDivider label="Or sign up with email" />
        </>
      )}

      {/* Sign Up Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Error Message */}
        {error && (
          <div
            className="bg-destructive/15 text-destructive text-sm p-3 rounded-md"
            style={{ animation: 'janua-slide-up 200ms ease, janua-shake 400ms ease' }}
          >
            {error}
          </div>
        )}

        {/* Name Fields */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="signup-firstName">First name</Label>
            <Input
              id="signup-firstName"
              type="text"
              placeholder="John"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              disabled={isLoading}
              autoComplete="given-name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="signup-lastName">Last name</Label>
            <Input
              id="signup-lastName"
              type="text"
              placeholder="Doe"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              disabled={isLoading}
              autoComplete="family-name"
            />
          </div>
        </div>

        {/* Email Input */}
        <div className="space-y-2">
          <Label htmlFor="signup-email">Email</Label>
          <Input
            id="signup-email"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isLoading}
            autoComplete="email"
          />
        </div>

        {/* Password Input with Strength Meter */}
        <PasswordInput
          id="signup-password"
          value={password}
          onChange={setPassword}
          placeholder="Create a strong password"
          disabled={isLoading}
          autoComplete="new-password"
          showStrength={showPasswordStrength}
        />

        {/* Terms and Conditions */}
        <div className="flex items-start gap-2">
          <Checkbox
            id="signup-terms"
            checked={agreedToTerms}
            onCheckedChange={(checked) => setAgreedToTerms(checked === true)}
            disabled={isLoading}
            className="mt-0.5"
          />
          <Label htmlFor="signup-terms" className="text-sm font-normal cursor-pointer">
            I agree to the{' '}
            <a href={termsUrl} className="text-primary hover:underline">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href={privacyUrl} className="text-primary hover:underline">
              Privacy Policy
            </a>
          </Label>
        </div>

        {/* Submit Button */}
        <Button type="submit" className="w-full" disabled={isLoading || !agreedToTerms}>
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Creating account...
            </>
          ) : (
            'Create account'
          )}
        </Button>
      </form>
    </AuthCard>
  )
}
