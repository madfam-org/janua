import type { Metadata } from 'next'
import { LegalPageLayout } from '@/components/legal/legal-page-layout'
import { termsOfService } from '@/lib/legal-content'

export const metadata: Metadata = {
  title: 'Terms of Service | Janua',
  description: termsOfService.intro,
}

export default function TermsPage() {
  return (
    <main>
      <LegalPageLayout
        title={termsOfService.title}
        subtitle={termsOfService.subtitle}
        intro={termsOfService.intro}
        sections={termsOfService.sections}
        lastUpdated={termsOfService.lastUpdated}
      />
    </main>
  )
}
