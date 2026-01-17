/**
 * Janua Dual-Skin Theme System
 * 
 * Two distinct visual themes for different user contexts:
 * - Solarpunk: For superusers (admin.janua.dev) - Terminal/hacker aesthetic
 * - Neutral: For tenant admins (app.janua.dev) - Professional SaaS dashboard
 */

export type ThemeSkin = 'solarpunk' | 'neutral';

export interface ThemeConfig {
  name: string;
  description: string;
  fonts: {
    primary: string;
    mono: string;
  };
  colors: {
    background: string;
    foreground: string;
    primary: string;
    primaryForeground: string;
    secondary: string;
    secondaryForeground: string;
    muted: string;
    mutedForeground: string;
    accent: string;
    accentForeground: string;
    destructive: string;
    destructiveForeground: string;
    border: string;
    input: string;
    ring: string;
    card: string;
    cardForeground: string;
    popover: string;
    popoverForeground: string;
  };
  effects: {
    glow?: string;
    scanlines?: boolean;
    terminalCursor?: boolean;
  };
}

/**
 * Solarpunk Theme - The Bridge (admin.janua.dev)
 * 
 * Design philosophy:
 * - Terminal/hacker aesthetic with Matrix-inspired visuals
 * - JetBrains Mono for all text (monospace everywhere)
 * - Matrix green (#00ff9d) as primary accent
 * - Deep blacks (#0a0a0a) for backgrounds
 * - Glow effects and terminal-style animations
 * 
 * Target audience: Internal superusers (@madfam.io only)
 */
export const solarpunkTheme: ThemeConfig = {
  name: 'Solarpunk',
  description: 'Terminal/hacker aesthetic for superuser administration',
  fonts: {
    primary: "'JetBrains Mono', monospace",
    mono: "'JetBrains Mono', monospace",
  },
  colors: {
    // Core
    background: '0 0% 4%',        // #0a0a0a - Deep terminal black
    foreground: '150 100% 50%',    // #00ff9d - Matrix green
    
    // Primary (Matrix Green)
    primary: '150 100% 50%',
    primaryForeground: '0 0% 4%',
    
    // Secondary (Darker gray)
    secondary: '0 0% 12%',
    secondaryForeground: '150 100% 50%',
    
    // Muted (Terminal gray)
    muted: '0 0% 15%',
    mutedForeground: '150 40% 60%',
    
    // Accent (Dimmer green)
    accent: '150 80% 40%',
    accentForeground: '0 0% 100%',
    
    // Destructive (Red alerts)
    destructive: '0 84.2% 60.2%',
    destructiveForeground: '210 40% 98%',
    
    // UI Elements
    border: '150 30% 20%',
    input: '0 0% 15%',
    ring: '150 100% 50%',
    
    // Card
    card: '0 0% 6%',
    cardForeground: '150 100% 50%',
    
    // Popover
    popover: '0 0% 8%',
    popoverForeground: '150 100% 50%',
  },
  effects: {
    glow: '0 0 20px hsl(150 100% 50% / 0.3)',
    scanlines: true,
    terminalCursor: true,
  },
};

/**
 * Neutral Theme - The Cockpit (app.janua.dev)
 * 
 * Design philosophy:
 * - Clean, professional SaaS dashboard aesthetic
 * - Inter font for readability and modern feel
 * - Customizable brand primary color (tenant can override)
 * - Clean whites and subtle grays
 * - No special effects, focus on clarity
 * 
 * Target audience: Tenant administrators (any authenticated user)
 */
export const neutralTheme: ThemeConfig = {
  name: 'Neutral',
  description: 'Professional SaaS dashboard for tenant administration',
  fonts: {
    primary: "'Inter', system-ui, -apple-system, sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  colors: {
    // Core
    background: '0 0% 100%',       // White
    foreground: '222.2 84% 4.9%',  // Near black
    
    // Primary (Customizable by tenant)
    primary: '222.2 47.4% 11.2%',
    primaryForeground: '210 40% 98%',
    
    // Secondary
    secondary: '210 40% 96.1%',
    secondaryForeground: '222.2 47.4% 11.2%',
    
    // Muted
    muted: '210 40% 96.1%',
    mutedForeground: '215.4 16.3% 46.9%',
    
    // Accent
    accent: '210 40% 96.1%',
    accentForeground: '222.2 47.4% 11.2%',
    
    // Destructive
    destructive: '0 84.2% 60.2%',
    destructiveForeground: '210 40% 98%',
    
    // UI Elements
    border: '214.3 31.8% 91.4%',
    input: '214.3 31.8% 91.4%',
    ring: '222.2 84% 4.9%',
    
    // Card
    card: '0 0% 100%',
    cardForeground: '222.2 84% 4.9%',
    
    // Popover
    popover: '0 0% 100%',
    popoverForeground: '222.2 84% 4.9%',
  },
  effects: {
    glow: undefined,
    scanlines: false,
    terminalCursor: false,
  },
};

/**
 * Get theme configuration by skin name
 */
export function getTheme(skin: ThemeSkin): ThemeConfig {
  switch (skin) {
    case 'solarpunk':
      return solarpunkTheme;
    case 'neutral':
      return neutralTheme;
    default:
      return neutralTheme;
  }
}

/**
 * Generate CSS variables from theme config
 */
export function generateCSSVariables(theme: ThemeConfig): string {
  return `
    --background: ${theme.colors.background};
    --foreground: ${theme.colors.foreground};
    --card: ${theme.colors.card};
    --card-foreground: ${theme.colors.cardForeground};
    --popover: ${theme.colors.popover};
    --popover-foreground: ${theme.colors.popoverForeground};
    --primary: ${theme.colors.primary};
    --primary-foreground: ${theme.colors.primaryForeground};
    --secondary: ${theme.colors.secondary};
    --secondary-foreground: ${theme.colors.secondaryForeground};
    --muted: ${theme.colors.muted};
    --muted-foreground: ${theme.colors.mutedForeground};
    --accent: ${theme.colors.accent};
    --accent-foreground: ${theme.colors.accentForeground};
    --destructive: ${theme.colors.destructive};
    --destructive-foreground: ${theme.colors.destructiveForeground};
    --border: ${theme.colors.border};
    --input: ${theme.colors.input};
    --ring: ${theme.colors.ring};
  `;
}

/**
 * Detect which theme to use based on domain
 */
export function detectThemeFromDomain(hostname: string): ThemeSkin {
  if (hostname.includes('admin.janua') || hostname.includes('localhost:3004')) {
    return 'solarpunk';
  }
  return 'neutral';
}

/**
 * Theme-specific utility classes
 */
export const themeUtilities = {
  solarpunk: {
    glow: 'shadow-[0_0_20px_hsl(150_100%_50%_/_0.3)]',
    glowText: 'drop-shadow-[0_0_10px_hsl(150_100%_50%_/_0.5)]',
    pulseBorder: 'animate-pulse-glow',
    terminal: 'font-mono bg-terminal-black text-matrix',
  },
  neutral: {
    cardHover: 'hover:shadow-md transition-shadow',
    buttonHover: 'hover:bg-primary/90 transition-colors',
    focusRing: 'focus-visible:ring-2 focus-visible:ring-ring',
  },
};

export default {
  solarpunk: solarpunkTheme,
  neutral: neutralTheme,
  getTheme,
  generateCSSVariables,
  detectThemeFromDomain,
  themeUtilities,
};
