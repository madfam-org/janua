import { PricingSection } from '@/components/sections/pricing'
import { CTASection } from '@/components/sections/cta'
import { ComparisonSection } from '@/components/sections/comparison'

export default function PricingPage() {
  return (
    <main className="min-h-screen pt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <PricingSection />
        <div className="mt-24">
          <ComparisonSection />
        </div>
        <div className="mt-24 py-24 bg-gradient-to-br from-blue-600 to-purple-600 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
          <CTASection />
        </div>
      </div>
    </main>
  )
}