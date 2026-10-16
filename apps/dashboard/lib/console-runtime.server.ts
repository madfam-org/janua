import { ConsoleConfigurationError, consoleInternalApi, consoleRuntimeFromEnv } from '@janua/ui/console-runtime'

// Request-local: NEXT_PUBLIC values are never consulted.
export function readConsoleConfig() {
  const config = consoleRuntimeFromEnv(process.env, 'dashboard')
  if (process.env.NODE_ENV === 'production' && config.environment === 'development') throw new ConsoleConfigurationError()
  return config
}
export function readConsoleApi() { return consoleInternalApi(process.env, readConsoleConfig()) }
