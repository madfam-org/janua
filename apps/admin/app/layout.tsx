import type { Metadata } from 'next'
// NOTE: Google Fonts temporarily disabled for build verification
// This works fine on Vercel - only an issue in sandboxed environments
// import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { FeatureFlagProvider } from '@janua/feature-flags'
import { ThemeProvider, FloatingThemeToggle } from '@janua/ui'
import { CONSOLE_CONFIG_ELEMENT } from '@janua/ui/console-runtime'
import { readConsoleConfig } from '@/lib/console-runtime.server'

export const dynamic = 'force-dynamic'

// const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Janua Admin - Internal Tools',
  description: 'Internal superadmin tools for Janua platform management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  let config
  try { config = readConsoleConfig() } catch {
    return <html lang="en"><body><p role="alert">Console configuration unavailable</p></body></html>
  }
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{/* className={inter.className} */}
        <div id={CONSOLE_CONFIG_ELEMENT} hidden data-config={JSON.stringify(config)} />
        <ThemeProvider>
          <AuthProvider runtimeConfig={config}>
            <FeatureFlagProvider
              context={{
                attributes: {
                  app: 'admin',
                  internal: true,
                  superadmin: true,
                },
              }}
            >
              {children}
            </FeatureFlagProvider>
          </AuthProvider>
          <FloatingThemeToggle />
        </ThemeProvider>
      </body>
    </html>
  )
}
