/** @jest-environment node */
import { NextRequest } from 'next/server'
import { middleware } from './middleware'
import { installConsoleFixture } from '../../tests/console-runtime-fixture'

beforeEach(() => installConsoleFixture('dashboard', {
  environment: 'staging', consoleOrigin: 'https://staging-app.madfam.io',
  apiOrigin: 'https://staging-auth.madfam.io', issuer: 'https://staging-auth.madfam.io',
  audience: 'janua-staging', jwksUri: 'https://staging-auth.madfam.io/.well-known/jwks.json',
}))

it('ignores an inherited production session cookie without expiring it', () => {
  const token = `header.${Buffer.from(JSON.stringify({ sub: 'synthetic', exp: Date.now() / 1000 + 300 })).toString('base64url')}.signature`
  const request = new NextRequest('https://staging-app.madfam.io/profile', { headers: { cookie: `janua_access_token=${token}` } })
  const result = middleware(request)
  expect(result.headers.get('location')).toBe('https://staging-app.madfam.io/login?redirect=%2Fprofile')
  expect(result.headers.get('set-cookie') || '').not.toContain('janua_access_token=')
  expect(result.headers.get('content-security-policy')).toContain('https://staging-auth.madfam.io')
  expect(result.headers.get('content-security-policy')).not.toContain('https://api.janua.dev')
})

it('rejects missing or foreign stage configuration before allowing even the login page', () => {
  process.env.JANUA_CONSOLE_API_URL = 'https://api.janua.dev'
  expect(middleware(new NextRequest('https://staging-app.madfam.io/login')).status).toBe(503)
})
