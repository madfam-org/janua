'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'

/**
 * TrustSection — Private Alpha placeholder.
 *
 * Previous versions of this component listed fictional customer logos
 * ("TechCorp", "StartupHub", "CloudNative") with fabricated user counts
 * (50K+, 75K+) and an unsupported 99.99% uptime SLA. Janua is in Private
 * Alpha; we do not yet have public customers to showcase or an
 * SRE-backed SLA to advertise.
 *
 * This component now renders an honest placeholder until we can replace
 * it with real, verifiable signals. Do not re-introduce fabricated logos
 * or stats here.
 */
export function TrustSection() {
  const [ref, inView] = useInView({
    triggerOnce: true,
    threshold: 0.1
  })

  return (
    <section className="py-24 bg-white dark:bg-gray-950" ref={ref}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
            Private Alpha
          </p>
          <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900 dark:text-white mb-4">
            Customer logos available after public launch
          </h2>
          <p className="text-base text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            Janua is currently in Private Alpha. We will share customer
            references, real usage metrics, and uptime data once we have
            them — not before.
          </p>
        </motion.div>
      </div>
    </section>
  )
}
