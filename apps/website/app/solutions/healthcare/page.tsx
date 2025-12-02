import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, Heart, Shield, FileText, Users, Lock, Database, Award, Stethoscope } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Healthcare Authentication | Janua',
  description: 'HIPAA-compliant authentication for healthcare applications. Secure patient data with enterprise-grade security and audit compliance.',
}

export default function HealthcarePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-green-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-green-950" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <div className="flex items-center justify-center gap-2 mb-6">
              <Heart className="w-8 h-8 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-600 dark:text-green-400 uppercase tracking-wide">Healthcare Solution</span>
            </div>

            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              HIPAA-Compliant{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-blue-600">
                Authentication
              </span>
            </h1>

            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10 max-w-3xl mx-auto">
              Secure patient data and healthcare applications with HIPAA-compliant authentication.
              Built for healthcare providers, telemedicine platforms, and health tech innovators.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="group" asChild>
                <Link href="https://app.janua.dev/auth/signup">
                  Get HIPAA Compliant
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>

              <Button size="lg" variant="outline" asChild>
                <Link href="https://docs.janua.dev/solutions/healthcare">
                  HIPAA Documentation
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* HIPAA Compliance */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-slate-900 dark:text-white mb-16">
            Built for Healthcare Compliance
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Award className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">HIPAA Compliant</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Signed BAAs and full HIPAA compliance certification
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Audit Ready</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Complete audit trails for compliance and regulatory reporting
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Database className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Data Encryption</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                End-to-end encryption for PHI protection at rest and in transit
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Lock className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Access Controls</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Role-based access with minimum necessary principle enforcement
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Healthcare Features */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Purpose-Built for Healthcare
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              Every feature designed to meet the unique security and compliance requirements of healthcare organizations.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Stethoscope className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Provider Authentication</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Secure practitioner login with NPI verification, license validation, and privilege management.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Patient Portal Security</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Secure patient authentication with identity verification and consent management.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Shield className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Break Glass Access</h3>
                  <p className="text-slate-600 dark:text-slate-400">
                    Emergency access protocols with full audit logging for critical patient care scenarios.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-green-100 to-blue-100 dark:from-green-900/20 dark:to-blue-900/20 rounded-2xl p-8">
              <div className="text-center">
                <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                  Secure Healthcare Innovation
                </h3>
                <p className="text-slate-600 dark:text-slate-300 mb-8">
                  Focus on patient care while we ensure your applications meet the highest healthcare security standards.
                </p>
                <div className="space-y-4">
                  <Button size="lg" className="w-full group" asChild>
                    <Link href="https://app.janua.dev/auth/signup">
                      Start HIPAA Compliant
                      <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" className="w-full" asChild>
                    <Link href="mailto:healthcare@janua.dev">
                      Request BAA
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Healthcare Use Cases
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">
              Trusted by healthcare organizations worldwide
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center mb-4">
                <Heart className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Telemedicine Platforms</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm">
                Secure video consultations with provider verification and patient authentication.
              </p>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center mb-4">
                <FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">EHR Systems</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm">
                Electronic health records with role-based access and comprehensive audit trails.
              </p>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm">
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center mb-4">
                <Database className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Health Apps</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm">
                Mobile health applications with secure patient data synchronization.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Healthcare CTA */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-6">
            Ready to Secure Healthcare Data?
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-10">
            Join healthcare organizations using Janua to protect patient privacy
            and meet regulatory compliance requirements.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="group" asChild>
              <Link href="https://app.janua.dev/auth/signup">
                Get HIPAA Compliant
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="mailto:healthcare@janua.dev">
                Request Healthcare Demo
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}