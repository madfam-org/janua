import { CONSOLE_CONFIG_ELEMENT, type ConsoleRuntimeConfig, type ConsoleSurface } from '../packages/ui/src/lib/console-runtime'

/** Synthetic nonsecret deployment fixture, never loaded by application code. */
export function installConsoleFixture(surface: ConsoleSurface, overrides: Partial<ConsoleRuntimeConfig> = {}) {
  const config: ConsoleRuntimeConfig = {
    surface, environment: 'production',
    consoleOrigin: surface === 'admin' ? 'https://admin.janua.dev' : 'https://app.janua.dev',
    apiOrigin: 'https://api.janua.dev', issuer: 'https://api.janua.dev',
    audience: 'janua.dev', jwksUri: 'https://api.janua.dev/.well-known/jwks.json',
    ...overrides,
  }
  for (const [name, value] of Object.entries({
    ENVIRONMENT: config.environment, ORIGIN: config.consoleOrigin, API_URL: config.apiOrigin,
    ISSUER: config.issuer, AUDIENCE: config.audience, JWKS_URL: config.jwksUri,
    INTERNAL_API_URL: config.environment === 'staging' ? 'http://janua-api.janua-staging.svc.cluster.local' : '',
  })) process.env[`JANUA_CONSOLE_${name}`] = value
  if (typeof document !== 'undefined' && typeof document.getElementById === 'function' &&
      typeof document.createElement === 'function' && document.body) {
    document.getElementById(CONSOLE_CONFIG_ELEMENT)?.remove()
    const element = document.createElement('div')
    element.id = CONSOLE_CONFIG_ELEMENT
    element.hidden = true
    element.setAttribute('data-config', JSON.stringify(config))
    document.body.prepend(element)
  }
  return config
}
