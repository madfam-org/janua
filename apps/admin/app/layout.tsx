import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { PlintoProvider } from '@plinto/react'
import { Toaster } from '@/components/ui/toaster'
import { QueryProvider } from '@/components/providers/query-provider'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Plinto Admin',
  description: 'Manage your Plinto identity platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <PlintoProvider>
          <QueryProvider>
            {children}
            <Toaster />
          </QueryProvider>
        </PlintoProvider>
      </body>
    </html>
  )
}