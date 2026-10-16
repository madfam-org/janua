/** Public console deployment contract. Never pass an environment object to the browser. */
export type ConsoleSurface = 'dashboard' | 'admin'
export interface ConsoleRuntimeConfig {
  surface: ConsoleSurface
  environment: 'production' | 'staging' | 'development'
  consoleOrigin: string
  apiOrigin: string
  issuer: string
  audience: string
  jwksUri: string
}

export const CONSOLE_CONFIG_ELEMENT = 'janua-console-runtime'
export const STAGING_INTERNAL_API = 'http://janua-api.janua-staging.svc.cluster.local'
const STAGING_ISSUER = 'https://staging-auth.madfam.io'
// Proposed bindings only: activating these hosts still requires operator review.
const STAGING_CONSOLES = {
  dashboard: 'https://staging-app.madfam.io',
  admin: 'https://staging-admin.madfam.io',
}
const FIELDS = ['surface', 'environment', 'consoleOrigin', 'apiOrigin', 'issuer', 'audience', 'jwksUri']

export class ConsoleConfigurationError extends Error {
  constructor() { super('Console configuration unavailable') }
}

function origin(value: unknown, development = false): string {
  if (typeof value !== 'string' || value.length > 300) throw new ConsoleConfigurationError()
  try {
    const url = new URL(value)
    if (value !== url.origin && value !== `${url.origin}/`) throw new ConsoleConfigurationError()
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if (url.protocol !== 'https:' && !(development && local && url.protocol === 'http:')) {
      throw new ConsoleConfigurationError()
    }
    return url.origin
  } catch { throw new ConsoleConfigurationError() }
}

/** Closed schema; no unrecognized field, credential, path, query or fragment is exposed. */
export function parseConsoleRuntimeConfig(value: unknown, surface: ConsoleSurface): ConsoleRuntimeConfig {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ConsoleConfigurationError()
  const record = value as Record<string, unknown>
  if (Object.keys(record).length !== FIELDS.length || Object.keys(record).some(key => !FIELDS.includes(key))) {
    throw new ConsoleConfigurationError()
  }
  const { environment, audience } = record
  if (record.surface !== surface || !['production', 'staging', 'development'].includes(String(environment)) ||
      typeof audience !== 'string' || !/^[A-Za-z0-9._:\/-]{1,150}$/.test(audience)) {
    throw new ConsoleConfigurationError()
  }
  const development = environment === 'development'
  const config: ConsoleRuntimeConfig = {
    surface,
    environment: environment as ConsoleRuntimeConfig['environment'],
    consoleOrigin: origin(record.consoleOrigin, development),
    apiOrigin: origin(record.apiOrigin, development),
    issuer: origin(record.issuer, development),
    audience,
    jwksUri: String(record.jwksUri),
  }
  if (config.jwksUri !== `${config.issuer}/.well-known/jwks.json`) throw new ConsoleConfigurationError()
  if (development && [config.consoleOrigin, config.apiOrigin, config.issuer].some(address =>
    !['localhost', '127.0.0.1', '[::1]'].includes(new URL(address).hostname))) throw new ConsoleConfigurationError()
  if (environment === 'staging' && (config.consoleOrigin !== STAGING_CONSOLES[surface] ||
      config.apiOrigin !== STAGING_ISSUER || config.issuer !== STAGING_ISSUER || audience !== 'janua-staging')) {
    throw new ConsoleConfigurationError()
  }
  // A partially changed profile must not turn staging into production implicitly.
  if (environment === 'production' && [config.consoleOrigin, config.apiOrigin, config.issuer].some(address =>
    address === STAGING_ISSUER || Object.values(STAGING_CONSOLES).includes(address))) throw new ConsoleConfigurationError()
  return Object.freeze(config)
}

/** Call on the server per request; deliberately whitelist only nonsecret fields. */
export function consoleRuntimeFromEnv(env: Record<string, string | undefined>, surface: ConsoleSurface): ConsoleRuntimeConfig {
  return parseConsoleRuntimeConfig({
    surface,
    environment: env.JANUA_CONSOLE_ENVIRONMENT,
    consoleOrigin: env.JANUA_CONSOLE_ORIGIN,
    apiOrigin: env.JANUA_CONSOLE_API_URL,
    issuer: env.JANUA_CONSOLE_ISSUER,
    audience: env.JANUA_CONSOLE_AUDIENCE,
    jwksUri: env.JANUA_CONSOLE_JWKS_URL,
  }, surface)
}

/** Internal transport is never serialized. Stage accepts only its exact owned service. */
export function consoleInternalApi(env: Record<string, string | undefined>, config: ConsoleRuntimeConfig): string {
  const value = env.JANUA_CONSOLE_INTERNAL_API_URL
  if (config.environment === 'staging') {
    if (value !== STAGING_INTERNAL_API) throw new ConsoleConfigurationError()
    return STAGING_INTERNAL_API
  }
  if (config.environment === 'production' && value === 'http://janua-api.janua.svc.cluster.local') return value
  return value ? origin(value, config.environment === 'development') : config.apiOrigin
}

/** Read existing server markup synchronously; no fetch, inline script or window bootstrap. */
export function browserConsoleConfig(surface: ConsoleSurface): ConsoleRuntimeConfig {
  if (typeof document === 'undefined' || typeof window === 'undefined') throw new ConsoleConfigurationError()
  try {
    const element = document.getElementById(CONSOLE_CONFIG_ELEMENT)
    const config = parseConsoleRuntimeConfig(JSON.parse(element?.getAttribute('data-config') || ''), surface)
    if (window.location.origin !== config.consoleOrigin) throw new ConsoleConfigurationError()
    return config
  } catch { throw new ConsoleConfigurationError() }
}

/** __Host- prevents an inherited Domain cookie from impersonating the stage session. */
export function consoleSessionCookie(config: ConsoleRuntimeConfig): string {
  return config.environment === 'staging' ? '__Host-janua_stage_session' : 'janua_access_token'
}

/** Existing imperative callers stay lazy: imports never construct an SDK. */
export function lazyConsoleObject<T extends object>(resolve: () => T): T {
  return new Proxy({} as T, {
    get(_target, property) {
      const object = resolve()
      const value = Reflect.get(object, property)
      return typeof value === 'function' ? value.bind(object) : value
    },
  })
}

export function lazyConsoleClient<T extends object>(surface: ConsoleSurface, factory: (config: ConsoleRuntimeConfig) => T): T {
  let client: T | undefined
  let fingerprint: string | undefined
  return lazyConsoleObject(() => {
    // Never initialize/mutate a server singleton; SSR only uses passed props.
    const config = browserConsoleConfig(surface)
    const current = JSON.stringify(config)
    if (fingerprint && fingerprint !== current) throw new ConsoleConfigurationError()
    if (!client) { client = factory(config); fingerprint = current }
    return client
  })
}

export function consoleCookieDomain(config: ConsoleRuntimeConfig): string {
  return config.environment === 'production' &&
    ['https://app.janua.dev', 'https://admin.janua.dev'].includes(config.consoleOrigin) ? '; domain=.janua.dev' : ''
}

export function consoleCsp(config: ConsoleRuntimeConfig): string {
  const development = config.environment === 'development'
  const production = config.environment === 'production'
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${development ? " 'unsafe-eval'" : ''}${production ? ' https://static.cloudflareinsights.com' : ''}`,
    `style-src 'self' 'unsafe-inline'${config.surface === 'admin' && production ? ' https://fonts.googleapis.com' : ''}`,
    `font-src 'self' data:${config.surface === 'admin' && production ? ' https://fonts.gstatic.com' : ''}`,
    config.surface === 'admin' ? "img-src 'self' data: https:" : "img-src 'self' data: blob:",
    `connect-src 'self' ${config.apiOrigin}${production ? ' https://cloudflareinsights.com' : ''}${development ? ' ws://localhost:*' : ''}`,
    "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
  ].join('; ')
}
