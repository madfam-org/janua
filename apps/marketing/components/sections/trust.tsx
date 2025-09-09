'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { Badge } from '@/components/ui/badge'

const companies = [
  {
    name: 'TechCorp',
    logo: '/logos/techcorp.svg',
    size: 'Enterprise',
    users: '50K+'
  },
  {
    name: 'StartupHub',
    logo: '/logos/startuphub.svg', 
    size: 'Scale',
    users: '25K+'
  },
  {
    name: 'DevTools Inc',
    logo: '/logos/devtools.svg',
    size: 'Pro',
    users: '10K+'
  },
  {
    name: 'BuildCo',
    logo: '/logos/buildco.svg',
    size: 'Pro', 
    users: '15K+'
  },
  {
    name: 'CloudNative',
    logo: '/logos/cloudnative.svg',
    size: 'Enterprise',
    users: '75K+'
  }
]

const stats = [
  {
    value: '500K+',
    label: 'Monthly Active Users',
    description: 'Secured across all platforms'
  },
  {
    value: '99.99%',
    label: 'Uptime SLA',
    description: 'Global infrastructure reliability'
  },
  {
    value: '< 30ms',
    label: 'Verification Speed', 
    description: 'Edge-optimized performance'
  },
  {
    value: '150+',
    label: 'Global Locations',
    description: 'Worldwide coverage'
  }
]

export function TrustSection() {
  const [ref, inView] = useInView({
    triggerOnce: true,
    threshold: 0.1
  })

  return (
    <section className="py-24 bg-white dark:bg-gray-950" ref={ref}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Trust indicators */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-8">
            Trusted by teams at
          </p>
          
          {/* Company logos */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 items-center justify-items-center">
            {companies.map((company, index) => (
              <motion.div
                key={company.name}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                className="flex flex-col items-center group cursor-pointer"
              >
                {/* Placeholder logo - in production would use actual logos */}
                <div className="w-20 h-12 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center group-hover:bg-gray-200 dark:group-hover:bg-gray-700 transition-colors">
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                    {company.name}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {company.size}
                  </Badge>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {company.users} users
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8"
        >
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.4 + index * 0.1 }}
              className="text-center"
            >
              <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
                {stat.value}
              </div>
              <div className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-1">
                {stat.label}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {stat.description}
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Additional trust signals */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8"
        >
          <div className="text-center p-6 rounded-lg bg-gray-50 dark:bg-gray-900">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg mb-4">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              SOC 2 Type II
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Audited security and availability controls
            </p>
          </div>

          <div className="text-center p-6 rounded-lg bg-gray-50 dark:bg-gray-900">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg mb-4">
              <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              GDPR & CCPA
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Full compliance with privacy regulations
            </p>
          </div>

          <div className="text-center p-6 rounded-lg bg-gray-50 dark:bg-gray-900">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-lg mb-4">
              <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              99.9% SLA
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Enterprise-grade uptime guarantee
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}