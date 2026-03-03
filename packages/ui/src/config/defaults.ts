import type { JanuaAuthConfig } from './types'

/**
 * Default auth config matching current component behavior.
 * All values here preserve backward compatibility.
 */
export const defaultAuthConfig: JanuaAuthConfig = {
  branding: {
    darkMode: 'auto',
  },
  authentication: {
    emailPassword: true,
    magicLink: false,
    passkeys: false,
    socialProviders: {
      google: true,
      github: true,
      microsoft: false,
      apple: false,
    },
    sso: {
      enabled: false,
      autoDetect: false,
    },
    mfa: {
      required: false,
      methods: ['totp'],
    },
    enableJanuaSSO: false,
  },
  flows: {
    signIn: {
      layout: 'card',
      showRememberMe: true,
      forgotPasswordUrl: '/forgot-password',
    },
    signUp: {
      enabled: true,
      layout: 'card',
      requireEmailVerification: true,
      termsUrl: '/terms',
      privacyUrl: '/privacy',
    },
  },
}

/**
 * Deep merge two auth configs. Source values override target values.
 * Handles nested objects correctly.
 */
export function mergeConfig(
  target: JanuaAuthConfig,
  source: Partial<JanuaAuthConfig>,
): JanuaAuthConfig {
  const result = { ...target }

  if (source.branding) {
    result.branding = { ...target.branding, ...source.branding }
  }

  if (source.authentication) {
    result.authentication = {
      ...target.authentication,
      ...source.authentication,
      socialProviders: {
        ...target.authentication.socialProviders,
        ...source.authentication.socialProviders,
      },
    }
    if (source.authentication.sso) {
      result.authentication.sso = {
        ...target.authentication.sso,
        ...source.authentication.sso,
      }
    }
    if (source.authentication.mfa) {
      result.authentication.mfa = {
        ...target.authentication.mfa,
        ...source.authentication.mfa,
      }
    }
  }

  if (source.flows) {
    result.flows = {
      signIn: { ...target.flows.signIn, ...source.flows.signIn },
      signUp: { ...target.flows.signUp, ...source.flows.signUp },
    }
  }

  if (source.locale) {
    result.locale = { ...target.locale, ...source.locale }
  }

  return result
}
