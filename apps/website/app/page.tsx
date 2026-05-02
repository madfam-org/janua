// Landing page composition. Each section below is a separate component that
// has been audited for verifiable claims against the codebase. See each
// component file's header comment for the source-of-truth file paths.
import { HonestHeroSection } from '@/components/sections/honest-hero'
import { PainPoints } from '@/components/sections/pain-points'
import { FeaturesGrid } from '@/components/sections/features'
import { HowItWorks } from '@/components/sections/how-it-works'
import { RealSDKExamples } from '@/components/sections/real-sdk-examples'
import { AccurateComparison } from '@/components/sections/accurate-comparison'
import { TransparencyRoadmap } from '@/components/sections/transparency-roadmap'
import { HonestPricing } from '@/components/sections/honest-pricing'
import { LandingCTA } from '@/components/sections/landing-cta'

import { Navigation } from '@/components/navigation'
import { Footer } from '@/components/footer'

export default function LandingPage() {
  return (
    <>
      <Navigation />
      <main className="relative">
        {/* Pain-point hook + verifiable status badges */}
        <HonestHeroSection />

        {/* Four conversations every founding engineer has had */}
        <PainPoints />

        {/* Verified feature grid with source paths */}
        <section className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-950">
          <div className="max-w-7xl mx-auto">
            <FeaturesGrid />
          </div>
        </section>

        {/* Three real steps with copy-paste commands */}
        <HowItWorks />

        {/* SDK examples drawn from packages/ */}
        <RealSDKExamples />

        {/* Janua vs Auth0, Clerk, Keycloak — every cell verifiable */}
        <AccurateComparison />

        {/* What ships vs what's maturing — no dated promises */}
        <TransparencyRoadmap />

        {/* Pricing aligned with billing_service.py canonical tiers */}
        <HonestPricing />

        {/* Dual CTA: self-host or talk to us */}
        <LandingCTA />
      </main>
      <Footer />
    </>
  )
}
