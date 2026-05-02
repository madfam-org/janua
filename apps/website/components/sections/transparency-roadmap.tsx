'use client'

import { motion } from 'framer-motion'
import { CheckCircle2, AlertCircle, GitBranch, ExternalLink } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'
import Link from 'next/link'

// We are in Private Alpha as of May 2026. We refuse to publish dated
// roadmap commitments here because we have missed every public Q1/Q2
// 2025 commitment we ever made. Instead this section surfaces the two
// honest signals: what is shipping vs what is still maturing.
const shipping = [
  'OIDC provider, OAuth 2.0 with PKCE, refresh + revoke',
  'WebAuthn passkeys, TOTP MFA with backup codes',
  '8 OAuth providers (Google, GitHub, Microsoft, Apple, Discord, Twitter, LinkedIn, Slack)',
  'Organizations, members, invitations, RBAC, custom roles',
  'Audit log with 30&ndash;365 day retention, CSV/JSON export',
  '26 webhook event types covering user, session, security, OAuth, admin lifecycle',
  '9 client SDKs (TypeScript, React, Next.js, SvelteKit, Vue, React Native, Flutter, Go, Python)',
  'Self-host: Docker Compose, Helm chart, AGPL-3.0 license',
]

const maturing = [
  {
    item: 'SAML 2.0 SSO + OIDC SSO (per-org)',
    detail:
      'Code is mounted under enterprise routers. Real-world IdP integration testing in flight. Pin a version before shipping to a customer who pays for it.',
  },
  {
    item: 'SCIM v2 provisioning',
    detail:
      'Users + Groups endpoints exist. We are still wiring it against Okta and Azure AD reference flows.',
  },
  {
    item: 'SOC 2 Type II audit',
    detail:
      'Status: audit in progress. Internal controls are in place. Independent attestation has not landed. See /solutions/enterprise for the operator detail.',
  },
  {
    item: 'ISO 27001, HIPAA, GDPR, PCI DSS',
    detail:
      'In-progress or planned. Self-attested controls only. Ask us before signing a contract that requires the cert today.',
  },
  {
    item: 'Production benchmarks',
    detail:
      'We are deliberately not publishing a latency or throughput number until we have a reproducible benchmark harness. The previous "<30ms" claim was based on edge architecture, not measurement.',
  },
]

export function TransparencyRoadmap() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-950">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12 max-w-3xl mx-auto">
          <Badge variant="outline" className="mb-4">
            Private Alpha &middot; updated as of May 2026
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            What ships vs what's maturing.
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400">
            We would rather lose your trust on a pricing comparison than break
            it on a compliance claim. Here is the line.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
              Shipping today
            </h3>
            <ul className="space-y-3">
              {shipping.map((s, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-start gap-3 text-sm text-slate-700 dark:text-slate-300"
                >
                  <span className="mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-green-500" />
                  <span dangerouslySetInnerHTML={{ __html: s }} />
                </motion.li>
              ))}
            </ul>
          </div>

          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-800/50">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              Maturing &mdash; ask before betting on it
            </h3>
            <ul className="space-y-4">
              {maturing.map((m, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.04 }}
                  className="text-sm"
                >
                  <p className="font-medium text-slate-900 dark:text-white">
                    {m.item}
                  </p>
                  <p className="text-slate-600 dark:text-slate-400 mt-1">
                    {m.detail}
                  </p>
                </motion.li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
          <Button asChild>
            <Link href="https://github.com/madfam-io/janua/issues" target="_blank" rel="noopener">
              <GitBranch className="w-4 h-4 mr-2" />
              Issue tracker
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/solutions/enterprise">
              <ExternalLink className="w-4 h-4 mr-2" />
              Compliance detail
            </Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
