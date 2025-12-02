import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, ShoppingCart, Shield, Zap, Globe, CreditCard, Users, BarChart3 } from 'lucide-react'

export const metadata: Metadata = {
  title: 'E-commerce Authentication | Janua',
  description: 'Secure, fast authentication for e-commerce platforms. Reduce cart abandonment and increase conversions with streamlined checkout flows.',
}

export default function EcommercePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-cyan-50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <div className="flex items-center justify-center gap-2 mb-6">
              <ShoppingCart className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              <span className="text-sm font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wide">E-commerce Solution</span>
            </div>

            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Streamline Checkout,{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600">
                Boost Conversions
              </span>
            </h1>

            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10 max-w-3xl mx-auto">
              Reduce cart abandonment with frictionless authentication. Passkey-powered checkout flows
              that work across devices, increase customer trust, and drive revenue growth.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="group" asChild>
                <Link href="https://app.janua.dev/auth/signup">
                  Start Free Trial
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>

              <Button size="lg" variant="outline" asChild>
                <Link href="https://docs.janua.dev/solutions/ecommerce">
                  View Documentation
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
            Why E-commerce Businesses Choose Janua
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <BarChart3 className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Reduce Cart Abandonment</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Streamlined auth flows reduce checkout friction by up to 40%
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Lightning Fast</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Sub-30ms authentication response times globally
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Bank-Grade Security</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                WebAuthn passkeys eliminate password-based vulnerabilities
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Globe className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Global Scale</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Edge deployment across 100+ locations worldwide
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
              Built for E-commerce Success
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              Everything you need to create secure, seamless checkout experiences that customers trust.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <CreditCard className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">One-Click Checkout</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Customers authenticate with biometrics or device recognition. No passwords, no friction.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Guest Checkout</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Enable secure guest purchases without forcing account creation. Convert more visitors to customers.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Shield className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Fraud Prevention</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Device-bound authentication reduces fraud while maintaining seamless user experience.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl p-8">
              <div className="text-center">
                <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                  Ready to Boost Conversions?
                </h3>
                <p className="text-slate-600 dark:text-slate-300 mb-8">
                  Join leading e-commerce brands using Janua for secure, fast checkout experiences.
                </p>
                <Button size="lg" className="w-full group" asChild>
                  <Link href="https://app.janua.dev/auth/signup">
                    Get Started Free
                    <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}