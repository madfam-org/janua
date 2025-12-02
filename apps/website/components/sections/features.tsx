'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { 
  Zap, 
  Shield, 
  Globe, 
  Key, 
  Users, 
  BarChart3,
  Code2,
  Lock,
  Settings
} from 'lucide-react'
import { Badge } from '@janua/ui'

const features = [
  {
    icon: Zap,
    title: 'Edge-Fast Verification',
    description: 'Sub-30ms token verification from 150+ global edge locations. Your users feel the speed.',
    category: 'Performance',
    highlight: 'Sub-30ms',
    benefits: [
      'Global edge network',
      'Cached JWKS endpoints', 
      'Regional failover',
      'CDN optimization'
    ]
  },
  {
    icon: Key,
    title: 'Passkeys-First Authentication', 
    description: 'WebAuthn and biometric authentication by default. Password-free, phishing-resistant security.',
    category: 'Security',
    highlight: 'WebAuthn',
    benefits: [
      'Biometric authentication',
      'Hardware security keys',
      'Phishing resistant',
      'Cross-device sync'
    ]
  },
  {
    icon: Shield,
    title: 'Zero-Trust Architecture',
    description: 'Per-tenant signing keys, JWT rotation, and OPA policy evaluation. Security built in, not bolted on.',
    category: 'Security', 
    highlight: 'Zero-Trust',
    benefits: [
      'Per-tenant isolation',
      'Automatic key rotation',
      'Policy-based access',
      'Audit trail'
    ]
  },
  {
    icon: Globe,
    title: 'Global Data Residency',
    description: 'Deploy authentication in your region. EU, US, or global - full control over data location.',
    category: 'Compliance',
    highlight: 'Your Region',
    benefits: [
      'EU/US data residency',
      'GDPR compliance',
      'Regional isolation',
      'Sovereign cloud'
    ]
  },
  {
    icon: Code2,
    title: '5-Minute Integration',
    description: 'Drop-in middleware for Next.js, React, Node.js. From zero to authenticated in minutes.',
    category: 'Developer Experience',
    highlight: '5 Minutes',
    benefits: [
      'Next.js middleware',
      'React hooks',
      'TypeScript support',
      'Framework agnostic'
    ]
  },
  {
    icon: Users,
    title: 'Organizations & RBAC',
    description: 'Multi-tenant by design. Roles, permissions, and team management that scales with your business.',
    category: 'Enterprise',
    highlight: 'Multi-Tenant',
    benefits: [
      'Team management',
      'Custom roles',
      'Permission systems',
      'Org hierarchies'
    ]
  },
  {
    icon: BarChart3,
    title: 'Analytics & Insights',
    description: 'Real-time authentication metrics, user behavior analysis, and security monitoring.',
    category: 'Analytics',
    highlight: 'Real-Time',
    benefits: [
      'Auth analytics',
      'Security metrics',
      'User insights',
      'Performance monitoring'
    ]
  },
  {
    icon: Lock,
    title: 'Advanced Security',
    description: 'Threat detection, anomaly monitoring, and automated incident response. Enterprise-grade protection.',
    category: 'Security',
    highlight: 'Threat Detection',
    benefits: [
      'Anomaly detection',
      'Automated response',
      'Risk scoring',
      'Fraud prevention'
    ]
  },
  {
    icon: Settings,
    title: 'Complete Customization',
    description: 'White-label UI, custom domains, branded emails. Make it yours from day one.',
    category: 'Customization',
    highlight: 'White-Label',
    benefits: [
      'Custom domains',
      'Branded UI',
      'Custom emails',
      'Theme system'
    ]
  }
]

const categories = [
  { name: 'All', color: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200' },
  { name: 'Performance', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  { name: 'Security', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
  { name: 'Developer Experience', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' },
  { name: 'Enterprise', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' },
  { name: 'Compliance', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  { name: 'Analytics', color: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300' },
  { name: 'Customization', color: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300' }
]

export function FeaturesGrid() {
  const [ref, inView] = useInView({
    triggerOnce: true,
    threshold: 0.1
  })

  return (
    <section className="py-24" ref={ref}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <Badge variant="outline" className="mb-4">
            Platform Features
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Everything you need for
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
              modern authentication
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            From edge-fast verification to enterprise-grade security, 
            Janua provides the complete identity infrastructure your applications need.
          </p>
        </motion.div>

        {/* Category filters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="flex flex-wrap gap-2 justify-center mb-12"
        >
          {categories.map((category) => (
            <Badge 
              key={category.name}
              variant="secondary" 
              className={`cursor-pointer hover:opacity-80 transition-opacity ${category.color}`}
            >
              {category.name}
            </Badge>
          ))}
        </motion.div>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon
            const categoryStyle = categories.find(cat => cat.name === feature.category)?.color || categories[0].color
            
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="group relative bg-white dark:bg-gray-900 rounded-2xl p-8 border border-gray-200 dark:border-gray-800 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-xl transition-all duration-300"
              >
                {/* Feature category badge */}
                <div className="flex items-center justify-between mb-6">
                  <Badge variant="secondary" className={categoryStyle}>
                    {feature.category}
                  </Badge>
                  <Badge variant="outline" className="text-xs font-bold">
                    {feature.highlight}
                  </Badge>
                </div>

                {/* Icon */}
                <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg mb-6 group-hover:scale-110 transition-transform duration-300">
                  <Icon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>

                {/* Content */}
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                  {feature.title}
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-6 leading-relaxed">
                  {feature.description}
                </p>

                {/* Benefits list */}
                <ul className="space-y-2">
                  {feature.benefits.map((benefit, benefitIndex) => (
                    <motion.li
                      key={benefit}
                      initial={{ opacity: 0, x: -20 }}
                      animate={inView ? { opacity: 1, x: 0 } : {}}
                      transition={{ duration: 0.3, delay: (index * 0.1) + (benefitIndex * 0.05) }}
                      className="flex items-center text-sm text-gray-500 dark:text-gray-400"
                    >
                      <svg className="w-4 h-4 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      {benefit}
                    </motion.li>
                  ))}
                </ul>

                {/* Hover effect */}
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/50 dark:to-purple-950/50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10" />
              </motion.div>
            )
          })}
        </div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="text-center mt-16"
        >
          <p className="text-gray-600 dark:text-gray-300 mb-4">
            Ready to see these features in action?
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Badge variant="outline" className="cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-950/50 transition-colors">
              View Documentation →
            </Badge>
            <Badge variant="outline" className="cursor-pointer hover:bg-purple-50 dark:hover:bg-purple-950/50 transition-colors">
              Try Interactive Demo →
            </Badge>
          </div>
        </motion.div>
      </div>
    </section>
  )
}