'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, AlertCircle, Users as _Users, Zap as _Zap, Shield as _Shield, Code2 as _Code2, HelpCircle } from 'lucide-react'
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

// Pricing aligned with the ratified enclii+janua packaging decision
// (internal-devops decisions/2026-07-11-enclii-janua-packaging-ratification.md)
// and the /pricing page (apps/website/components/sections/pricing.tsx).
//
// Community (Open Source): Free, self-host, 2,000 MAU on managed
// Pro (Managed):           $29/mo flat per project, up to 10,000 MAU (fair use)
// Business (SSO):          $149/mo — design-partner / contract, NOT self-serve
// Enterprise:              Custom, Unlimited
const pricingTiers: PricingTier[] = [
  {
    name: 'Community',
    price: 'Free',
    description: 'Perfect for side projects and MVPs',
    mau: '2,000 MAU',
    badge: 'Great for MVPs',
    features: [
      'Passkey authentication',
      'Email + password auth',
      'Session management',
      'Community support',
      'Single region'
    ],
    notIncluded: [
      'No SLA',
      'No custom domains',
      'No SSO/SAML',
      'No advanced MFA'
    ],
    honestNote: 'Perfect for validating your idea without cost'
  },
  {
    name: 'Pro',
    price: '$29',
    description: 'Managed hosting for growing startups and teams',
    mau: 'Up to 10,000 MAU (flat, fair use)',
    badge: 'Most Popular',
    features: [
      'Everything in Community',
      'Social logins (OAuth)',
      'Organizations & RBAC',
      'Webhooks & events',
      'Email support',
      'Custom domain',
      'Advanced MFA (TOTP)',
      'Audit logs (30 days)'
    ],
    notIncluded: [
      'No SSO/SAML',
      'No SCIM',
      'No custom contracts'
    ],
    honestNote: 'Scales with you as you find product-market fit'
  },
  {
    name: 'Business',
    price: '$149',
    description: 'SSO/SAML for compliance-driven teams',
    mau: 'Higher volume',
    badge: 'Design partner',
    features: [
      'Everything in Pro',
      'SSO/SAML',
      'Advanced security policies',
      'Priority support',
      'Audit logs (90 days)',
      'Custom JWT claims',
      'IP allowlisting',
      'Rate limiting controls'
    ],
    notIncluded: [
      'No SCIM',
      'No custom contracts',
      'No dedicated support'
    ],
    honestNote: 'Early access via our design-partner program — talk to us'
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'For enterprises with custom needs',
    mau: 'Unlimited',
    badge: 'Full Support',
    features: [
      'Everything in Business',
      'SCIM provisioning',
      'Custom contracts & SLAs',
      'Dedicated support',
      // SLA is negotiated per contract at launch. We do not advertise a
      // specific uptime percentage publicly until we have an SRE on-call
      // rotation, an SLO definition file, and reproducible measurements.
      'Uptime SLA negotiated per contract',
      'Audit logs (unlimited)',
      'Custom integrations',
      'Security reviews',
      'MSA & BAA available',
      'White-glove onboarding'
    ],
    notIncluded: [],
    honestNote: 'Transparent pricing based on your actual needs'
  }
]

interface ComparisonRow {
  feature: string
  community: boolean | string
  pro: boolean | string
  business: boolean | string
  enterprise: boolean | string
}

const detailedComparison: ComparisonRow[] = [
  {
    feature: 'Monthly Active Users',
    community: '2,000',
    pro: '10,000',
    business: '50,000',
    enterprise: 'Unlimited'
  },
  {
    feature: 'Passkeys (WebAuthn)',
    community: true,
    pro: true,
    business: true,
    enterprise: true
  },
  {
    feature: 'MFA/TOTP',
    community: false,
    pro: true,
    business: true,
    enterprise: true
  },
  {
    feature: 'OAuth Providers',
    community: 'Email/password only',
    pro: 'Social (OAuth)',
    business: 'All',
    enterprise: 'All + Custom'
  },
  {
    feature: 'Support',
    community: 'Community',
    pro: 'Email',
    business: 'Priority',
    enterprise: 'Dedicated'
  },
  {
    feature: 'SLA',
    community: false,
    pro: false,
    business: false,
    // SLA is only offered at the Enterprise tier and is negotiated per
    // contract. No public uptime percentage until SRE on-call + SLO
    // definitions are in place.
    enterprise: 'Negotiated per contract'
  },
  {
    feature: 'SAML SSO',
    community: false,
    pro: false,
    business: true,
    enterprise: true
  },
  {
    feature: 'Audit Log Retention',
    community: false,
    pro: '30 days',
    business: '90 days',
    enterprise: 'Unlimited'
  }
]

export function HonestPricing() {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [showComparison, setShowComparison] = useState(false)

  const yearlyDiscount = 0.2 // 20% off

  // Business (SSO) is a design-partner / contract tier — not self-serve — so
  // it is shown with its flat monthly price but no self-serve yearly discount.
  const isContactTier = (tier: PricingTier) =>
    tier.name === 'Business' || tier.price === 'Custom'

  const getPrice = (tier: PricingTier) => {
    const { price } = tier
    if (price === 'Free' || price === 'Custom') return price
    const numPrice = parseInt(price.replace('$', ''))
    if (billingCycle === 'yearly' && !isContactTier(tier)) {
      const yearlyPrice = Math.round(numPrice * (1 - yearlyDiscount))
      return `$${yearlyPrice}`
    }
    return price
  }

  const getPriceLabel = (tier: PricingTier) => {
    const { price } = tier
    if (price === 'Free') return ''
    if (price === 'Custom') return 'Contact us'
    if (tier.name === 'Business') return '/mo · contact sales'
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
            <span>Currently in Private Alpha. Production packages coming soon.</span>
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
                tier.name === 'Pro'
                  ? 'border-blue-500 shadow-lg scale-105'
                  : 'border-slate-200 dark:border-slate-800'
              } p-6`}
            >
              {tier.badge && (
                <Badge
                  variant={tier.name === 'Pro' ? 'default' : 'secondary'}
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
                    {getPrice(tier)}
                  </span>
                  <span className="text-sm text-slate-600 dark:text-slate-400">
                    {getPriceLabel(tier)}
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
                variant={tier.name === 'Pro' ? 'default' : 'outline'}
                className="w-full"
                asChild
              >
                <Link
                  href={
                    isContactTier(tier)
                      ? '/contact'
                      : `https://app.janua.dev/auth/signup${
                          tier.name === 'Pro' ? '?plan=pro' : ''
                        }`
                  }
                >
                  {tier.price === 'Custom'
                    ? 'Contact Sales'
                    : tier.name === 'Business'
                      ? 'Contact us'
                      : 'Get Started'}
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
                    Community
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Pro
                  </th>
                  <th className="text-center p-4 font-semibold text-slate-900 dark:text-white">
                    Business
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
                      {typeof row.community === 'boolean' ? (
                        row.community ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.community}
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.pro === 'boolean' ? (
                        row.pro ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.pro}
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {typeof row.business === 'boolean' ? (
                        row.business ? (
                          <Check className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-400 mx-auto" />
                        )
                      ) : (
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          {row.business}
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
                What happens if I exceed the 10,000 MAU fair-use cap?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Pro is flat per project, not per-MAU metered. If you consistently run past the
                fair-use cap we&apos;ll reach out to move you to Business or a custom plan. We never cut off
                authentication - your users won&apos;t be affected.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                Are the SDKs really production-ready if not published yet?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                The code is production-ready, but we're finalizing package registry setup. You can use them
                directly from GitHub today. Public NPM/PyPI publishing is coming soon.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                What about test coverage?
              </h4>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                We're transparent about this. While the core authentication flows are well-tested, overall
                coverage needs improvement. We're actively working on this.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
