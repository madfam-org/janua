import * as React from 'react'
import { ThemeProvider as NextThemesProvider } from 'next-themes'
import type { ThemeConfig } from '../themes/dual-skin'
import { generateCSSVariables } from '../themes/dual-skin'
import { getPreset, type PresetName } from '../tokens/presets'

export interface JanuaThemeProviderProps {
  children: React.ReactNode
  /** Named theme preset */
  preset?: PresetName
  /** Granular color overrides (merged on top of preset) */
  theme?: Partial<ThemeConfig['colors']>
  /** Dark mode strategy */
  darkMode?: 'auto' | 'light' | 'dark'
  /** Shorthand: sets --primary HSL value */
  accentColor?: string
}

interface JanuaThemeContextValue {
  preset: PresetName
  theme: ThemeConfig
}

const JanuaThemeContext = React.createContext<JanuaThemeContextValue | null>(null)

/**
 * Hook to access the current Janua theme context.
 * Returns null when used outside a JanuaThemeProvider (backward-compat).
 */
export function useJanuaTheme(): JanuaThemeContextValue | null {
  return React.useContext(JanuaThemeContext)
}

/**
 * Convert an accentColor (hex like "#10b981") to an HSL string for CSS vars.
 * Accepts hex (#rrggbb) or passthrough HSL strings.
 */
function hexToHSL(hex: string): string {
  // If it already looks like an HSL value (contains spaces and no #), pass through
  if (!hex.startsWith('#')) return hex

  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  let h = 0
  let s = 0

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break
      case g: h = ((b - r) / d + 2) / 6; break
      case b: h = ((r - g) / d + 4) / 6; break
    }
  }

  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}

export function JanuaThemeProvider({
  children,
  preset = 'default',
  theme: colorOverrides,
  darkMode = 'auto',
  accentColor,
}: JanuaThemeProviderProps) {
  const baseTheme = React.useMemo(() => getPreset(preset), [preset])

  // Merge: base preset → color overrides → accentColor shorthand
  const mergedTheme = React.useMemo<ThemeConfig>(() => {
    const colors = { ...baseTheme.colors }

    if (colorOverrides) {
      Object.assign(colors, colorOverrides)
    }

    if (accentColor) {
      const hsl = hexToHSL(accentColor)
      colors.primary = hsl
      colors.ring = hsl
    }

    return { ...baseTheme, colors }
  }, [baseTheme, colorOverrides, accentColor])

  // Generate CSS variable string
  const cssVars = React.useMemo(
    () => generateCSSVariables(mergedTheme),
    [mergedTheme]
  )

  // Map darkMode prop to next-themes values
  const nextThemesProps = React.useMemo(() => {
    switch (darkMode) {
      case 'light': return { forcedTheme: 'light' } as const
      case 'dark': return { forcedTheme: 'dark' } as const
      default: return { enableSystem: true } as const
    }
  }, [darkMode])

  const contextValue = React.useMemo<JanuaThemeContextValue>(
    () => ({ preset, theme: mergedTheme }),
    [preset, mergedTheme]
  )

  return (
    <JanuaThemeContext.Provider value={contextValue}>
      <NextThemesProvider
        attribute="class"
        defaultTheme={darkMode === 'auto' ? 'system' : darkMode}
        {...nextThemesProps}
      >
        <div style={parseCSSVarsToStyle(cssVars)}>
          {children}
        </div>
      </NextThemesProvider>
    </JanuaThemeContext.Provider>
  )
}

/** Parse a CSS variable string into a React style object */
function parseCSSVarsToStyle(cssVars: string): React.CSSProperties {
  const style: Record<string, string> = {}
  const lines = cssVars.split(';')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || !trimmed.startsWith('--')) continue
    const colonIdx = trimmed.indexOf(':')
    if (colonIdx === -1) continue
    const key = trimmed.slice(0, colonIdx).trim()
    const value = trimmed.slice(colonIdx + 1).trim()
    style[key] = value
  }
  return style as React.CSSProperties
}
