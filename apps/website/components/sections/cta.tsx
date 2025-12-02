'use client'

import { motion } from 'framer-motion'
import { ArrowRight, Calendar, FileText, CreditCard } from 'lucide-react'
import { Button } from '@janua/ui'
import Link from 'next/link'

export function CTASection() {
  return (
    <div className="text-center text-white">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
      >
        {/* Main CTA */}
        <h2 className="text-4xl sm:text-5xl font-bold mb-4">
          Ready to own your identity layer?
        </h2>
        <p className="text-xl sm:text-2xl text-blue-100 mb-8 max-w-2xl mx-auto">
          Start with 10,000 free MAU. No credit card required.
          <br />
          Ship authentication in 5 minutes.
        </p>

        {/* Feature badges */}
        <div className="flex flex-wrap gap-4 justify-center mb-10">
          <div className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-full backdrop-blur">
            <CreditCard className="h-4 w-4" />
            <span className="text-sm">No credit card</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-full backdrop-blur">
            <FileText className="h-4 w-4" />
            <span className="text-sm">10,000 free MAU</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-full backdrop-blur">
            <Calendar className="h-4 w-4" />
            <span className="text-sm">No time limit</span>
          </div>
        </div>

        {/* Primary CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="flex flex-wrap gap-4 justify-center"
        >
          <Link href="https://app.janua.dev/auth/signup">
            <Button
              size="lg"
              className="text-lg px-10 py-6 bg-white text-blue-600 hover:bg-gray-100"
            >
              Get Started
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
          <Link href="https://app.janua.dev/auth/signup">
            <Button
              size="lg"
              variant="outline"
              className="text-lg px-10 py-6 border-white text-white hover:bg-white/10"
            >
              Create Free Account
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </motion.div>

        {/* Alternative actions */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mt-8 flex flex-wrap gap-6 justify-center text-sm"
        >
          <Link
            href="https://demo.janua.dev"
            className="text-white/80 hover:text-white underline underline-offset-4"
          >
            Schedule a demo
          </Link>
          <Link
            href="https://docs.janua.dev"
            className="text-white/80 hover:text-white underline underline-offset-4"
          >
            Read documentation
          </Link>
          <Link
            href="/pricing"
            className="text-white/80 hover:text-white underline underline-offset-4"
          >
            View pricing details
          </Link>
        </motion.div>

        {/* Trust indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-12 pt-8 border-t border-white/20"
        >
          <p className="text-sm text-white/60 mb-4">
            Trusted by engineering teams at
          </p>
          <div className="flex gap-8 justify-center items-center opacity-70">
            <div className="text-white font-semibold">MADFAM</div>
            <div className="text-white font-semibold">Forge Sight</div>
            <div className="text-white font-semibold">Aureo Labs</div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  )
}