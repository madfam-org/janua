/**
 * WebAuthn Helper for Passkey Authentication
 * This module provides browser-side WebAuthn integration for passkey authentication
 */

import type { Auth } from './auth';
import type { AuthResponse } from './types';
import { PasskeyError, ConfigurationError } from './errors';

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

    // Convert base64 strings to ArrayBuffers
    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      challenge: this.base64ToArrayBuffer(options.challenge),
      rp: options.rp,
      user: {
        ...options.user,
        id: this.base64ToArrayBuffer(options.user.id)
      },
      pubKeyCredParams: options.pubKeyCredParams as PublicKeyCredentialParameters[],
      timeout: options.timeout,
      excludeCredentials: options.excludeCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: this.base64ToArrayBuffer(cred.id)
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

    // Convert ArrayBuffers back to base64 for transmission
    // Build PublicKeyCredentialJSON structure expected by verifyPasskeyRegistration
    const verificationData = {
      id: credential.id,
      rawId: this.arrayBufferToBase64(credential.rawId),
      type: 'public-key' as const,
      response: {
        clientDataJSON: this.arrayBufferToBase64(response.clientDataJSON),
        attestationObject: this.arrayBufferToBase64(response.attestationObject)
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

    // Convert base64 strings to ArrayBuffers
    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      challenge: this.base64ToArrayBuffer(options.challenge),
      rpId: options.rpId,
      timeout: options.timeout,
      userVerification: options.userVerification as UserVerificationRequirement,
      allowCredentials: options.allowCredentials?.map(cred => ({
        type: cred.type as PublicKeyCredentialType,
        id: this.base64ToArrayBuffer(cred.id)
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

    // Convert ArrayBuffers back to base64 for transmission
    const verificationData = {
      id: credential.id,
      rawId: this.arrayBufferToBase64(credential.rawId),
      type: 'public-key' as const,
      response: {
        clientDataJSON: this.arrayBufferToBase64(response.clientDataJSON),
        authenticatorData: this.arrayBufferToBase64(response.authenticatorData),
        signature: this.arrayBufferToBase64(response.signature),
        userHandle: response.userHandle ? this.arrayBufferToBase64(response.userHandle) : undefined
      }
    };

    // Verify with server and get auth tokens - pass credential, challenge, and email
    const result = await this.auth.verifyPasskeyAuthentication(
      verificationData,
      options.challenge,
      email
    );

    // Map response to AuthResponse format - cast token_type to literal 'bearer'
    return {
      user: result.user,
      tokens: {
        access_token: result.access_token,
        refresh_token: result.refresh_token,
        token_type: result.token_type as 'bearer',
        expires_in: result.expires_in
      }
    };
  }

  /**
   * Convert base64 string to ArrayBuffer
   */
  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = window.atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * Convert ArrayBuffer to base64 string
   */
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      const byte = bytes[i];
      if (byte !== undefined) {
        binary += String.fromCharCode(byte);
      }
    }
    return window.btoa(binary);
  }
}
