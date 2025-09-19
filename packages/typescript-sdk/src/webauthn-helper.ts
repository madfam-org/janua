/**
 * WebAuthn Helper for Passkey Authentication
 * This module provides browser-side WebAuthn integration for passkey authentication
 */

import type { Auth } from './auth';
import type { AuthResponse } from './types';

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
    window?.PublicKeyCredential &&
    navigator?.credentials?.create &&
    navigator?.credentials?.get
  );

  const platform = available &&
    PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable
      ? PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
      : Promise.resolve(false);

  const conditional = available &&
    PublicKeyCredential.isConditionalMediationAvailable
      ? PublicKeyCredential.isConditionalMediationAvailable()
      : Promise.resolve(false);

  return {
    available,
    platform: false, // Will be updated asynchronously
    conditional: false // Will be updated asynchronously
  };
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
      throw new Error('WebAuthn is not supported in this browser');
    }

    // Get registration options from server
    const options = await this.auth.getPasskeyRegistrationOptions({ name });

    // Convert base64 strings to ArrayBuffers
    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      ...options.publicKey,
      challenge: this.base64ToArrayBuffer(options.publicKey.challenge),
      user: {
        ...options.publicKey.user,
        id: this.base64ToArrayBuffer(options.publicKey.user.id)
      },
      excludeCredentials: options.publicKey.excludeCredentials?.map(cred => ({
        ...cred,
        id: this.base64ToArrayBuffer(cred.id)
      }))
    };

    // Create the credential
    const credential = await navigator.credentials.create({
      publicKey: publicKeyCredentialCreationOptions
    }) as PublicKeyCredential;

    if (!credential) {
      throw new Error('Failed to create passkey');
    }

    // Get the response
    const response = credential.response as AuthenticatorAttestationResponse;

    // Convert ArrayBuffers back to base64 for transmission
    const verificationData = {
      credential_id: this.arrayBufferToBase64(credential.rawId),
      client_data: this.arrayBufferToBase64(response.clientDataJSON),
      attestation_object: this.arrayBufferToBase64(response.attestationObject),
      public_key: '', // Will be extracted server-side from attestation object
      transports: (credential as any).response.getTransports?.() || []
    };

    // Verify with server
    await this.auth.verifyPasskeyRegistration(verificationData);
  }

  /**
   * Authenticate with a passkey
   */
  async authenticateWithPasskey(email?: string): Promise<AuthResponse> {
    // Check WebAuthn availability
    if (!window?.PublicKeyCredential) {
      throw new Error('WebAuthn is not supported in this browser');
    }

    // Get authentication options from server
    const options = await this.auth.getPasskeyAuthenticationOptions(email);

    // Convert base64 strings to ArrayBuffers
    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      ...options.publicKey,
      challenge: this.base64ToArrayBuffer(options.publicKey.challenge),
      allowCredentials: options.publicKey.allowCredentials?.map(cred => ({
        ...cred,
        id: this.base64ToArrayBuffer(cred.id)
      }))
    };

    // Get the credential
    const credential = await navigator.credentials.get({
      publicKey: publicKeyCredentialRequestOptions
    }) as PublicKeyCredential;

    if (!credential) {
      throw new Error('Authentication cancelled or failed');
    }

    // Get the response
    const response = credential.response as AuthenticatorAssertionResponse;

    // Convert ArrayBuffers back to base64 for transmission
    const verificationData = {
      credential_id: this.arrayBufferToBase64(credential.rawId),
      client_data: this.arrayBufferToBase64(response.clientDataJSON),
      authenticator_data: this.arrayBufferToBase64(response.authenticatorData),
      signature: this.arrayBufferToBase64(response.signature),
      user_handle: response.userHandle ? this.arrayBufferToBase64(response.userHandle) : undefined
    };

    // Verify with server and get auth tokens
    return await this.auth.verifyPasskeyAuthentication(verificationData);
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
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }
}