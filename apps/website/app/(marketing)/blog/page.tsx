import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, BookOpen, Github, Mail, Rss } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Blog | Janua',
  description:
    'Technical writing on authentication and identity infrastructure from the Janua team. The blog is in progress — follow releases and docs in the meantime.',
  robots: {
    index: false,
    follow: true,
  },
}

const resources = [
  {
    icon: BookOpen,
    title: 'Documentation',
    description: 'Guides, API reference, and self-hosting runbooks.',
    href: 'https://docs.janua.dev',
    cta: 'Read docs',
  },
  {
    icon: Github,
    title: 'GitHub releases',
    description: 'Ship notes and changelog entries as we cut versions.',
    href: 'https://github.com/madfam-org/janua/releases',
    cta: 'View releases',
  },
  {
    icon: Rss,
    title: 'Live demo',
    description: 'Try auth flows before we publish long-form posts.',
    href: '/demo',
    cta: 'Open demo',
  },
]

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      <section className="relative pt-12 pb-24 overflow-hidden">
        <div className="absolute inset-0 bg-hero-surface" />
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="inline-flex items-center rounded-full border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 px-3 py-1 text-xs font-medium uppercase tracking-wider text-brand mb-6">
            Blog in progress
          </p>
          <h1 className="font-display text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-6">
            Writing is{' '}
            <span className="text-brand-gradient">on the roadmap</span>
          </h1>
          <p className="text-xl text-slate-600 dark:text-slate-300 mb-4">
            We are not publishing placeholder articles. When the blog launches,
            expect deep dives on passkeys, OIDC, self-hosting, and audit-ready
            identity design.
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-10">
            Until then, follow releases and docs — that is where we ship facts first.
          </p>
          <Button asChild className="bg-brand-gradient hover:opacity-90 text-white">
            <Link href="mailto:hello@janua.dev?subject=Janua%20blog%20updates">
              <Mail className="mr-2 h-4 w-4" />
              Notify me at launch
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>

      <section className="pb-24">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="font-display text-2xl font-bold text-slate-900 dark:text-white mb-8 text-center">
            Read now
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {resources.map((item) => {
              const Icon = item.icon
              return (
                <article
                  key={item.title}
                  className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 p-6 flex flex-col"
                >
                  <div className="w-10 h-10 rounded-lg bg-brand-muted flex items-center justify-center mb-4">
                    <Icon className="w-5 h-5 text-brand" />
                  </div>
                  <h3 className="font-display text-lg font-semibold text-slate-900 dark:text-white mb-2">
                    {item.title}
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 flex-1">
                    {item.description}
                  </p>
                  <Button variant="outline" className="w-full" asChild>
                    <Link href={item.href}>
                      {item.cta}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </article>
              )
            })}
          </div>
        </div>
      </section>
    </div>
  )
}
