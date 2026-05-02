'use client'

import { motion } from 'framer-motion'
import { Check, X, Minus, ExternalLink } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'
import Link from 'next/link'

type Cell = 'yes' | 'no' | 'partial' | string

interface Row {
  feature: string
  description?: string
  janua: Cell
  auth0: Cell
  clerk: Cell
  keycloak: Cell
  notes?: string
}

// Janua cells: traced to code in this repo.
// Competitor cells: based on each vendor's public docs as of 2026.
// We do not invent cells. Where a competitor wins, we show it.
const rows: Row[] = [
  // Standards & protocols
  {
    feature: 'OIDC provider',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'yes',
  },
  {
    feature: 'OAuth 2.0 + PKCE',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'yes',
  },
  {
    feature: 'SAML 2.0 SSO',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'yes',
    notes: 'Janua: per-org config, JIT provisioning. Rolling out under enterprise routers.',
  },
  {
    feature: 'SCIM v2 provisioning',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'partial',
    keycloak: 'partial',
    notes: 'Janua: rolling out. Clerk: enterprise plan only.',
  },
  {
    feature: 'WebAuthn / Passkeys',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'yes',
  },
  {
    feature: 'TOTP MFA',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'yes',
  },
  // Where data lives
  {
    feature: 'You own the user table',
    description: 'Identity data lives in your Postgres, not the vendor\'s.',
    janua: 'yes',
    auth0: 'no',
    clerk: 'no',
    keycloak: 'yes',
  },
  {
    feature: 'Self-host (production-grade)',
    description: 'Helm chart or docker-compose, not a hidden dev mode.',
    janua: 'yes',
    auth0: 'no',
    clerk: 'no',
    keycloak: 'yes',
  },
  {
    feature: 'OSS license',
    janua: 'AGPL-3.0',
    auth0: 'Proprietary',
    clerk: 'Proprietary',
    keycloak: 'Apache-2.0',
    notes: 'Keycloak\'s Apache-2.0 is more permissive than Janua\'s AGPL-3.0.',
  },
  // Operator surface
  {
    feature: 'Audit log + retention controls',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'partial',
    keycloak: 'partial',
    notes: 'Janua: 30&ndash;365 day retention, CSV/JSON export. Clerk: enterprise plan.',
  },
  {
    feature: 'Webhook events for security + lifecycle',
    janua: '26 types',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'partial',
  },
  // Developer experience
  {
    feature: 'Client SDKs in repo',
    janua: '9',
    auth0: '15+',
    clerk: '5',
    keycloak: '3',
    notes: 'Auth0 wins on raw SDK count. Janua ships TS, React, Next, Svelte, Vue, RN, Flutter, Go, Python.',
  },
  {
    feature: 'Next.js middleware',
    janua: 'yes',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'no',
  },
  // Pricing transparency
  {
    feature: 'Free tier MAU',
    janua: '2,000',
    auth0: '7,500',
    clerk: '10,000',
    keycloak: 'Unlimited (self-host)',
    notes: 'Clerk and Auth0 win on free-tier MAU. Keycloak is free at any scale if you operate it.',
  },
  {
    feature: 'Paid entry tier (per month)',
    janua: '$69 / 10k MAU',
    auth0: '$240+',
    clerk: '$25 + per-MAU',
    keycloak: 'Self-operate',
  },
  // Compliance
  {
    feature: 'SOC 2 Type II',
    janua: 'in progress',
    auth0: 'yes',
    clerk: 'yes',
    keycloak: 'n/a (you self-attest)',
    notes: 'Auth0 and Clerk win here today. Janua audit is in progress; see /solutions/enterprise.',
  },
]

const StatusCell = ({ value }: { value: Cell }) => {
  if (value === 'yes') return <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
  if (value === 'no') return <X className="w-4 h-4 text-slate-400" />
  if (value === 'partial') return <Minus className="w-4 h-4 text-amber-600 dark:text-amber-400" />
  return <span className="text-xs font-medium text-slate-900 dark:text-white">{value}</span>
}

export function AccurateComparison() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12 max-w-3xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Janua, Auth0, Clerk, Keycloak.
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400">
            One table. Every cell verifiable. Where a competitor wins, we say
            so out loud.
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
          <table className="w-full border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-900/50">
              <tr>
                <th className="text-left p-4 font-semibold text-slate-900 dark:text-white">
                  Feature
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Janua</div>
                  <span className="text-xs text-slate-500">Self-host or managed</span>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Auth0</div>
                  <span className="text-xs text-slate-500">SaaS</span>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Clerk</div>
                  <span className="text-xs text-slate-500">SaaS</span>
                </th>
                <th className="text-center p-4">
                  <div className="font-semibold text-slate-900 dark:text-white">Keycloak</div>
                  <span className="text-xs text-slate-500">Self-host</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <motion.tr
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.02 }}
                  className="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/30"
                >
                  <td className="p-4">
                    <div className="font-medium text-slate-900 dark:text-white">
                      {row.feature}
                    </div>
                    {row.description && (
                      <div className="text-xs text-slate-500 mt-1">
                        {row.description}
                      </div>
                    )}
                    {row.notes && (
                      <div
                        className="text-xs text-amber-600 dark:text-amber-400 mt-1"
                        dangerouslySetInnerHTML={{ __html: row.notes }}
                      />
                    )}
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusCell value={row.janua} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusCell value={row.auth0} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusCell value={row.clerk} />
                    </div>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex justify-center">
                      <StatusCell value={row.keycloak} />
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-8 grid md:grid-cols-2 gap-6">
          <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
              Where Janua wins
            </h3>
            <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
              <li>You keep the user table. Self-host on Postgres you operate.</li>
              <li>One bill at $69/$299, not per-MAU metered SaaS pricing.</li>
              <li>SCIM v2 + audit retention without an enterprise upsell.</li>
              <li>9 client SDKs in the same monorepo as the API.</li>
            </ul>
          </div>
          <div className="p-6 rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
              Where the others win (today)
            </h3>
            <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
              <li><strong>Auth0:</strong> 15+ official SDKs, SOC 2 Type II already on the wall.</li>
              <li><strong>Clerk:</strong> larger free tier (10k MAU) and a more polished prebuilt UI.</li>
              <li><strong>Keycloak:</strong> Apache-2.0 (more permissive than our AGPL-3.0) and a longer track record.</li>
              <li>If your enterprise customer demands a SOC 2 letter today, Auth0 or Clerk ships faster.</li>
            </ul>
          </div>
        </div>

        <div className="mt-8 flex gap-4 justify-center">
          <Button asChild>
            <Link href="https://github.com/madfam-io/janua" target="_blank" rel="noopener">
              <ExternalLink className="w-4 h-4 mr-2" />
              Read the source
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/solutions/enterprise">
              Compliance detail
            </Link>
          </Button>
        </div>

        <p className="mt-6 text-xs text-center text-slate-500 dark:text-slate-500">
          Competitor cells are based on public documentation as of 2026.
          Spotted something we got wrong?{' '}
          <Link href="https://github.com/madfam-io/janua/issues/new" className="underline">
            Open an issue
          </Link>
          .
        </p>
      </div>
    </section>
  )
}

// Re-export with the legacy name for any import that still references it.
export { AccurateComparison as HonestComparison }
