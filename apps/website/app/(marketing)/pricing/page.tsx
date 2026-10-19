import { PricingSection } from '@/components/sections/pricing'
import { CTASection } from '@/components/sections/cta'
import { ComparisonSection } from '@/components/sections/comparison'
import { fetchJanuaProPrice } from '@/lib/dhanam-catalog'

// Pro's MXN price comes from Dhanam's public catalog, read on the server and
// refreshed every 300 s (CATALOG_REVALIDATE_SECONDS; Next needs a literal
// here). A failed read renders the page without an MXN figure.
export const revalidate = 300

export default async function PricingPage() {
  const proMxn = await fetchJanuaProPrice()
  return (
    <main className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <PricingSection proMxn={proMxn} />
        <div className="mt-24">
          <ComparisonSection />
        </div>
        <div className="mt-24 py-24 bg-brand-gradient-br rounded-3xl px-4 sm:px-6 lg:px-8 shadow-brand">
          <CTASection />
        </div>
      </div>
    </main>
  )
}