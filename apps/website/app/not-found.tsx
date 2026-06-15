import Link from 'next/link'
import { ArrowLeft, FileQuestion } from 'lucide-react'
import { Button } from '@janua/ui'

export default function NotFound() {
  return (
    <main className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="max-w-lg w-full text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-muted mb-6">
          <FileQuestion className="w-8 h-8 text-brand" />
        </div>
        <p className="text-sm font-medium uppercase tracking-wider text-brand mb-3">
          404
        </p>
        <h1 className="font-display text-4xl font-bold tracking-tight text-slate-900 dark:text-white mb-4">
          Page not found
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mb-8">
          The route you requested does not exist or may have moved. Try the home
          page, documentation, or live demo.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Button asChild className="bg-brand-gradient hover:opacity-90 text-white">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to home
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/demo">Live demo</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
