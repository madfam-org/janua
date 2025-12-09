import type { Metadata } from 'next'
// NOTE: Google Fonts temporarily disabled for build verification
// This works fine on Vercel - only an issue in sandboxed environments
// import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { FeatureFlagProvider } from '@janua/feature-flags'
import { ThemeProvider, FloatingThemeToggle } from '@janua/ui'

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
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{/* className={inter.className} */}
        <ThemeProvider>
          <AuthProvider>
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