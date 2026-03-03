/**
 * JanuaAuthConfig — Runtime configuration for auth UI components.
 * Can be provided statically or fetched from the Janua API.
 */
export interface JanuaAuthConfig {
  branding: {
    /** URL to logo image */
    logoUrl?: string
    /** Application name displayed in headers */
    appName?: string
    /** Primary brand color (hex or HSL) */
    primaryColor?: string
    /** Theme preset name */
    themePreset?: string
    /** Dark mode strategy */
    darkMode?: 'auto' | 'light' | 'dark'
  }
  authentication: {
    /** Enable email/password login */
    emailPassword: boolean
    /** Enable passwordless magic link */
    magicLink?: boolean
    /** Enable WebAuthn passkey login */
    passkeys?: boolean
    /** Social OAuth providers */
    socialProviders: {
      google?: boolean
      github?: boolean
      microsoft?: boolean
      apple?: boolean
    }
    /** SSO configuration */
    sso?: {
      /** Enable SSO login */
      enabled: boolean
      /** Auto-detect SSO by email domain */
      autoDetect?: boolean
    }
    /** MFA configuration */
    mfa?: {
      /** Require MFA for all users */
      required?: boolean
      /** Allowed MFA methods */
      methods?: ('totp' | 'sms')[]
    }
    /** Enable "Sign in with Janua" for MADFAM ecosystem */
    enableJanuaSSO?: boolean
  }
  flows: {
    signIn: {
      /** Layout variant */
      layout?: 'card' | 'modal' | 'page'
      /** Show "Remember me" checkbox */
      showRememberMe?: boolean
      /** Forgot password URL */
      forgotPasswordUrl?: string
      /** Redirect URL after login */
      redirectUrl?: string
      /** Custom header text */
      headerText?: string
      /** Custom header description */
      headerDescription?: string
    }
    signUp: {
      /** Enable sign-up (false to disable registration) */
      enabled: boolean
      /** Layout variant */
      layout?: 'card' | 'modal' | 'page'
      /** Require email verification after sign-up */
      requireEmailVerification?: boolean
      /** Terms of Service URL */
      termsUrl?: string
      /** Privacy Policy URL */
      privacyUrl?: string
    }
  }
  locale?: {
    /** Override sign-in page title */
    signInTitle?: string
    /** Override sign-in page description */
    signInDescription?: string
    /** Override sign-up page title */
    signUpTitle?: string
    /** Override sign-up page description */
    signUpDescription?: string
  }
}
