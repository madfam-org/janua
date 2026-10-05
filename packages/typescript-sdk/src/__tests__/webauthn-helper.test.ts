/**
 * WebAuthnHelper hands the browser decoded bytes and sends base64url back
 * (J4-001). `navigator.credentials` is stubbed; the server values are
 * base64url with `-`, `_` and no padding, which the old `atob` decoding
 * rejected.
 */

import type { Auth } from '../auth';
import { WebAuthnHelper } from '../webauthn-helper';

const bytes = (data: BufferSource) =>
  Array.from(
    ArrayBuffer.isView(data)
      ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
      : new Uint8Array(data)
  );
const buffer = (values: number[]) => new Uint8Array(values).buffer;

// base64url fixtures and the bytes they decode to.
const CHALLENGE = '-_-_AAEC-v78_Q';
const CHALLENGE_BYTES = [251, 255, 191, 0, 1, 2, 250, 254, 252, 253];
const USER_ID = '--__QUI';
const USER_ID_BYTES = [0xfb, 0xef, 0xff, 0x41, 0x42];
const CREDENTIAL_ID = '__79_A';
const CREDENTIAL_ID_BYTES = [0xff, 0xfe, 0xfd, 0xfc];

// What the authenticator returns, and its base64url form.
const RAW_ID_BYTES = [0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff, 0x3e, 0x3f];
const RAW_ID = '-vv8_f7_Pj8';

const credentials = { create: jest.fn(), get: jest.fn() };

beforeAll(() => {
  Object.defineProperty(window, 'PublicKeyCredential', {
    value: function PublicKeyCredential() {},
    configurable: true,
  });
  Object.defineProperty(navigator, 'credentials', { value: credentials, configurable: true });
});

beforeEach(() => {
  credentials.create.mockReset();
  credentials.get.mockReset();
});

describe('registerPasskey', () => {
  it('passes decoded bytes to navigator.credentials.create and posts base64url', async () => {
    const auth = {
      getPasskeyRegistrationOptions: jest.fn().mockResolvedValue({
        challenge: CHALLENGE,
        rp: { id: 'example.test', name: 'Example' },
        user: { id: USER_ID, name: 'person@example.test', displayName: 'Person' },
        pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
        timeout: 60000,
        excludeCredentials: [{ id: CREDENTIAL_ID, type: 'public-key' }],
        authenticatorSelection: { residentKey: 'discouraged', userVerification: 'preferred' },
        attestation: 'none',
      }),
      verifyPasskeyRegistration: jest.fn().mockResolvedValue({ verified: true }),
    };
    credentials.create.mockResolvedValue({
      id: RAW_ID,
      rawId: buffer(RAW_ID_BYTES),
      type: 'public-key',
      response: {
        clientDataJSON: buffer([0xfb, 0xff]),
        attestationObject: buffer([0xff, 0xfe, 0xfd, 0xfc]),
      },
    });

    await new WebAuthnHelper(auth as unknown as Auth).registerPasskey('Laptop');

    expect(credentials.create).toHaveBeenCalledTimes(1);
    const { publicKey } = credentials.create.mock.calls[0][0];
    expect(bytes(publicKey.challenge)).toEqual(CHALLENGE_BYTES);
    expect(bytes(publicKey.user.id)).toEqual(USER_ID_BYTES);
    expect(publicKey.user.name).toBe('person@example.test');
    expect(bytes(publicKey.excludeCredentials[0].id)).toEqual(CREDENTIAL_ID_BYTES);
    expect(publicKey.rp).toEqual({ id: 'example.test', name: 'Example' });
    // No attachment preference unless the server sends one (#697).
    expect(publicKey.authenticatorSelection.authenticatorAttachment).toBeUndefined();

    expect(auth.verifyPasskeyRegistration).toHaveBeenCalledWith(
      {
        id: RAW_ID,
        rawId: RAW_ID,
        type: 'public-key',
        response: { clientDataJSON: '-_8', attestationObject: '__79_A' },
      },
      'Laptop'
    );
  });
});

describe('authenticateWithPasskey', () => {
  it('passes decoded bytes to navigator.credentials.get and posts base64url', async () => {
    const auth = {
      getPasskeyAuthenticationOptions: jest.fn().mockResolvedValue({
        challenge: CHALLENGE,
        rpId: 'example.test',
        timeout: 60000,
        userVerification: 'preferred',
        allowCredentials: [{ id: CREDENTIAL_ID, type: 'public-key' }],
        sessionId: 'session-fixture',
      }),
      verifyPasskeyAuthentication: jest.fn().mockResolvedValue({
        user: { id: 'u1' },
        access_token: 'access-fixture',
        refresh_token: 'refresh-fixture',
        token_type: 'bearer',
        expires_in: 900,
      }),
    };
    credentials.get.mockResolvedValue({
      id: RAW_ID,
      rawId: buffer(RAW_ID_BYTES),
      type: 'public-key',
      response: {
        clientDataJSON: buffer([0xfb, 0xff]),
        authenticatorData: buffer([0xff, 0xfe, 0xfd, 0xfc]),
        signature: buffer([0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff, 0x3e, 0x3f]),
        userHandle: buffer(USER_ID_BYTES),
      },
    });

    const result = await new WebAuthnHelper(auth as unknown as Auth).authenticateWithPasskey(
      'person@example.test'
    );

    const { publicKey } = credentials.get.mock.calls[0][0];
    expect(bytes(publicKey.challenge)).toEqual(CHALLENGE_BYTES);
    expect(bytes(publicKey.allowCredentials[0].id)).toEqual(CREDENTIAL_ID_BYTES);
    expect(publicKey.rpId).toBe('example.test');

    expect(auth.verifyPasskeyAuthentication).toHaveBeenCalledWith(
      {
        id: RAW_ID,
        rawId: RAW_ID,
        type: 'public-key',
        response: {
          clientDataJSON: '-_8',
          authenticatorData: '__79_A',
          signature: RAW_ID,
          userHandle: USER_ID,
        },
      },
      'session-fixture',
      'person@example.test'
    );
    expect(result.tokens.access_token).toBe('access-fixture');
  });
});
