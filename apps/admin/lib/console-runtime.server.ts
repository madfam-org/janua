import { ConsoleConfigurationError, consoleInternalApi, consoleRuntimeFromEnv } from '@janua/ui/console-runtime'

export function readConsoleConfig() {
  const config = consoleRuntimeFromEnv(process.env, 'admin')
  if (process.env.NODE_ENV === 'production' && config.environment === 'development') throw new ConsoleConfigurationError()
  return config
}
export function readConsoleApi() { return consoleInternalApi(process.env, readConsoleConfig()) }
