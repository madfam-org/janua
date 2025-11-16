import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { Separator } from '../separator'
import { cn } from '../../lib/utils'
import { parseApiError, formatErrorMessage, AUTH_ERRORS } from '../../lib/error-messages'

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
  /** Plinto client instance for API integration */
  plintoClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
}

export function SignUp({
  className,
  redirectUrl,
  signInUrl,
  afterSignUp,
  onError,
  appearance = { theme: 'light' },
  socialProviders = {
    google: true,
    github: true,
    microsoft: false,
    apple: false,
  },
  logoUrl,
  requireEmailVerification = true,
  showPasswordStrength = true,
  plintoClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: SignUpProps) {
  const [firstName, setFirstName] = React.useState('')
  const [lastName, setLastName] = React.useState('')
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [showPassword, setShowPassword] = React.useState(false)
  const [agreedToTerms, setAgreedToTerms] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Password strength calculation
  const calculatePasswordStrength = (pwd: string): number => {
    let strength = 0
    if (pwd.length >= 8) strength += 25
    if (pwd.length >= 12) strength += 25
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) strength += 25
    if (/\d/.test(pwd)) strength += 15
    if (/[^a-zA-Z0-9]/.test(pwd)) strength += 10
    return Math.min(strength, 100)
  }

  const passwordStrength = calculatePasswordStrength(password)
  const strengthLabel =
    passwordStrength >= 75 ? 'Strong' : passwordStrength >= 50 ? 'Medium' : 'Weak'
  const strengthColor =
    passwordStrength >= 75
      ? 'bg-green-500'
      : passwordStrength >= 50
      ? 'bg-yellow-500'
      : 'bg-red-500'

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
      if (plintoClient) {
        // Use Plinto SDK client for real API integration
        const response = await plintoClient.auth.signUp({
          email,
          password,
          firstName,
          lastName,
        })

        // SDK automatically handles token storage
        if (requireEmailVerification) {
          // Show verification message (user not fully authenticated until verified)
          setError(null)
          alert('Please check your email to verify your account')
        } else {
          afterSignUp?.(response.user)
          if (redirectUrl) {
            window.location.href = redirectUrl
          }
        }
      } else {
        // Fallback to direct fetch if SDK client not provided
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
          // Show verification message
          setError(null)
          alert('Please check your email to verify your account')
        } else {
          afterSignUp?.(data.user)
          if (redirectUrl) {
            window.location.href = redirectUrl
          }
        }
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: err instanceof Error ? err.message : undefined
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
      if (plintoClient) {
        // Use Plinto SDK for OAuth flow
        const response = await plintoClient.auth.initiateOAuth(provider, {
          redirectUrl: redirectUrl || window.location.origin,
        })
        // Redirect to OAuth provider
        window.location.href = response.url
      } else {
        // Fallback to direct URL redirect
        const oauthUrl = `${apiUrl}/api/v1/auth/oauth/${provider}?redirect_url=${encodeURIComponent(redirectUrl || window.location.origin)}`
        window.location.href = oauthUrl
      }
    } catch (err) {
      const actionableError = parseApiError(err, {
        message: `${provider} sign up failed`
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
      setIsLoading(false)
    }
  }

  const hasSocialProviders =
    socialProviders.google ||
    socialProviders.github ||
    socialProviders.microsoft ||
    socialProviders.apple

  return (
    <Card className={cn('w-full max-w-md mx-auto p-6', className)}>
      {/* Logo */}
      {logoUrl && (
        <div className="flex justify-center mb-6">
          <img src={logoUrl} alt="Logo" className="h-12" />
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold">Create your account</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Get started with your free account
        </p>
      </div>

      {/* Social Sign Up Buttons */}
      {hasSocialProviders && (
        <>
          <div className="space-y-3 mb-6">
            {socialProviders.google && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => handleSocialSignUp('google')}
                disabled={isLoading}
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Sign up with Google
              </Button>
            )}

            {socialProviders.github && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => handleSocialSignUp('github')}
                disabled={isLoading}
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                Sign up with GitHub
              </Button>
            )}
          </div>

          <div className="relative mb-6">
            <Separator />
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground">
              Or sign up with email
            </span>
          </div>
        </>
      )}

      {/* Sign Up Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Error Message */}
        {error && (
          <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
            {error}
          </div>
        )}

        {/* Name Fields */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="firstName">First name</Label>
            <Input
              id="firstName"
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
            <Label htmlFor="lastName">Last name</Label>
            <Input
              id="lastName"
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
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
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
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Create a strong password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              autoComplete="new-password"
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex={-1}
            >
              {showPassword ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                  />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                  />
                </svg>
              )}
            </button>
          </div>

          {/* Password Strength Meter */}
          {showPasswordStrength && password && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Password strength:</span>
                <span className={cn('font-medium', {
                  'text-red-500': passwordStrength < 50,
                  'text-yellow-500': passwordStrength >= 50 && passwordStrength < 75,
                  'text-green-500': passwordStrength >= 75,
                })}>
                  {strengthLabel}
                </span>
              </div>
              <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className={cn('h-full transition-all duration-300', strengthColor)}
                  style={{ width: `${passwordStrength}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Use 12+ characters with uppercase, lowercase, numbers, and symbols
              </p>
            </div>
          )}
        </div>

        {/* Terms and Conditions */}
        <div className="flex items-start">
          <input
            id="terms"
            type="checkbox"
            className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary"
            checked={agreedToTerms}
            onChange={(e) => setAgreedToTerms(e.target.checked)}
            disabled={isLoading}
            required
          />
          <Label htmlFor="terms" className="ml-2 text-sm font-normal">
            I agree to the{' '}
            <a href="/terms" className="text-primary hover:underline">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href="/privacy" className="text-primary hover:underline">
              Privacy Policy
            </a>
          </Label>
        </div>

        {/* Submit Button */}
        <Button type="submit" className="w-full" disabled={isLoading || !agreedToTerms}>
          {isLoading ? 'Creating account...' : 'Create account'}
        </Button>
      </form>

      {/* Sign In Link */}
      {signInUrl && (
        <p className="text-center text-sm text-muted-foreground mt-6">
          Already have an account?{' '}
          <a href={signInUrl} className="text-primary hover:underline font-medium">
            Sign in
          </a>
        </p>
      )}
    </Card>
  )
}
