'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, ArrowRight } from 'lucide-react'
import { Button } from '@janua/ui'
import Link from 'next/link'
import { cn } from '@/lib/utils'

export function PricingSection() {
  const [isAnnual, setIsAnnual] = useState(false)

  const plans = [
    {
      name: 'Community',
      description: 'Perfect for side projects and MVPs',
      price: { monthly: 0, annual: 0 },
      featured: false,
      cta: 'Start Free',
      href: 'https://app.janua.dev/auth/signup',
      features: [
        '2,000 monthly active users',
        'Passkey authentication',
        'Email + password auth',
        'Session management',
        'Edge verification (<30ms)',
        'Community support',
        'Single region'
      ],
      limitations: [
        'No SLA',
        'No custom domains',
        'No SSO/SAML',
        'No advanced MFA'
      ]
    },
    {
      name: 'Pro',
      description: 'For growing startups and teams',
      price: { monthly: 69, annual: 59 },
      featured: true,
      cta: 'Start 14-day trial',
      href: 'https://app.janua.dev/auth/signup?plan=pro',
      features: [
        '10,000 monthly active users',
        'Everything in Community',
        'Social logins (OAuth)',
        'Organizations & RBAC',
        'Webhooks & events',
        'Email support',
        '99.9% uptime SLA',
        'Custom domain',
        'Advanced MFA (TOTP)',
        'Audit logs (30 days)',
        'Multi-region'
      ],
      limitations: [
        'No SSO/SAML',
        'No SCIM',
        'No custom contracts'
      ]
    },
    {
      name: 'Scale',
      description: 'For scale-ups with compliance needs',
      price: { monthly: 299, annual: 249 },
      featured: false,
      cta: 'Start 14-day trial',
      href: 'https://app.janua.dev/auth/signup?plan=scale',
      features: [
        '50,000 monthly active users',
        'Everything in Pro',
        'SSO/SAML',
        'Advanced security policies',
        'Priority support',
        '99.95% uptime SLA',
        'Audit logs (90 days)',
        'Custom JWT claims',
        'IP allowlisting',
        'Rate limiting controls'
      ],
      limitations: [
        'No SCIM',
        'No custom contracts',
        'No dedicated support'
      ]
    },
    {
      name: 'Enterprise',
      description: 'For enterprises with custom needs',
      price: { monthly: 'Custom', annual: 'Custom' },
      featured: false,
      cta: 'Contact Sales',
      href: 'https://app.janua.dev/contact-sales',
      features: [
        'Unlimited MAU',
        'Everything in Scale',
        'SCIM provisioning',
        'Custom contracts & SLAs',
        'Dedicated support',
        '99.99% uptime SLA',
        'Audit logs (unlimited)',
        'Custom integrations',
        'Data residency options',
        'Security reviews',
        'MSA & BAA available',
        'White-glove onboarding'
      ],
      limitations: []
    }
  ]

  return (
    <div className="py-12">
      <div className="text-center mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
            Simple, transparent pricing
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto mb-8">
            Start free with 2,000 MAU. No credit card required.
            Scale as you grow with predictable pricing.
          </p>

          {/* Billing toggle */}
          <div className="flex items-center justify-center gap-4">
            <span className={cn(
              "text-sm font-medium",
              !isAnnual ? "text-gray-900 dark:text-white" : "text-gray-500"
            )}>
              Monthly
            </span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-200 dark:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span
                className={cn(
                  "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                  isAnnual ? "translate-x-6" : "translate-x-1"
                )}
              />
            </button>
            <span className={cn(
              "text-sm font-medium",
              isAnnual ? "text-gray-900 dark:text-white" : "text-gray-500"
            )}>
              Annual
              <span className="ml-2 text-green-600 dark:text-green-400 font-semibold">
                Save 15%
              </span>
            </span>
          </div>
        </motion.div>
      </div>

      {/* Pricing cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
        {plans.map((plan, index) => (
          <motion.div
            key={plan.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className={cn(
              "relative rounded-2xl border p-8",
              plan.featured
                ? "border-blue-500 bg-gradient-to-b from-blue-50 to-white dark:from-blue-950/20 dark:to-gray-900"
                : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
            )}
          >
            {plan.featured && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-blue-600 to-purple-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                  MOST POPULAR
                </span>
              </div>
            )}

            <div className="mb-6">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                {plan.name}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {plan.description}
              </p>
            </div>

            <div className="mb-6">
              {typeof plan.price.monthly === 'number' ? (
                <>
                  <span className="text-4xl font-bold text-gray-900 dark:text-white">
                    ${isAnnual ? plan.price.annual : plan.price.monthly}
                  </span>
                  <span className="text-gray-600 dark:text-gray-400 ml-2">
                    /month
                  </span>
                  {isAnnual && typeof plan.price.monthly === 'number' && plan.price.monthly > 0 && typeof plan.price.annual === 'number' && (
                    <div className="text-sm text-gray-500 mt-1">
                      <span className="line-through">${plan.price.monthly * 12}</span>
                      <span className="ml-2 text-green-600 dark:text-green-400">
                        Save ${(plan.price.monthly - plan.price.annual) * 12}/year
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <span className="text-3xl font-bold text-gray-900 dark:text-white">
                  {plan.price.monthly}
                </span>
              )}
            </div>

            <Link href={plan.href}>
              <Button
                className={cn(
                  "w-full mb-6",
                  plan.featured
                    ? "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                    : ""
                )}
                variant={plan.featured ? "default" : "outline"}
              >
                {plan.cta}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>

            <div className="space-y-3">
              {plan.features.map((feature) => (
                <div key={feature} className="flex items-start gap-3">
                  <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    {feature}
                  </span>
                </div>
              ))}
              {plan.limitations.map((limitation) => (
                <div key={limitation} className="flex items-start gap-3">
                  <X className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-500 dark:text-gray-500">
                    {limitation}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Additional pricing info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="mt-16 p-8 bg-gray-50 dark:bg-gray-900 rounded-2xl"
      >
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 text-center">
          Overage Pricing
        </h3>
        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-2">
              $10
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              per 1,000 additional MAU
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Pro tier
            </div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-2">
              $8
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              per 1,000 additional MAU
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Scale tier
            </div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-2">
              Custom
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Volume discounts available
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Enterprise tier
            </div>
          </div>
        </div>
      </motion.div>

      {/* FAQ */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6 }}
        className="mt-16"
      >
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-8 text-center">
          Frequently Asked Questions
        </h3>
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              What counts as a Monthly Active User (MAU)?
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Any unique user who authenticates at least once in a calendar month. 
              Multiple logins by the same user count as one MAU.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Can I change plans anytime?
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Yes! You can upgrade or downgrade at any time. Changes take effect 
              immediately and we'll prorate your billing.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              Do you offer startup discounts?
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Yes! Startups in accelerators or with less than $1M funding can get 
              50% off Pro tier for the first year. Contact us for details.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
              What payment methods do you accept?
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              We accept all major credit cards, ACH transfers for annual plans, 
              and can work with your procurement process for Enterprise.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  )
}