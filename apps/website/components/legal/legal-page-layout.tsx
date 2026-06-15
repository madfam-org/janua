import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import type { LegalSection } from '@/lib/legal-content'

type LegalPageLayoutProps = {
  title: string
  subtitle?: string
  intro: string
  sections: LegalSection[]
  lastUpdated?: string
}

export function LegalPageLayout({
  title,
  subtitle,
  intro,
  sections,
  lastUpdated,
}: LegalPageLayoutProps) {
  return (
    <article className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors mb-8"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to home
      </Link>

      <header className="mb-10">
        <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-slate-900 dark:text-white mb-3">
          {title}
        </h1>
        {subtitle && (
          <p className="text-lg text-slate-600 dark:text-slate-300">{subtitle}</p>
        )}
        {lastUpdated && (
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
            Last updated: {lastUpdated}
          </p>
        )}
      </header>

      <p className="text-base leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
        {intro}
      </p>

      <nav
        aria-label="Table of contents"
        className="mb-12 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/50 p-6"
      >
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
          Contents
        </h2>
        <ol className="space-y-2 text-sm">
          {sections.map((section, i) => (
            <li key={section.title}>
              <a
                href={`#section-${i}`}
                className="text-brand hover:text-brand-deep transition-colors"
              >
                {i + 1}. {section.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-10">
        {sections.map((section, i) => (
          <section key={section.title} id={`section-${i}`} className="scroll-mt-nav">
            <h2 className="font-display text-xl font-semibold text-slate-900 dark:text-white mb-3">
              {i + 1}. {section.title}
            </h2>
            <p className="text-base leading-relaxed text-slate-700 dark:text-slate-300">
              {section.content}
            </p>
            {section.subsections?.map((sub) => (
              <div key={sub.title} className="mt-5 ml-4 border-l-2 border-brand/30 pl-4">
                <h3 className="font-medium text-slate-900 dark:text-white mb-2">
                  {sub.title}
                </h3>
                <p className="text-base leading-relaxed text-slate-700 dark:text-slate-300">
                  {sub.content}
                </p>
              </div>
            ))}
          </section>
        ))}
      </div>

      <hr className="my-12 border-slate-200 dark:border-slate-800" />
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Questions? Contact{' '}
        <a href="mailto:legal@janua.dev" className="text-brand hover:text-brand-deep">
          legal@janua.dev
        </a>
        . Parent entity policies may also apply at{' '}
        <a
          href="https://madfam.io/privacy"
          className="text-brand hover:text-brand-deep"
          target="_blank"
          rel="noopener noreferrer"
        >
          madfam.io
        </a>
        .
      </p>
    </article>
  )
}
