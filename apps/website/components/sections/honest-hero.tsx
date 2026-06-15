'use client'

import { motion } from 'framer-motion'
import { ArrowRight, GitBranch, Code2, Server, Webhook } from 'lucide-react'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import Link from 'next/link'

// All claims here trace to code:
// - 9 client SDKs in packages/ (typescript-sdk, react-sdk, nextjs-sdk,
//   sveltekit-sdk, vue-sdk, react-native-sdk, flutter-sdk, go-sdk, python-sdk)
// - 26 webhook event types in apps/api/app/services/webhooks.py (WebhookEventType enum)
// - AGPL-3.0 license at repo root (LICENSE)
// - Self-host paths: docker-compose.yml + deployment/helm + deployment/production
//
// Numbers we deliberately do NOT print here (no defensible source):
// - "<30ms latency" / "150+ edge locations" / "100+ edge locations"
//   (those are Cloudflare/Vercel infra capabilities, not Janua benchmarks)
// - "test coverage X%" (drifted; left to the security/transparency page)
export function HonestHeroSection() {
  return (
    <section className="relative min-h-[85vh] flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-hero-surface">
        <div className="absolute inset-0 bg-grid-slate-100 dark:bg-grid-slate-800 opacity-[0.03]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center max-w-4xl mx-auto">
          {/* Status badges — every one verifiable */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex flex-wrap justify-center gap-3 mb-8"
          >
            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <GitBranch className="w-3 h-3 mr-1.5 text-green-600 dark:text-green-400" />
              <span className="text-xs font-medium">AGPL-3.0 open source</span>
            </Badge>

            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <Server className="w-3 h-3 mr-1.5 text-blue-600 dark:text-blue-400" />
              <span className="text-xs font-medium">Self-host or managed</span>
            </Badge>

            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <Code2 className="w-3 h-3 mr-1.5 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-medium">9 client SDKs</span>
            </Badge>

            <Badge variant="outline" className="px-3 py-1.5 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
              <Webhook className="w-3 h-3 mr-1.5 text-cyan-600 dark:text-cyan-400" />
              <span className="text-xs font-medium">26 webhook events</span>
            </Badge>
          </motion.div>

          {/* Pain-point headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-slate-900 dark:text-white"
          >
            Stop writing OAuth{' '}
            <span className="text-brand-gradient">
              at midnight.
            </span>
          </motion.h1>

          {/* Subheadline — concrete, no marketing throat-clearing */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-6 text-xl text-slate-600 dark:text-slate-300 max-w-3xl mx-auto"
          >
            Janua is the auth platform you actually own. OIDC, OAuth 2.0 + PKCE, MFA,
            passkeys, audit log, webhooks &mdash; in your database, on your infrastructure,
            under your license.
          </motion.p>

          {/* CTAs — both real */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mt-10 flex flex-col sm:flex-row gap-4 justify-center"
          >
            <Button size="lg" className="group bg-brand-gradient hover:opacity-90 text-white shadow-brand" asChild>
              <Link href="https://docs.janua.dev/self-hosting">
                Start self-hosting
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="mailto:hello@janua.dev?subject=Janua%20managed%20%2F%20enterprise">
                Talk to us
              </Link>
            </Button>

            <Button size="lg" variant="outline" asChild>
              <Link href="https://github.com/madfam-org/janua" target="_blank" rel="noopener">
                <GitBranch className="mr-2 w-4 h-4" />
                Read the source
              </Link>
            </Button>
          </motion.div>

          {/* What works today — only verified features */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-8 text-left"
          >
            <div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                Standards, not strings
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                OIDC provider, OAuth 2.0 with PKCE, SAML 2.0 SSO, SCIM v2 user
                provisioning. No vendor lock-in.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                Modern auth, day one
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                WebAuthn passkeys, TOTP MFA, OAuth across 8 providers
                (Google, GitHub, Microsoft, Apple, Discord, Twitter, LinkedIn, Slack).
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
                Audit-ready surface
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Append-only audit log with 30&ndash;365 day retention, 26 webhook
                events covering user, session, security, and admin lifecycle.
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
