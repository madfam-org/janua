import * as reactSdk from './index'

describe('@janua/react-sdk barrel exports', () => {
  it('should export the module', () => {
    expect(module).toBeDefined()
  })

  // Provider and main hook
  describe('Provider exports', () => {
    it('should export JanuaProvider', () => {
      expect(reactSdk.JanuaProvider).toBeDefined()
      expect(typeof reactSdk.JanuaProvider).toBe('function')
    })

    it('should export useJanua hook', () => {
      expect(reactSdk.useJanua).toBeDefined()
      expect(typeof reactSdk.useJanua).toBe('function')
    })
  })

  // Specialized hooks
  describe('Hook exports', () => {
    it('should export useAuth', () => {
      expect(reactSdk.useAuth).toBeDefined()
      expect(typeof reactSdk.useAuth).toBe('function')
    })

    it('should export useSession', () => {
      expect(reactSdk.useSession).toBeDefined()
      expect(typeof reactSdk.useSession).toBe('function')
    })

    it('should export useUser', () => {
      expect(reactSdk.useUser).toBeDefined()
      expect(typeof reactSdk.useUser).toBe('function')
    })

    it('should export useOrganization', () => {
      expect(reactSdk.useOrganization).toBeDefined()
      expect(typeof reactSdk.useOrganization).toBe('function')
    })

    it('should export usePasskey', () => {
      expect(reactSdk.usePasskey).toBeDefined()
      expect(typeof reactSdk.usePasskey).toBe('function')
    })

    it('should export useMFA', () => {
      expect(reactSdk.useMFA).toBeDefined()
      expect(typeof reactSdk.useMFA).toBe('function')
    })

    it('should export useRealtime', () => {
      expect(reactSdk.useRealtime).toBeDefined()
      expect(typeof reactSdk.useRealtime).toBe('function')
    })
  })

  // Components
  describe('Component exports', () => {
    it('should export SignIn', () => {
      expect(reactSdk.SignIn).toBeDefined()
      expect(typeof reactSdk.SignIn).toBe('function')
    })

    it('should export SignUp', () => {
      expect(reactSdk.SignUp).toBeDefined()
      expect(typeof reactSdk.SignUp).toBe('function')
    })

    it('should export UserProfile', () => {
      expect(reactSdk.UserProfile).toBeDefined()
      expect(typeof reactSdk.UserProfile).toBe('function')
    })

    it('should export UserButton', () => {
      expect(reactSdk.UserButton).toBeDefined()
      expect(typeof reactSdk.UserButton).toBe('function')
    })

    it('should export Protect', () => {
      expect(reactSdk.Protect).toBeDefined()
      expect(typeof reactSdk.Protect).toBe('function')
    })

    it('should export AuthGuard', () => {
      expect(reactSdk.AuthGuard).toBeDefined()
      expect(typeof reactSdk.AuthGuard).toBe('function')
    })

    it('should export OrgSwitcher', () => {
      expect(reactSdk.OrgSwitcher).toBeDefined()
      expect(typeof reactSdk.OrgSwitcher).toBe('function')
    })

    it('should export SignedIn', () => {
      expect(reactSdk.SignedIn).toBeDefined()
      expect(typeof reactSdk.SignedIn).toBe('function')
    })

    it('should export SignedOut', () => {
      expect(reactSdk.SignedOut).toBeDefined()
      expect(typeof reactSdk.SignedOut).toBe('function')
    })

    it('should export MFAChallenge', () => {
      expect(reactSdk.MFAChallenge).toBeDefined()
      expect(typeof reactSdk.MFAChallenge).toBe('function')
    })
  })

  // PKCE utilities (the exports that caused the original crash)
  describe('PKCE utility exports', () => {
    it('should export generateCodeVerifier', () => {
      expect(reactSdk.generateCodeVerifier).toBeDefined()
      expect(typeof reactSdk.generateCodeVerifier).toBe('function')
    })

    it('should export generateCodeChallenge', () => {
      expect(reactSdk.generateCodeChallenge).toBeDefined()
      expect(typeof reactSdk.generateCodeChallenge).toBe('function')
    })

    it('should export generateState', () => {
      expect(reactSdk.generateState).toBeDefined()
      expect(typeof reactSdk.generateState).toBe('function')
    })

    it('should export storePKCEParams', () => {
      expect(reactSdk.storePKCEParams).toBeDefined()
      expect(typeof reactSdk.storePKCEParams).toBe('function')
    })

    it('should export retrievePKCEParams', () => {
      expect(reactSdk.retrievePKCEParams).toBeDefined()
      expect(typeof reactSdk.retrievePKCEParams).toBe('function')
    })

    it('should export clearPKCEParams', () => {
      expect(reactSdk.clearPKCEParams).toBeDefined()
      expect(typeof reactSdk.clearPKCEParams).toBe('function')
    })

    it('should export validateState', () => {
      expect(reactSdk.validateState).toBeDefined()
      expect(typeof reactSdk.validateState).toBe('function')
    })

    it('should export parseOAuthCallback', () => {
      expect(reactSdk.parseOAuthCallback).toBeDefined()
      expect(typeof reactSdk.parseOAuthCallback).toBe('function')
    })

    it('should export buildAuthorizationUrl', () => {
      expect(reactSdk.buildAuthorizationUrl).toBeDefined()
      expect(typeof reactSdk.buildAuthorizationUrl).toBe('function')
    })
  })

  // Error utilities
  describe('Error utility exports', () => {
    it('should export createErrorState', () => {
      expect(reactSdk.createErrorState).toBeDefined()
      expect(typeof reactSdk.createErrorState).toBe('function')
    })

    it('should export mapErrorToState', () => {
      expect(reactSdk.mapErrorToState).toBeDefined()
      expect(typeof reactSdk.mapErrorToState).toBe('function')
    })

    it('should export isAuthRequiredError', () => {
      expect(reactSdk.isAuthRequiredError).toBeDefined()
      expect(typeof reactSdk.isAuthRequiredError).toBe('function')
    })

    it('should export isNetworkIssue', () => {
      expect(reactSdk.isNetworkIssue).toBeDefined()
      expect(typeof reactSdk.isNetworkIssue).toBe('function')
    })

    it('should export getUserFriendlyMessage', () => {
      expect(reactSdk.getUserFriendlyMessage).toBeDefined()
      expect(typeof reactSdk.getUserFriendlyMessage).toBe('function')
    })

    it('should export ReactJanuaError class', () => {
      expect(reactSdk.ReactJanuaError).toBeDefined()
      expect(typeof reactSdk.ReactJanuaError).toBe('function')
    })
  })

  // Error classes re-exported from typescript-sdk
  describe('Error class re-exports from typescript-sdk', () => {
    it('should export JanuaError', () => {
      expect(reactSdk.JanuaError).toBeDefined()
      expect(typeof reactSdk.JanuaError).toBe('function')
    })

    it('should export AuthenticationError', () => {
      expect(reactSdk.AuthenticationError).toBeDefined()
      expect(typeof reactSdk.AuthenticationError).toBe('function')
    })

    it('should export ValidationError', () => {
      expect(reactSdk.ValidationError).toBeDefined()
      expect(typeof reactSdk.ValidationError).toBe('function')
    })

    it('should export NetworkError', () => {
      expect(reactSdk.NetworkError).toBeDefined()
      expect(typeof reactSdk.NetworkError).toBe('function')
    })

    it('should export TokenError', () => {
      expect(reactSdk.TokenError).toBeDefined()
      expect(typeof reactSdk.TokenError).toBe('function')
    })

    it('should export OAuthError', () => {
      expect(reactSdk.OAuthError).toBeDefined()
      expect(typeof reactSdk.OAuthError).toBe('function')
    })

    it('should export OAuthProvider', () => {
      expect(reactSdk.OAuthProvider).toBeDefined()
    })

    it('should export error type guards', () => {
      expect(reactSdk.isAuthenticationError).toBeDefined()
      expect(typeof reactSdk.isAuthenticationError).toBe('function')
      expect(reactSdk.isValidationError).toBeDefined()
      expect(typeof reactSdk.isValidationError).toBe('function')
      expect(reactSdk.isNetworkError).toBeDefined()
      expect(typeof reactSdk.isNetworkError).toBe('function')
      expect(reactSdk.isJanuaError).toBeDefined()
      expect(typeof reactSdk.isJanuaError).toBe('function')
    })
  })

  // Storage key constants
  describe('Storage key exports', () => {
    it('should export STORAGE_KEYS', () => {
      expect(reactSdk.STORAGE_KEYS).toBeDefined()
      expect(typeof reactSdk.STORAGE_KEYS).toBe('object')
    })

    it('should export PKCE_STORAGE_KEYS', () => {
      expect(reactSdk.PKCE_STORAGE_KEYS).toBeDefined()
      expect(typeof reactSdk.PKCE_STORAGE_KEYS).toBe('object')
    })
  })

  // Version constants
  describe('Version exports', () => {
    it('should export SDK_VERSION', () => {
      expect(reactSdk.SDK_VERSION).toBeDefined()
      expect(typeof reactSdk.SDK_VERSION).toBe('string')
    })

    it('should export SDK_NAME', () => {
      expect(reactSdk.SDK_NAME).toBe('@janua/react-sdk')
    })
  })
})
