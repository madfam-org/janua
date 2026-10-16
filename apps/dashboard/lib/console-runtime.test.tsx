/** @jest-environment-options {"url":"https://staging-app.madfam.io"} */
import { installConsoleFixture } from '../../../tests/console-runtime-fixture'
import {
  browserConsoleConfig, consoleCsp, consoleInternalApi, consoleRuntimeFromEnv,
  consoleSessionCookie, lazyConsoleClient, parseConsoleRuntimeConfig,
} from '@janua/ui/console-runtime'
import { clearAuthCookie, getAuthToken, setAuthCookie } from './auth-storage'

const stage = {
  surface: 'dashboard' as const, environment: 'staging' as const,
  consoleOrigin: 'https://staging-app.madfam.io', apiOrigin: 'https://staging-auth.madfam.io',
  issuer: 'https://staging-auth.madfam.io', audience: 'janua-staging',
  jwksUri: 'https://staging-auth.madfam.io/.well-known/jwks.json',
}
beforeEach(() => { installConsoleFixture('dashboard', stage) })

it('exposes exactly public fields, never environment credentials or internal transport', () => {
  process.env.SYNTHETIC_SECRET = 'sensitive-fixture'
  const config = consoleRuntimeFromEnv(process.env, 'dashboard')
  expect(config).toEqual(stage)
  expect(JSON.stringify(config)).not.toContain('sensitive-fixture')
  expect(JSON.stringify(config)).not.toContain('.svc.cluster.local')
  delete process.env.SYNTHETIC_SECRET
})

it.each([
  { apiOrigin: 'https://api.janua.dev' }, { issuer: 'https://auth.madfam.io' },
  { audience: 'janua.dev' }, { jwksUri: 'https://foreign.invalid/.well-known/jwks.json' },
  { consoleOrigin: 'https://app.janua.dev' }, { surface: 'admin' },
  { environment: 'preview' }, { clientSecret: 'forbidden-fixture' },
  { apiOrigin: 'https://staging-auth.madfam.io/path' },
  { apiOrigin: 'https://user:pass@staging-auth.madfam.io' },
  { apiOrigin: 'https://staging-auth.madfam.io?next=https://api.janua.dev' },
  { apiOrigin: "https://staging-auth.madfam.io; script-src *" },
  { audience: '</script><script>alert(1)</script>' },
])('rejects partial, foreign or injectable staging configuration: %s', bad => {
  expect(() => parseConsoleRuntimeConfig({ ...stage, ...bad }, 'dashboard')).toThrow('Console configuration unavailable')
})

it.each(Object.keys(stage))('rejects missing %s without a production fallback', field => {
  const config = { ...stage } as Record<string, unknown>
  delete config[field]
  expect(() => parseConsoleRuntimeConfig(config, 'dashboard')).toThrow()
})

it('pins internal stage transport to the exact owned API service', () => {
  expect(consoleInternalApi(process.env, stage)).toBe('http://janua-api.janua-staging.svc.cluster.local')
  for (const value of [undefined, 'https://api.janua.dev', 'http://janua-api.janua.svc.cluster.local',
    'http://janua-api.janua-staging.svc.cluster.local/redirect', 'https://foreign.invalid']) {
    expect(() => consoleInternalApi({ JANUA_CONSOLE_INTERNAL_API_URL: value }, stage)).toThrow()
  }
})

it('uses staging-only request CSP; environment changes require no rebuilt bundle', () => {
  const stageCsp = consoleCsp(stage)
  expect(stageCsp).toContain("connect-src 'self' https://staging-auth.madfam.io;")
  expect(stageCsp).not.toMatch(/api\.janua\.dev|cloudflareinsights|unsafe-eval/)
  const production = installConsoleFixture('dashboard')
  expect(consoleCsp(production)).toContain("connect-src 'self' https://api.janua.dev")
})

it('imports lazily, blocks absent config before constructing an SDK, and binds methods correctly', () => {
  const factory = jest.fn(() => ({ marker: 'stage', value() { return this.marker } }))
  const client = lazyConsoleClient('dashboard', factory)
  expect(factory).not.toHaveBeenCalled()
  document.getElementById('janua-console-runtime')!.remove()
  expect(() => client.value()).toThrow()
  expect(factory).not.toHaveBeenCalled()
  installConsoleFixture('dashboard', stage)
  expect(client.value()).toBe('stage')
  expect(client.value()).toBe('stage')
  expect(factory).toHaveBeenCalledTimes(1)
  installConsoleFixture('dashboard')
  expect(() => client.value()).toThrow()
  expect(factory).toHaveBeenCalledTimes(1)
})

it('rejects a valid config served on a foreign console host before SDK construction', () => {
  installConsoleFixture('dashboard')
  expect(() => browserConsoleConfig('dashboard')).toThrow()
})

it('ignores inherited production cookies and only writes/expires the host-only staging cookie', () => {
  document.cookie = 'janua_access_token=production-fixture; Domain=.madfam.io; Path=/; Secure'
  expect(getAuthToken()).toBeNull()
  setAuthCookie('stage-fixture')
  expect(getAuthToken()).toBe('stage-fixture')
  expect(consoleSessionCookie(stage)).toBe('__Host-janua_stage_session')
  clearAuthCookie()
  expect(getAuthToken()).toBeNull()
  expect(document.cookie).toContain('janua_access_token=production-fixture')
  expect(document.cookie).not.toContain('__Host-janua_stage_session=')
  document.cookie = 'janua_access_token=; Domain=.madfam.io; Path=/; Secure; Max-Age=0'
})
