/**
 * WebAuthn Helper for Passkey Authentication
 * This module provides browser-side WebAuthn integration for passkey authentication
 */

import type { Auth } from './auth';
import type { AuthResponse } from './types';
import { PasskeyError, ConfigurationError } from './errors';
import { arrayBufferToBase64Url, base64UrlToArrayBuffer } from './utils/webauthn-encoding';

export interface WebAuthnSupport {
  available: boolean;
  platform: boolean;
  conditional: boolean;
}

/**
 * Check WebAuthn support in the current environment
 */
export function checkWebAuthnSupport(): WebAuthnSupport {
  const available = !!(
    typeof window !== 'undefined' &&
    window.PublicKeyCredential &&
    typeof navigator !== 'undefined' &&
    navigator.credentials &&
    typeof navigator.credentials.create === 'function' &&
    typeof navigator.credentials.get === 'function'
  );

  return {
    available,
    platform: false, // Will be updated asynchronously via checkPlatformAuthenticator()
    conditional: false // Will be updated asynchronously via checkConditionalMediation()
  };
}

/**
 * Check if platform authenticator is available (async)
 */
export async function checkPlatformAuthenticator(): Promise<boolean> {
  if (typeof window === 'undefined' || !window.PublicKeyCredential) {
    return false;
  }
  if (PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) {
    return PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  }
  return false;
}

/**
 * Check if conditional mediation is available (async)
 */
export async function checkConditionalMediation(): Promise<boolean> {
  if (typeof window === 'undefined' || !window.PublicKeyCredential) {
    return false;
  }
  if (PublicKeyCredential.isConditionalMediationAvailable) {
    return PublicKeyCredential.isConditionalMediationAvailable();
  }
  return false;
}

/**
 * Helper class for WebAuthn operations
 */
export class WebAuthnHelper {
  constructor(private auth: Auth) {}

  /**
   * Register a new passkey
   */
  async registerPasskey(name?: string): Promise<void> {
    // Check WebAuthn availability
    if (!window?.PublicKeyCredential) {
      throw new ConfigurationError('WebAuthn is not supported in this browser');
    }

    // Get registration options from server (returns flat structure, not wrapped in publicKey)
    const options = await this.auth.getPasskeyRegistrationOptions({ name });

    // The server sends binary values as base64url (not standard base64)
    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      challenge: base64UrlToArrayBuffer(options.challenge),
      rp: options.rp,
      user: {
        ...options.user,
        id: base64UrlToArrayBuffer(options.user.id)
      },
      pubKeyCredParams: options.pubKeyCredParams as PublicKeyCredentialParameters[],
      timeout: options.timeout,
      excludeCredentials: options.excludeCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: base64UrlToArrayBuffer(cred.id)
      })),
      authenticatorSelection: options.authenticatorSelection,
      attestation: options.attestation as AttestationConveyancePreference
    };

    // Create the credential
    const credential = await navigator.credentials.create({
      publicKey: publicKeyCredentialCreationOptions
    }) as PublicKeyCredential;

    if (!credential) {
      throw new PasskeyError('Failed to create passkey');
    }

    // Get the response
    const response = credential.response as AuthenticatorAttestationResponse;

    // Send binary values back as base64url, as the server expects
    // Build PublicKeyCredentialJSON structure expected by verifyPasskeyRegistration
    const verificationData = {
      id: credential.id,
      rawId: arrayBufferToBase64Url(credential.rawId),
      type: 'public-key' as const,
      response: {
        clientDataJSON: arrayBufferToBase64Url(response.clientDataJSON),
        attestationObject: arrayBufferToBase64Url(response.attestationObject)
      }
    };

    // Verify with server
    await this.auth.verifyPasskeyRegistration(verificationData, name);
  }

  /**
   * Authenticate with a passkey
   */
  async authenticateWithPasskey(email?: string): Promise<AuthResponse> {
    // Check WebAuthn availability
    if (!window?.PublicKeyCredential) {
      throw new ConfigurationError('WebAuthn is not supported in this browser');
    }

    // Get authentication options from server (returns flat structure, not wrapped in publicKey)
    const options = await this.auth.getPasskeyAuthenticationOptions(email);

    // The server sends binary values as base64url (not standard base64)
    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      challenge: base64UrlToArrayBuffer(options.challenge),
      rpId: options.rpId,
      timeout: options.timeout,
      userVerification: options.userVerification as UserVerificationRequirement,
      allowCredentials: options.allowCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: base64UrlToArrayBuffer(cred.id)
      }))
    };

    // Get the credential
    const credential = await navigator.credentials.get({
      publicKey: publicKeyCredentialRequestOptions
    }) as PublicKeyCredential;

    if (!credential) {
      throw new PasskeyError('Authentication cancelled or failed');
    }

    // Get the response
    const response = credential.response as AuthenticatorAssertionResponse;

    // Send binary values back as base64url, as the server expects
    const verificationData = {
      id: credential.id,
      rawId: arrayBufferToBase64Url(credential.rawId),
      type: 'public-key' as const,
      response: {
        clientDataJSON: arrayBufferToBase64Url(response.clientDataJSON),
        authenticatorData: arrayBufferToBase64Url(response.authenticatorData),
        signature: arrayBufferToBase64Url(response.signature),
        userHandle: response.userHandle ? arrayBufferToBase64Url(response.userHandle) : undefined
      }
    };

    // Verify with server and get auth tokens. The verify endpoint reads the
    // one-time challenge server-side by `sessionId` (it does NOT accept a
    // client-supplied challenge — 2026-08-23 replay-hardening), so we pass the
    // sessionId minted by getPasskeyAuthenticationOptions, not options.challenge.
    const result = await this.auth.verifyPasskeyAuthentication(
      verificationData,
      options.sessionId,
      email
    );

    // Map response to AuthResponse format - cast token_type to literal 'bearer'.
    // The passkey verify endpoint returns only a partial user object
    // ({id, email, first_name, last_name}); callers that need the full profile
    // should follow up with getCurrentUser().
    return {
      user: result.user as import('./types').User,
      tokens: {
        access_token: result.access_token,
        refresh_token: result.refresh_token,
        token_type: result.token_type as 'bearer',
        expires_in: result.expires_in
      }
    };
  }
}
