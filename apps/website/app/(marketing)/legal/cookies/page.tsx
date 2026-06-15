import type { Metadata } from 'next'
import { LegalPageLayout } from '@/components/legal/legal-page-layout'
import { cookiePolicy } from '@/lib/legal-content'

export const metadata: Metadata = {
  title: 'Cookie Policy | Janua',
  description: cookiePolicy.intro,
}

export default function CookiesPage() {
  return (
    <main>
      <LegalPageLayout
        title={cookiePolicy.title}
        subtitle={cookiePolicy.subtitle}
        intro={cookiePolicy.intro}
        sections={cookiePolicy.sections}
        lastUpdated={cookiePolicy.lastUpdated}
      />
    </main>
  )
}
