import { AboutSection } from '@/components/sections/about'
import { CTASection } from '@/components/sections/cta'

export default function AboutPage() {
  return (
    <main className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <AboutSection />
        <div className="mt-24 py-24 bg-brand-gradient-br rounded-3xl px-4 sm:px-6 lg:px-8 shadow-brand">
          <CTASection />
        </div>
      </div>
    </main>
  )
}