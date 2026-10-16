/** @jest-environment node */
import { createRemoteJWKSet, generateKeyPair, SignJWT } from 'jose'
import { verifyAdminSession } from './admin-session'
import { installConsoleFixture } from '../../../tests/console-runtime-fixture'

// Keep real signature verification. Only replace the remote JWKS transport.
let keys: Awaited<ReturnType<typeof generateKeyPair>>
let otherKeys: Awaited<ReturnType<typeof generateKeyPair>>
jest.mock('jose', () => ({
  ...jest.requireActual('jose'),
  createRemoteJWKSet: jest.fn(() => async () => keys.publicKey),
}))

const operator = { id: 'operator-id', email: 'operator@janua.dev', is_admin: true }
const mockFetch = jest.fn()
const originalFetch = global.fetch
const originalEnv = { ...process.env }

async function token(overrides: Record<string, unknown> = {}, key = keys.privateKey) {
  const payload: Record<string, unknown> = {
    sub: operator.id,
    exp: Math.floor(Date.now() / 1000) + 300,
    iss: 'https://api.janua.dev',
    aud: 'janua.dev',
    type: 'access',
    ...overrides,
  }
  for (const claim of Object.keys(payload)) if (payload[claim] === undefined) delete payload[claim]
  return new SignJWT(payload).setProtectedHeader({ alg: 'RS256', kid: 'test-key' }).sign(key)
}

beforeAll(async () => {
  keys = await generateKeyPair('RS256')
  otherKeys = await generateKeyPair('RS256')
})
beforeEach(() => {
  for (const name of ['JANUA_ISSUER', 'JANUA_ADMIN_AUDIENCE', 'JANUA_JWKS_URL', 'NEXT_PUBLIC_JANUA_AUDIENCE', 'NEXT_PUBLIC_JANUA_API_URL', 'NEXT_PUBLIC_API_URL', 'INTERNAL_API_URL', 'ALLOWED_ADMIN_DOMAINS']) delete process.env[name]
  process.env.JANUA_ISSUER = 'https://api.janua.dev'
  global.fetch = mockFetch
  mockFetch.mockReset().mockResolvedValue({ ok: true, json: async () => operator })
})
afterAll(() => { global.fetch = originalFetch; process.env = originalEnv })

it('accepts a real signed password-session token with no roles or is_admin claims', async () => {
  const accessToken = await token()
  await expect(verifyAdminSession(accessToken)).resolves.toMatchObject({ user: operator })
  expect(mockFetch).toHaveBeenCalledWith('https://api.janua.dev/api/v1/auth/me', expect.objectContaining({
    headers: { Authorization: `Bearer ${accessToken}` }, cache: 'no-store', redirect: 'error',
  }))
})

it('accepts OIDC access tokens with the console audience and authoritative platform access', async () => {
  await expect(verifyAdminSession(await token({ client_id: 'console', roles: ['member'], is_admin: true }))).resolves.toMatchObject({ user: operator })
})

it('uses the configured canonical issuer/key endpoint and rechecks current authorization on every call', async () => {
  installConsoleFixture('admin', { issuer: 'https://auth.madfam.io', jwksUri: 'https://auth.madfam.io/.well-known/jwks.json' })
  const accessToken = await token({ iss: 'https://auth.madfam.io' })
  await expect(verifyAdminSession(accessToken)).resolves.toMatchObject({ user: operator })
  await expect(verifyAdminSession(accessToken)).resolves.toMatchObject({ user: operator })
  expect(mockFetch.mock.calls.filter(([url]) => url.includes('openid-configuration'))).toHaveLength(0)
  expect(mockFetch).toHaveBeenCalledTimes(2)
  expect(createRemoteJWKSet).toHaveBeenCalledWith(new URL('https://auth.madfam.io/.well-known/jwks.json'), { timeoutDuration: 5000 })
  await expect(verifyAdminSession(await token({ iss: 'https://other.example' }))).rejects.toMatchObject({ status: 401 })
})

it('fails closed on missing configuration before any remote request', async () => {
  delete process.env.JANUA_CONSOLE_ISSUER
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 503 })
  expect(mockFetch).not.toHaveBeenCalled()
})

it('pins stage issuer/audience and internal JWKS/user lookup, rejecting a production token before forwarding it', async () => {
  installConsoleFixture('admin', { environment: 'staging', consoleOrigin: 'https://staging-admin.madfam.io',
    apiOrigin: 'https://staging-auth.madfam.io', issuer: 'https://staging-auth.madfam.io',
    audience: 'janua-staging', jwksUri: 'https://staging-auth.madfam.io/.well-known/jwks.json' })
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 401 })
  expect(mockFetch).not.toHaveBeenCalled()
  const stageToken = await token({ iss: 'https://staging-auth.madfam.io', aud: 'janua-staging' })
  await expect(verifyAdminSession(stageToken)).resolves.toMatchObject({ user: operator })
  expect(createRemoteJWKSet).toHaveBeenCalledWith(new URL('http://janua-api.janua-staging.svc.cluster.local/.well-known/jwks.json'), { timeoutDuration: 5000 })
  expect(mockFetch).toHaveBeenCalledWith('http://janua-api.janua-staging.svc.cluster.local/api/v1/auth/me', expect.objectContaining({
    headers: { Authorization: `Bearer ${stageToken}` }, credentials: 'omit', redirect: 'error',
  }))
})

it.each([
  ['issuer', { iss: 'https://other.example' }],
  ['audience', { aud: 'another-api' }],
  ['expiry', { exp: 1 }],
  ['missing expiry', { exp: undefined }],
  ['missing subject', { sub: undefined }],
  ['missing audience', { aud: undefined }],
  ['refresh token', { type: 'refresh' }],
  ['ID token', { type: undefined }],
  ['service subject', { sub: 'service-account:test' }],
  ['service login', { is_service_account: true }],
])('rejects %s before consulting the user API', async (_label, claims) => {
  await expect(verifyAdminSession(await token(claims))).rejects.toMatchObject({ status: 401 })
  expect(mockFetch).not.toHaveBeenCalled()
})

it('rejects a forged RSA signature', async () => {
  await expect(verifyAdminSession(await token({}, otherKeys.privateKey))).rejects.toMatchObject({ status: 401 })
  expect(mockFetch).not.toHaveBeenCalled()
})

it('rejects HS256 even when its claims look right', async () => {
  const forged = await new SignJWT({ sub: operator.id, exp: Math.floor(Date.now() / 1000) + 60, iss: 'https://api.janua.dev', aud: 'janua.dev', type: 'access' })
    .setProtectedHeader({ alg: 'HS256' }).sign(new TextEncoder().encode('test-only-signing-key-with-32-bytes'))
  await expect(verifyAdminSession(forged)).rejects.toMatchObject({ status: 401 })
})

it.each([false, undefined, 'true'])('refuses org admin / demoted operator when DB is_admin is %s', async isAdmin => {
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...operator, is_admin: isAdmin, roles: ['superadmin', 'admin'] }) })
  await expect(verifyAdminSession(await token({ roles: ['admin'], is_admin: true }))).rejects.toMatchObject({ status: 403 })
})

it('requires the authenticated API user to match the signed subject', async () => {
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...operator, id: 'other-user' }) })
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 401 })
})

it('compares exact normalized domains and honors the server allowlist', async () => {
  process.env.ALLOWED_ADMIN_DOMAINS = '@custom.example'
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 403 })
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...operator, email: 'operator@CUSTOM.EXAMPLE' }) })
  await expect(verifyAdminSession(await token())).resolves.toBeDefined()
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...operator, email: 'operator@evilcustom.example' }) })
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 403 })
})

it.each([401, 403, 500])('fails closed on upstream HTTP %s', async status => {
  mockFetch.mockResolvedValue({ ok: false, status })
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: status < 500 ? 401 : 503 })
})

it('fails closed on network errors and malformed identity responses', async () => {
  mockFetch.mockRejectedValueOnce(new Error('network unavailable'))
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 503 })
  mockFetch.mockResolvedValueOnce({ ok: true, json: async () => { throw new Error('invalid JSON') } })
  await expect(verifyAdminSession(await token())).rejects.toMatchObject({ status: 503 })
})

it('checks current authorization on every call instead of caching operator access', async () => {
  const accessToken = await token()
  await verifyAdminSession(accessToken)
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...operator, is_admin: false }) })
  await expect(verifyAdminSession(accessToken)).rejects.toMatchObject({ status: 403 })
  expect(mockFetch).toHaveBeenCalledTimes(2)
})
