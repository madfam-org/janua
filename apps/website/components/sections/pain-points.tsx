'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { Clock, Building2, FileSearch, Lock } from 'lucide-react'

// Audience: founding/lead engineers building B2B SaaS who hit the auth wall.
// Each card names a pain in concrete language and answers it with a feature
// that exists in the codebase. No future-tense promises in this section.
const pains = [
  {
    icon: Clock,
    pain: '"I shouldn\'t be writing OAuth in 2026."',
    pain_detail:
      'Two weeks gone on PKCE + refresh logic, and you still don\'t trust the session boundary.',
    answer:
      'Drop in @janua/nextjs middleware or one of 9 client SDKs. OIDC, OAuth 2.0 + PKCE, refresh, and revocation are already wired.',
  },
  {
    icon: Building2,
    pain: '"We lost a deal because we couldn\'t ship SAML."',
    pain_detail:
      'Enterprise procurement asks for SSO. Six weeks of Keycloak ops is not the answer.',
    answer:
      'SAML 2.0 SSO and OIDC SSO are mounted under /api/v1/sso. SCIM v2 provisioning lives at /api/v1/scim. No new infra to stand up.',
  },
  {
    icon: FileSearch,
    pain: '"Audit logging? We deflect when customers ask."',
    pain_detail:
      'Compliance review lands without a log surface, and you scramble to grep application logs into a spreadsheet.',
    answer:
      'Append-only audit log with filter, export (CSV/JSON), and 30&ndash;365 day retention. 26 webhook events stream lifecycle to your SIEM.',
  },
  {
    icon: Lock,
    pain: '"$5/MAU to a vendor that owns my user table? No."',
    pain_detail:
      'You don\'t want your identity layer behind a usage-based meter on someone else\'s database.',
    answer:
      'Self-host under AGPL-3.0. User table stays in your Postgres. Free up to 2,000 MAU, $69 Pro, $299 Scale, custom Enterprise on the managed plan.',
  },
]

export function PainPoints() {
  const [ref, inView] = useInView({ triggerOnce: true, threshold: 0.1 })

  return (
    <section
      ref={ref}
      className="py-24 px-4 sm:px-6 lg:px-8 bg-white dark:bg-slate-950"
    >
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 max-w-3xl mx-auto"
        >
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-6">
            You know these by heart.
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            Four conversations every founding engineer has had at 2am. Janua's
            answer to each is in the codebase, not the roadmap.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {pains.map((p, i) => {
            const Icon = p.icon
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="group relative p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
              >
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-lg bg-red-50 dark:bg-red-900/20">
                    <Icon className="w-5 h-5 text-red-600 dark:text-red-400" />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-lg text-slate-900 dark:text-white">
                      {p.pain}
                    </p>
                    <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                      {p.pain_detail}
                    </p>
                    <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                      <p
                        className="text-sm text-slate-700 dark:text-slate-300"
                        dangerouslySetInnerHTML={{ __html: p.answer }}
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
