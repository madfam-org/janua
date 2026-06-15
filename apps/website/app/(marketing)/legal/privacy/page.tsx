import type { Metadata } from 'next'
import { LegalPageLayout } from '@/components/legal/legal-page-layout'
import { privacyPolicy } from '@/lib/legal-content'

export const metadata: Metadata = {
  title: 'Privacy Policy | Janua',
  description: privacyPolicy.intro,
}

export default function PrivacyPage() {
  return (
    <main>
      <LegalPageLayout
        title={privacyPolicy.title}
        subtitle={privacyPolicy.subtitle}
        intro={privacyPolicy.intro}
        sections={privacyPolicy.sections}
        lastUpdated={privacyPolicy.lastUpdated}
      />
    </main>
  )
}
