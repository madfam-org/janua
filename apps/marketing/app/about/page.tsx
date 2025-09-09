import { AboutSection } from '@/components/sections/about'
import { CTASection } from '@/components/sections/cta'

export default function AboutPage() {
  return (
    <main className="min-h-screen pt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <AboutSection />
        <div className="mt-24 py-24 bg-gradient-to-br from-blue-600 to-purple-600 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
          <CTASection />
        </div>
      </div>
    </main>
  )
}