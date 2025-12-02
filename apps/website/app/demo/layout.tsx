import type { Metadata } from 'next'
import Link from 'next/link'
import { Navigation } from '@/components/navigation'

export const metadata: Metadata = {
  title: 'Interactive Demo | Janua Authentication Platform',
  description: 'Try Janua authentication components live. Experience MFA, passkeys, SSO, and more before signing up.',
}

const demoLinks = [
  { href: '/demo/signin', label: 'Sign In', description: 'Email, social, passkey login' },
  { href: '/demo/signup', label: 'Sign Up', description: 'User registration flow' },
  { href: '/demo/mfa', label: 'MFA', description: 'TOTP, SMS, backup codes' },
  { href: '/demo/security', label: 'Security', description: 'Sessions & devices' },
  { href: '/demo/sso', label: 'SSO', description: 'SAML & OIDC setup' },
  { href: '/demo/organizations', label: 'Organizations', description: 'Multi-tenancy' },
  { href: '/demo/rbac', label: 'RBAC', description: 'Roles & permissions' },
  { href: '/demo/compliance', label: 'Compliance', description: 'Audit logs & GDPR' },
  { href: '/demo/profile', label: 'Profile', description: 'User settings' },
]

export default function DemoLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 pt-16">
        <div className="container mx-auto px-4 py-8">
          {/* Header */}
          <header className="mb-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                  Try Janua Live
                </h1>
                <p className="text-slate-600 dark:text-slate-400 mt-2">
                  Interactive demos of our authentication components
                </p>
              </div>
              <Link
                href="/"
                className="text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
              >
                ← Back to Home
              </Link>
            </div>
          </header>

          {/* Navigation */}
          <nav className="mb-8 bg-white dark:bg-slate-800 rounded-lg shadow-sm p-4">
            <div className="flex flex-wrap gap-2">
              {demoLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-colors"
                  title={link.description}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </nav>

          {/* Content */}
          <main>{children}</main>

          {/* CTA Footer */}
          <footer className="mt-12 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-8 text-center">
            <h2 className="text-2xl font-bold text-white mb-2">
              Ready to get started?
            </h2>
            <p className="text-blue-100 mb-6">
              Create your free account and add authentication to your app in minutes.
            </p>
            <div className="flex justify-center gap-4">
              <Link
                href="https://app.janua.dev/signup"
                className="px-6 py-3 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition-colors"
              >
                Sign Up Free
              </Link>
              <Link
                href="/docs"
                className="px-6 py-3 border border-white text-white font-semibold rounded-lg hover:bg-white/10 transition-colors"
              >
                View Docs
              </Link>
            </div>
          </footer>
        </div>
      </div>
    </>
  )
}
