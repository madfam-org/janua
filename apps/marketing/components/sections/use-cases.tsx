'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { 
  ShoppingCart, 
  Briefcase, 
  GraduationCap, 
  HeartHandshake, 
  Building2, 
  Gamepad2,
  ArrowRight,
  Users,
  Clock,
  Shield
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const useCases = [
  {
    icon: ShoppingCart,
    title: 'E-commerce & Retail',
    description: 'Secure customer authentication for online stores and marketplaces',
    stats: { users: '2M+', conversion: '+23%', security: '99.9%' },
    challenges: [
      'Cart abandonment due to complex registration',
      'Account takeover and fraud prevention',
      'Cross-device shopping experience'
    ],
    solutions: [
      'Passwordless checkout with passkeys',
      'Real-time fraud detection',
      'Seamless device synchronization'
    ],
    color: 'from-green-400 to-blue-500',
    bgColor: 'bg-green-50 dark:bg-green-950/20'
  },
  {
    icon: Briefcase,
    title: 'SaaS & B2B Platforms',
    description: 'Enterprise-grade authentication for business applications',
    stats: { users: '500K+', uptime: '99.99%', compliance: 'SOC 2' },
    challenges: [
      'Complex user provisioning',
      'Multi-tenant security isolation',
      'Compliance requirements'
    ],
    solutions: [
      'Automated SCIM provisioning',
      'Per-tenant encryption keys',
      'Built-in compliance controls'
    ],
    color: 'from-blue-400 to-purple-500',
    bgColor: 'bg-blue-50 dark:bg-blue-950/20'
  },
  {
    icon: GraduationCap,
    title: 'Education & EdTech',
    description: 'Secure access management for students, teachers, and administrators',
    stats: { users: '1M+', institutions: '500+', uptime: '99.9%' },
    challenges: [
      'Age-appropriate authentication',
      'Classroom access control',
      'Parent/guardian oversight'
    ],
    solutions: [
      'Simplified biometric login',
      'Role-based class permissions',
      'Guardian consent workflows'
    ],
    color: 'from-purple-400 to-pink-500',
    bgColor: 'bg-purple-50 dark:bg-purple-950/20'
  },
  {
    icon: HeartHandshake,
    title: 'Healthcare & Telehealth',
    description: 'HIPAA-compliant identity management for healthcare providers',
    stats: { users: '250K+', compliance: 'HIPAA', security: 'Zero-Trust' },
    challenges: [
      'HIPAA compliance requirements',
      'Emergency access protocols',
      'Multi-provider coordination'
    ],
    solutions: [
      'HIPAA-compliant audit trails',
      'Emergency break-glass access',
      'Provider federation support'
    ],
    color: 'from-red-400 to-orange-500',
    bgColor: 'bg-red-50 dark:bg-red-950/20'
  },
  {
    icon: Building2,
    title: 'Financial Services',
    description: 'Bank-grade security for fintech and financial applications',
    stats: { transactions: '10M+', fraud: '<0.01%', compliance: 'PCI DSS' },
    challenges: [
      'Regulatory compliance',
      'Fraud prevention',
      'High-value transaction security'
    ],
    solutions: [
      'Multi-factor authentication',
      'AI-powered risk assessment',
      'Regulatory reporting tools'
    ],
    color: 'from-yellow-400 to-red-500',
    bgColor: 'bg-yellow-50 dark:bg-yellow-950/20'
  },
  {
    icon: Gamepad2,
    title: 'Gaming & Entertainment',
    description: 'Fast, secure authentication for gaming platforms and content',
    stats: { users: '5M+', latency: '<50ms', sessions: '24/7' },
    challenges: [
      'Low-latency requirements',
      'Cross-platform gaming',
      'Parental controls'
    ],
    solutions: [
      'Edge-optimized verification',
      'Universal account linking',
      'Advanced parental controls'
    ],
    color: 'from-indigo-400 to-cyan-500',
    bgColor: 'bg-indigo-50 dark:bg-indigo-950/20'
  }
]

export function UseCases() {
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
            Industry Solutions
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Built for every
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
              industry vertical
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            From e-commerce to healthcare, Plinto provides specialized authentication 
            solutions that meet the unique requirements of your industry.
          </p>
        </motion.div>

        {/* Use cases grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-16">
          {useCases.map((useCase, index) => {
            const Icon = useCase.icon
            
            return (
              <motion.div
                key={useCase.title}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className={`group relative ${useCase.bgColor} rounded-2xl p-8 border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 transition-all duration-300 overflow-hidden`}
              >
                {/* Background gradient */}
                <div className={`absolute inset-0 bg-gradient-to-br ${useCase.color} opacity-0 group-hover:opacity-5 transition-opacity duration-300`} />
                
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl bg-gradient-to-br ${useCase.color} text-white shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                        {useCase.title}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-300 text-sm mt-1">
                        {useCase.description}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                  {Object.entries(useCase.stats).map(([key, value]) => (
                    <div key={key} className="text-center">
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">
                        {value}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                        {key}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Challenges & Solutions */}
                <div className="grid md:grid-cols-2 gap-6">
                  {/* Challenges */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
                      <Clock className="w-4 h-4 mr-2 text-red-500" />
                      Challenges
                    </h4>
                    <ul className="space-y-2">
                      {useCase.challenges.map((challenge, challengeIndex) => (
                        <li key={challengeIndex} className="text-sm text-gray-600 dark:text-gray-400 flex items-start">
                          <span className="w-1 h-1 bg-red-400 rounded-full mt-2 mr-3 flex-shrink-0" />
                          {challenge}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Solutions */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
                      <Shield className="w-4 h-4 mr-2 text-green-500" />
                      Solutions
                    </h4>
                    <ul className="space-y-2">
                      {useCase.solutions.map((solution, solutionIndex) => (
                        <li key={solutionIndex} className="text-sm text-gray-600 dark:text-gray-400 flex items-start">
                          <svg className="w-3 h-3 text-green-500 mt-1 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          {solution}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="text-center bg-gray-50 dark:bg-gray-900 rounded-2xl p-12"
        >
          <Users className="w-12 h-12 text-blue-600 dark:text-blue-400 mx-auto mb-6" />
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Don't see your industry?
          </h3>
          <p className="text-lg text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto">
            Plinto's flexible architecture adapts to any use case. Our team works with you 
            to design the perfect authentication solution for your specific requirements.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="text-lg px-8">
              Schedule Consultation
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8">
              View All Case Studies
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  )
}