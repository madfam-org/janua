import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, Calendar, User, Clock } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Blog | Janua',
  description: 'Stay updated with the latest in authentication, security, and developer insights from the Janua team.',
}

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      <section className="relative pt-32 pb-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-5xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Security & Developer{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600">
                Insights
              </span>
            </h1>
            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10">
              Deep dives into authentication, security best practices, and the future of edge-native development.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mt-16">
            <article className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="p-6">
                <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-3">
                  <Calendar className="w-4 h-4" />
                  <span>Coming Soon</span>
                </div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">
                  The Future of Passwordless Authentication
                </h2>
                <p className="text-slate-600 dark:text-slate-400 mb-4">
                  Exploring how WebAuthn and passkeys are revolutionizing user authentication and security.
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <User className="w-4 h-4" />
                    <span>Janua Team</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <Clock className="w-4 h-4" />
                    <span>5 min read</span>
                  </div>
                </div>
              </div>
            </article>

            <article className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="p-6">
                <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-3">
                  <Calendar className="w-4 h-4" />
                  <span>Coming Soon</span>
                </div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">
                  Building Edge-Native Applications
                </h2>
                <p className="text-slate-600 dark:text-slate-400 mb-4">
                  Best practices for leveraging edge computing to create globally fast applications.
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <User className="w-4 h-4" />
                    <span>Janua Team</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <Clock className="w-4 h-4" />
                    <span>8 min read</span>
                  </div>
                </div>
              </div>
            </article>

            <article className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="p-6">
                <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-3">
                  <Calendar className="w-4 h-4" />
                  <span>Coming Soon</span>
                </div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">
                  Security Compliance Made Simple
                </h2>
                <p className="text-slate-600 dark:text-slate-400 mb-4">
                  How to meet SOC 2, HIPAA, and GDPR requirements without compromising developer velocity.
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <User className="w-4 h-4" />
                    <span>Janua Team</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <Clock className="w-4 h-4" />
                    <span>6 min read</span>
                  </div>
                </div>
              </div>
            </article>
          </div>

          <div className="text-center mt-16">
            <p className="text-slate-600 dark:text-slate-400 mb-8">
              Our blog is launching soon with in-depth technical content and industry insights.
            </p>
            <Button className="group" asChild>
              <Link href="/contact">
                Subscribe for Updates
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}