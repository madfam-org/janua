/**
 * Dashboard passkey registration, end to end in jsdom (J4-001).
 *
 * Real dashboard API module and real SDK source; only the SDK client's HTTP
 * `post` and `navigator.credentials` are stubbed. The server's registration options carry
 * base64url values (`-`, `_`, no padding) -- the dashboard used to decode them
 * with `atob`, which throws on those characters -- and the request shapes are
 * the ones the API validates (options with a JSON body, verification wrapped
 * in `credential`).
 */

import { registerPasskey } from './api'
import { januaClient } from './janua-client'

// base64url fixtures and the bytes they decode to.
const CHALLENGE = '-_-_AAEC-v78_Q'
const CHALLENGE_BYTES = [251, 255, 191, 0, 1, 2, 250, 254, 252, 253]
const USER_ID = '--__QUI'
const USER_ID_BYTES = [0xfb, 0xef, 0xff, 0x41, 0x42]
const CREDENTIAL_ID = '__79_A'
const CREDENTIAL_ID_BYTES = [0xff, 0xfe, 0xfd, 0xfc]
const RAW_ID_BYTES = [0xfa, 0xfb, 0xfc, 0xfd, 0xfe, 0xff, 0x3e, 0x3f]
const RAW_ID = '-vv8_f7_Pj8'

const bytes = (data: BufferSource) =>
  Array.from(
    ArrayBuffer.isView(data)
      ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
      : new Uint8Array(data),
  )
const buffer = (values: number[]) => new Uint8Array(values).buffer

const REGISTRATION_OPTIONS = {
  challenge: CHALLENGE,
  rp: { id: 'janua.dev', name: 'Janua' },
  user: { id: USER_ID, name: 'person@example.test', displayName: 'Person' },
  pubKeyCredParams: [
    { type: 'public-key', alg: -7 },
    { type: 'public-key', alg: -257 },
  ],
  timeout: 60000,
  excludeCredentials: [{ id: CREDENTIAL_ID, type: 'public-key' }],
  authenticatorSelection: { residentKey: 'discouraged', userVerification: 'preferred' },
  attestation: 'none',
}

const credentials = { create: jest.fn(), get: jest.fn() }
let post: jest.SpyInstance

beforeAll(() => {
  Object.defineProperty(window, 'PublicKeyCredential', {
    value: function PublicKeyCredential() {},
    configurable: true,
  })
  Object.defineProperty(navigator, 'credentials', { value: credentials, configurable: true })
})

beforeEach(() => {
  credentials.create.mockReset()
  // The SDK's Auth module posts through this same client instance.
  post = jest.spyOn(januaClient.http, 'post').mockImplementation(async (url: string) => {
    if (url === '/api/v1/passkeys/register/options') {
      return { data: REGISTRATION_OPTIONS, status: 200, statusText: 'OK', headers: {} }
    }
    if (url === '/api/v1/passkeys/register/verify') {
      return {
        data: { verified: true, passkey_id: 'pk-1', message: 'ok' },
        status: 200,
        statusText: 'OK',
        headers: {},
      }
    }
    throw new Error(`unexpected POST ${url}`)
  })
  credentials.create.mockResolvedValue({
    id: RAW_ID,
    rawId: buffer(RAW_ID_BYTES),
    type: 'public-key',
    response: {
      clientDataJSON: buffer([0xfb, 0xff]),
      attestationObject: buffer(CREDENTIAL_ID_BYTES),
    },
  })
})

afterEach(() => {
  post.mockRestore()
})

function bodyPostedTo(path: string): unknown {
  const call = post.mock.calls.find(([url]) => url === path)
  expect(call).toBeDefined()
  return call![1]
}

describe('registerPasskey (dashboard)', () => {
  it('hands navigator.credentials.create the decoded bytes of the base64url options', async () => {
    await registerPasskey('Laptop')

    expect(credentials.create).toHaveBeenCalledTimes(1)
    const { publicKey } = credentials.create.mock.calls[0][0]
    expect(bytes(publicKey.challenge)).toEqual(CHALLENGE_BYTES)
    expect(bytes(publicKey.user.id)).toEqual(USER_ID_BYTES)
    expect(publicKey.user.name).toBe('person@example.test')
    expect(publicKey.excludeCredentials).toHaveLength(1)
    expect(bytes(publicKey.excludeCredentials[0].id)).toEqual(CREDENTIAL_ID_BYTES)
    expect(publicKey.rp).toEqual({ id: 'janua.dev', name: 'Janua' })
    expect(publicKey.pubKeyCredParams).toEqual(REGISTRATION_OPTIONS.pubKeyCredParams)
  })

  it('requests the options with a JSON body (the API answers 422 without one)', async () => {
    await registerPasskey('Laptop')

    const body = bodyPostedTo('/api/v1/passkeys/register/options')
    expect(body).toEqual(expect.any(Object))
    expect(body).not.toBeNull()
  })

  it('posts the credential as base64url, wrapped in `credential`, with the name', async () => {
    await registerPasskey('Laptop')

    expect(bodyPostedTo('/api/v1/passkeys/register/verify')).toEqual({
      credential: {
        id: RAW_ID,
        rawId: RAW_ID,
        type: 'public-key',
        response: { clientDataJSON: '-_8', attestationObject: CREDENTIAL_ID },
      },
      name: 'Laptop',
    })
  })

  it('does not verify when the browser returns no credential', async () => {
    credentials.create.mockResolvedValue(null)

    await expect(registerPasskey('Laptop')).rejects.toThrow()
    expect(post.mock.calls.some(([url]) => url === '/api/v1/passkeys/register/verify')).toBe(
      false,
    )
  })
})
