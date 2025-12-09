import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { ThemeProvider, FloatingThemeToggle } from '@janua/ui'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Janua Dashboard',
  description: 'Manage your authentication and identity settings',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
          <FloatingThemeToggle />
        </ThemeProvider>
      </body>
    </html>
  )
}

// NOTE: FeatureFlagProvider temporarily removed due to React types conflict
// between Next.js 15 (React 19) and @janua/feature-flags (React 18 types)
// TODO: Re-add once types are aligned across the monorepo