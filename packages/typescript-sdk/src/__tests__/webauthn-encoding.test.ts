/**
 * base64url <-> ArrayBuffer for WebAuthn data (J4-001).
 *
 * The API sends WebAuthn binary values as base64url (`-`, `_`, no padding).
 * `atob` rejects those characters, so the old standard-base64 decoding threw
 * for most challenges, user ids and credential ids.
 */

import { arrayBufferToBase64Url, base64UrlToArrayBuffer } from '../utils/webauthn-encoding';
import * as sdk from '../index';

const bytes = (buffer: ArrayBuffer) => Array.from(new Uint8Array(buffer));

// Fixed vectors (Node: Buffer.from(bytes).toString('base64url')).
const VECTORS: Array<{ name: string; bytes: number[]; base64url: string; base64: string }> = [
  {
    name: 'a challenge with "-" and "_" and no padding',
    bytes: [251, 255, 191, 0, 1, 2, 250, 254, 252, 253],
    base64url: '-_-_AAEC-v78_Q',
    base64: '+/+/AAEC+v78/Q==',
  },
  {
    name: 'a user id whose base64 form is padded with one "="',
    bytes: [0xfb, 0xef, 0xff, 0x41, 0x42],
    base64url: '--__QUI',
    base64: '++//QUI=',
  },
  {
    name: 'a credential id that is only "_" and "-" heavy',
    bytes: [0xff, 0xfe, 0xfd, 0xfc],
    base64url: '__79_A',
    base64: '//79/A==',
  },
];

describe('base64UrlToArrayBuffer', () => {
  it.each(VECTORS)('decodes $name', ({ bytes: expected, base64url }) => {
    expect(bytes(base64UrlToArrayBuffer(base64url))).toEqual(expected);
  });

  it('is what atob alone cannot do', () => {
    // The bug being fixed: standard-base64 decoding throws on these values.
    expect(() => atob('-_-_AAEC-v78_Q')).toThrow();
  });

  it.each(VECTORS)('still accepts standard base64 for $name', ({ bytes: expected, base64 }) => {
    expect(bytes(base64UrlToArrayBuffer(base64))).toEqual(expected);
  });

  it('decodes the empty string to an empty buffer', () => {
    expect(base64UrlToArrayBuffer('').byteLength).toBe(0);
  });
});

describe('arrayBufferToBase64Url', () => {
  it.each(VECTORS)('encodes $name without padding', ({ bytes: input, base64url }) => {
    const encoded = arrayBufferToBase64Url(new Uint8Array(input).buffer);
    expect(encoded).toBe(base64url);
    expect(encoded).not.toMatch(/[+/=]/);
  });

  it('encodes a view over part of a larger buffer (only the viewed bytes)', () => {
    const backing = new Uint8Array([9, 9, 0xff, 0xfe, 0xfd, 0xfc, 9]);
    expect(arrayBufferToBase64Url(backing.subarray(2, 6))).toBe('__79_A');
  });
});

describe('round trip', () => {
  it('returns every byte value unchanged at every length mod 3', () => {
    const all = Array.from({ length: 256 }, (_, i) => i);
    for (const length of [0, 1, 2, 3, 31, 32, 64, 255, 256]) {
      const input = all.slice(0, length).reverse();
      const encoded = arrayBufferToBase64Url(new Uint8Array(input).buffer);
      expect(encoded).toMatch(/^[A-Za-z0-9_-]*$/);
      expect(bytes(base64UrlToArrayBuffer(encoded))).toEqual(input);
    }
  });
});

describe('package exports', () => {
  it('exports both functions from the SDK entry point', () => {
    expect(sdk.base64UrlToArrayBuffer).toBe(base64UrlToArrayBuffer);
    expect(sdk.arrayBufferToBase64Url).toBe(arrayBufferToBase64Url);
  });
});
