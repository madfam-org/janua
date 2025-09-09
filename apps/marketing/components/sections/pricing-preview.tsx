'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { Check, ArrowRight, Zap, Building2, Rocket, Crown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const tiers = [
  {
    name: 'Community',
    icon: Zap,
    price: 'Free',
    description: 'Perfect for side projects and small applications',
    mau: '2,000 MAU',
    highlight: false,
    color: 'from-gray-400 to-gray-600',
    bgColor: 'bg-white dark:bg-gray-900',
    borderColor: 'border-gray-200 dark:border-gray-800',
    features: [
      '2,000 monthly active users',
      'Passkeys authentication',
      'Social login (Google, GitHub)',
      'Basic organizations',
      'Community support',
      'Standard integrations',
      'Email notifications'
    ],
    limitations: [
      'Community support only',
      'Standard SLA',
      'Basic customization'
    ]
  },
  {
    name: 'Pro',
    icon: Building2,
    price: '$69',
    period: '/month',
    description: 'For growing teams and production applications',
    mau: '10,000 MAU',
    highlight: true,
    color: 'from-blue-400 to-blue-600',
    bgColor: 'bg-blue-50 dark:bg-blue-950/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    features: [
      'Everything in Community',
      '10,000 monthly active users',
      'Advanced RBAC',
      'Custom domains',
      'Email support',
      'Webhooks & APIs',
      'Advanced analytics',
      'Custom branding',
      'SSO integrations'
    ],
    limitations: []
  },
  {
    name: 'Scale',
    icon: Rocket,
    price: '$299',
    period: '/month',
    description: 'For high-growth companies and demanding workloads',
    mau: '50,000 MAU',
    highlight: false,
    color: 'from-purple-400 to-purple-600',
    bgColor: 'bg-purple-50 dark:bg-purple-950/20',
    borderColor: 'border-purple-200 dark:border-purple-800',
    features: [
      'Everything in Pro',
      '50,000 monthly active users',
      'Priority support',
      'Advanced security features',
      'Custom integrations',
      'Compliance reporting',
      'Multi-region deployment',
      'Advanced rate limiting',
      'Custom SLA'
    ],
    limitations: []
  },
  {
    name: 'Enterprise',
    icon: Crown,
    price: 'Custom',
    description: 'Tailored solutions for large organizations',
    mau: 'Unlimited',
    highlight: false,
    color: 'from-yellow-400 to-orange-500',
    bgColor: 'bg-gradient-to-br from-yellow-50 to-orange-50 dark:from-yellow-950/20 dark:to-orange-950/20',
    borderColor: 'border-yellow-200 dark:border-yellow-800',
    features: [
      'Everything in Scale',
      'Unlimited monthly active users',
      'Dedicated support team',
      'Custom contract terms',
      'On-premise deployment',
      'SAML & OIDC providers',
      'SCIM provisioning',
      'Custom compliance',
      'Dedicated infrastructure'
    ],
    limitations: []
  }
]

const faqs = [
  {
    question: 'What counts as a Monthly Active User (MAU)?',
    answer: 'An MAU is a unique user who authenticates at least once during a calendar month. We count across all your applications and environments.'
  },
  {
    question: 'Can I upgrade or downgrade anytime?',
    answer: 'Yes! You can change your plan anytime. Upgrades are immediate, downgrades take effect at the next billing cycle.'
  },
  {
    question: 'Do you offer annual discounts?',
    answer: 'Yes, annual plans receive a 20% discount. Contact sales for enterprise pricing and custom terms.'
  }
]

export function PricingPreview() {
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
            Simple Pricing
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Scale with confidence,
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
              pay as you grow
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            Start free and upgrade when you're ready. No hidden fees, no surprises. 
            Just transparent pricing that scales with your success.
          </p>
        </motion.div>

        {/* Pricing cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
          {tiers.map((tier, index) => {
            const Icon = tier.icon
            
            return (
              <motion.div
                key={tier.name}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className={`relative ${tier.bgColor} rounded-2xl p-8 border-2 ${tier.borderColor} ${tier.highlight ? 'shadow-xl scale-105 z-10' : 'hover:shadow-lg'} transition-all duration-300`}
              >
                {/* Popular badge */}
                {tier.highlight && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <Badge className={`bg-gradient-to-r ${tier.color} text-white border-0 shadow-lg`}>
                      Most Popular
                    </Badge>
                  </div>
                )}

                {/* Header */}
                <div className="text-center mb-8">
                  <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-r ${tier.color} text-white mb-4`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    {tier.name}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-300 text-sm mb-4">
                    {tier.description}
                  </p>
                  <div className="flex items-baseline justify-center">
                    <span className="text-4xl font-bold text-gray-900 dark:text-white">
                      {tier.price}
                    </span>
                    {tier.period && (
                      <span className="text-gray-600 dark:text-gray-300 ml-1">
                        {tier.period}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                    {tier.mau}
                  </div>
                </div>

                {/* CTA */}
                <Button 
                  className={`w-full mb-8 ${tier.highlight ? `bg-gradient-to-r ${tier.color} hover:shadow-lg` : ''}`}
                  variant={tier.highlight ? 'default' : 'outline'}
                  size="lg"
                >
                  {tier.name === 'Community' ? 'Start Free' : 
                   tier.name === 'Enterprise' ? 'Contact Sales' : 'Start Trial'}
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Button>

                {/* Features */}
                <ul className="space-y-3">
                  {tier.features.map((feature, featureIndex) => (
                    <li key={featureIndex} className="flex items-start text-sm">
                      <Check className="w-4 h-4 text-green-500 mt-0.5 mr-3 flex-shrink-0" />
                      <span className="text-gray-600 dark:text-gray-300">
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* Limitations */}
                {tier.limitations.length > 0 && (
                  <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                      Limitations
                    </h4>
                    <ul className="space-y-2">
                      {tier.limitations.map((limitation, limitationIndex) => (
                        <li key={limitationIndex} className="flex items-start text-sm text-gray-500 dark:text-gray-400">
                          <span className="w-1 h-1 bg-gray-400 rounded-full mt-2 mr-3 flex-shrink-0" />
                          {limitation}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>

        {/* Feature comparison hint */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="text-center mb-16"
        >
          <Button variant="outline" size="lg" className="group">
            View Detailed Feature Comparison
            <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Button>
        </motion.div>

        {/* FAQ */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="bg-gray-50 dark:bg-gray-900 rounded-2xl p-12"
        >
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white text-center mb-8">
            Frequently Asked Questions
          </h3>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {faqs.map((faq, index) => (
              <motion.div
                key={faq.question}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: 0.7 + index * 0.1 }}
              >
                <h4 className="font-semibold text-gray-900 dark:text-white mb-3">
                  {faq.question}
                </h4>
                <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
                  {faq.answer}
                </p>
              </motion.div>
            ))}
          </div>

          <div className="text-center mt-8 pt-8 border-t border-gray-200 dark:border-gray-700">
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              More questions? We're here to help.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button variant="outline">
                Contact Sales
              </Button>
              <Button variant="outline">
                View Documentation
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}