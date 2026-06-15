'use client'

import { motion } from 'framer-motion'
import { ArrowRight, Server, Mail } from 'lucide-react'
import { Button } from '@janua/ui'
import Link from 'next/link'

// Two real CTAs:
//   - Self-host: docs.janua.dev/self-hosting (operator path)
//   - Talk to us: hello@janua.dev (managed/enterprise path)
// MAU number aligned with the canonical billing tier
// (apps/api/app/services/billing_service.py + components/sections/pricing.tsx).
export function LandingCTA() {
  return (
    <section className="py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto rounded-3xl bg-brand-gradient-br p-12 text-white shadow-brand">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <h2 className="text-4xl sm:text-5xl font-bold mb-4">
            Own your identity layer.
          </h2>
          <p className="text-lg text-blue-50 mb-10 max-w-2xl mx-auto">
            Self-host on your own Postgres for free, or let us run it. Either
            way, your user table stays yours. Free tier: 2,000 MAU.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" variant="secondary" className="group" asChild>
              <Link href="https://docs.janua.dev/self-hosting">
                <Server className="mr-2 w-4 h-4" />
                Start self-hosting
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button size="lg" variant="outline" className="bg-transparent border-white text-white hover:bg-white hover:text-blue-600" asChild>
              <Link href="mailto:hello@janua.dev?subject=Janua%20managed%20%2F%20enterprise">
                <Mail className="mr-2 w-4 h-4" />
                Talk to us
              </Link>
            </Button>
          </div>

          <p className="mt-6 text-xs text-blue-100">
            No credit card. Self-host stays free at any scale under AGPL-3.0.
          </p>
        </motion.div>
      </div>
    </section>
  )
}
