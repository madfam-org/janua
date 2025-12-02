'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, AlertCircle, Users, Zap, Shield, Code2, HelpCircle } from 'lucide-react'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import Link from 'next/link'

interface PricingTier {
  name: string
  price: string
  description: string
  mau: string
  features: string[]
  notIncluded: string[]
  badge?: string
  honestNote?: string
}

const pricingTiers: PricingTier[] = [
  {
    name: 'Developer',
    price: 'Free',
    description: 'Perfect for testing and small projects',
    mau: '10,000 MAU',
    badge: 'Great for MVPs',
    features: [
      'All authentication methods',
      'Passkeys & MFA included',
      'All 13 SDKs',
      'Edge deployment',
      'Community support',
      'Basic analytics'
    ],
    notIncluded: [
      'No SLA guarantees',
      'No dedicated support',
      'No custom domains',
      'No advanced audit logs'
    ],
    honestNote: 'Perfect for validating your idea without cost'
  },
  {
    name: 'Startup',
    price: '$99',
    description: 'For growing applications',
    mau: '50,000 MAU',
    badge: 'Most Popular',
    features: [
      'Everything in Developer',
      '99.9% uptime SLA',
      'Email support',
      'Custom domains',
      'Advanced analytics',
      'Webhook events',
      'Team management (5 seats)'
    ],
    notIncluded: [
      'No priority support',
      'No SAML SSO',
      'No compliance reports'
    ],
    honestNote: 'Scales with you as you find product-market fit'
  },
  {
    name: 'Growth',
    price: '$499',
    description: 'For scaling businesses',
    mau: '250,000 MAU',
    features: [
      'Everything in Startup',
      'Priority support',
      'SAML SSO',
      'Advanced RBAC',
      'Audit logs (90 days)',
      'Team management (25 seats)',
      'Custom rate limits'
    ],
    notIncluded: [
      'No dedicated success manager',
      'No custom contracts',
      'No on-premise deployment'
    ],
    honestNote: 'Enterprise features without enterprise pricing'
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'For large organizations',
    mau: 'Unlimited',
    badge: 'Full Support',
    features: [
      'Everything in Growth',
      'Dedicated success manager',
      'Custom contracts & SLAs',
      'Compliance assistance',
      'Unlimited audit retention',
      'Unlimited team seats',
      'On-premise option',
      'White-label option'
    ],
    notIncluded: [],
    honestNote: 'Transparent pricing based on your actual needs'
  }
]

interface ComparisonRow {
  feature: string
  developer: boolean | string
  startup: boolean | string
  growth: boolean | string
  enterprise: boolean | string
}

const detailedComparison: ComparisonRow[] = [
  {
    feature: 'Monthly Active Users',
    developer: '10,000',
    startup: '50,000',
    growth: '250,000',
    enterprise: 'Unlimited'
  },
  {
    feature: 'Passkeys (WebAuthn)',
    developer: true,
    startup: true,
    growth: true,
    enterprise: true
  },
  {
    feature: 'MFA/TOTP',
    developer: true,
    startup: true,
    growth: true,
    enterprise: true
  },
  {
    feature: 'OAuth Providers',
    developer: '5',
    startup: '5',
    growth: 'All',
    enterprise: 'All + Custom'
  },
  {
    feature: 'Edge Response Time',
    developer: '<30ms*',
    startup: '<30ms*',
    growth: '<30ms*',
    enterprise: '<30ms*'
  },
  {
    feature: 'Support',
    developer: 'Community',
    startup: 'Email',
    growth: 'Priority',
    enterprise: 'Dedicated'
  },
  {
    feature: 'SLA',
    developer: false,
    startup: '99.9%',
    growth: '99.95%',
    enterprise: 'Custom'
  },
  {
    feature: 'SAML SSO',
    developer: false,
    startup: false,
    growth: true,
    enterprise: true
  },
  {
    feature: 'Audit Log Retention',
    developer: '7 days',
    startup: '30 days',
    growth: '90 days',
    enterprise: 'Unlimited'
  }
]

export function HonestPricing() {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [showComparison, setShowComparison] = useState(false)

  const yearlyDiscount = 0.2 // 20% off

  const getPrice = (price: string) => {
    if (price === 'Free' || price === 'Custom') return price
    const numPrice = parseInt(price.replace('$', ''))
    if (billingCycle === 'yearly') {
      const yearlyPrice = Math.round(numPrice * (1 - yearlyDiscount))
      return `$${yearlyPrice}`
    }
    return price
  }

  const getPriceLabel = (price: string) => {
    if (price === 'Free') return ''
    if (price === 'Custom') return 'Contact us'
    return billingCycle === 'monthly' ? '/month' : '/month (billed annually)'
  }

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Simple, Honest Pricing
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            No hidden fees. No surprise charges. Just transparent pricing that scales with your growth.
          </p>

          {/* Important Note */}
          <div className="mt-6 inline-flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
            <AlertCircle className="w-4 h-4" />
            <span>Currently in beta. Production packages coming Q1 2025.</span>
          </div>
        </div>

        {/* Billing Toggle */}
        <div className="flex justify-center mb-12">
          <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-1 inline-flex">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                billingCycle === 'monthly'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                billingCycle === 'yearly'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              Yearly
              <Badge variant="secondary" className="ml-2 text-xs">
                Save 20%
              </Badge>
            </button>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
          {pricingTiers.map((tier, idx) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className={`relative bg-white dark:bg-slate-900 rounded-lg border ${
                tier.name === 'Startup'
                  ? 'border-blue-500 shadow-lg scale-105'
                  : 'border-slate-200 dark:border-slate-800'
              } p-6`}
            >
              {tier.badge && (
                <Badge
                  variant={tier.name === 'Startup' ? 'default' : 'secondary'}
                  className="absolute -top-3 left-1/2 -translate-x-1/2"
                >
                  {tier.badge}
                </Badge>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  {tier.name}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  {tier.description}
                </p>
              </div>

              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-slate-900 dark:text-white">
                    {getPrice(tier.price)}
                  </span>
                  <span className="text-sm text-slate-600 dark:text-slate-400">
                    {getPriceLabel(tier.price)}
                  </span>
                </div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mt-2">
                  {tier.mau}
                </p>
              </div>

              {/* Features */}
              <div className="space-y-3 mb-6">
                {tier.features.map((feature, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Check className="w-4 h-4 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      {feature}
                    </span>
                  </div>
                ))}
              </div>

              {/* Not Included */}
              {tier.notIncluded.length > 0 && (
                <div className="space-y-2 mb-6 pt-4 border-t border-slate-100 dark:border-slate-800">
                  {tier.notIncluded.map((item, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <X className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {item}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Honest Note */}
              {tier.honestNote && (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic mb-6">
                  {tier.honestNote}
                </p>
              )}

              {/* CTA Button */}
              <Button
                variant={tier.name === 'Startup' ? 'default' : 'outline'}
                className="w-full"
                asChild
              >
                <Link href={tier.price === 'Custom' ? '/contact' : '/signup'}>
                  {tier.price === 'Custom' ? 'Contact Sales' : 'Get Started'}
                </Link>
              </Button>
            </motion.div>
          ))}
        </div>

        {/* Detailed Comparison */}
        <div className="text-center mb-8">
          <Button
            variant="outline"
            onClick={() => setShowComparison(!showComparison)}
          >
            <HelpCircle className="w-4 h-4 mr-2" />
            {showComparison ? 'Hide' : 'Show'} Detailed Comparison
          </Button>
        </div>

        {showComparison && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="overflow-x-auto"
          >
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  <th className="text-left p-4 font-semibold text-slate-900 dark:text-white">
                    Feature
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Developer
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Startup
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Growth
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Enterprise
                  </th>
                </tr>
              </thead>
              <tbody>
                {detailedComparison.map((row, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-slate-100 dark:border-slate-800"
                  >
                    <td className="p-4 text-sm font-medium text-slate-700 dark:text-slate-300">
                      {row.feature}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.developer === 'boolean' ? (
                        row.developer ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.developer}
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.startup === 'boolean' ? (
                        row.startup ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.startup}
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.growth === 'boolean' ? (
                        row.growth ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.growth}
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.enterprise === 'boolean' ? (
                        row.enterprise ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.enterprise}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="text-xs text-slate-500 dark:text-slate-400 mt-4 text-center">
              * Edge response times based on architecture design. Production benchmarks coming Q1 2025.
            </p>
          </motion.div>
        )}

        {/* Honest FAQ */}
        <div className="mt-16 p-8 bg-slate-50 dark:bg-slate-900/50 rounded-lg">
          <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-6">
            Honest Answers to Common Questions
          </h3>

          <div className="space-y-6">
            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                Why are you cheaper than Auth0 and Clerk?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                We're newer and still proving ourselves. Our edge-native architecture is also inherently more
                cost-effective. As we mature and add features, prices may adjust, but we'll always grandfather
                existing customers.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                What happens if I exceed my MAU limit?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                We'll notify you at 80% usage and help you upgrade. We never cut off authentication - your
                users won't be affected. Overages are billed at standard rates with no penalties.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                Are the SDKs really production-ready if not published yet?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                The code is production-ready, but we're finalizing package registry setup. You can use them
                directly from GitHub today. NPM/PyPI publishing is coming in Q1 2025.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                What about the 31.3% test coverage?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                We're transparent about this. While the core authentication flows are well-tested, overall
                coverage needs improvement. We're actively working on this and update the percentage weekly.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}