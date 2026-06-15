import { Footer } from '@/components/footer'
import { Navigation } from '@/components/navigation'

/** Shared marketing chrome — nav + footer on every public page except /demo. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navigation />
      <div className="min-h-screen pt-16">{children}</div>
      <Footer />
    </>
  )
}
