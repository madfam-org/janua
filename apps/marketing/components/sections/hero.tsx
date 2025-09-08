'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Play, Zap, Shield, Globe } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export function HeroSection() {
  const [currentMetric, setCurrentMetric] = useState(0)
  
  const metrics = [
    { value: '<30ms', label: 'Edge Verification', icon: Zap },
    { value: '5 min', label: 'Integration Time', icon: ArrowRight },
    { value: '99.99%', label: 'Uptime SLA', icon: Shield },
    { value: '150+', label: 'Global Locations', icon: Globe },
  ]

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentMetric((prev) => (prev + 1) % metrics.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [metrics.length])

  return (
    <section className="relative pt-32 pb-24 sm:pt-40 sm:pb-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Main content */}
        <div className="text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm font-medium mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
              </span>
              Now in Private Alpha
            </div>

            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-gray-900 dark:text-white">
              Identity infrastructure
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
                that moves at the speed
              </span>
              <br />
              of your users
            </h1>

            {/* Subheadline */}
            <p className="mt-6 text-xl sm:text-2xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
              Sub-30ms global verification. Passkeys-first. Your data, your control.
              <br />
              The secure substrate for modern identity.
            </p>
          </motion.div>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mt-10 flex flex-col sm:flex-row gap-4 justify-center"
          >
            <Link href="/sign-up">
              <Button size="lg" className="text-lg px-8 py-6 w-full sm:w-auto">
                Start Building
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link href="#playground">
              <Button size="lg" variant="outline" className="text-lg px-8 py-6 w-full sm:w-auto">
                <Play className="mr-2 h-5 w-5" />
                View Demo
              </Button>
            </Link>
          </motion.div>

          {/* Metrics */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-8 max-w-4xl mx-auto"
          >
            {metrics.map((metric, index) => {
              const Icon = metric.icon
              return (
                <motion.div
                  key={metric.label}
                  animate={{
                    scale: currentMetric === index ? 1.05 : 1,
                    opacity: currentMetric === index ? 1 : 0.7,
                  }}
                  transition={{ duration: 0.3 }}
                  className="text-center"
                >
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-gray-100 dark:bg-gray-800 mb-3">
                    <Icon className="h-6 w-6 text-gray-700 dark:text-gray-300" />
                  </div>
                  <div className="text-3xl font-bold text-gray-900 dark:text-white">
                    {metric.value}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {metric.label}
                  </div>
                </motion.div>
              )
            })}
          </motion.div>
        </div>

        {/* Animated visual */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mt-20 relative"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-blue-400 to-purple-400 blur-3xl opacity-20" />
          <div className="relative bg-gray-900 rounded-2xl shadow-2xl p-8 overflow-hidden">
            {/* Code preview */}
            <div className="font-mono text-sm">
              <div className="text-gray-500">// 5-minute integration</div>
              <div className="mt-2">
                <span className="text-blue-400">import</span>
                <span className="text-white"> {'{ '}</span>
                <span className="text-green-400">withPlinto</span>
                <span className="text-white">{' }'}</span>
                <span className="text-blue-400"> from</span>
                <span className="text-yellow-400"> '@plinto/nextjs'</span>
              </div>
              <div className="mt-4">
                <span className="text-blue-400">export default</span>
                <span className="text-green-400"> withPlinto</span>
                <span className="text-white">(</span>
                <span className="text-purple-400">{'{'}</span>
              </div>
              <div className="ml-4">
                <span className="text-white">publicRoutes</span>
                <span className="text-gray-400">:</span>
                <span className="text-yellow-400"> ['/']</span>
                <span className="text-gray-400">,</span>
              </div>
              <div className="ml-4">
                <span className="text-white">afterAuth</span>
                <span className="text-gray-400">:</span>
                <span className="text-purple-400"> redirectToOrg</span>
              </div>
              <div>
                <span className="text-purple-400">{'}'}</span>
                <span className="text-white">)</span>
              </div>
              <div className="mt-4 text-gray-500">
                // Authentication ready. Ship it! 🚀
              </div>
            </div>

            {/* Animated latency indicator */}
            <div className="absolute top-4 right-4">
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-green-400 text-xs font-medium">Live</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}