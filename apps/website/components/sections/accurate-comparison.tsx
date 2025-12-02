'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, Minus, AlertCircle, Info, ExternalLink } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'
import Link from 'next/link'

type FeatureStatus = 'yes' | 'no' | 'partial' | 'coming'

interface ComparisonRow {
  feature: string
  category: string
  description?: string
  janua: FeatureStatus | string
  auth0: FeatureStatus | string
  clerk: FeatureStatus | string
  supabase: FeatureStatus | string
  footnote?: string
}

const comparisonData: ComparisonRow[] = [
  // Performance
  {
    feature: 'Edge Latency',
    category: 'Performance',
    description: 'Authentication response time from edge locations',
    janua: '<30ms*',
    auth0: '100-200ms',
    clerk: '80-150ms',
    supabase: '60-120ms',
    footnote: 'Based on edge architecture, not yet benchmarked at scale'
  },
  {
    feature: 'Global Edge Deployment',
    category: 'Performance',
    janua: 'yes',
    auth0: 'no',
    clerk: 'partial',
    supabase: 'no'
  },

  // Authentication Methods
  {
    feature: 'Passkeys (WebAuthn)',
    category: 'Authentication',
    description: 'FIDO2/WebAuthn passwordless authentication',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'partial'
  },
  {
    feature: 'MFA/TOTP',
    category: 'Authentication',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'Magic Links',
    category: 'Authentication',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'OAuth Providers',
    category: 'Authentication',
    janua: '5+',
    auth0: '50+',
    clerk: '20+',
    supabase: '15+'
  },

  // Enterprise Features
  {
    feature: 'SAML SSO',
    category: 'Enterprise',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'partial'
  },
  {
    feature: 'OIDC SSO',
    category: 'Enterprise',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'RBAC',
    category: 'Enterprise',
    description: 'Role-based access control',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'Audit Logging',
    category: 'Enterprise',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'partial'
  },

  // Developer Experience
  {
    feature: 'SDK Languages',
    category: 'Developer Experience',
    janua: '13',
    auth0: '15+',
    clerk: '5',
    supabase: '8'
  },
  {
    feature: 'TypeScript SDK',
    category: 'Developer Experience',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'React Hooks',
    category: 'Developer Experience',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'Migration Tools',
    category: 'Developer Experience',
    description: 'Tools to migrate from other providers',
    janua: 'yes',
    auth0: 'no',
    clerk: 'no',
    supabase: 'no'
  },

  // Security & Compliance
  {
    feature: 'Third-Party Security Audit',
    category: 'Security',
    janua: 'coming',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'partial',
    footnote: 'Janua audit scheduled Q1 2025'
  },
  {
    feature: 'SOC 2 Compliance',
    category: 'Security',
    janua: 'coming',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'no',
    footnote: 'Janua targeting Q2 2025'
  },
  {
    feature: 'GDPR Compliant',
    category: 'Security',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    supabase: 'yes'
  },
  {
    feature: 'Open Source Core',
    category: 'Security',
    description: 'Core authentication logic is open source',
    janua: 'yes',
    auth0: 'no',
    clerk: 'no',
    supabase: 'yes'
  },

  // Testing & Quality
  {
    feature: 'Test Coverage',
    category: 'Quality',
    description: 'Percentage of code covered by tests',
    janua: '31.3%',
    auth0: 'N/A',
    clerk: 'N/A',
    supabase: 'N/A',
    footnote: 'Janua improving weekly, targeting 85%+'
  },

  // Pricing
  {
    feature: 'Free Tier MAU',
    category: 'Pricing',
    description: 'Monthly Active Users in free tier',
    janua: '10,000',
    auth0: '7,000',
    clerk: '10,000',
    supabase: '50,000'
  },
  {
    feature: 'Pricing Model',
    category: 'Pricing',
    janua: '$ (Dev-friendly)',
    auth0: '$$$$ (Enterprise)',
    clerk: '$$$ (Growth)',
    supabase: '$$ (Usage)'
  }
]

const StatusIcon = ({ status }: { status: FeatureStatus | string }) => {
  if (status === 'yes') {
    return <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
  }
  if (status === 'no') {
    return <X className="w-4 h-4 text-slate-400" />
  }
  if (status === 'partial') {
    return <Minus className="w-4 h-4 text-amber-600 dark:text-amber-400" />
  }
  if (status === 'coming') {
    return (
      <Badge variant="secondary" className="text-xs">
        Coming Soon
      </Badge>
    )
  }
  // For string values
  return <span className="text-sm font-medium text-slate-900 dark:text-white">{status}</span>
}

export function AccurateComparison() {
  const [selectedCategory, setSelectedCategory] = useState<string>('All')
  const [showFootnotes, setShowFootnotes] = useState(true)

  const categories = ['All', ...Array.from(new Set(comparisonData.map(row => row.category)))]

  const filteredData = selectedCategory === 'All'
    ? comparisonData
    : comparisonData.filter(row => row.category === selectedCategory)

  const footnotes = Array.from(new Set(comparisonData.filter(row => row.footnote).map(row => row.footnote)))

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Honest Feature Comparison
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-3xl mx-auto">
            A transparent comparison of Janua with established authentication providers.
            We believe in honest communication about our capabilities and roadmap.
          </p>
        </div>

        {/* Category Filter */}
        <div className="mb-8 flex flex-wrap gap-2 justify-center">
          {categories.map(category => (
            <Button
              key={category}
              variant={selectedCategory === category ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(category)}
            >
              {category}
            </Button>
          ))}
        </div>

        {/* Comparison Table */}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="text-left p-4 font-semibold text-slate-900 dark:text-white">
                  Feature
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Janua</div>
                  <Badge variant="outline" className="mt-1 text-xs">Edge-Native</Badge>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Auth0</div>
                  <span className="text-xs text-slate-500">Enterprise Leader</span>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Clerk</div>
                  <span className="text-xs text-slate-500">Modern DX</span>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Supabase</div>
                  <span className="text-xs text-slate-500">Open Source</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((row, idx) => (
                <motion.tr
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.02 }}
                  className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/50"
                >
                  <td className="p-4">
                    <div className="flex items-start gap-2">
                      <div>
                        <div className="font-medium text-slate-900 dark:text-white">
                          {row.feature}
                        </div>
                        {row.description && (
                          <div className="text-xs text-slate-500 mt-1">
                            {row.description}
                          </div>
                        )}
                        {row.footnote && (
                          <div className="flex items-center gap-1 mt-1">
                            <Info className="w-3 h-3 text-amber-500" />
                            <span className="text-xs text-amber-600 dark:text-amber-400">
                              See footnote
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusIcon status={row.janua} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusIcon status={row.auth0} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusIcon status={row.clerk} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusIcon status={row.supabase} />
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footnotes */}
        {showFootnotes && footnotes.length > 0 && (
          <div className="mt-8 p-6 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <h3 className="font-semibold text-amber-900 dark:text-amber-100 mb-3">
              Important Notes
            </h3>
            <ul className="space-y-2">
              {footnotes.map((footnote, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{footnote}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Transparency Section */}
        <div className="mt-12 p-8 bg-slate-50 dark:bg-slate-900/50 rounded-lg">
          <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">
            Our Commitment to Transparency
          </h3>
          <div className="grid sm:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                Where We Excel
              </h4>
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-green-600 mt-0.5" />
                  <span>Edge-native architecture for superior performance</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-green-600 mt-0.5" />
                  <span>Modern SDK ecosystem with 13 production-ready packages</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-green-600 mt-0.5" />
                  <span>Complete passkey and MFA implementation</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-green-600 mt-0.5" />
                  <span>Open source core for transparency</span>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-2">
                Where We're Growing
              </h4>
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <li className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5" />
                  <span>Third-party security audit (Q1 2025)</span>
                </li>
                <li className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5" />
                  <span>Test coverage improving (currently 31.3%)</span>
                </li>
                <li className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5" />
                  <span>OAuth provider count (expanding from 5)</span>
                </li>
                <li className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5" />
                  <span>Enterprise certifications (SOC 2 in progress)</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-6 flex gap-4">
            <Button asChild>
              <Link href="https://github.com/madfam-io/janua" target="_blank">
                <ExternalLink className="w-4 h-4 mr-2" />
                View Source Code
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/roadmap">
                View Public Roadmap
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}