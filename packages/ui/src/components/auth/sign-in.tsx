import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Checkbox } from '../checkbox'
import { cn } from '../../lib/utils'
import { parseApiError, formatErrorMessage } from '../../lib/error-messages'
import { AuthCard, type AuthCardLayout } from './auth-card'
import { SocialButton, type SocialProvider } from './social-buttons'
import { AuthDivider } from './divider'
import { PasswordInput } from './password-input'

export interface SignInProps {
  /** Optional custom class name */
  className?: string
  /** Redirect URL after successful sign-in */
  redirectUrl?: string
  /** URL to sign-up page */
  signUpUrl?: string
  /** Callback after successful sign-in */
  afterSignIn?: (user: any) => void
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
  /** Show "Remember me" checkbox */
  showRememberMe?: boolean
  /** Janua client instance for API integration */
  januaClient?: any
  /** API URL for direct fetch calls (fallback if no client provided) */
  apiUrl?: string
  /** Layout variant */
  layout?: AuthCardLayout
  /** Show passkey sign-in button */
  enablePasskey?: boolean
  /** Show SSO email domain detection */
  enableSSO?: boolean
  /** Callback when SSO domain is detected */
  onSSODetected?: (domain: string) => void
  /** Show magic link option */
  enableMagicLink?: boolean
  /** Show "Sign in with Janua" button for MADFAM apps */
  enableJanuaSSO?: boolean
  /** Callback when API returns MFA challenge */
  onMFARequired?: (session: any) => void
  /** Custom header text */
  headerText?: string
  /** Custom header description */
  headerDescription?: string
  /** Configurable forgot password URL */
  forgotPasswordUrl?: string
  /** Terms of Service URL */
  termsUrl?: string
  /** Privacy Policy URL */
  privacyUrl?: string
  /** Show email/password form (default true). Set false for SSO-only configs */
  showEmailPassword?: boolean
}

export function SignIn({
  className,
  redirectUrl,
  signUpUrl,
  afterSignIn,
  onError,
  appearance: _appearance = { theme: 'light' },
  socialProviders = {
    google: true,
    github: true,
    microsoft: false,
    apple: false,
  },
  logoUrl,
  showRememberMe = true,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  layout = 'card',
  enablePasskey = false,
  enableSSO = false,
  onSSODetected,
  enableMagicLink = false,
  enableJanuaSSO = false,
  onMFARequired,
  headerText = 'Sign in to your account',
  headerDescription = 'Welcome back! Please enter your details',
  forgotPasswordUrl = '/forgot-password',
  termsUrl = '/terms',
  privacyUrl = '/privacy',
  showEmailPassword = true,
}: SignInProps) {
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [remember, setRemember] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      if (januaClient) {
        const response = await januaClient.auth.signIn({
          email,
          password,
          remember,
        })

        // Check if MFA is required
        if (response.mfaRequired && onMFARequired) {
          onMFARequired(response)
          setIsLoading(false)
          return
        }

        afterSignIn?.(response.user)

        if (redirectUrl) {
          window.location.href = redirectUrl
        }
      } else {
        const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password, remember }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))

          // Check for MFA challenge response
          if (response.status === 403 && errorData.mfa_required && onMFARequired) {
            onMFARequired(errorData)
            setIsLoading(false)
            return
          }

          const actionableError = parseApiError(errorData, { status: response.status })
          setError(formatErrorMessage(actionableError, true))
          onError?.(new Error(actionableError.message))
          setIsLoading(false)
          return
        }

        const data = await response.json()
        afterSignIn?.(data.user)

        if (redirectUrl) {
          window.location.href = redirectUrl
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

  const handleSocialLogin = async (provider: string) => {
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
        message: `${provider} authentication failed`,
      })
      setError(formatErrorMessage(actionableError, true))
      onError?.(new Error(actionableError.message))
      setIsLoading(false)
    }
  }

  // SSO email domain detection
  const handleEmailBlur = React.useCallback(() => {
    if (!enableSSO || !onSSODetected || !email.includes('@')) return
    const domain = email.split('@')[1]
    if (domain) {
      onSSODetected(domain)
    }
  }, [email, enableSSO, onSSODetected])

  const socialProviderList: SocialProvider[] = []
  if (socialProviders.google) socialProviderList.push('google')
  if (socialProviders.github) socialProviderList.push('github')
  if (socialProviders.microsoft) socialProviderList.push('microsoft')
  if (socialProviders.apple) socialProviderList.push('apple')
  if (enableJanuaSSO) socialProviderList.push('janua')

  const hasSocialProviders = socialProviderList.length > 0

  const header = (
    <div className="text-center mb-6" style={{ animation: 'janua-fade-in 300ms ease' }}>
      <h2 className="text-2xl font-bold">{headerText}</h2>
      <p className="text-sm text-muted-foreground mt-1">{headerDescription}</p>
    </div>
  )

  const footer = signUpUrl ? (
    <p className="text-center text-sm text-muted-foreground mt-6">
      Don&apos;t have an account?{' '}
      <a href={signUpUrl} className="text-primary hover:underline font-medium">
        Sign up
      </a>
    </p>
  ) : undefined

  return (
    <AuthCard layout={layout} logo={logoUrl} header={header} footer={footer} className={className}>
      {/* Social Login Buttons */}
      {hasSocialProviders && (
        <>
          <div className="space-y-2.5 mb-6">
            {socialProviderList.map((provider, i) => (
              <SocialButton
                key={provider}
                provider={provider}
                onClick={() => handleSocialLogin(provider)}
                disabled={isLoading}
                animationIndex={i}
              />
            ))}
          </div>
          {showEmailPassword && <AuthDivider label="Or continue with email" />}
        </>
      )}

      {/* Email/Password Form */}
      {showEmailPassword && <form onSubmit={handleSubmit} className="space-y-4">
        {/* Error Message */}
        {error && (
          <div
            className="bg-destructive/15 text-destructive text-sm p-3 rounded-md"
            style={{ animation: 'janua-slide-up 200ms ease, janua-shake 400ms ease' }}
          >
            {error}
          </div>
        )}

        {/* Email Input */}
        <div className="space-y-2">
          <Label htmlFor="signin-email">Email</Label>
          <Input
            id="signin-email"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={handleEmailBlur}
            required
            disabled={isLoading}
            autoComplete="email"
          />
        </div>

        {/* Password Input */}
        <PasswordInput
          id="signin-password"
          value={password}
          onChange={setPassword}
          disabled={isLoading}
          autoComplete="current-password"
          labelAction={
            <a
              href={forgotPasswordUrl}
              className="text-sm text-primary hover:underline"
              tabIndex={-1}
            >
              Forgot password?
            </a>
          }
        />

        {/* Remember Me */}
        {showRememberMe && (
          <div className="flex items-center gap-2">
            <Checkbox
              id="signin-remember"
              checked={remember}
              onCheckedChange={(checked) => setRemember(checked === true)}
              disabled={isLoading}
            />
            <Label htmlFor="signin-remember" className="text-sm font-normal cursor-pointer">
              Remember me for 30 days
            </Label>
          </div>
        )}

        {/* Submit Button */}
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Signing in...
            </>
          ) : (
            'Sign in'
          )}
        </Button>

        {/* Passkey Button */}
        {enablePasskey && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            disabled={isLoading}
            onClick={() => {
              // Passkey auth handled by PasskeyButton component in Phase 5
              // Placeholder for direct integration
            }}
          >
            Sign in with Passkey
          </Button>
        )}

        {/* Magic Link Toggle */}
        {enableMagicLink && (
          <div className="text-center">
            <button
              type="button"
              className="text-sm text-primary hover:underline"
              disabled={isLoading}
              onClick={() => {
                // Magic link handled by MagicLinkForm component in Phase 5
              }}
            >
              Email me a sign-in link
            </button>
          </div>
        )}
      </form>}

      {/* Legal Links */}
      <p className="text-center text-xs text-muted-foreground mt-6">
        By continuing, you agree to the{' '}
        <a href={termsUrl} className="underline hover:text-foreground" target="_blank" rel="noopener noreferrer">
          Terms of Service
        </a>{' '}
        and{' '}
        <a href={privacyUrl} className="underline hover:text-foreground" target="_blank" rel="noopener noreferrer">
          Privacy Policy
        </a>
        .
      </p>

      {/* Powered by Janua */}
      <p className="text-center text-xs text-muted-foreground mt-3 opacity-60">
        Powered by Janua
      </p>
    </AuthCard>
  )
}
