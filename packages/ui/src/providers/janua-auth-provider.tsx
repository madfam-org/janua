import * as React from 'react'
import type { JanuaAuthConfig } from '../config/types'
import { defaultAuthConfig, mergeConfig } from '../config/defaults'
import { JanuaThemeProvider, type JanuaThemeProviderProps } from './janua-theme-provider'
import type { PresetName } from '../tokens/presets'

export interface JanuaAuthProviderProps {
  children: React.ReactNode
  /** Static config object */
  config?: Partial<JanuaAuthConfig>
  /** URL to fetch config from Janua API (e.g. /api/v1/auth/ui-config?client_id=X) */
  configUrl?: string
  /** Janua SDK client instance — passed through to auth components */
  januaClient?: any
  /** API URL fallback for direct fetch calls */
  apiUrl?: string
}

interface JanuaAuthContextValue {
  config: JanuaAuthConfig
  isLoading: boolean
  januaClient?: any
  apiUrl?: string
}

const JanuaAuthContext = React.createContext<JanuaAuthContextValue | null>(null)

/**
 * Hook to access auth config from the nearest JanuaAuthProvider.
 * Returns null when used outside a provider (backward-compat — components fall back to props).
 */
export function useJanuaAuthConfig(): JanuaAuthContextValue | null {
  return React.useContext(JanuaAuthContext)
}

export function JanuaAuthProvider({
  children,
  config: staticConfig,
  configUrl,
  januaClient,
  apiUrl,
}: JanuaAuthProviderProps) {
  const [fetchedConfig, setFetchedConfig] = React.useState<Partial<JanuaAuthConfig> | null>(null)
  const [isLoading, setIsLoading] = React.useState(!!configUrl)

  // Fetch config from API if configUrl is provided
  React.useEffect(() => {
    if (!configUrl) return
    let cancelled = false

    async function fetchConfig() {
      try {
        const response = await fetch(configUrl!)
        if (!response.ok) {
          console.warn(`[JanuaAuthProvider] Failed to fetch config from ${configUrl}: ${response.status}`)
          return
        }
        const data = await response.json()
        if (!cancelled) {
          setFetchedConfig(data)
        }
      } catch (err) {
        console.warn(`[JanuaAuthProvider] Error fetching config:`, err)
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    fetchConfig()
    return () => { cancelled = true }
  }, [configUrl])

  // Merge: defaults → fetched config → static config (static wins)
  const mergedConfig = React.useMemo<JanuaAuthConfig>(() => {
    let result = defaultAuthConfig
    if (fetchedConfig) {
      result = mergeConfig(result, fetchedConfig)
    }
    if (staticConfig) {
      result = mergeConfig(result, staticConfig)
    }
    return result
  }, [fetchedConfig, staticConfig])

  const contextValue = React.useMemo<JanuaAuthContextValue>(() => ({
    config: mergedConfig,
    isLoading,
    januaClient,
    apiUrl,
  }), [mergedConfig, isLoading, januaClient, apiUrl])

  // Derive theme provider props from branding config
  const themePreset = (mergedConfig.branding.themePreset || 'default') as PresetName
  const themeProviderProps: JanuaThemeProviderProps = {
    children,
    preset: themePreset,
    darkMode: mergedConfig.branding.darkMode,
    accentColor: mergedConfig.branding.primaryColor,
  }

  return (
    <JanuaAuthContext.Provider value={contextValue}>
      <JanuaThemeProvider {...themeProviderProps}>
        {children}
      </JanuaThemeProvider>
    </JanuaAuthContext.Provider>
  )
}
