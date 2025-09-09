'use client'

import { motion } from 'framer-motion'
import { Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ComparisonSection() {
  const competitors = [
    { name: 'Plinto', highlight: true },
    { name: 'Clerk' },
    { name: 'Auth0' },
    { name: 'Supabase' }
  ]

  const metrics = [
    {
      category: 'Performance',
      items: [
        {
          metric: 'Edge Verification',
          plinto: '<30ms',
          clerk: '50-100ms',
          auth0: '80-150ms',
          supabase: '60-120ms'
        },
        {
          metric: 'Global Edge PoPs',
          plinto: '150+',
          clerk: '~30',
          auth0: '~20',
          supabase: '~15'
        },
        {
          metric: 'Time to First Auth',
          plinto: '5 min',
          clerk: '30 min',
          auth0: '45 min',
          supabase: '20 min'
        }
      ]
    },
    {
      category: 'Features',
      items: [
        {
          metric: 'Passkey Support',
          plinto: 'Native',
          clerk: 'Add-on',
          auth0: 'Beta',
          supabase: 'Planned'
        },
        {
          metric: 'Multi-Region Data',
          plinto: true,
          clerk: false,
          auth0: true,
          supabase: false
        },
        {
          metric: 'Event Sourcing',
          plinto: true,
          clerk: false,
          auth0: false,
          supabase: false
        },
        {
          metric: 'Plugin Architecture',
          plinto: true,
          clerk: false,
          auth0: 'Limited',
          supabase: false
        }
      ]
    },
    {
      category: 'Pricing',
      items: [
        {
          metric: 'Free Tier MAU',
          plinto: '10,000',
          clerk: '5,000',
          auth0: '7,000',
          supabase: '50,000'
        },
        {
          metric: 'Pro Tier Price',
          plinto: '$69/mo',
          clerk: '$99/mo',
          auth0: '$240/mo',
          supabase: '$25/mo'
        },
        {
          metric: 'Overage Cost/1k MAU',
          plinto: '$10',
          clerk: '$20',
          auth0: '$28',
          supabase: '$0.00325'
        }
      ]
    },
    {
      category: 'Developer Experience',
      items: [
        {
          metric: 'SDK Languages',
          plinto: '6+',
          clerk: '4',
          auth0: '10+',
          supabase: '8'
        },
        {
          metric: 'Local Development',
          plinto: true,
          clerk: 'Limited',
          auth0: true,
          supabase: true
        },
        {
          metric: 'Self-Hosting',
          plinto: 'Coming',
          clerk: false,
          auth0: false,
          supabase: true
        }
      ]
    }
  ]

  const renderValue = (value: any, isPlinto: boolean = false) => {
    if (typeof value === 'boolean') {
      return value ? (
        <Check className={cn("h-5 w-5", isPlinto ? "text-green-500" : "text-gray-400")} />
      ) : (
        <X className="h-5 w-5 text-gray-300 dark:text-gray-600" />
      )
    }
    
    if (value === 'Limited') {
      return <span className="text-yellow-600 dark:text-yellow-400">{value}</span>
    }
    
    return <span className={cn(isPlinto && "font-semibold text-blue-600 dark:text-blue-400")}>{value}</span>
  }

  return (
    <div>
      <div className="text-center mb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Built different. Performs better.
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            See how Plinto compares to other identity platforms. 
            Spoiler: we're faster, more flexible, and actually care about your data sovereignty.
          </p>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="overflow-x-auto"
      >
        <div className="min-w-[800px]">
          {/* Table Header */}
          <div className="grid grid-cols-5 gap-4 p-4 bg-gray-50 dark:bg-gray-900 rounded-t-xl border-b border-gray-200 dark:border-gray-700">
            <div className="font-semibold text-gray-900 dark:text-white">
              Feature
            </div>
            {competitors.map((comp) => (
              <div
                key={comp.name}
                className={cn(
                  "font-semibold text-center",
                  comp.highlight
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-600 dark:text-gray-400"
                )}
              >
                {comp.name}
                {comp.highlight && (
                  <div className="text-xs font-normal mt-1">
                    (That's us!)
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Table Body */}
          <div className="bg-white dark:bg-gray-800 rounded-b-xl">
            {metrics.map((category, categoryIndex) => (
              <div key={category.category}>
                {/* Category Header */}
                <div className="px-4 py-2 bg-gray-100 dark:bg-gray-700/50">
                  <h3 className="font-semibold text-sm text-gray-700 dark:text-gray-300">
                    {category.category}
                  </h3>
                </div>

                {/* Category Items */}
                {category.items.map((item, itemIndex) => (
                  <motion.div
                    key={item.metric}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.3, delay: itemIndex * 0.05 }}
                    className={cn(
                      "grid grid-cols-5 gap-4 p-4",
                      itemIndex !== category.items.length - 1 && "border-b border-gray-100 dark:border-gray-700"
                    )}
                  >
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {item.metric}
                    </div>
                    <div className="text-center">{renderValue(item.plinto, true)}</div>
                    <div className="text-center">{renderValue(item.clerk)}</div>
                    <div className="text-center">{renderValue(item.auth0)}</div>
                    <div className="text-center">{renderValue(item.supabase)}</div>
                  </motion.div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* CTA */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mt-12 text-center"
      >
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Ready to switch? We have migration guides for all major platforms.
        </p>
        <div className="flex gap-4 justify-center">
          <a
            href="https://docs.plinto.dev/migration/clerk"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Migrate from Clerk →
          </a>
          <a
            href="https://docs.plinto.dev/migration/auth0"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Migrate from Auth0 →
          </a>
          <a
            href="https://docs.plinto.dev/migration/supabase"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Migrate from Supabase →
          </a>
        </div>
      </motion.div>
    </div>
  )
}