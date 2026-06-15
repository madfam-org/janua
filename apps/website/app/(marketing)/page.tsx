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

export default function LandingPage() {
  return (
    <main className="relative">
      <HonestHeroSection />
      <PainPoints />

      <section
        id="features"
        className="scroll-mt-nav py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-950"
      >
        <div className="max-w-7xl mx-auto">
          <FeaturesGrid />
        </div>
      </section>

      <div id="performance" className="scroll-mt-nav">
        <HowItWorks />
      </div>

      <div id="integrations" className="scroll-mt-nav">
        <RealSDKExamples />
      </div>

      <AccurateComparison />

      <div id="security" className="scroll-mt-nav">
        <TransparencyRoadmap />
      </div>

      <HonestPricing />
      <LandingCTA />
    </main>
  )
}
