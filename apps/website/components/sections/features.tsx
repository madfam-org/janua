'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import {
  Shield,
  Key,
  Users,
  Code2,
  FileSearch,
  Webhook,
  Server,
  Globe,
  Building2,
} from 'lucide-react'
import { Badge } from '@janua/ui'

// Every feature here traces to a router, service, or package in the repo.
// "Rolling out" entries point at code that exists but is gated under
// enterprise_routers (mounted in apps/api/app/main.py) and may not be
// fully production-hardened yet. We say so.
const features = [
  {
    icon: Shield,
    title: 'OIDC + OAuth 2.0 with PKCE',
    description:
      'Standards-compliant OIDC provider and OAuth 2.0 authorization server with PKCE. Mounted at /api/v1/oauth and /api/v1/oauth-clients.',
    source: 'apps/api/app/routers/v1/oauth*.py',
  },
  {
    icon: Key,
    title: 'Passkeys (WebAuthn / FIDO2)',
    description:
      'Passwordless registration and login via WebAuthn. Implemented with the python webauthn library, exposed at /api/v1/passkeys.',
    source: 'apps/api/app/routers/v1/passkeys.py',
  },
  {
    icon: Shield,
    title: 'TOTP MFA + backup codes',
    description:
      'Time-based one-time passwords with QR enrolment and recovery codes. Per-user enable/disable from /api/v1/mfa.',
    source: 'apps/api/app/routers/v1/mfa.py',
  },
  {
    icon: Building2,
    title: 'SAML 2.0 SSO + OIDC SSO',
    description:
      'Per-organization SSO configuration: metadata URL or XML upload, JIT provisioning, default-role mapping. Mounted at /api/v1/sso.',
    badge: 'Rolling out',
    source: 'apps/api/app/routers/v1/sso.py + apps/api/app/sso/routers/',
  },
  {
    icon: Users,
    title: 'SCIM v2 provisioning',
    description:
      'SCIM v2 endpoints for Users and Groups so identity providers can sync directories without you writing webhook handlers.',
    badge: 'Rolling out',
    source: 'apps/api/app/routers/v1/scim.py',
  },
  {
    icon: Users,
    title: 'Organizations + RBAC',
    description:
      'Multi-tenant orgs, members, invitations, custom roles, and per-org policies. Audit-logged, exposed at /api/v1/organizations and /api/v1/rbac.',
    source: 'apps/api/app/routers/v1/organizations.py + rbac.py',
  },
  {
    icon: FileSearch,
    title: 'Audit log with retention',
    description:
      'Append-only audit log with filtering, CSV/JSON export, and 30&ndash;365 day retention controls for compliance review.',
    source: 'apps/api/app/routers/v1/audit_logs.py',
  },
  {
    icon: Webhook,
    title: '26 webhook event types',
    description:
      'User, session, org, security (MFA, passkey, password, suspicious activity), OAuth, and admin events. Signed delivery, retry, and dead-letter.',
    source: 'apps/api/app/services/webhooks.py (WebhookEventType)',
  },
  {
    icon: Code2,
    title: '9 client SDKs',
    description:
      'TypeScript, React, Next.js, SvelteKit, Vue, React Native, Flutter, Go, Python &mdash; all in packages/ alongside the API.',
    source: 'packages/{typescript,react,nextjs,sveltekit,vue,react-native,flutter,go,python}-sdk',
  },
  {
    icon: Server,
    title: 'Self-host or managed',
    description:
      'Docker Compose for a laptop, Helm chart for Kubernetes, or run the managed tier. Same code path. AGPL-3.0 core.',
    source: 'docker-compose.yml + deployment/helm + LICENSE',
  },
  {
    icon: Globe,
    title: '8 OAuth providers built in',
    description:
      'Google, GitHub, Microsoft, Apple, Discord, Twitter, LinkedIn, Slack. Add your own by registering a client config.',
    source: 'apps/api/app/services/oauth.py',
  },
]

export function FeaturesGrid() {
  const [ref, inView] = useInView({ triggerOnce: true, threshold: 0.1 })

  return (
    <section className="py-24" ref={ref}>
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 max-w-3xl mx-auto"
        >
          <Badge variant="outline" className="mb-4">
            What ships today
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-6">
            Auth that already exists.
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            No "imagine if". Every card below points at a router or package in
            the open-source repo. Items tagged{' '}
            <span className="font-semibold">Rolling out</span> are mounted but
            still hardening &mdash; pin a version before shipping to your
            enterprise customer.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: index * 0.05 }}
                className="group relative bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                    <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  {feature.badge && (
                    <Badge variant="outline" className="text-xs bg-amber-50 dark:bg-amber-900/20 border-amber-200 text-amber-700 dark:text-amber-300">
                      {feature.badge}
                    </Badge>
                  )}
                </div>

                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                  {feature.title}
                </h3>
                <p
                  className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: feature.description }}
                />

                <p className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 text-xs font-mono text-slate-500 dark:text-slate-500">
                  {feature.source}
                </p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
