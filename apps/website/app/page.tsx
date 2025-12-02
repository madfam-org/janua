// Honest marketing components - no exaggeration, just facts
import { HonestHeroSection } from '@/components/sections/honest-hero'
import { PerformanceDemo } from '@/components/sections/performance-demo'
import { AccurateComparison } from '@/components/sections/accurate-comparison'
import { RealSDKExamples } from '@/components/sections/real-sdk-examples'
import { TransparencyRoadmap } from '@/components/sections/transparency-roadmap'
import { HonestPricing } from '@/components/sections/honest-pricing'

// Keep existing components that are factual
import { Navigation } from '@/components/navigation'
import { Footer } from '@/components/footer'
import { FeaturesGrid } from '@/components/sections/features'
import { DeveloperExperience } from '@/components/sections/developer-experience'

export default function LandingPage() {
  return (
    <>
      <Navigation />
      <main className="relative">
        {/* Honest Hero - Real metrics, no exaggeration */}
        <HonestHeroSection />

        {/* Interactive Performance Demo - Let users test real latency */}
        <PerformanceDemo />

        {/* Core features - What actually exists */}
        <section className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-950">
          <div className="max-w-7xl mx-auto">
            <FeaturesGrid />
          </div>
        </section>

        {/* Real SDK Examples - Actual working code */}
        <RealSDKExamples />

        {/* Developer Experience - Honest about our tools */}
        <section className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-950">
          <div className="max-w-7xl mx-auto">
            <DeveloperExperience />
          </div>
        </section>

        {/* Accurate Comparison - Fair assessment vs competitors */}
        <AccurateComparison />

        {/* Transparency & Roadmap - Where we are and where we're going */}
        <TransparencyRoadmap />

        {/* Honest Pricing - Clear about what's included */}
        <HonestPricing />
      </main>
      <Footer />
    </>
  )
}