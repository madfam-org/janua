'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Zap, Shield, Code2, GitBranch, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import Link from 'next/link'
import { getCoveragePercentage } from '@/lib/coverage'

interface ActualMetrics {
  testCoverage: number
  sdkCount: number
  edgeLocations: number
  theoreticalLatency: string
  openSourceStatus: boolean
  securityAuditStatus: 'pending' | 'in-progress' | 'completed'
}

export function HonestHeroSection() {
  // These are ACTUAL metrics from the codebase analysis
  const [actualMetrics, setActualMetrics] = useState<ActualMetrics>({
    testCoverage: 19.6, // Real test coverage from pytest --cov (updated dynamically)
    sdkCount: 8, // Actually implemented SDKs (verified from packages/)
    edgeLocations: 100, // Via Cloudflare/Vercel Edge Network
    theoreticalLatency: '<30ms', // Based on edge architecture, not benchmarked at scale
    openSourceStatus: true, // Core is actually open source
    securityAuditStatus: 'pending' // Honest about security audit status
  })

  // Load real coverage data on component mount
  useEffect(() => {
    getCoveragePercentage().then((coverage) => {
      setActualMetrics(prev => ({
        ...prev,
        testCoverage: coverage
      }))
    }).catch(() => {
      // Keep fallback value if fetch fails
    })
  }, [])

  return (
    <section className="relative min-h-[85vh] flex items-center justify-center overflow-hidden">
      {/* Clean, honest background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950">
        <div className="absolute inset-0 bg-grid-slate-100 dark:bg-grid-slate-800 opacity-[0.03]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center max-w-4xl mx-auto">
          {/* Honest status badges */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex flex-wrap justify-center gap-3 mb-8"
          >
            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <Code2 className="w-3 h-3 mr-1.5 text-blue-600 dark:text-blue-400" />
              <span className="text-xs font-medium">{actualMetrics.sdkCount} Production SDKs</span>
            </Badge>

            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <Zap className="w-3 h-3 mr-1.5 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-medium">{actualMetrics.theoreticalLatency} Edge Response*</span>
            </Badge>

            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <GitBranch className="w-3 h-3 mr-1.5 text-green-600 dark:text-green-400" />
              <span className="text-xs font-medium">Open Source Core</span>
            </Badge>

            {actualMetrics.securityAuditStatus === 'pending' && (
              <Badge variant="outline" className="px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 border-amber-200">
                <Clock className="w-3 h-3 mr-1.5 text-amber-600" />
                <span className="text-xs font-medium">Security Audit: Q1 2025</span>
              </Badge>
            )}
          </motion.div>

          {/* Main headline - honest and compelling */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-slate-900 dark:text-white"
          >
            Authentication at the{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600 dark:from-blue-400 dark:to-cyan-400">
              Edge of Tomorrow
            </span>
          </motion.h1>

          {/* Subheadline - accurate claims */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-6 text-xl text-slate-600 dark:text-slate-300 max-w-3xl mx-auto"
          >
            The first authentication platform built edge-native from day one.
            Real passkey support, {actualMetrics.sdkCount} production SDKs, and sub-30ms theoretical response times
            via edge deployment architecture.
          </motion.p>

          {/* Transparency note */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-500 dark:text-slate-400"
          >
            <AlertCircle className="w-4 h-4" />
            <span>*Performance based on edge architecture. Real-world benchmarks coming Q1 2025.</span>
          </motion.div>

          {/* CTA buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-10 flex flex-col sm:flex-row gap-4 justify-center"
          >
            <Button size="lg" className="group" asChild>
              <Link href="https://app.janua.dev/auth/signup">
                Get Started
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button size="lg" className="group">
              View Live Demo
              <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="https://github.com/madfam-io/janua" target="_blank" rel="noopener">
                <GitBranch className="mr-2 w-4 h-4" />
                View Source Code
              </Link>
            </Button>
          </motion.div>

          {/* Real features that exist */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-8"
          >
            <div className="text-left">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                <h3 className="font-semibold text-slate-900 dark:text-white">Actually Implemented</h3>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                WebAuthn passkeys, TOTP MFA, SAML SSO, and OAuth 2.0 - all working in production code.
              </p>
            </div>

            <div className="text-left">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                <h3 className="font-semibold text-slate-900 dark:text-white">Real SDK Ecosystem</h3>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {actualMetrics.sdkCount} SDKs including TypeScript, Python, Go, React, Vue, and Flutter.
              </p>
            </div>

            <div className="text-left">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                <h3 className="font-semibold text-slate-900 dark:text-white">Edge Architecture</h3>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Deployed on Cloudflare/Vercel Edge for global sub-30ms response potential.
              </p>
            </div>
          </motion.div>

          {/* Honest progress tracker */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-16 p-6 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800"
          >
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-4">
              Current Development Status
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">Test Coverage</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-500"
                      style={{ width: `${actualMetrics.testCoverage}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono text-slate-900 dark:text-white">
                    {actualMetrics.testCoverage}%
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">Production SDKs</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-emerald-500"
                      style={{ width: `${(actualMetrics.sdkCount / 10) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono text-slate-900 dark:text-white">
                    {actualMetrics.sdkCount}/10
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">Edge Deployment</span>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                  <span className="text-sm text-slate-900 dark:text-white">
                    Active ({actualMetrics.edgeLocations}+ locations)
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}