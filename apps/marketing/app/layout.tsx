import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/react'
import '../styles/globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://plinto.dev'),
  title: 'Plinto - Edge-Fast Identity Platform',
  description: 'Secure substrate for identity. Edge-fast verification with full control. The modern alternative to Auth0 and Clerk.',
  keywords: ['identity', 'authentication', 'auth', 'JWT', 'passkeys', 'WebAuthn', 'edge computing'],
  authors: [{ name: 'Aureo Labs' }],
  openGraph: {
    title: 'Plinto - Edge-Fast Identity Platform',
    description: 'Secure substrate for identity. Edge-fast verification with full control.',
    url: 'https://plinto.dev',
    siteName: 'Plinto',
    images: [
      {
        url: 'https://plinto.dev/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Plinto - Edge-Fast Identity Platform'
      }
    ],
    locale: 'en_US',
    type: 'website'
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Plinto - Edge-Fast Identity Platform',
    description: 'Secure substrate for identity. Edge-fast verification with full control.',
    images: ['https://plinto.dev/og-image.png']
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1
    }
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={`${inter.className} antialiased bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100`}>
        <div className="relative">
          {children}
        </div>
        <Analytics />
      </body>
    </html>
  )
}