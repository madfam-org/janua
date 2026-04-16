import { Suspense } from 'react'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth'
import { ThemeProvider, FloatingThemeToggle } from '@janua/ui'
import { PostHogProvider } from '@/components/PostHogProvider'

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
            <Suspense fallback={null}>
              <PostHogProvider>
                {children}
              </PostHogProvider>
            </Suspense>
          </AuthProvider>
          <FloatingThemeToggle />
        </ThemeProvider>
      </body>
    </html>
  )
}

// NOTE: FeatureFlagProvider temporarily removed due to React types conflict
// between Next.js 15 (React 19) and @janua/feature-flags (React 18 types)
// TODO(2026-04-16): Re-add FeatureFlagProvider once React types are aligned across the monorepo -- tracked in backlog
