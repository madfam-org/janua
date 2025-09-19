import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { PlintoProvider } from '@plinto/react-sdk';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Plinto Authentication Example',
  description: 'Production-ready authentication with Plinto SDK',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <PlintoProvider
          config={{
            baseURL: process.env.NEXT_PUBLIC_PLINTO_API_URL || 'https://api.plinto.dev',
            apiKey: process.env.NEXT_PUBLIC_PLINTO_API_KEY,
            environment: process.env.NODE_ENV === 'production' ? 'production' : 'development',
          }}
        >
          {children}
        </PlintoProvider>
      </body>
    </html>
  );
}