import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, Building2, Shield, Globe, Users, Settings, Lock, FileText, Award } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Enterprise Authentication | Janua',
  description: 'Enterprise-grade authentication with SOC 2 compliance, 99.99% uptime, and dedicated support. Secure your organization at scale.',
}

export default function EnterprisePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-800" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <div className="flex items-center justify-center gap-2 mb-6">
              <Building2 className="w-8 h-8 text-slate-700 dark:text-slate-300" />
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 uppercase tracking-wide">Enterprise Solution</span>
            </div>

            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Enterprise-Grade{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-slate-700 to-blue-600">
                Authentication
              </span>
            </h1>

            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10 max-w-3xl mx-auto">
              SOC 2 compliant, 99.99% uptime SLA, and enterprise-grade security.
              Secure your organization with authentication infrastructure built for the largest enterprises.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="group" asChild>
                <Link href="mailto:enterprise@janua.dev">
                  Contact Sales
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>

              <Button size="lg" variant="outline" asChild>
                <Link href="https://docs.janua.dev/enterprise">
                  Enterprise Docs
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Compliance & Security */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-slate-900 dark:text-white mb-16">
            Enterprise-Ready Compliance
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Award className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">SOC 2 Type II</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Certified secure by independent auditors
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">GDPR & CCPA</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Full compliance with global privacy regulations
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Lock className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Zero Trust</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Built on zero-trust security principles
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Globe className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">99.99% Uptime</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Enterprise SLA with financial guarantees
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise Features */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Built for Enterprise Scale
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              Every feature designed to meet the rigorous demands of enterprise security and operations teams.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            <div className="space-y-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-slate-700 dark:text-slate-300" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Advanced User Management</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Bulk user provisioning, automated deprovisioning, and SCIM integration for seamless directory sync.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText className="w-6 h-6 text-slate-700 dark:text-slate-300" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Comprehensive Audit Logs</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Complete audit trail with real-time monitoring, alerting, and compliance reporting.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Settings className="w-6 h-6 text-slate-700 dark:text-slate-300" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Flexible Deployment</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Cloud, on-premise, or hybrid deployment options to meet your compliance requirements.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Shield className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Advanced Threat Protection</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    AI-powered anomaly detection, device fingerprinting, and behavioral analysis.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Globe className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Global Data Residency</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Choose where your data is stored and processed to meet regional compliance requirements.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Award className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Dedicated Support</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    24/7 dedicated support team with guaranteed response times and technical account management.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise CTA */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-6">
            Ready for Enterprise Authentication?
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-10">
            Join Fortune 500 companies using Janua to secure their organizations.
            Let's discuss your specific requirements and compliance needs.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white mb-2">99.99%</div>
              <div className="text-sm text-slate-600 dark:text-slate-400">Uptime SLA</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white mb-2">&lt; 24h</div>
              <div className="text-sm text-slate-600 dark:text-slate-400">Support Response</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white mb-2">SOC 2</div>
              <div className="text-sm text-slate-600 dark:text-slate-400">Type II Certified</div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="group" asChild>
              <Link href="mailto:enterprise@janua.dev">
                Contact Enterprise Sales
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="https://calendly.com/janua/enterprise-demo">
                Schedule Demo
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}