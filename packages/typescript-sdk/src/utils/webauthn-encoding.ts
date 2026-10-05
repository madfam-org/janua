/**
 * base64url <-> ArrayBuffer for WebAuthn data.
 *
 * The API sends every binary WebAuthn value (challenge, user id, credential
 * ids) as base64url (RFC 4648 section 5: `-` and `_`, no padding) and reads
 * the browser's response the same way. `atob` only accepts standard base64,
 * so decoding these values with it throws `InvalidCharacterError` whenever a
 * value contains `-` or `_` -- for a random 32-byte challenge, most of the
 * time.
 *
 * Decoding also accepts standard base64 (with or without padding), so a value
 * from an older server still decodes. Encoding always produces base64url
 * without padding, which is what the WebAuthn JSON forms and the API expect.
 * Browser-safe: no Node `Buffer`.
 */

/** Decode a base64url (or standard base64) string to an ArrayBuffer. */
export function base64UrlToArrayBuffer(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/** Encode bytes as base64url without padding. */
export function arrayBufferToBase64Url(data: ArrayBuffer | ArrayBufferView): string {
  // ArrayBuffer.isView, not `instanceof ArrayBuffer`: the buffer may come from
  // another realm (an iframe, or jsdom under test).
  const bytes = ArrayBuffer.isView(data)
    ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
    : new Uint8Array(data);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i] as number);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
