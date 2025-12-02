import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, Cloud, Shield, Users, Settings, Zap, Database, Lock, BarChart3 } from 'lucide-react'

export const metadata: Metadata = {
  title: 'SaaS Authentication | Janua',
  description: 'Enterprise-grade authentication for SaaS applications. Multi-tenant architecture, SSO integration, and developer-friendly APIs.',
}

export default function SaasPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-purple-950" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <div className="flex items-center justify-center gap-2 mb-6">
              <Cloud className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              <span className="text-sm font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wide">SaaS Solution</span>
            </div>

            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Enterprise Auth for{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-blue-600">
                Modern SaaS
              </span>
            </h1>

            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10 max-w-3xl mx-auto">
              Multi-tenant architecture, enterprise SSO, and developer-friendly APIs.
              Build secure SaaS applications without the authentication complexity.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="group" asChild>
                <Link href="https://app.janua.dev/auth/signup">
                  Start Building
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>

              <Button size="lg" variant="outline" asChild>
                <Link href="https://docs.janua.dev/solutions/saas">
                  API Documentation
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Key Benefits */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-slate-900 dark:text-white mb-16">
            Why SaaS Teams Choose Janua
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Database className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Multi-Tenant Ready</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Built-in tenant isolation and management for SaaS applications
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Settings className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Enterprise SSO</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                SAML, OIDC, and custom integrations for enterprise customers
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Developer First</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Clean APIs, comprehensive SDKs, and excellent documentation
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <BarChart3 className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Usage Analytics</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Detailed insights into user authentication patterns and security
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Enterprise-Grade Features
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              Everything your SaaS needs to serve enterprise customers while maintaining developer velocity.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Organization Management</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Complete tenant management with role-based access control and user provisioning APIs.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Lock className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Advanced Security</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    MFA enforcement, session management, and compliance-ready audit logging.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Settings className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Custom Branding</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    White-label authentication flows that match your brand and customer experience.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/20 dark:to-blue-900/20 rounded-2xl p-8">
              <div className="text-center">
                <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                  Ship Enterprise Features Fast
                </h3>
                <p className="text-slate-600 dark:text-slate-300 mb-8">
                  Focus on your product while we handle the authentication complexity your enterprise customers demand.
                </p>
                <div className="space-y-4">
                  <Button size="lg" className="w-full group" asChild>
                    <Link href="https://app.janua.dev/auth/signup">
                      Start Free Trial
                      <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" className="w-full" asChild>
                    <Link href="https://docs.janua.dev/quickstart">
                      5-Minute Quickstart
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Code Example */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Simple Integration
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">
              Get started with just a few lines of code
            </p>
          </div>

          <div className="bg-slate-900 dark:bg-slate-800 rounded-lg p-6 overflow-x-auto">
            <pre className="text-green-400 font-mono text-sm">
              <code>{`// Initialize Janua in your SaaS app
import { JanuaAuth } from '@janua/react'

function App() {
  return (
    <JanuaAuth
      tenantId="your-tenant-id"
      organizationId="customer-org-id"
      config={{
        sso: true,
        mfa: 'optional',
        branding: {
          logo: '/your-logo.png',
          primaryColor: '#6366f1'
        }
      }}
    >
      <YourSaaSApp />
    </JanuaAuth>
  )
}`}</code>
            </pre>
          </div>
        </div>
      </section>
    </div>
  )
}