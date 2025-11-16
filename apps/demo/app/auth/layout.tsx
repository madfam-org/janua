import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Authentication Components Showcase | Plinto Demo',
  description: 'Interactive showcase of @plinto/ui authentication components',
}

export default function AuthShowcaseLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                @plinto/ui Showcase
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-2">
                Production-ready authentication components
              </p>
            </div>
            <Link
              href="/"
              className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
            >
              ← Back to Demo
            </Link>
          </div>
        </header>

        {/* Navigation */}
        <nav className="mb-8 bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4">
          <div className="flex flex-wrap gap-2">
            <Link
              href="/auth/signin-showcase"
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              SignIn
            </Link>
            <Link
              href="/auth/signup-showcase"
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              SignUp
            </Link>
            <Link
              href="/auth/mfa-showcase"
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              MFA
            </Link>
            <Link
              href="/auth/security-showcase"
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              Security
            </Link>
            <Link
              href="/auth/compliance-showcase"
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              Compliance
            </Link>
          </div>
        </nav>

        {/* Content */}
        <main>{children}</main>

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-gray-600 dark:text-gray-400">
          <p>
            Built with{' '}
            <a
              href="https://github.com/yourusername/plinto"
              className="text-blue-600 dark:text-blue-400 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              @plinto/ui
            </a>{' '}
            | Open-source authentication components
          </p>
        </footer>
      </div>
    </div>
  )
}
