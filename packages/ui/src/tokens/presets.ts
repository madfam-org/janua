import type { ThemeConfig } from '../themes/dual-skin'
import { solarpunkTheme } from '../themes/dual-skin'

/**
 * Theme presets for JanuaThemeProvider.
 * Each preset is a ThemeConfig-compatible object.
 */

/** Default preset - matches the current neutral theme (shadcn defaults) */
export const defaultPreset: ThemeConfig = {
  name: 'Default',
  description: 'Clean professional theme matching shadcn defaults',
  fonts: {
    primary: "'Inter', system-ui, -apple-system, sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  colors: {
    background: '0 0% 100%',
    foreground: '222.2 84% 4.9%',
    primary: '222.2 47.4% 11.2%',
    primaryForeground: '210 40% 98%',
    secondary: '210 40% 96.1%',
    secondaryForeground: '222.2 47.4% 11.2%',
    muted: '210 40% 96.1%',
    mutedForeground: '215.4 16.3% 46.9%',
    accent: '210 40% 96.1%',
    accentForeground: '222.2 47.4% 11.2%',
    destructive: '0 84.2% 60.2%',
    destructiveForeground: '210 40% 98%',
    border: '214.3 31.8% 91.4%',
    input: '214.3 31.8% 91.4%',
    ring: '222.2 84% 4.9%',
    card: '0 0% 100%',
    cardForeground: '222.2 84% 4.9%',
    popover: '0 0% 100%',
    popoverForeground: '222.2 84% 4.9%',
  },
  effects: {
    scanlines: false,
    terminalCursor: false,
  },
}

/** MADFAM brand preset - blue accent for ecosystem apps */
export const madfamPreset: ThemeConfig = {
  name: 'MADFAM',
  description: 'MADFAM ecosystem brand theme',
  fonts: {
    primary: "'Inter', system-ui, -apple-system, sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  colors: {
    background: '0 0% 100%',
    foreground: '222.2 84% 4.9%',
    primary: '221 83% 53%',         // MADFAM brand blue (#3b82f6)
    primaryForeground: '0 0% 100%',
    secondary: '210 40% 96.1%',
    secondaryForeground: '222.2 47.4% 11.2%',
    muted: '210 40% 96.1%',
    mutedForeground: '215.4 16.3% 46.9%',
    accent: '221 83% 96%',
    accentForeground: '221 83% 53%',
    destructive: '0 84.2% 60.2%',
    destructiveForeground: '210 40% 98%',
    border: '214.3 31.8% 91.4%',
    input: '214.3 31.8% 91.4%',
    ring: '221 83% 53%',
    card: '0 0% 100%',
    cardForeground: '222.2 84% 4.9%',
    popover: '0 0% 100%',
    popoverForeground: '222.2 84% 4.9%',
  },
  effects: {
    scanlines: false,
    terminalCursor: false,
  },
}

/** Solarpunk preset - re-exports the solarpunk theme from dual-skin */
export { solarpunkTheme as solarpunkPreset } from '../themes/dual-skin'

export type PresetName = 'default' | 'madfam' | 'solarpunk'

export const presets: Record<PresetName, ThemeConfig> = {
  default: defaultPreset,
  madfam: madfamPreset,
  solarpunk: solarpunkTheme,
}

export function getPreset(name: PresetName): ThemeConfig {
  return presets[name]
}
