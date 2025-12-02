import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, MapPin, Clock, DollarSign, Users, Globe, Heart, Award } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Careers | Janua',
  description: 'Join our mission to build the future of authentication. Remote-first culture, competitive benefits, and meaningful work.',
}

export default function CareersPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-5xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Build the Future of{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600">
                Authentication
              </span>
            </h1>
            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10">
              Join our remote-first team building edge-native authentication that powers millions of users worldwide.
            </p>
          </div>
        </div>
      </section>

      {/* Culture & Benefits */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Why Work at Janua?
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">
              We're building something meaningful with a team that values excellence, transparency, and work-life balance.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Globe className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Remote First</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Work from anywhere with flexible hours and async collaboration.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <DollarSign className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Competitive Equity</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Meaningful equity stake in a fast-growing authentication platform.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Heart className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Health & Wellness</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Comprehensive health insurance and wellness stipend.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Award className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Learning & Growth</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Conference budget, learning stipend, and mentorship programs.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Open Positions */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Open Positions
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">
              We're growing our team across engineering, product, and operations.
            </p>
          </div>

          <div className="space-y-6">
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                <div className="mb-4 md:mb-0">
                  <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                    Senior Platform Engineer
                  </h3>
                  <div className="flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-400">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-4 h-4" />
                      <span>Remote</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      <span>Full-time</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      <span>Engineering</span>
                    </div>
                  </div>
                  <p className="text-slate-600 dark:text-slate-400 mt-2">
                    Build and scale our edge-native authentication infrastructure. Experience with Go, Rust, or distributed systems.
                  </p>
                </div>
                <Button className="group shrink-0" asChild>
                  <Link href="mailto:careers@janua.dev?subject=Senior Platform Engineer">
                    Apply Now
                    <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                <div className="mb-4 md:mb-0">
                  <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                    Frontend Engineer
                  </h3>
                  <div className="flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-400">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-4 h-4" />
                      <span>Remote</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      <span>Full-time</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      <span>Engineering</span>
                    </div>
                  </div>
                  <p className="text-slate-600 dark:text-slate-400 mt-2">
                    Create beautiful, accessible authentication experiences. React, TypeScript, and modern web standards expertise.
                  </p>
                </div>
                <Button className="group shrink-0" asChild>
                  <Link href="mailto:careers@janua.dev?subject=Frontend Engineer">
                    Apply Now
                    <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                <div className="mb-4 md:mb-0">
                  <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                    Developer Relations Engineer
                  </h3>
                  <div className="flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-400">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-4 h-4" />
                      <span>Remote</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      <span>Full-time</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      <span>Developer Experience</span>
                    </div>
                  </div>
                  <p className="text-slate-600 dark:text-slate-400 mt-2">
                    Build community, create educational content, and help developers succeed with Janua's authentication platform.
                  </p>
                </div>
                <Button className="group shrink-0" asChild>
                  <Link href="mailto:careers@janua.dev?subject=Developer Relations Engineer">
                    Apply Now
                    <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>

          <div className="text-center mt-12">
            <p className="text-slate-600 dark:text-slate-400 mb-6">
              Don't see the perfect role? We're always looking for exceptional talent.
            </p>
            <Button variant="outline" className="group" asChild>
              <Link href="mailto:careers@janua.dev?subject=General Interest">
                Send Us Your Resume
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}